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
        logging.FileHandler('scraping_pinchofyum.log'),
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
                    # Wait for article content or recipe cards
                    page.wait_for_selector('.post-summary, .entry-content, article', timeout=10000)
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
    """Get recipe links from the main recipes page with pagination"""
    all_links = set()
    
    # Only scrape from the main "All Recipes" page with pagination
    main_recipes_url = "https://pinchofyum.com/recipes/all"
    
    try:
        logger.info(f"Starting with main recipes page: {main_recipes_url}")
        
        # Try multiple pages of the "All Recipes" section (up to 106 pages based on web search)
        for page in range(1, 107):  # Try up to 106 pages as indicated on the site
            if len(all_links) >= max_recipes:
                break
                
            try:
                if page == 1:
                    current_url = main_recipes_url
                else:
                    current_url = f"{main_recipes_url}/page/{page}"
                
                logger.info(f"Fetching page {page}: {current_url}")
                html = get_rendered_html(current_url)
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Look for recipe links - Pinch of Yum uses different patterns
                    recipe_links = soup.find_all('a', href=True)
                    
                    new_links = 0
                    for link in recipe_links:
                        href = link['href']
                        # Check if it's a recipe URL from pinchofyum.com
                        if (href.startswith('https://pinchofyum.com/') and 
                            href != 'https://pinchofyum.com/' and
                            href != 'https://pinchofyum.com/recipes' and
                            href != 'https://pinchofyum.com/recipes/all' and
                            not any(x in href for x in ['/category/', '/tag/', '/author/', '/page/', '/recipes/', '/about', '/blog', '/contact', '/privacy', '/terms', '/start-here', '?s=', '#', '.jpg', '.png', '.pdf', '/food-blogger-pro', '/clariti', '/income-reports', '/blogging-resources', '/media-mentions', '/sponsored-content'])):
                            
                            if href not in all_links:
                                all_links.add(href)
                                new_links += 1
                                if len(all_links) >= max_recipes:
                                    break
                    
                    logger.info(f"Found {new_links} new recipe links from page {page} (total: {len(all_links)})")
                    
                    # If no new links found on this page, maybe we've reached the end
                    if new_links == 0 and page > 1:
                        logger.info(f"No new links found on page {page}, continuing to try a few more pages")
                        # Don't break immediately, try a few more pages in case of empty pages
                        if page > 5:  # But if we're past page 5 with no results, break
                            break
                    
                    time.sleep(1)  # Be polite between pages
                    
            except Exception as e:
                logger.error(f"Error processing page {page}: {e}")
                continue
        
        logger.info(f"Collected {len(all_links)} recipe links from All Recipes pages")
            
    except Exception as e:
        logger.error(f"Error processing main recipes pages: {e}")
    
    logger.info(f"Total unique recipe links collected: {len(all_links)}")
    return list(all_links)

