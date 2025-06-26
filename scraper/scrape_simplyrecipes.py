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
from urllib.parse import urlparse, urljoin

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping_simplyrecipes.log'),
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
                
                # Wait for key elements
                try:
                    page.wait_for_selector('h1', timeout=10000)
                    # Wait for article content
                    page.wait_for_selector('.mntl-sc-page', timeout=10000)
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

def get_recipe_links_from_main_page(max_recipes=700):
    """Get recipe links from the main recipes page and search for more"""
    all_links = set()
    base_url = "https://www.simplyrecipes.com"
    
    # First, try the main recipes page
    main_recipes_url = "https://www.simplyrecipes.com/recipes-5090746"
    
    try:
        logger.info(f"Fetching main recipes page: {main_recipes_url}")
        html = get_rendered_html(main_recipes_url)
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for recipe links on the main page
            recipe_links = soup.find_all('a', href=True)
            
            for link in recipe_links:
                href = link['href']
                # Check if it's a recipe URL - look for actual recipe patterns
                if (href.startswith('https://www.simplyrecipes.com/') and 
                    any(pattern in href for pattern in ['-recipe-', '-chicken-', '-beef-', '-fish-', '-pasta-', '-soup-', '-salad-', '-dessert-', '-bread-', '-cake-', '-cookie-', '-pie-', '-sauce-', '-dip-', '-stir-fry-', '-roast-', '-baked-', '-grilled-', '-fried-']) and
                    not any(x in href for x in ['category', 'tag', 'author', '/recipes/', '/recipes-', 'collection'])):
                    
                    if href not in all_links:
                        all_links.add(href)
                        if len(all_links) >= max_recipes:
                            break
            
            logger.info(f"Found {len(all_links)} recipe links from main page")
            
    except Exception as e:
        logger.error(f"Error processing main recipes page: {e}")
    
    # If we need more recipes, try expanded category pages with pagination
    if len(all_links) < max_recipes:
        # Try more category pages including subcategories
        category_urls = [
            "https://www.simplyrecipes.com/dinner-recipes-5091433",
            "https://www.simplyrecipes.com/breakfast-recipes-5091541", 
            "https://www.simplyrecipes.com/lunch-recipes-5091263",
            "https://www.simplyrecipes.com/dessert-recipes-5091513",
            "https://www.simplyrecipes.com/snacks-and-appetizer-recipes-5090762",
            # Add more specific categories
            "https://www.simplyrecipes.com/chicken-recipes-5091427",
            "https://www.simplyrecipes.com/beef-recipes-5091430", 
            "https://www.simplyrecipes.com/pork-recipes-5091429",
            "https://www.simplyrecipes.com/fish-and-seafood-recipes-5091428",
            "https://www.simplyrecipes.com/pasta-recipes-5091426",
            "https://www.simplyrecipes.com/soup-recipes-5091425",
            "https://www.simplyrecipes.com/salad-recipes-5091424",
            "https://www.simplyrecipes.com/bread-recipes-5091423",
            "https://www.simplyrecipes.com/cake-recipes-5091422",
            "https://www.simplyrecipes.com/cookie-recipes-5091421"
        ]
        
        for category_url in category_urls:
            if len(all_links) >= max_recipes:
                break
                
            # Try multiple pages for each category
            for page in range(1, 6):  # Try up to 5 pages per category
                if len(all_links) >= max_recipes:
                    break
                    
                try:
                    if page == 1:
                        current_url = category_url
                    else:
                        # Try common pagination patterns
                        current_url = f"{category_url}?page={page}"
                    
                    logger.info(f"Fetching category page: {current_url}")
                    html = get_rendered_html(current_url)
                    if html:
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Look for recipe cards or links
                        recipe_links = soup.find_all('a', href=True)
                        
                        new_links = 0
                        for link in recipe_links:
                            href = link['href']
                            if (href.startswith('https://www.simplyrecipes.com/') and 
                                any(pattern in href for pattern in ['-recipe-', '-chicken-', '-beef-', '-fish-', '-pasta-', '-soup-', '-salad-', '-dessert-', '-bread-', '-cake-', '-cookie-', '-pie-', '-sauce-', '-dip-', '-stir-fry-', '-roast-', '-baked-', '-grilled-', '-fried-']) and
                                not any(x in href for x in ['category', 'tag', 'author', '/recipes/', '/recipes-', 'collection'])):
                                
                                if href not in all_links:
                                    all_links.add(href)
                                    new_links += 1
                                    if len(all_links) >= max_recipes:
                                        break
                        
                        logger.info(f"Found {new_links} new recipe links from {current_url}")
                        
                        # If no new links found on this page, no point trying next page
                        if new_links == 0 and page > 1:
                            logger.info(f"No new links found on page {page}, stopping pagination for this category")
                            break
                            
                        time.sleep(1)  # Be polite between pages
                        
                except Exception as e:
                    logger.error(f"Error processing category page {current_url}: {e}")
                    continue
            
            time.sleep(2)  # Be polite between categories
    
    # If we still need more, try searching through other sections
    if len(all_links) < max_recipes:
        logger.info(f"Still need more recipes ({len(all_links)}/{max_recipes}), searching additional sections...")
        
        # Try recipe collections and other sections
        additional_sections = [
            "https://www.simplyrecipes.com/holiday-recipes-5090741",
            "https://www.simplyrecipes.com/vegetarian-recipes-5090751",
            "https://www.simplyrecipes.com/vegan-recipes-5090753",
            "https://www.simplyrecipes.com/gluten-free-recipes-5090756",
            "https://www.simplyrecipes.com/quick-easy-recipes-5090745",
            "https://www.simplyrecipes.com/healthy-recipes-5090748",
            "https://www.simplyrecipes.com/comfort-food-5090742"
        ]
        
        for section_url in additional_sections:
            if len(all_links) >= max_recipes:
                break
                
            try:
                logger.info(f"Fetching additional section: {section_url}")
                html = get_rendered_html(section_url)
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    recipe_links = soup.find_all('a', href=True)
                    new_links = 0
                    
                    for link in recipe_links:
                        href = link['href']
                        if (href.startswith('https://www.simplyrecipes.com/') and 
                            any(pattern in href for pattern in ['-recipe-', '-chicken-', '-beef-', '-fish-', '-pasta-', '-soup-', '-salad-', '-dessert-', '-bread-', '-cake-', '-cookie-', '-pie-', '-sauce-', '-dip-', '-stir-fry-', '-roast-', '-baked-', '-grilled-', '-fried-']) and
                            not any(x in href for x in ['category', 'tag', 'author', '/recipes/', '/recipes-', 'collection'])):
                            
                            if href not in all_links:
                                all_links.add(href)
                                new_links += 1
                                if len(all_links) >= max_recipes:
                                    break
                    
                    logger.info(f"Found {new_links} new recipe links from {section_url}")
                    time.sleep(3)  # Be polite
                    
            except Exception as e:
                logger.error(f"Error processing section {section_url}: {e}")
                continue
    
    logger.info(f"Final recipe link collection: {len(all_links)} unique recipes found")
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
        
        # Title - look for the main heading
        title = ''
        title_tag = soup.find('h1', class_='heading__title')
        if not title_tag:
            title_tag = soup.find('h1')
        if title_tag:
            title = title_tag.get_text(strip=True)
                
        if not title:
            logger.error(f"No title found for recipe at {url}")
            return None
            
        logger.info(f"Found title: {title}")
        
        # Image - look for primary image
        image_url = ''
        img_tag = soup.find('img', class_='primary-image__image')
        if not img_tag:
            img_tag = soup.find('img', alt=True)
        if img_tag and img_tag.has_attr('src'):
            image_url = img_tag['src']
            if image_url.startswith('/'):
                image_url = urljoin("https://www.simplyrecipes.com", image_url)
        elif img_tag and img_tag.has_attr('data-src'):
            image_url = img_tag['data-src']
            if image_url.startswith('/'):
                image_url = urljoin("https://www.simplyrecipes.com", image_url)
                
        logger.info(f"Found image URL: {image_url}")
        
        # Look for cooking time in meta tags
        ready_in = ''
        meta_tag = soup.find('meta', property='article:section')
        if meta_tag:
            ready_in = meta_tag.get('content', '')
                
        # Ingredients - look for specific structured content
        ingredients = []
        
        # Try to find the ingredients list in the structured content
        ingredient_list = soup.find('ul', id=re.compile(r'mntl-sc-block_\d+-0'))
        if ingredient_list and any('chicken' in li.get_text().lower() or 'cup' in li.get_text().lower() for li in ingredient_list.find_all('li')):
            for item in ingredient_list.find_all('li'):
                text = item.get_text(strip=True)
                if text and text not in ingredients:
                    ingredients.append(text)
        
        # If not found, try other selectors
        if not ingredients:
            for selector in ['ul li', '.ingredients li', '.recipe-ingredients li']:
                ingredient_elements = soup.select(selector)
                if ingredient_elements:
                    for item in ingredient_elements:
                        text = item.get_text(strip=True)
                        # Filter to likely ingredient text
                        if (text and len(text) > 5 and 
                            any(word in text.lower() for word in ['cup', 'pound', 'ounce', 'tablespoon', 'teaspoon', 'chicken', 'beef', 'onion', 'garlic', 'oil', 'salt', 'pepper']) and
                            text not in ingredients):
                            ingredients.append(text)
                    if ingredients:
                        break
                
        logger.info(f"Found {len(ingredients)} ingredients")
        
        # Instructions - look for paragraphs in the structured content
        directions = []
        
        # Find all paragraphs in the structured content area
        content_area = soup.find('div', class_='mntl-sc-page')
        if content_area:
            paragraphs = content_area.find_all('p', id=re.compile(r'mntl-sc-block_\d+-0'))
            for p in paragraphs:
                text = p.get_text(strip=True)
                # Filter for instruction-like text
                if (text and len(text) > 20 and 
                    any(word in text.lower() for word in ['add', 'place', 'bake', 'cook', 'heat', 'mix', 'stir', 'cover', 'remove', 'serve', 'marinate', 'preheat']) and
                    not any(skip in text.lower() for skip in ['advertisement', 'related', 'more recipes']) and
                    text not in directions):
                    directions.append(text)
        
        logger.info(f"Found {len(directions)} directions")
        
        # Try to extract from JSON-LD structured data if we don't have enough
        if not ingredients or not directions:
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = data[0]
                    
                    if data.get('@type') == 'Recipe':
                        if not ingredients and 'recipeIngredient' in data:
                            ingredients = data['recipeIngredient']
                            logger.info(f"Found {len(ingredients)} ingredients from JSON-LD")
                        
                        if not directions and 'recipeInstructions' in data:
                            for instruction in data['recipeInstructions']:
                                if isinstance(instruction, dict):
                                    text = instruction.get('text', '')
                                elif isinstance(instruction, str):
                                    text = instruction
                                else:
                                    continue
                                if text:
                                    directions.append(text)
                            logger.info(f"Found {len(directions)} directions from JSON-LD")
                        break
                except:
                    continue
        
        # Final validation
        if not ingredients:
            logger.warning(f"No ingredients found for recipe {url}")
            return None
            
        if not directions:
            logger.warning(f"No directions found for recipe {url}")
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

