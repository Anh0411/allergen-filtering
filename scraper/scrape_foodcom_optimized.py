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
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from typing import Optional, List, Dict, Any

# Setup logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('foodcom_scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from recipes.models import Recipe

class FoodComScraper:
    def __init__(self, max_retries: int = 3, delay_range: tuple = (2, 5)):
        self.max_retries = max_retries
        self.delay_range = delay_range
        self.session = requests.Session()
        
        # Better User-Agent rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
        ]
        
        self.existing_ids = self._load_existing_ids()
        logger.info(f'Loaded {len(self.existing_ids)} existing recipe IDs')

    def _load_existing_ids(self) -> set:
        """Load existing recipe IDs to avoid duplicates"""
        existing_recipes = Recipe.objects.filter(original_url__icontains='food.com')
        existing_ids = set()
        
        for recipe in existing_recipes:
            if recipe.original_url:
                match = re.search(r'recipe[/-](\d+)', recipe.original_url)
                if match:
                    existing_ids.add(int(match.group(1)))
        return existing_ids

    def _get_random_delay(self) -> float:
        """Get random delay to appear more human-like"""
        return random.uniform(*self.delay_range)

    def _get_headers(self) -> Dict[str, str]:
        """Get randomized headers"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def get_rendered_html(self, url: str) -> Optional[str]:
        """Use Playwright for JavaScript-heavy pages"""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Loading with Playwright: {url} (attempt {attempt+1}/{self.max_retries})")
                
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=['--no-sandbox', '--disable-dev-shm-usage']
                    )
                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent=random.choice(self.user_agents)
                    )
                    page = context.new_page()
                    
                    # Navigate to page
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    
                    # Wait for content to load
                    try:
                        # Wait for recipe content or error indicator
                        page.wait_for_selector('h1, .error-message, [data-testid="recipe-title"]', timeout=10000)
                        page.wait_for_load_state('networkidle', timeout=15000)
                    except Exception as e:
                        logger.warning(f"Timeout waiting for selectors on {url}: {e}")
                    
                    # Check if it's a 404 or error page
                    title = page.title().lower()
                    if any(error in title for error in ['404', 'not found', 'error']):
                        logger.info(f"404 or error page detected: {url}")
                        browser.close()
                        return None
                    
                    html = page.content()
                    browser.close()
                    return html
                    
            except Exception as e:
                logger.error(f"Playwright error for {url} (attempt {attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self._get_random_delay())
                
        logger.error(f"Failed to load {url} after {self.max_retries} attempts")
        return None

    def get_simple_html(self, url: str) -> Optional[str]:
        """Use requests for simpler pages"""
        for attempt in range(self.max_retries):
            try:
                headers = self._get_headers()
                response = self.session.get(url, headers=headers, timeout=30)
                
                if response.status_code == 404:
                    logger.info(f"404 for URL: {url}")
                    return None
                elif response.status_code != 200:
                    logger.warning(f"Status {response.status_code} for {url}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self._get_random_delay())
                        continue
                    return None
                
                return response.text
                
            except Exception as e:
                logger.error(f"Request error for {url} (attempt {attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self._get_random_delay())
                
        return None

    def extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract structured data from JSON-LD"""
        try:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = data[0]
                    
                    if data.get('@type') == 'Recipe' or 'Recipe' in str(data.get('@type', '')):
                        return data
                except (json.JSONDecodeError, AttributeError):
                    continue
        except Exception as e:
            logger.debug(f"Error extracting JSON-LD: {e}")
        return None

    def scrape_recipe(self, url: str) -> Optional[Dict[str, Any]]:
        """Enhanced recipe scraping with fallback strategies"""
        try:
            logger.info(f"Scraping recipe: {url}")
            
            # Try simple request first (faster)
            html = self.get_simple_html(url)
            
            # If that fails or content looks incomplete, use Playwright
            if not html or len(html) < 5000:  # Arbitrary threshold for "complete" page
                html = self.get_rendered_html(url)
            
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try structured data first
            json_ld = self.extract_json_ld(soup)
            if json_ld:
                return self._extract_from_json_ld(json_ld, url)
            
            # Fallback to HTML parsing
            return self._extract_from_html(soup, url)
            
        except Exception as e:
            logger.error(f"Error scraping recipe {url}: {str(e)}", exc_info=True)
            return None

    def _extract_from_json_ld(self, data: Dict, url: str) -> Optional[Dict[str, Any]]:
        """Extract recipe data from JSON-LD structured data"""
        try:
            # Extract basic info
            title = data.get('name', '').strip()
            if not title:
                return None
            
            # Extract ingredients
            ingredients = []
            recipe_ingredients = data.get('recipeIngredient', [])
            if isinstance(recipe_ingredients, list):
                ingredients = [ing.strip() for ing in recipe_ingredients if ing.strip()]
            
            # Extract instructions
            directions = []
            recipe_instructions = data.get('recipeInstructions', [])
            if isinstance(recipe_instructions, list):
                for instruction in recipe_instructions:
                    if isinstance(instruction, dict):
                        text = instruction.get('text', '').strip()
                        if text:
                            directions.append(text)
                    elif isinstance(instruction, str):
                        directions.append(instruction.strip())
            
            # Extract timing
            times = []
            for time_field in ['prepTime', 'cookTime', 'totalTime']:
                time_val = data.get(time_field)
                if time_val:
                    times.append(f"{time_field}: {time_val}")
            ready_in = ' | '.join(times)
            
            # Extract image
            image_url = ''
            image_data = data.get('image', [])
            if isinstance(image_data, list) and image_data:
                image_url = image_data[0] if isinstance(image_data[0], str) else image_data[0].get('url', '')
            elif isinstance(image_data, str):
                image_url = image_data
            elif isinstance(image_data, dict):
                image_url = image_data.get('url', '')
            
            if not ingredients or not directions:
                logger.warning(f"Incomplete data from JSON-LD for {url}: ingredients={len(ingredients)}, directions={len(directions)}")
                return None
            
            logger.info(f"Successfully extracted from JSON-LD: {title}")
            logger.info(f"  Ingredients: {len(ingredients)}, Instructions: {len(directions)}")
            
            return {
                'title': title,
                'instructions': directions,
                'times': ready_in,
                'image_url': image_url,
                'scraped_ingredients_text': ingredients,
                'original_url': url
            }
            
        except Exception as e:
            logger.error(f"Error extracting from JSON-LD: {e}")
            return None

    def _extract_from_html(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Fallback HTML extraction with multiple selector strategies"""
        try:
            # Title extraction with multiple strategies
            title = ''
            title_selectors = [
                'h1[data-testid="recipe-title"]',
                'h1.recipe-title',
                '.recipe-header h1',
                'h1',
                '[data-testid="recipe-name"]'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and not any(x in title.lower() for x in ["404", "not found", "error"]):
                        break
            
            if not title:
                logger.warning(f"No title found for {url}")
                return None
            
            # Image extraction
            image_url = ''
            image_selectors = [
                '.primary-image img',
                '.recipe-image img',
                '[data-testid="recipe-image"] img',
                '.recipe-photo img',
                'img[alt*="recipe"]'
            ]
            
            for selector in image_selectors:
                img_elem = soup.select_one(selector)
                if img_elem:
                    image_url = img_elem.get('src') or img_elem.get('data-src', '')
                    if image_url:
                        if image_url.startswith('/'):
                            image_url = urljoin(url, image_url)
                        break
            
            # Timing extraction
            ready_in = ''
            time_selectors = [
                '.recipe-times',
                '.prep-time, .cook-time, .total-time',
                '[data-testid="recipe-time"]',
                '.facts__value'
            ]
            
            for selector in time_selectors:
                time_elems = soup.select(selector)
                if time_elems:
                    times = [elem.get_text(strip=True) for elem in time_elems]
                    ready_in = ' | '.join(filter(None, times))
                    break
            
            # Ingredients extraction
            ingredients = []
            ingredient_selectors = [
                'ul.ingredient-list li',
                '.recipe-ingredients li',
                '[data-testid="ingredients"] li',
                '.ingredients-section li',
                '.recipe-ingredient'
            ]
            
            for selector in ingredient_selectors:
                ingredient_elems = soup.select(selector)
                if ingredient_elems:
                    for li in ingredient_elems:
                        # Handle quantity + text structure
                        qty = li.select_one('.ingredient-quantity, .quantity')
                        text = li.select_one('.ingredient-text, .text')
                        
                        if qty and text:
                            ingredient_line = f"{qty.get_text(strip=True)} {text.get_text(strip=True)}"
                        else:
                            ingredient_line = li.get_text(strip=True)
                        
                        if ingredient_line:
                            ingredients.append(ingredient_line)
                    
                    if len(ingredients) >= 3:  # Need reasonable number of ingredients
                        break
            
            # Directions extraction
            directions = []
            direction_selectors = [
                'ul.direction-list li',
                'ol.recipe-instructions li',
                '[data-testid="instructions"] li',
                '.directions li',
                '.recipe-instruction'
            ]
            
            for selector in direction_selectors:
                direction_elems = soup.select(selector)
                if direction_elems:
                    for li in direction_elems:
                        direction_text = li.get_text(strip=True)
                        if direction_text and len(direction_text) > 10:
                            directions.append(direction_text)
                    
                    if len(directions) >= 2:  # Need reasonable number of directions
                        break
            
            if not ingredients or not directions:
                logger.warning(f"Incomplete data from HTML for {url}: ingredients={len(ingredients)}, directions={len(directions)}")
                return None
            
            logger.info(f"Successfully extracted from HTML: {title}")
            logger.info(f"  Ingredients: {len(ingredients)}, Instructions: {len(directions)}")
            
            return {
                'title': title,
                'instructions': directions,
                'times': ready_in,
                'image_url': image_url,
                'scraped_ingredients_text': ingredients,
                'original_url': url
            }
            
        except Exception as e:
            logger.error(f"Error extracting from HTML: {e}")
            return None

    def discover_recipe_urls(self, max_urls: int = 1000) -> List[str]:
        """Discover actual recipe URLs instead of guessing IDs"""
        urls = set()
        
        # Try sitemap first
        sitemap_urls = self._get_sitemap_urls()
        urls.update(sitemap_urls[:max_urls//2])
        
        # Try category pages
        category_urls = self._get_category_urls(max_urls - len(urls))
        urls.update(category_urls)
        
        logger.info(f"Discovered {len(urls)} recipe URLs")
        return list(urls)[:max_urls]

    def _get_sitemap_urls(self) -> List[str]:
        """Extract recipe URLs from sitemap"""
        urls = []
        sitemap_base = "https://www.food.com/sitemap"
        
        try:
            # Try common sitemap patterns
            sitemap_urls = [
                f"{sitemap_base}.xml",
                f"{sitemap_base}/recipes.xml",
                f"{sitemap_base}/recipe-sitemap.xml"
            ]
            
            for sitemap_url in sitemap_urls:
                try:
                    response = self.session.get(sitemap_url, headers=self._get_headers(), timeout=30)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'xml')
                        locs = soup.find_all('loc')
                        
                        for loc in locs:
                            url = loc.get_text().strip()
                            if 'recipe' in url and url not in urls:
                                urls.append(url)
                        
                        logger.info(f"Found {len(urls)} URLs from {sitemap_url}")
                        break
                        
                except Exception as e:
                    logger.debug(f"Error fetching sitemap {sitemap_url}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error getting sitemap URLs: {e}")
        
        return urls

    def _get_category_urls(self, max_urls: int) -> List[str]:
        """Extract recipe URLs from category pages"""
        urls = set()
        
        # Common food.com category pages
        category_pages = [
            "https://www.food.com/ideas/most-popular-recipes",
            "https://www.food.com/ideas/easy-recipes",
            "https://www.food.com/ideas/quick-recipes",
            "https://www.food.com/ideas/healthy-recipes",
            "https://www.food.com/ideas/chicken-recipes",
            "https://www.food.com/ideas/beef-recipes",
            "https://www.food.com/ideas/dessert-recipes"
        ]
        
        for page_url in category_pages:
            if len(urls) >= max_urls:
                break
                
            try:
                html = self.get_rendered_html(page_url)
                if not html:
                    continue
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for recipe links
                recipe_links = soup.find_all('a', href=True)
                for link in recipe_links:
                    href = link['href']
                    if 'recipe' in href:
                        if href.startswith('/'):
                            href = urljoin("https://www.food.com", href)
                        
                        if href.startswith('https://www.food.com') and href not in urls:
                            urls.add(href)
                            
                            if len(urls) >= max_urls:
                                break
                
                logger.info(f"Found {len(urls)} URLs from {page_url}")
                time.sleep(self._get_random_delay())
                
            except Exception as e:
                logger.error(f"Error getting category URLs from {page_url}: {e}")
                continue
        
        return list(urls)

    def save_recipe(self, recipe_data: Dict[str, Any]) -> bool:
        """Save recipe to database with error handling"""
        try:
            # Check if recipe already exists
            existing = Recipe.objects.filter(original_url=recipe_data['original_url']).first()
            if existing:
                logger.info(f"Recipe already exists: {recipe_data['title']}")
                return True
            
            Recipe.objects.create(**recipe_data)
            logger.info(f"Saved new recipe: {recipe_data['title']}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving recipe {recipe_data.get('title', 'Unknown')}: {e}")
            return False

def main(max_recipes: int = 1000, use_discovery: bool = True, start_id: int = None, end_id: int = None):
    """Main scraping function with improved strategy"""
    scraper = FoodComScraper()
    
    if use_discovery:
        # Use URL discovery instead of ID guessing
        logger.info("Using URL discovery method...")
        urls = scraper.discover_recipe_urls(max_recipes)
    else:
        # Fallback to ID-based approach if discovery fails
        logger.info("Using ID-based approach...")
        if not start_id:
            start_id = 1
        if not end_id:
            end_id = start_id + max_recipes
        
        urls = []
        for recipe_id in range(start_id, end_id + 1):
            if recipe_id not in scraper.existing_ids:
                urls.append(f'https://www.food.com/recipe/recipe-{recipe_id}')
    
    logger.info(f'Starting to scrape {len(urls)} recipes...')
    
    successful = 0
    failed = 0
    
    for i, url in enumerate(urls, 1):
        logger.info(f'Processing recipe {i}/{len(urls)}: {url}')
        
        data = scraper.scrape_recipe(url)
        if data and scraper.save_recipe(data):
            successful += 1
        else:
            failed += 1
        
        # Progress logging
        if i % 50 == 0:
            logger.info(f'Progress: {i}/{len(urls)} processed, {successful} successful, {failed} failed')
        
        # Be polite with delays
        time.sleep(scraper._get_random_delay())
    
    logger.info(f'Scraping completed! {successful} successful, {failed} failed')
    logger.info(f'Total Food.com recipes in database: {Recipe.objects.filter(original_url__icontains="food.com").count()}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape Food.com recipes with enhanced strategies.')
    parser.add_argument('--max-recipes', type=int, default=1000, help='Maximum number of recipes to scrape')
    parser.add_argument('--use-discovery', action='store_true', default=True, help='Use URL discovery instead of ID guessing')
    parser.add_argument('--start-id', type=int, help='Starting recipe ID (for ID-based approach)')
    parser.add_argument('--end-id', type=int, help='Ending recipe ID (for ID-based approach)')
    
    args = parser.parse_args()
    main(
        max_recipes=args.max_recipes,
        use_discovery=args.use_discovery,
        start_id=args.start_id,
        end_id=args.end_id
    ) 