def scrape_recipe(url):
    """Scrape recipe data from a Pinch of Yum recipe page"""
    try:
        logger.info(f"Scraping recipe: {url}")
        html = get_rendered_html(url)
        if not html:
            return None
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract recipe title
        title = ""
        # Try multiple selectors for title
        title_selectors = ['h1.entry-title', 'h1', '.recipe-title', '.entry-title']
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text().strip()
                break
        
        if not title:
            logger.warning(f"Could not find title for {url}")
            return None
        
        # Extract ingredients
        ingredients_text = ""
        ingredients_list = []
        
        # Try multiple selectors for ingredients
        ingredients_selectors = [
            '.recipe-ingredients li',
            '.ingredients li', 
            '.recipe-card-ingredients li',
            '[class*="ingredient"] li',
            '.entry-content li'
        ]
        
        for selector in ingredients_selectors:
            ingredients = soup.select(selector)
            if ingredients:
                for ingredient in ingredients:
                    ingredient_text = ingredient.get_text().strip()
                    if ingredient_text and len(ingredient_text) > 3:  # Filter out very short items
                        ingredients_list.append(ingredient_text)
                break
        
        if ingredients_list:
            ingredients_text = "\n".join(ingredients_list)
        else:
            # Try to find ingredients in other formats
            ingredients_text_selectors = [
                '.recipe-ingredients',
                '.ingredients',
                '.recipe-card-ingredients',
                '[class*="ingredient"]'
            ]
            
            for selector in ingredients_text_selectors:
                ingredients_elem = soup.select_one(selector)
                if ingredients_elem:
                    ingredients_text = ingredients_elem.get_text().strip()
                    break
        
        if not ingredients_text:
            logger.warning(f"Could not find ingredients for {url}")
            return None
        
        # Extract instructions
        instructions = ""
        instructions_list = []
        
        # Try multiple selectors for instructions
        instructions_selectors = [
            '.recipe-instructions li',
            '.instructions li',
            '.recipe-card-instructions li', 
            '.recipe-instructions ol li',
            '.instructions ol li',
            '[class*="instruction"] li',
            '.entry-content ol li'
        ]
        
        for selector in instructions_selectors:
            instruction_items = soup.select(selector)
            if instruction_items:
                for item in instruction_items:
                    instruction_text = item.get_text().strip()
                    if instruction_text and len(instruction_text) > 10:  # Filter out very short items
                        instructions_list.append(instruction_text)
                break
        
        if instructions_list:
            instructions = "\n".join([f"{i+1}. {inst}" for i, inst in enumerate(instructions_list)])
        else:
            # Try to find instructions in other formats
            instructions_text_selectors = [
                '.recipe-instructions',
                '.instructions',
                '.recipe-card-instructions',
                '[class*="instruction"]',
                '.entry-content .recipe-instructions'
            ]
            
            for selector in instructions_text_selectors:
                instructions_elem = soup.select_one(selector)
                if instructions_elem:
                    instructions = instructions_elem.get_text().strip()
                    break
        
        if not instructions:
            # Try to find instructions in the main content
            content_selectors = ['.entry-content', '.post-content', 'article']
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    # Look for numbered lists or paragraphs that might contain instructions
                    paragraphs = content.find_all(['p', 'div'])
                    instruction_candidates = []
                    for p in paragraphs:
                        text = p.get_text().strip()
                        if len(text) > 20 and any(word in text.lower() for word in ['heat', 'add', 'mix', 'cook', 'bake', 'stir', 'combine', 'place', 'serve']):
                            instruction_candidates.append(text)
                    
                    if instruction_candidates:
                        instructions = "\n".join([f"{i+1}. {inst}" for i, inst in enumerate(instruction_candidates)])
                        break
        
        if not instructions:
            logger.warning(f"Could not find instructions for {url}")
            instructions = "Instructions not found"
        
        # Extract cooking times
        times = ""
        time_selectors = [
            '.recipe-times',
            '.prep-time',
            '.cook-time', 
            '.total-time',
            '[class*="time"]',
            '.recipe-meta'
        ]
        
        for selector in time_selectors:
            time_elem = soup.select_one(selector)
            if time_elem:
                times = time_elem.get_text().strip()
                break
        
        # Extract image URL
        image_url = ""
        # Try multiple selectors for the main recipe image
        image_selectors = [
            '.recipe-image img',
            '.entry-content img',
            '.post-thumbnail img',
            'article img',
            '.featured-image img'
        ]
        
        for selector in image_selectors:
            img_elem = soup.select_one(selector)
            if img_elem:
                image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
                if image_url:
                    # Make sure it's a full URL
                    if not image_url.startswith('http'):
                        image_url = urljoin(url, image_url)
                    break
        
        recipe_data = {
            'title': title,
            'instructions': instructions,
            'times': times,
            'image_url': image_url,
            'original_url': url,
            'scraped_ingredients_text': ingredients_text
        }
        
        logger.info(f"Successfully scraped recipe: {title}")
        return recipe_data
        
    except Exception as e:
        logger.error(f"Error scraping recipe {url}: {e}")
        return None

def test_scrape_single_recipe():
    """Test scraping a single recipe to verify selectors work"""
    test_urls = [
        "https://pinchofyum.com/thai-shrimp-curry-with-yummy-shallot-crispies",
        "https://pinchofyum.com/crispy-buffalo-tofu-with-caesar-salad",
        "https://pinchofyum.com/the-best-soft-chocolate-chip-cookies"
    ]
    
    for test_url in test_urls:
        logger.info(f"Testing recipe scraping with: {test_url}")
        recipe_data = scrape_recipe(test_url)
        if recipe_data:
            logger.info(f"Test successful!")
            logger.info(f"Title: {recipe_data['title']}")
            logger.info(f"Ingredients (first 200 chars): {recipe_data['scraped_ingredients_text'][:200]}...")
            logger.info(f"Instructions (first 200 chars): {recipe_data['instructions'][:200]}...")
            logger.info(f"Times: {recipe_data['times']}")
            logger.info(f"Image URL: {recipe_data['image_url']}")
            return True
        else:
            logger.warning(f"Test failed for {test_url}, trying next one...")
    
    logger.error("All test URLs failed")
    return False