def test_scrape_single_recipe():
    """Test scraping a single recipe to verify our selectors work"""
    test_url = "https://www.simplyrecipes.com/cilantro-lime-chicken-recipe-11724380"
    logger.info(f"Testing single recipe scrape: {test_url}")
    
    data = scrape_recipe(test_url)
    if data:
        logger.info("Test scrape successful!")
        logger.info(f"Title: {data['title']}")
        logger.info(f"Ingredients count: {len(data['scraped_ingredients_text'])}")
        logger.info(f"Instructions count: {len(data['instructions'])}")
        logger.info(f"Sample ingredients: {data['scraped_ingredients_text'][:3]}")
        logger.info(f"Sample instruction: {data['instructions'][0][:100] if data['instructions'] else 'None'}")
        logger.info(f"Image URL: {data['image_url']}")
        logger.info(f"Times: {data['times']}")
        return True
    else:
        logger.error("Test scrape failed!")
        return False

def save_recipe_data(recipe_data):
    """Save recipe data with proper field length handling"""
    try:
        # Debug: Print field lengths
        logger.info(f"Field lengths - Title: {len(recipe_data.get('title', ''))}, Times: {len(recipe_data.get('times', ''))}")
        logger.info(f"Original URL length: {len(recipe_data.get('original_url', ''))}")
        logger.info(f"Image URL length: {len(recipe_data.get('image_url', ''))}")
        logger.info(f"Instructions type: {type(recipe_data.get('instructions', ''))}, length: {len(str(recipe_data.get('instructions', '')))}")
        logger.info(f"Ingredients type: {type(recipe_data.get('scraped_ingredients_text', ''))}, length: {len(str(recipe_data.get('scraped_ingredients_text', '')))}")
        
        # Truncate fields to fit database constraints
        recipe_data['title'] = recipe_data['title'][:300] if recipe_data['title'] else ''
        recipe_data['times'] = recipe_data['times'][:100] if recipe_data['times'] else ''
        
        # Ensure URLs are within reasonable length
        if len(recipe_data.get('original_url', '')) > 200:
            logger.warning(f"Original URL too long: {len(recipe_data['original_url'])} chars")
            recipe_data['original_url'] = recipe_data['original_url'][:200]
        
        if len(recipe_data.get('image_url', '')) > 500:
            logger.warning(f"Image URL too long: {len(recipe_data['image_url'])} chars")
            recipe_data['image_url'] = recipe_data['image_url'][:500]
        
        # Truncate ingredient text items to reasonable lengths
        if isinstance(recipe_data['scraped_ingredients_text'], list):
            recipe_data['scraped_ingredients_text'] = [
                item[:500] for item in recipe_data['scraped_ingredients_text']
            ]
        
        # Truncate instruction text items
        if isinstance(recipe_data['instructions'], list):
            recipe_data['instructions'] = [
                item[:1000] for item in recipe_data['instructions']
            ]
        
        return Recipe.objects.create(**recipe_data)
    except Exception as e:
        logger.error(f"Error creating recipe: {str(e)}")
        logger.error(f"Recipe data keys: {list(recipe_data.keys())}")
        # Try to identify the problematic field
        for key, value in recipe_data.items():
            if isinstance(value, str) and len(value) > 200:
                logger.error(f"Long field {key}: {len(value)} chars - {value[:100]}...")
        return None

