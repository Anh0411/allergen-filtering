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

BASE_URL_FIRST = 'https://www.food.com/search/'
BASE_URL_PAGED = 'https://www.food.com/search/?pn={}'

def get_rendered_html(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to load {url} (attempt {attempt+1}/{max_retries})")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Set a shorter timeout for initial page load
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # Wait for search results container and check for recipe divs
                try:
                    # First wait for the search results container
                    page.wait_for_selector('.search-results', timeout=10000)
                    
                    # Then wait for at least one recipe div to be present
                    page.wait_for_selector('.fd-tile.fd-recipe', timeout=20000)
                    
                    # Additional wait to ensure content is fully loaded
                    page.wait_for_load_state('networkidle', timeout=10000)
                    
                except Exception as e:
                    logger.warning(f"Selector not found quickly on {url}: {e}")
                    time.sleep(3)
                
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            logger.error(f"Error loading {url} (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(5)
    logger.error(f"Failed to load {url} after {max_retries} attempts.")
    return None

def scroll_until_next_page(page, current_page, max_pages):
    """Scroll the page until the URL changes to the next page number."""
    if current_page >= max_pages:
        return None
        
    next_page = current_page + 1
    target_url = f"https://www.food.com/search/?pn={next_page}"
    
    logger.info(f"Scrolling to load page {next_page}")
    
    # Scroll in smaller increments with pauses
    for _ in range(10):  # Try up to 10 scroll attempts
        # Scroll down
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)  # Wait for content to load
        
        # Check if URL has changed
        current_url = page.url
        if target_url in current_url:
            logger.info(f"Successfully loaded page {next_page}")
            time.sleep(3)  # Additional wait after URL change
            return next_page
            
    logger.warning(f"Failed to load page {next_page} after scrolling")
    return None

def get_all_recipe_links(max_pages):
    """Get all recipe links by scrolling through pages."""
    all_links = []
    current_page = 1
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Start with the first page
        logger.info(f"Loading initial page")
        page.goto(BASE_URL_FIRST, wait_until="domcontentloaded")
        
        while current_page <= max_pages:
            # Wait for content to load
            try:
                page.wait_for_selector('.search-results', timeout=10000)
                page.wait_for_selector('.fd-tile.fd-recipe', timeout=20000)
            except Exception as e:
                logger.warning(f"Error waiting for content on page {current_page}: {e}")
            
            # Get current page content
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            recipe_divs = soup.find_all('div', class_='fd-tile fd-recipe')
            new_links = [div.get('data-url') for div in recipe_divs if div.get('data-url')]
            
            # Add only new links
            for link in new_links:
                if link not in all_links:
                    all_links.append(link)
            
            logger.info(f"Found {len(new_links)} new links on page {current_page}, total unique links: {len(all_links)}")
            
            # Try to load next page
            next_page = scroll_until_next_page(page, current_page, max_pages)
            if not next_page:
                break
                
            current_page = next_page
        
        browser.close()
    
    return all_links

def scrape_recipe(url):
    try:
        if not url:
            logger.error("Empty URL provided")
            return None
            
        logger.info(f"Scraping recipe: {url}")
        resp = requests.get(url)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch recipe page. Status code: {resp.status_code}")
            return None
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Title
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else ''
        if not title:
            logger.error(f"No title found for recipe at {url}")
            return None
            
        logger.info(f"Found title: {title}")
        
        # Image
        image_url = ''
        primary_image_div = soup.find('div', class_='primary-image')
        if primary_image_div:
            img_tag = primary_image_div.find('img', class_='only-desktop') or primary_image_div.find('img')
            if img_tag and img_tag.has_attr('src'):
                image_url = img_tag['src']
                logger.info(f"Found image URL: {image_url}")
        
        # Cooking time
        ready_in = ''
        for dt in soup.find_all('dt', class_='facts__label'):
            if 'Ready In:' in dt.get_text():
                dd = dt.find_next_sibling('dd')
                if dd:
                    ready_in = dd.get_text(strip=True)
                    logger.info(f"Found cooking time: {ready_in}")
                break
        
        # Ingredients
        ingredients = []
        ingredient_list = soup.find('ul', class_='ingredient-list')
        if ingredient_list:
            for li in ingredient_list.find_all('li', recursive=False):
                qty = li.find('span', class_='ingredient-quantity')
                text = li.find('span', class_='ingredient-text')
                if text:
                    ingredient_line = (qty.get_text(' ', strip=True) + ' ' if qty else '') + text.get_text(' ', strip=True)
                    ingredients.append(ingredient_line.strip())
        logger.info(f"Found {len(ingredients)} ingredients")
        
        # Directions
        directions = []
        direction_list = soup.find('ul', class_='direction-list')
        if direction_list:
            for li in direction_list.find_all('li', class_='direction'):
                directions.append(li.get_text(strip=True))
        logger.info(f"Found {len(directions)} directions")
        
        if not ingredients or not directions:
            logger.warning(f"Missing data for recipe {url}: ingredients={len(ingredients)}, directions={len(directions)}")
            return None
        
        # Save to DB
        recipe_data = {
            'title': title,
            'instructions': '\n'.join(directions),
            'times': ready_in,
            'image_url': image_url,
            'scraped_ingredients_text': '\n'.join(ingredients),
            'original_url': url  # Make sure URL is included in the data
        }
        
        return recipe_data
        
    except Exception as e:
        logger.error(f"Error scraping recipe {url}: {str(e)}", exc_info=True)
        return None

def main(max_pages=None):
    if not max_pages:
        max_pages = float('inf')
        
    logger.info(f'Starting to scrape up to {max_pages} pages...')
    
    # Get all recipe links first
    all_links = get_all_recipe_links(max_pages)
    logger.info(f'Found total of {len(all_links)} unique recipe links')
    
    # Now scrape each recipe
    for link in all_links:
        if not link:  # Skip empty links
            continue
            
        full_url = f'https://www.food.com{link}' if link.startswith('/') else link
        existing_recipe = Recipe.objects.filter(original_url=full_url).first()
        
        if existing_recipe and existing_recipe.scraped_ingredients_text and existing_recipe.instructions:
            logger.info(f'Already scraped with complete data: {full_url}')
            continue
            
        if existing_recipe:
            logger.info(f'Re-scraping incomplete recipe: {full_url}')
            
        data = scrape_recipe(full_url)
        if data:
            try:
                if existing_recipe:
                    for key, value in data.items():
                        setattr(existing_recipe, key, value)
                    existing_recipe.save()
                    logger.info(f'Updated recipe: {full_url}')
                else:
                    Recipe.objects.create(**data)
                    logger.info(f'Scraped and saved: {full_url}')
            except Exception as e:
                logger.error(f"Error saving recipe {full_url}: {str(e)}")
        else:
            logger.error(f'Failed to scrape: {full_url}')
        time.sleep(3)  # Be polite

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape Food.com recipes.')
    parser.add_argument('--max-pages', type=int, help='Maximum number of pages to scrape (default: all)')
    args = parser.parse_args()
    main(max_pages=args.max_pages) 