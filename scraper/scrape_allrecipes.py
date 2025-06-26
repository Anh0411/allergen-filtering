import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import sys
import django
import time
import argparse
import logging
import re
import json
from urllib.parse import urlparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from recipes.models import Recipe

def get_rendered_html(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to load {url} (attempt {attempt+1}/{max_retries})")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                page = context.new_page()
                
                # Set a shorter timeout for initial page load
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # Wait for key elements with shorter timeouts
                try:
                    page.wait_for_selector('h1', timeout=10000)
                    # Wait for recipe cards to load
                    page.wait_for_selector('a[data-testid="recipe-card"]', timeout=10000)
                except Exception as e:
                    logger.warning(f"Some selectors not found on {url}: {e}")
                    # Continue anyway as we might still have some content
                
                # Give a small delay for any remaining content to load
                time.sleep(2)
                
                html = page.content()
                context.close()
                browser.close()
                return html
        except Exception as e:
            logger.error(f"Error loading {url} (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(5)
    logger.error(f"Failed to load {url} after {max_retries} attempts.")
    return None

def get_recipe_links(max_recipes=1000):
    """Get recipe links from Allrecipes.com breakfast and brunch category."""
    all_links = set()
    base_url = "https://www.allrecipes.com/recipes/78/breakfast-and-brunch/"
    
    page = 1
    while len(all_links) < max_recipes:
        url = f"{base_url}?page={page}" if page > 1 else base_url
        try:
            logger.info(f"Fetching category page: {url}")
            html = get_rendered_html(url)
            if not html:
                logger.error(f"Failed to get HTML for {url}")
                break
                
            soup = BeautifulSoup(html, 'html.parser')
            recipe_cards = soup.select('a[data-testid="recipe-card"]')
            
            if not recipe_cards:
                logger.info("No more recipe cards found, ending pagination")
                break
                
            new_links = 0
            for card in recipe_cards:
                if card.has_attr('href'):
                    recipe_url = card['href']
                    if '/recipe/' in recipe_url and recipe_url not in all_links:
                        all_links.add(recipe_url)
                        new_links += 1
                        if len(all_links) >= max_recipes:
                            break
            
            logger.info(f"Found {new_links} new recipe links on page {page}")
            if new_links == 0:
                logger.info("No new links found on this page, ending pagination")
                break
                
            page += 1
            time.sleep(3)  # Be polite
            
        except Exception as e:
            logger.error(f"Error processing category page {url}: {e}")
            break
    
    return list(all_links)[:max_recipes]

def scrape_recipe(url):
    try:
        if not url:
            logger.error("Empty URL provided")
            return None
            
        logger.info(f"Scraping recipe: {url}")
        html = get_rendered_html(url)
        if not html:
            return None
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Title
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else ''
        if not title:
            logger.error(f"No title found for recipe at {url}")
            return None
            
        logger.info(f"Found title: {title}")
        
        # Image
        image_url = ''
        img_tag = soup.find('img', {'data-testid': 'primary-image'})
        if img_tag and img_tag.has_attr('src'):
            image_url = img_tag['src']
            logger.info(f"Found image URL: {image_url}")
        
        # Cooking time
        ready_in = ''
        time_tag = soup.find('div', {'data-testid': 'recipe-meta-item'})
        if time_tag:
            ready_in = time_tag.get_text(strip=True)
            logger.info(f"Found cooking time: {ready_in}")
        
        # Ingredients
        ingredients = []
        ingredient_list = soup.select('ul[data-testid="ingredient-list"] li')
        for item in ingredient_list:
            text = item.get_text(strip=True)
            if text:
                ingredients.append(text)
        logger.info(f"Found {len(ingredients)} ingredients")
        
        # Directions
        directions = []
        direction_list = soup.select('ol[data-testid="instruction-list"] li')
        for item in direction_list:
            text = item.get_text(strip=True)
            if text:
                directions.append(text)
        logger.info(f"Found {len(directions)} directions")
        
        if not ingredients or not directions:
            logger.warning(f"Missing data for recipe {url}: ingredients={len(ingredients)}, directions={len(directions)}")
            return None
        
        # Save to DB
        recipe_data = {
            'title': title,
            'instructions': directions,
            'times': ready_in,
            'image_url': image_url,
            'scraped_ingredients_text': ingredients,
            'original_url': url
        }
        
        return recipe_data
        
    except Exception as e:
        logger.error(f"Error scraping recipe {url}: {str(e)}", exc_info=True)
        return None

def main(max_recipes=1000):
    logger.info(f'Starting to scrape up to {max_recipes} recipes...')
    
    # Get all recipe links first
    all_links = get_recipe_links(max_recipes)
    logger.info(f'Found total of {len(all_links)} unique recipe links')
    
    # Now scrape each recipe
    total_links = len(all_links)
    for index, link in enumerate(all_links, 1):
        if not link:  # Skip empty links
            continue
            
        logger.info(f'Scraping recipe {index}/{total_links}: {link}')
        
        existing_recipe = Recipe.objects.filter(original_url=link).first()
        
        if existing_recipe and existing_recipe.scraped_ingredients_text and existing_recipe.instructions:
            logger.info(f'Already scraped with complete data: {link}')
            continue
            
        if existing_recipe:
            logger.info(f'Re-scraping incomplete recipe: {link}')
            
        data = scrape_recipe(link)
        if data:
            try:
                if existing_recipe:
                    for key, value in data.items():
                        setattr(existing_recipe, key, value)
                    existing_recipe.save()
                    logger.info(f'Updated recipe: {link}')
                else:
                    Recipe.objects.create(**data)
                    logger.info(f'Scraped and saved: {link}')
            except Exception as e:
                logger.error(f"Error saving recipe {link}: {str(e)}")
        else:
            logger.error(f'Failed to scrape: {link}')
        time.sleep(2)  # Be polite

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape Allrecipes.com recipes.')
    parser.add_argument('--max-recipes', type=int, default=1000, help='Maximum number of recipes to scrape (default: 1000)')
    args = parser.parse_args()
    main(max_recipes=args.max_recipes) 