def save_recipe_data(recipe_data):
    """Save recipe data to the database"""
    try:
        # Check if recipe already exists
        existing_recipe = Recipe.objects.filter(original_url=recipe_data['original_url']).first()
        
        if existing_recipe:
            logger.info(f"Recipe already exists, updating: {recipe_data['title']}")
            return update_recipe_data(existing_recipe, recipe_data)
        else:
            logger.info(f"Creating new recipe: {recipe_data['title']}")
            recipe = Recipe.objects.create(
                title=recipe_data['title'],
                instructions=recipe_data['instructions'],
                times=recipe_data['times'],
                image_url=recipe_data['image_url'],
                original_url=recipe_data['original_url'],
                scraped_ingredients_text=recipe_data['scraped_ingredients_text']
            )
            logger.info(f"Successfully saved recipe: {recipe.title}")
            return recipe
            
    except Exception as e:
        logger.error(f"Error saving recipe {recipe_data['title']}: {e}")
        return None

def update_recipe_data(existing_recipe, recipe_data):
    """Update existing recipe with new data"""
    try:
        # Update fields if they're different or empty
        updated = False
        
        if existing_recipe.title != recipe_data['title']:
            existing_recipe.title = recipe_data['title']
            updated = True
            
        if existing_recipe.instructions != recipe_data['instructions']:
            existing_recipe.instructions = recipe_data['instructions']
            updated = True
            
        if existing_recipe.times != recipe_data['times']:
            existing_recipe.times = recipe_data['times']
            updated = True
            
        if existing_recipe.image_url != recipe_data['image_url']:
            existing_recipe.image_url = recipe_data['image_url']
            updated = True
            
        if existing_recipe.scraped_ingredients_text != recipe_data['scraped_ingredients_text']:
            existing_recipe.scraped_ingredients_text = recipe_data['scraped_ingredients_text']
            updated = True
        
        if updated:
            existing_recipe.save()
            logger.info(f"Updated existing recipe: {existing_recipe.title}")
        else:
            logger.info(f"No updates needed for recipe: {existing_recipe.title}")
            
        return existing_recipe
        
    except Exception as e:
        logger.error(f"Error updating recipe {existing_recipe.title}: {e}")
        return None

def main(max_recipes=700, test_only=False):
    """Main function to scrape Pinch of Yum recipes"""
    logger.info(f"Starting Pinch of Yum recipe scraper...")
    logger.info(f"Target: {max_recipes} recipes")
    
    if test_only:
        logger.info("Running in test mode - testing selectors on a few recipes")
        success = test_scrape_single_recipe()
        if success:
            logger.info("Test completed successfully!")
        else:
            logger.error("Test failed!")
        return
    
    # Get recipe links
    logger.info("Collecting recipe links...")
    recipe_links = get_recipe_links_from_main_page(max_recipes)
    
    if not recipe_links:
        logger.error("No recipe links found!")
        return
    
    logger.info(f"Found {len(recipe_links)} recipe links")
    
    # Count existing recipes from pinchofyum.com
    existing_count = Recipe.objects.filter(original_url__contains='pinchofyum.com').count()
    logger.info(f"Existing Pinch of Yum recipes in database: {existing_count}")
    
    successful_scrapes = 0
    failed_scrapes = 0
    
    # Scrape each recipe
    for i, url in enumerate(recipe_links, 1):
        try:
            logger.info(f"Processing recipe {i}/{len(recipe_links)}: {url}")
            
            # Check if we already have this recipe
            if Recipe.objects.filter(original_url=url).exists():
                logger.info(f"Recipe already exists in database: {url}")
                successful_scrapes += 1
                continue
            
            recipe_data = scrape_recipe(url)
            if recipe_data:
                saved_recipe = save_recipe_data(recipe_data)
                if saved_recipe:
                    successful_scrapes += 1
                    logger.info(f"Progress: {successful_scrapes}/{max_recipes} recipes scraped successfully")
                    
                    # Check if we've reached our target
                    if successful_scrapes >= max_recipes:
                        logger.info(f"Reached target of {max_recipes} recipes!")
                        break
                else:
                    failed_scrapes += 1
            else:
                failed_scrapes += 1
                logger.warning(f"Failed to scrape recipe: {url}")
            
            # Be polite - small delay between requests
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error processing recipe {url}: {e}")
            failed_scrapes += 1
            continue
    
    # Final summary
    total_pinchofyum_recipes = Recipe.objects.filter(original_url__contains='pinchofyum.com').count()
    logger.info(f"Scraping completed!")
    logger.info(f"Successfully scraped: {successful_scrapes} recipes")
    logger.info(f"Failed to scrape: {failed_scrapes} recipes")
    logger.info(f"Total Pinch of Yum recipes in database: {total_pinchofyum_recipes}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape recipes from Pinch of Yum')
    parser.add_argument('--max-recipes', type=int, default=700, help='Maximum number of recipes to scrape')
    parser.add_argument('--test', action='store_true', help='Run in test mode to verify selectors')
    
    args = parser.parse_args()
    
    main(max_recipes=args.max_recipes, test_only=args.test) 