def update_recipe_data(existing_recipe, recipe_data):
    """Update existing recipe with proper field length handling"""
    try:
        # Truncate fields to fit database constraints
        recipe_data['title'] = recipe_data['title'][:300] if recipe_data['title'] else ''
        recipe_data['times'] = recipe_data['times'][:100] if recipe_data['times'] else ''
        
        # Truncate ingredient text items to reasonable lengths
        if isinstance(recipe_data['scraped_ingredients_text'], list):
            recipe_data['scraped_ingredients_text'] = [
                item[:500] for item in recipe_data['scraped_ingredients_text']
            ]
        
        # Truncate instruction text items
        if isinstance(recipe_data['instructions'], list):
            recipe_data['instructions'] = [
                item[:1000] for item in recipe_data['instructions']
            ]
        
        for key, value in recipe_data.items():
            setattr(existing_recipe, key, value)
        existing_recipe.save()
        return existing_recipe
    except Exception as e:
        logger.error(f"Error updating recipe: {str(e)}")
        return None

def main(max_recipes=700, test_only=False):
    if test_only:
        logger.info("Running test mode - scraping single recipe")
        return test_scrape_single_recipe()
    
    logger.info(f'Starting to scrape up to {max_recipes} recipes from SimplyRecipes.com...')
    
    # Get all recipe links first
    all_links = get_recipe_links_from_main_page(max_recipes)
    logger.info(f'Found total of {len(all_links)} unique recipe links')
    
    if len(all_links) == 0:
        logger.error("No recipe links found!")
        return
    
    # Now scrape each recipe
    total_links = len(all_links)
    successful_scrapes = 0
    
    for index, link in enumerate(all_links, 1):
        if not link:  # Skip empty links
            continue
            
        logger.info(f'Scraping recipe {index}/{total_links}: {link}')
        
        existing_recipe = Recipe.objects.filter(original_url=link).first()
        
        if existing_recipe and existing_recipe.scraped_ingredients_text and existing_recipe.instructions:
            logger.info(f'Already scraped with complete data: {link}')
            successful_scrapes += 1
            continue
            
        if existing_recipe:
            logger.info(f'Re-scraping incomplete recipe: {link}')
            
        data = scrape_recipe(link)
        if data:
            try:
                if existing_recipe:
                    result = update_recipe_data(existing_recipe, data)
                    if result:
                        logger.info(f'Updated recipe: {link}')
                        successful_scrapes += 1
                    else:
                        logger.error(f'Failed to update recipe: {link}')
                else:
                    result = save_recipe_data(data)
                    if result:
                        logger.info(f'Scraped and saved: {link}')
                        successful_scrapes += 1
                    else:
                        logger.error(f'Failed to save recipe: {link}')
            except Exception as e:
                logger.error(f"Error saving recipe {link}: {str(e)}")
        else:
            logger.error(f'Failed to scrape: {link}')
            
        time.sleep(2)  # Be polite
    
    logger.info(f'Scraping completed! Successfully scraped {successful_scrapes}/{total_links} recipes')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape SimplyRecipes.com recipes.')
    parser.add_argument('--max-recipes', type=int, default=700, help='Maximum number of recipes to scrape (default: 700)')
    parser.add_argument('--test', action='store_true', help='Test mode: scrape only one recipe to verify functionality')
    args = parser.parse_args()
    main(max_recipes=args.max_recipes, test_only=args.test) 