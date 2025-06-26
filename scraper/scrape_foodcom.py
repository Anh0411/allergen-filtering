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

def get_rendered_html(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to load {url} (attempt {attempt+1}/{max_retries})")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Set a shorter timeout for initial page load
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # Wait for content to load
                try:
                    page.wait_for_selector('h1', timeout=10000)
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
            'instructions': directions,  # Store as array directly
            'times': ready_in,
            'image_url': image_url,
            'scraped_ingredients_text': ingredients,  # Store as array directly
            'original_url': url  # Make sure URL is included in the data
        }
        
        return recipe_data
        
    except Exception as e:
        logger.error(f"Error scraping recipe {url}: {str(e)}", exc_info=True)
        return None

def main(start_id=None, end_id=None):
    if not start_id:
        start_id = 1
    if not end_id:
        end_id = start_id + 1000
        
    logger.info(f'Starting to scrape recipes from ID {start_id} to {end_id}...')
    
    # Get the highest recipe ID we already have
    existing_recipes = Recipe.objects.all()
    existing_ids = set()
    for recipe in existing_recipes:
        if recipe.original_url:
            match = re.search(r'recipe/([^/]+)-(\d+)', recipe.original_url)
            if match:
                existing_ids.add(int(match.group(2)))
    
    logger.info(f'Found {len(existing_ids)} existing recipe IDs')
    
    # Scrape recipes in the ID range
    for recipe_id in range(start_id, end_id + 1):
        if recipe_id in existing_ids:
            logger.info(f'Skipping existing recipe ID: {recipe_id}')
            continue
            
        url = f'https://www.food.com/recipe/recipe-{recipe_id}'
        logger.info(f'Scraping recipe ID {recipe_id}: {url}')
        
        data = scrape_recipe(url)
        if data:
            try:
                Recipe.objects.create(**data)
                logger.info(f'Scraped and saved: {url}')
            except Exception as e:
                logger.error(f"Error saving recipe {url}: {str(e)}")
        else:
            logger.error(f'Failed to scrape: {url}')
        time.sleep(1)  # Be polite

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape Food.com recipes.')
    parser.add_argument('--start-id', type=int, help='Starting recipe ID')
    parser.add_argument('--end-id', type=int, help='Ending recipe ID')
    args = parser.parse_args()
    main(start_id=args.start_id, end_id=args.end_id) 