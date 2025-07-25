import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import sys
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
        logging.FileHandler('scraping_inspiredtaste.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')

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
                
                # Wait for key elements - be more specific and give shorter timeouts
                try:
                    # Try to wait for main content, but don't fail if some selectors don't exist
                    page.wait_for_selector('body', timeout=5000)  # Always exists
                    
                    # Try specific selectors but don't fail if they don't exist
                    try:
                        page.wait_for_selector('article, .entry-content, .post-content, main', timeout=3000) 
                    except:
                        pass  # Continue even if these specific selectors aren't found
                        
                except Exception as e:
                    logger.warning(f"Some selectors not found on {url}: {e}")
                    # Continue anyway as we might still have some content
                
                # Give a small delay for any remaining content to load
                time.sleep(1)  # Reduced from 2 seconds
                
                html = page.content()
                context.close()
                browser.close()
                return html
        except Exception as e:
            logger.error(f"Error loading {url} (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(3)  # Reduced from 5 seconds
    logger.error(f"Failed to load {url} after {max_retries} attempts.")
    return None

def get_recipe_links_from_categories(max_recipes=1000):
    """Get recipe links from multiple sources on InspiredTaste.net"""
    all_links = set()
    base_url = "https://www.inspiredtaste.net"
    
    # List of actual category URLs from the website structure
    category_urls = [
        "https://www.inspiredtaste.net/category/recipes/",  
        "https://www.inspiredtaste.net/category/recipes/page/2/",
        "https://www.inspiredtaste.net/category/recipes/page/3/",
        "https://www.inspiredtaste.net/category/recipes/page/4/",
        "https://www.inspiredtaste.net/category/recipes/page/5/",
        "https://www.inspiredtaste.net/category/dinner-recipes/",
        "https://www.inspiredtaste.net/category/baking/",
        "https://www.inspiredtaste.net/category/breakfast/",
        "https://www.inspiredtaste.net/category/appetizers/",
        "https://www.inspiredtaste.net/category/side-dishes/",
        "https://www.inspiredtaste.net/category/soups-and-stews/",
        "https://www.inspiredtaste.net/category/pasta-recipes/",
        "https://www.inspiredtaste.net/category/chicken-recipes/",
        "https://www.inspiredtaste.net/category/vegetarian/",
        "https://www.inspiredtaste.net/category/dessert-recipes/",
        "https://www.inspiredtaste.net/category/quick/",
        "https://www.inspiredtaste.net/category/salad-recipes/",
        "https://www.inspiredtaste.net/category/beef-recipes/",
        "https://www.inspiredtaste.net/category/pork-recipes/",
        "https://www.inspiredtaste.net/category/seafood-recipes/"
    ]
    
    try:
        for category_url in category_urls:
            if len(all_links) >= max_recipes:
                break
                
            logger.info(f"Processing category: {category_url}")
            html = get_rendered_html(category_url)
            
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for recipe links in the category page
                # InspiredTaste uses these selectors for recipe links
                recipe_link_selectors = [
                    'article h2 a',  # Main recipe title links
                    'article h3 a',  # Alternative recipe title links
                    '.entry-title a',  # Entry title links
                    'h2.entry-title a',  # Specific entry title links
                    '.recipe-link a',  # Recipe specific links
                    'a[href*="/recipe/"]',  # Links containing /recipe/
                    'h1 a[href]',  # H1 links
                    'h2 a[href]',  # H2 links
                    'h3 a[href]'   # H3 links
                ]
                
                new_links = 0
                for selector in recipe_link_selectors:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href')
                        if href:
                            # Convert relative URLs to absolute
                            if href.startswith('/'):
                                href = base_url + href
                            elif href.startswith(base_url):
                                pass  # Already absolute
                            else:
                                continue  # Skip external links
                            
                            # Filter to only recipe URLs
                            if (href.startswith(base_url) and 
                                href != base_url and 
                                href != f"{base_url}/" and
                                not any(x in href for x in [
                                    '/category/', '/tag/', '/author/', '/page/', 
                                    '/about', '/contact', '/privacy', '/terms',
                                    '?', '#', '.jpg', '.png', '.pdf',
                                    '/wp-content/', '/wp-admin/', 'mailto:', 'tel:'
                                ]) and
                                # Must have some content after the domain
                                len(href.replace(base_url, '').strip('/')) > 3):
                                
                                if href not in all_links:
                                    all_links.add(href)
                                    new_links += 1
                                    if len(all_links) >= max_recipes:
                                        break
                    
                    if len(all_links) >= max_recipes:
                        break
                
                logger.info(f"Found {new_links} new recipe links from {category_url} (total: {len(all_links)})")
                time.sleep(2)  # Be polite between requests
    
    except Exception as e:
        logger.error(f"Error processing category URLs: {e}")
    
    # If we still need more recipes, try to get more from additional pages
    if len(all_links) < max_recipes:
        logger.info(f"Need more recipes ({len(all_links)}/{max_recipes}), trying additional pages...")
        
        # Try more pages from the main recipe category
        for page_num in range(6, 21):  # Pages 6-20
            if len(all_links) >= max_recipes:
                break
                
            page_url = f"https://www.inspiredtaste.net/category/recipes/page/{page_num}/"
            logger.info(f"Processing additional page: {page_url}")
            
            try:
                html = get_rendered_html(page_url)
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Check if this page exists (not 404)
                    title = soup.select_one('title')
                    if title and any(x in title.get_text().lower() for x in ["404", "not found", "page cannot be found"]):
                        logger.info(f"Reached end of pagination at page {page_num}")
                        break
                    
                    # Extract recipe links
                    links = soup.select('article h2 a, article h3 a, .entry-title a')
                    new_links = 0
                    for link in links:
                        href = link.get('href')
                        if href:
                            if href.startswith('/'):
                                href = base_url + href
                            
                            if (href.startswith(base_url) and 
                                not any(x in href for x in ['/category/', '/tag/', '/author/', '/page/']) and
                                href not in all_links):
                                all_links.add(href)
                                new_links += 1
                                if len(all_links) >= max_recipes:
                                    break
                    
                    logger.info(f"Found {new_links} additional recipes from page {page_num}")
                    if new_links == 0:
                        logger.info(f"No more recipes found, stopping at page {page_num}")
                        break
                        
                    time.sleep(2)
                else:
                    logger.info(f"Could not load page {page_num}, stopping pagination")
                    break
                    
            except Exception as e:
                logger.error(f"Error processing page {page_num}: {e}")
                continue
    
    logger.info(f"Collected {len(all_links)} total recipe links")
    return list(all_links)

def scrape_recipe(url):
    """Scrape a single recipe from InspiredTaste.net"""
    try:
        logger.info(f"Scraping recipe: {url}")
        html = get_rendered_html(url)
        
        if not html:
            logger.error(f"Failed to get HTML for {url}")
            return None
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract recipe data
        recipe_data = {}
        
        # Title - try multiple selectors
        title_selectors = [
            'h1.entry-title',
            'h1.headline', 
            'h1',
            '.post-title h1',
            '.recipe-title h1',
            '.entry-header h1',
            'header h1',
            'article h1'
        ]
        title = None
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and not any(x in title.lower() for x in ["404", "page cannot be found", "page not found", "not found"]):
                    break
        
        if not title or any(x in title.lower() for x in ["404", "page cannot be found", "page not found", "not found"]):
            logger.warning(f"404 or invalid page detected for {url}: {title}")
            return None
            
        recipe_data['title'] = title
        recipe_data['url'] = url
        
        # Description - try multiple approaches
        description_selectors = [
            '.recipe-summary',
            '.entry-content p:first-of-type',
            '.recipe-description',
            '.post_content p:first-of-type',
            '.post-content p:first-of-type',
            'article p:first-of-type',
            'meta[name="description"]',
            'meta[property="og:description"]'
        ]
        description = ""
        for selector in description_selectors:
            if selector.startswith('meta'):
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    description = desc_elem.get('content', '').strip()
                    if description and len(description) > 20:
                        break
            else:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    if description and len(description) > 20:
                        break
        
        recipe_data['description'] = description
        
        # Image URL
        image_selectors = [
            '.recipe-image img',
            '.entry-content img:first-of-type',
            'img[class*="recipe"]',
            'img[class*="featured"]',
            '.post_content img:first-of-type',
            '.post-content img:first-of-type',
            'article img:first-of-type',
            'meta[property="og:image"]'
        ]
        image_url = ""
        for selector in image_selectors:
            if selector.startswith('meta'):
                img_elem = soup.select_one(selector)
                if img_elem:
                    image_url = img_elem.get('content', '').strip()
                    if image_url:
                        break
            else:
                img_elem = soup.select_one(selector)
                if img_elem:
                    image_url = img_elem.get('src') or img_elem.get('data-src') or ""
                    if image_url:
                        if image_url.startswith('/'):
                            image_url = 'https://www.inspiredtaste.net' + image_url
                        break
        
        recipe_data['image_url'] = image_url
        
        # Try to extract from JSON-LD structured data first
        ingredients = []
        instructions = []
        prep_time = ""
        cook_time = ""
        servings = ""
        
        # Look for JSON-LD structured data
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                json_data = json.loads(script.string)
                if isinstance(json_data, list):
                    for item in json_data:
                        if isinstance(item, dict) and item.get('@type') == 'Recipe':
                            json_data = item
                            break
                
                if isinstance(json_data, dict) and json_data.get('@type') == 'Recipe':
                    # Extract from structured data
                    if json_data.get('recipeIngredient'):
                        ingredients = json_data['recipeIngredient']
                    
                    if json_data.get('recipeInstructions'):
                        instructions = []
                        for instruction in json_data['recipeInstructions']:
                            if isinstance(instruction, dict):
                                inst_text = instruction.get('text', '')
                                if not inst_text:
                                    inst_text = instruction.get('name', '')
                                if inst_text:
                                    instructions.append(inst_text)
                            else:
                                instructions.append(str(instruction))
                    
                    prep_time = json_data.get('prepTime', '')
                    cook_time = json_data.get('cookTime', '')  
                    servings = str(json_data.get('recipeYield', '') or json_data.get('yield', ''))
                    
                    if ingredients and instructions:
                        break
                        
            except Exception as e:
                logger.warning(f"Error parsing JSON-LD data: {e}")
                continue
        
        # If no structured data found, try HTML selectors
        if not ingredients:
            ingredient_selectors = [
                '.recipe-ingredients li',
                '.ingredients li', 
                'ul[class*="ingredient"] li',
                '.entry-content ul li',
                '.post_content ul li',
                '.post-content ul li',
                'article ul li',
                '.itr-ingredients li',
                '.wp-block-list li',
                'div[class*="ingredient"] li'
            ]
            for selector in ingredient_selectors:
                ingredient_elems = soup.select(selector)
                if ingredient_elems:
                    temp_ingredients = []
                    for elem in ingredient_elems:
                        ingredient_text = elem.get_text(strip=True)
                        if ingredient_text and len(ingredient_text) > 3:
                            temp_ingredients.append(ingredient_text)
                    if len(temp_ingredients) >= 3:  # Need at least 3 ingredients
                        ingredients = temp_ingredients
                        break
        
        if not instructions:
            instruction_selectors = [
                '.recipe-instructions li',
                '.instructions li',
                'ol[class*="instruction"] li', 
                '.entry-content ol li',
                '.post_content ol li',
                '.post-content ol li',
                'article ol li',
                '.itr-directions li',
                '.wp-block-list li',
                'div[class*="instruction"] li',
                'div[class*="directions"] li'
            ]
            for selector in instruction_selectors:
                instruction_elems = soup.select(selector)
                if instruction_elems:
                    temp_instructions = []
                    for elem in instruction_elems:
                        instruction_text = elem.get_text(strip=True)
                        if instruction_text and len(instruction_text) > 10:
                            temp_instructions.append(instruction_text)
                    if len(temp_instructions) >= 2:  # Need at least 2 instructions
                        instructions = temp_instructions
                        break
        
        recipe_data['ingredients'] = ingredients
        recipe_data['instructions'] = instructions
        recipe_data['prep_time'] = prep_time
        recipe_data['cook_time'] = cook_time
        recipe_data['servings'] = servings
        
        # Validate essential data - must have either ingredients OR instructions
        if not ingredients and not instructions:
            logger.warning(f"No ingredients or instructions found for {url}")
            # Don't return None immediately, let's try to save what we have
            # return None
            
        logger.info(f"Successfully scraped recipe: {title}")
        logger.info(f"  Ingredients: {len(ingredients)}, Instructions: {len(instructions)}")
        return recipe_data
        
    except Exception as e:
        logger.error(f"Error scraping recipe {url}: {e}")
        return None

def test_scrape_single_recipe():
    """Test scraping a single recipe"""
    # Try multiple URLs until we find one that works
    test_urls = [
        "https://www.inspiredtaste.net/",  # Homepage should always work
        "https://www.inspiredtaste.net/recipe-index/",  # Recipe index
    ]
    
    for test_url in test_urls:
        logger.info(f"Testing single recipe scrape: {test_url}")
        
        recipe_data = scrape_recipe(test_url)
        if recipe_data and recipe_data['title'] and "404" not in recipe_data['title'] and "Page Cannot Be Found" not in recipe_data['title'] and "Page not found" not in recipe_data['title']:
            logger.info("Test successful!")
            logger.info(f"Title: {recipe_data['title']}")
            logger.info(f"Description: {recipe_data['description'][:100]}..." if recipe_data['description'] else "No description")
            logger.info(f"Ingredients count: {len(recipe_data['ingredients'])}")
            logger.info(f"Instructions count: {len(recipe_data['instructions'])}")
            if recipe_data['ingredients']:
                logger.info(f"First ingredient: {recipe_data['ingredients'][0]}")
            if recipe_data['instructions']:
                logger.info(f"First instruction: {recipe_data['instructions'][0][:100]}...")
            return recipe_data
    
    logger.error("All test URLs failed!")
    return None

def save_recipe_data(recipe_data):
    """Save recipe data to Django model"""
    try:
        # Check if recipe already exists
        existing_recipe = Recipe.objects.filter(original_url=recipe_data['url']).first()
        
        if existing_recipe:
            logger.info(f"Recipe already exists: {recipe_data['title']}")
            return update_recipe_data(existing_recipe, recipe_data)
        
        # Convert arrays to strings for storage
        ingredients_text = '\n'.join(recipe_data.get('ingredients', [])) if recipe_data.get('ingredients') else recipe_data.get('description', '')
        instructions_text = '\n'.join(recipe_data.get('instructions', [])) if recipe_data.get('instructions') else ''
        times_text = f"Prep: {recipe_data.get('prep_time', '')}, Cook: {recipe_data.get('cook_time', '')}, Servings: {recipe_data.get('servings', '')}"
        
        # Create new recipe
        recipe = Recipe(
            title=recipe_data['title'][:300],  # Ensure title fits in field
            scraped_ingredients_text=ingredients_text,
            instructions=instructions_text,
            times=times_text[:300],  # Ensure times fits in field
            original_url=recipe_data['url'],
            image_url=recipe_data.get('image_url', '')[:500] if recipe_data.get('image_url') else '',  # Ensure URL fits
        )
        
        recipe.save()
        logger.info(f"Saved new recipe: {recipe_data['title']}")
        return recipe
        
    except Exception as e:
        logger.error(f"Error saving recipe {recipe_data['title']}: {e}")
        return None

def update_recipe_data(existing_recipe, recipe_data):
    """Update existing recipe with new data"""
    try:
        # Convert arrays to strings for storage
        ingredients_text = '\n'.join(recipe_data.get('ingredients', [])) if recipe_data.get('ingredients') else recipe_data.get('description', '')
        instructions_text = '\n'.join(recipe_data.get('instructions', [])) if recipe_data.get('instructions') else ''
        times_text = f"Prep: {recipe_data.get('prep_time', '')}, Cook: {recipe_data.get('cook_time', '')}, Servings: {recipe_data.get('servings', '')}"
        
        # Update fields if they're empty or if new data is better
        if not existing_recipe.scraped_ingredients_text and ingredients_text:
            existing_recipe.scraped_ingredients_text = ingredients_text
        
        if not existing_recipe.instructions and instructions_text:
            existing_recipe.instructions = instructions_text
        
        if not existing_recipe.times and times_text.strip() != "Prep: , Cook: , Servings: ":
            existing_recipe.times = times_text[:300]
        
        if not existing_recipe.image_url and recipe_data.get('image_url'):
            existing_recipe.image_url = recipe_data['image_url'][:500]
        
        existing_recipe.save()
        logger.info(f"Updated existing recipe: {recipe_data['title']}")
        return existing_recipe
        
    except Exception as e:
        logger.error(f"Error updating recipe {recipe_data['title']}: {e}")
        return None

def main(max_recipes=1000, test_only=False):
    """Main scraping function"""
    logger.info(f"Starting InspiredTaste.net scraper - {'test mode' if test_only else f'collecting up to {max_recipes} recipes'}")
    
    if test_only:
        return test_scrape_single_recipe()
    
    # Get recipe links
    recipe_links = get_recipe_links_from_categories(max_recipes)
    
    if not recipe_links:
        logger.error("No recipe links found!")
        return
    
    logger.info(f"Found {len(recipe_links)} recipe links to scrape")
    
    # Scrape recipes
    successful_scrapes = 0
    failed_scrapes = 0
    
    for i, url in enumerate(recipe_links, 1):
        try:
            logger.info(f"Processing recipe {i}/{len(recipe_links)}: {url}")
            
            recipe_data = scrape_recipe(url)
            if recipe_data:
                saved_recipe = save_recipe_data(recipe_data)
                if saved_recipe:
                    successful_scrapes += 1
                else:
                    failed_scrapes += 1
            else:
                failed_scrapes += 1
                
            # Add delay between requests
            time.sleep(2)
            
            # Log progress every 50 recipes
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{len(recipe_links)} processed, {successful_scrapes} successful, {failed_scrapes} failed")
                
        except Exception as e:
            logger.error(f"Error processing recipe {url}: {e}")
            failed_scrapes += 1
            continue
    
    logger.info(f"Scraping completed! {successful_scrapes} successful, {failed_scrapes} failed")
    
    # Final count
    total_recipes = Recipe.objects.filter(original_url__icontains='inspiredtaste.net').count()
    logger.info(f"Total InspiredTaste recipes in database: {total_recipes}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape recipes from InspiredTaste.net')
    parser.add_argument('--max-recipes', type=int, default=1000, help='Maximum number of recipes to scrape')
    parser.add_argument('--test', action='store_true', help='Test mode - scrape only one recipe')
    
    args = parser.parse_args()
    
    main(max_recipes=args.max_recipes, test_only=args.test) 