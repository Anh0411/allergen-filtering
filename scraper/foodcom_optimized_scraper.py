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
from dataclasses import dataclass
from enum import Enum

# Setup logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('foodcom_optimized_scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from recipes.models import Recipe

class ScrapingStrategy(Enum):
    """Enum for different scraping strategies"""
    SIMPLE_REQUEST = "simple_request"
    PLAYWRIGHT = "playwright"
    DUAL = "dual"

@dataclass
class ScrapingConfig:
    """Configuration for scraping behavior"""
    max_retries: int = 3
    delay_range: tuple = (2, 5)
    timeout: int = 30
    max_workers: int = 3
    strategy: ScrapingStrategy = ScrapingStrategy.DUAL
    min_html_size: int = 5000
    enable_duplicate_check: bool = True

class HTMLFetcher:
    """Handles HTML fetching with multiple strategies"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.session = requests.Session()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

    def _get_random_delay(self) -> float:
        """Get random delay between requests"""
        return random.uniform(*self.config.delay_range)

    def _get_headers(self) -> Dict[str, str]:
        """Get rotating headers"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def fetch_simple(self, url: str) -> Optional[str]:
        """Fetch HTML using simple requests"""
        for attempt in range(self.config.max_retries):
            try:
                headers = self._get_headers()
                response = self.session.get(url, headers=headers, timeout=self.config.timeout)
                
                if response.status_code == 404:
                    logger.info(f"404 for URL: {url}")
                    return None
                elif response.status_code != 200:
                    logger.warning(f"Status {response.status_code} for {url}")
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self._get_random_delay())
                        continue
                    return None
                
                return response.text
                
            except Exception as e:
                logger.error(f"Request error for {url} (attempt {attempt+1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self._get_random_delay())
                
        return None

    def fetch_with_playwright(self, url: str) -> Optional[str]:
        """Fetch HTML using Playwright for JavaScript-heavy pages"""
        for attempt in range(self.config.max_retries):
            try:
                logger.info(f"Loading with Playwright: {url} (attempt {attempt+1}/{self.config.max_retries})")
                
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
                logger.error(f"Playwright error for {url} (attempt {attempt+1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self._get_random_delay())
                
        logger.error(f"Failed to load {url} after {self.config.max_retries} attempts")
        return None

    def fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML using the configured strategy"""
        if self.config.strategy == ScrapingStrategy.SIMPLE_REQUEST:
            return self.fetch_simple(url)
        elif self.config.strategy == ScrapingStrategy.PLAYWRIGHT:
            return self.fetch_with_playwright(url)
        elif self.config.strategy == ScrapingStrategy.DUAL:
            # Try simple request first (faster)
            html = self.fetch_simple(url)
            
            # If that fails or content looks incomplete, use Playwright
            if not html or len(html) < self.config.min_html_size:
                html = self.fetch_with_playwright(url)
            
            return html
        else:
            raise ValueError(f"Unknown scraping strategy: {self.config.strategy}")

class RecipeDataExtractor:
    """Handles extraction of recipe data from HTML"""
    
    @staticmethod
    def extract_json_ld(soup: BeautifulSoup) -> Optional[Dict]:
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

    @staticmethod
    def extract_from_json_ld(data: Dict, url: str) -> Optional[Dict[str, Any]]:
        """Extract recipe data from JSON-LD structured data"""
        try:
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
                logger.warning(f"Incomplete JSON-LD data for {url}: ingredients={len(ingredients)}, directions={len(directions)}")
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

    @staticmethod
    def extract_from_html(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Extract recipe data from HTML with improved selectors"""
        try:
            # Try multiple title selectors
            title = ''
            title_selectors = [
                'h1.recipe-title',
                'h1[class*="title"]',
                'h1.entry-title', 
                '.recipe-header h1',
                'h1',
                '.recipe-title',
                '[data-module="RecipeTitle"] h1'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title:
                logger.warning(f"No title found for {url}")
                return None
            
            # Extract ingredients with multiple strategies
            ingredients = []
            ingredient_selectors = [
                '.recipe-ingredients li',
                '.ingredients li',
                '[class*="ingredient"] li',
                '.recipe-ingredient',
                '[data-module="RecipeIngredients"] li'
            ]
            
            for selector in ingredient_selectors:
                ingredient_elems = soup.select(selector)
                if ingredient_elems:
                    ingredients = [elem.get_text(strip=True) for elem in ingredient_elems if elem.get_text(strip=True)]
                    break
            
            # Extract instructions
            directions = []
            direction_selectors = [
                '.recipe-instructions li',
                '.instructions li',
                '.recipe-directions li',
                '.directions li',
                '[class*="instruction"] li',
                '[data-module="RecipeInstructions"] li'
            ]
            
            for selector in direction_selectors:
                direction_elems = soup.select(selector)
                if direction_elems:
                    directions = [elem.get_text(strip=True) for elem in direction_elems if elem.get_text(strip=True)]
                    break
            
            if not ingredients or not directions:
                logger.warning(f"Incomplete HTML data for {url}: ingredients={len(ingredients)}, directions={len(directions)}")
                return None
            
            logger.info(f"Successfully extracted from HTML: {title}")
            logger.info(f"  Ingredients: {len(ingredients)}, Instructions: {len(directions)}")
            
            return {
                'title': title,
                'instructions': directions,
                'times': '',
                'image_url': '',
                'scraped_ingredients_text': ingredients,
                'original_url': url
            }
            
        except Exception as e:
            logger.error(f"Error extracting from HTML: {e}")
            return None

class URLDiscovery:
    """Handles discovery of recipe URLs from various sources"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.base_url = "https://www.food.com/recipe"
        self.existing_urls = self._load_existing_urls() if config.enable_duplicate_check else set()

    def _load_existing_urls(self) -> set:
        """Load existing recipe URLs from database"""
        return set(Recipe.objects.filter(original_url__icontains='food.com').values_list('original_url', flat=True))

    def get_recipe_urls_from_page(self, page_num: int, html_fetcher: HTMLFetcher) -> List[str]:
        """Extract recipe URLs from a specific page number"""
        page_url = f"{self.base_url}?pn={page_num}"
        
        logger.info(f"Fetching recipe URLs from page {page_num}: {page_url}")
        
        html = html_fetcher.fetch_html(page_url)
        if not html:
            logger.error(f"Failed to load page {page_num}")
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        recipe_urls = []
        
        # Multiple selectors with specific URL validation
        selectors = [
            'a[href*="/recipe/"]',  # General recipe links
            '.recipe-card a[href]',  # Recipe cards
            '.recipe-item a[href]',  # Recipe items  
            '.recipe-title a[href]', # Recipe titles
            'article a[href*="/recipe/"]',  # Articles with recipe links
            '.grid-item a[href*="/recipe/"]',  # Grid items
            '.card a[href*="/recipe/"]',  # Card layouts
            '.item a[href*="/recipe/"]',  # Generic items
            'h3 a[href*="/recipe/"]',  # Title links
            'h2 a[href*="/recipe/"]',  # Main title links
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    # Handle relative URLs
                    if href.startswith('/'):
                        href = urljoin("https://www.food.com", href)
                    
                    # Specific filtering for actual recipe URLs
                    if (('food.com' in href or href.startswith('/recipe/')) and 
                        '/recipe/' in href and 
                        href not in self.existing_urls and
                        href not in recipe_urls and
                        not any(exclude in href for exclude in [
                            '#', 'javascript:', 'mailto:', 
                            '/recipe/all/', '/recipe/search', '/recipe?',
                            '/recipe/category/', '/recipe/collection/'
                        ])):
                        
                        # Additional validation: must look like individual recipe URL
                        if (not any(category in href.lower() for category in [
                            'popular', 'trending', 'newest', 'editor-pick',
                            'quick-and-easy', 'healthy', '?ref=nav'
                        ]) and 
                        (re.search(r'/recipe/[a-zA-Z0-9\-]+-\d+/?$', href) or  # recipe-name-123
                         re.search(r'/recipe/\d+/?$', href))):  # /recipe/123
                            
                            # Clean up the URL
                            if href.startswith('/recipe/'):
                                href = f"https://www.food.com{href}"
                            
                            recipe_urls.append(href)
        
        # Remove duplicates while preserving order
        unique_urls = []
        seen = set()
        for url in recipe_urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)
        
        logger.info(f"Found {len(unique_urls)} recipe URLs on page {page_num}")
        if len(unique_urls) > 0:
            logger.info(f"Sample URLs: {unique_urls[:3]}")
        return unique_urls

class DatabaseManager:
    """Handles database operations for recipes"""
    
    @staticmethod
    def save_recipe(recipe_data: Dict[str, Any]) -> bool:
        """Save recipe to database"""
        try:
            recipe, created = Recipe.objects.get_or_create(
                original_url=recipe_data['original_url'],
                defaults={
                    'title': recipe_data['title'],
                    'times': recipe_data.get('times', ''),
                    'image_url': recipe_data.get('image_url', ''),
                    'scraped_ingredients_text': recipe_data['scraped_ingredients_text'],
                    'instructions': recipe_data['instructions']
                }
            )
            
            if created:
                logger.info(f"Saved new recipe: {recipe_data['title']}")
            else:
                logger.info(f"Recipe already exists: {recipe_data['title']}")
                # Update existing recipe
                recipe.title = recipe_data['title']
                recipe.times = recipe_data.get('times', '')
                recipe.image_url = recipe_data.get('image_url', '')
                recipe.scraped_ingredients_text = recipe_data['scraped_ingredients_text']
                recipe.instructions = recipe_data['instructions']
                recipe.save()
                logger.info(f"Updated existing recipe: {recipe_data['title']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving recipe: {e}")
            return False

    @staticmethod
    def check_recipe_exists(url: str) -> bool:
        """Check if recipe already exists in database"""
        return Recipe.objects.filter(original_url=url).exists()

class FoodComOptimizedScraper:
    """Main scraper class with all optimizations and threading support"""
    
    def __init__(self, config: ScrapingConfig = None):
        self.config = config or ScrapingConfig()
        self.html_fetcher = HTMLFetcher(self.config)
        self.url_discovery = URLDiscovery(self.config)
        self.data_extractor = RecipeDataExtractor()
        self.db_manager = DatabaseManager()

    def scrape_recipe(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single recipe with comprehensive error handling"""
        try:
            logger.info(f"Scraping recipe: {url}")
            
            # Check if recipe already exists
            if self.config.enable_duplicate_check and self.db_manager.check_recipe_exists(url):
                logger.info(f"Recipe already exists: {url}")
                return None
            
            # Fetch HTML
            html = self.html_fetcher.fetch_html(url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try structured data first
            json_ld = self.data_extractor.extract_json_ld(soup)
            if json_ld:
                recipe_data = self.data_extractor.extract_from_json_ld(json_ld, url)
                if recipe_data:
                    return recipe_data
            
            # Fallback to HTML parsing
            return self.data_extractor.extract_from_html(soup, url)
            
        except Exception as e:
            logger.error(f"Error scraping recipe {url}: {str(e)}", exc_info=True)
            return None

    def _scrape_and_save(self, url: str) -> bool:
        """Helper method to scrape and save a single recipe"""
        try:
            recipe_data = self.scrape_recipe(url)
            if recipe_data:
                return self.db_manager.save_recipe(recipe_data)
            return False
        except Exception as e:
            logger.error(f"Error in _scrape_and_save for {url}: {e}")
            return False

    def scrape_page_range(self, start_page: int, end_page: int) -> tuple[int, int]:
        """Scrape recipes from a range of pages with threading"""
        all_urls = []
        
        # Collect all URLs first
        for page_num in range(start_page, end_page + 1):
            logger.info(f"Collecting URLs from page {page_num}")
            urls = self.url_discovery.get_recipe_urls_from_page(page_num, self.html_fetcher)
            all_urls.extend(urls)
            
            # Add delay between pages
            time.sleep(self.html_fetcher._get_random_delay())
        
        logger.info(f"Collected {len(all_urls)} total URLs to process")
        
        # Process URLs with threading
        successful_scrapes = 0
        failed_scrapes = 0
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all scraping tasks
            future_to_url = {executor.submit(self._scrape_and_save, url): url for url in all_urls}
            
            # Process completed tasks
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    success = future.result()
                    if success:
                        successful_scrapes += 1
                    else:
                        failed_scrapes += 1
                except Exception as e:
                    logger.error(f"Exception occurred while processing {url}: {e}")
                    failed_scrapes += 1
                
                # Add delay between requests
                time.sleep(self.html_fetcher._get_random_delay())
        
        logger.info(f"Scraping completed: {successful_scrapes} successful, {failed_scrapes} failed")
        return successful_scrapes, failed_scrapes

    def scrape_single_recipe(self, url: str) -> bool:
        """Scrape and save a single recipe"""
        return self._scrape_and_save(url)

def main(start_page: int = 1, end_page: int = 10, max_workers: int = 3, 
         strategy: str = "dual", enable_duplicate_check: bool = True):
    """Main function to run the optimized scraper"""
    
    # Create configuration
    config = ScrapingConfig(
        max_workers=max_workers,
        strategy=ScrapingStrategy(strategy),
        enable_duplicate_check=enable_duplicate_check
    )
    
    scraper = FoodComOptimizedScraper(config)
    
    logger.info(f"Starting Food.com optimized scraping from pages {start_page} to {end_page}")
    logger.info(f"Strategy: {config.strategy.value}, Workers: {config.max_workers}")
    
    successful, failed = scraper.scrape_page_range(start_page, end_page)
    
    logger.info(f"Scraping completed! {successful} successful, {failed} failed")
    
    # Final count
    total_count = Recipe.objects.filter(original_url__icontains='food.com').count()
    logger.info(f"Total Food.com recipes in database: {total_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Optimized Food.com recipe scraper with threading')
    parser.add_argument('--start-page', type=int, default=1, help='Starting page number')
    parser.add_argument('--end-page', type=int, default=10, help='Ending page number')
    parser.add_argument('--max-workers', type=int, default=3, help='Maximum number of worker threads')
    parser.add_argument('--strategy', choices=['simple', 'playwright', 'dual'], 
                       default='dual', help='Scraping strategy')
    parser.add_argument('--no-duplicate-check', action='store_true', 
                       help='Disable duplicate checking')
    
    args = parser.parse_args()
    main(args.start_page, args.end_page, args.max_workers, 
         args.strategy, not args.no_duplicate_check) 