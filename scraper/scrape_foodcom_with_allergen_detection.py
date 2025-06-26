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
from urllib.parse import urljoin, urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from typing import Optional, List, Dict, Any
import traceback

# Setup logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('foodcom_allergen_scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from recipes.models import Recipe, AllergenAnalysisResult
from allergen_filtering.nlp_processor import get_nlp_processor

class FoodComAllergenScraper:
    def __init__(self, max_retries: int = 3, delay_range: tuple = (2, 5)):
        self.base_url = "https://www.food.com/recipe"
        self.session = requests.Session()
        self.max_retries = max_retries
        self.delay_range = delay_range
        
        # Load existing recipe URLs to avoid duplicates
        self.existing_urls = self._load_existing_urls()
        logger.info(f"Loaded {len(self.existing_urls)} existing recipe URLs for duplicate detection")
        
        # Initialize NLP processor for allergen detection
        try:
            self.nlp_processor = get_nlp_processor()
            logger.info("NLP processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize NLP processor: {e}")
            self.nlp_processor = None
        
        # User agent rotation
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

    def _load_existing_urls(self) -> set:
        """Load existing recipe URLs from database"""
        return set(Recipe.objects.filter(original_url__icontains='food.com').values_list('original_url', flat=True))

    def _get_random_delay(self) -> float:
        """Get random delay between requests"""
        return random.uniform(*self.delay_range)

    def _get_headers(self) -> Dict[str, str]:
        """Get rotating headers"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def get_rendered_html(self, url: str) -> Optional[str]:
        """Get HTML content using Playwright with improved timeout handling"""
        for attempt in range(self.max_retries):
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent=random.choice(self.user_agents),
                        viewport={'width': 1920, 'height': 1080}
                    )
                    page = context.new_page()
                    
                    # Navigate to page with longer timeout
                    page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    
                    # IMPROVED: Try multiple selector strategies with shorter individual timeouts
                    content_loaded = False
                    
                    # Strategy 1: Wait for any content indicators (shorter timeout)
                    try:
                        page.wait_for_selector('body', timeout=5000)
                        content_loaded = True
                    except:
                        logger.debug(f"Body selector timeout for {url}")
                    
                    # Strategy 2: Try specific Food.com elements
                    if not content_loaded:
                        try:
                            page.wait_for_selector('div, article, main, section', timeout=8000)
                            content_loaded = True
                        except:
                            logger.debug(f"Content div timeout for {url}")
                    
                    # Strategy 3: Wait for network to be mostly idle (shorter timeout)
                    try:
                        page.wait_for_load_state('networkidle', timeout=8000)
                    except:
                        logger.debug(f"Network idle timeout for {url} - continuing anyway")
                    
                    # Give page extra time to render JavaScript content
                    time.sleep(2)
                    
                    html = page.content()
                    browser.close()
                    
                    # Validate we got meaningful content
                    if len(html) > 5000:  # Reasonable size check
                        return html
                    else:
                        logger.warning(f"Got small HTML response for {url}: {len(html)} chars")
                        if attempt < self.max_retries - 1:
                            continue
                    
                    return html
                    
            except Exception as e:
                logger.warning(f"Playwright error for {url} (attempt {attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self._get_random_delay())
                
        logger.error(f"Failed to load {url} after {self.max_retries} attempts")
        return None

    def get_recipe_urls_from_page(self, page_num: int) -> List[str]:
        """Extract recipe URLs from a specific page number with improved parsing"""
        page_url = f"{self.base_url}?pn={page_num}"
        
        logger.info(f"Fetching recipe URLs from page {page_num}: {page_url}")
        
        html = self.get_rendered_html(page_url)
        if not html:
            logger.error(f"Failed to load page {page_num}")
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        recipe_urls = []
        
        # IMPROVED: Multiple selectors but with specific URL validation
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
                    
                    # SPECIFIC filtering for actual recipe URLs
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
                        # Food.com recipes have format: /recipe/recipe-name-12345
                        import re
                        # More flexible regex that matches actual Food.com patterns
                        # Exclude obvious category pages but allow recipe pages
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
        seen = set()
        unique_urls = []
        for url in recipe_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        logger.info(f"Found {len(unique_urls)} unique recipe URLs on page {page_num}")
        return unique_urls

    def extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract JSON-LD structured data from page"""
        try:
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Recipe':
                        return data
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                return item
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting JSON-LD: {e}")
        return None

    def scrape_recipe(self, url: str) -> Optional[Dict[str, Any]]:
        """Enhanced recipe scraping with allergen detection"""
        try:
            logger.info(f"Scraping recipe: {url}")
            
            # Check if recipe already exists
            if Recipe.objects.filter(original_url=url).exists():
                logger.info(f"Recipe already exists: {url}")
                return None
            
            html = self.get_rendered_html(url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try structured data first
            json_ld = self.extract_json_ld(soup)
            if json_ld:
                recipe_data = self._extract_from_json_ld(json_ld, url)
                if recipe_data:
                    return recipe_data
            
            # Fallback to HTML parsing
            return self._extract_from_html(soup, url)
            
        except Exception as e:
            logger.error(f"Error scraping recipe {url}: {str(e)}", exc_info=True)
            return None

    def _extract_from_json_ld(self, data: Dict, url: str) -> Optional[Dict[str, Any]]:
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

    def _extract_from_html(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
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

    def analyze_allergens(self, recipe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze allergens in the recipe using NLP processor"""
        if not self.nlp_processor:
            logger.warning("NLP processor not available, skipping allergen analysis")
            return None
        
        try:
            # Combine ingredients and instructions for analysis
            analysis_text = f"""
            Ingredients: {', '.join(recipe_data['scraped_ingredients_text'])}
            
            Instructions: {' '.join(recipe_data['instructions'])}
            """
            
            # Perform allergen analysis
            start_time = time.time()
            analysis = self.nlp_processor.analyze_allergens(analysis_text)
            processing_time = time.time() - start_time
            
            # Extract ingredients for detailed analysis
            extracted_ingredients = self.nlp_processor.extract_ingredients(analysis_text)
            
            logger.info(f"Allergen analysis completed for {recipe_data['title']}")
            logger.info(f"  Risk Level: {analysis.risk_level}")
            logger.info(f"  Detected Allergens: {list(analysis.detected_allergens.keys())}")
            logger.info(f"  Processing Time: {processing_time:.2f}s")
            
            return {
                'risk_level': analysis.risk_level,
                'confidence_scores': analysis.confidence_scores,
                'detected_allergens': {
                    category: [match.text for match in matches] 
                    for category, matches in analysis.detected_allergens.items()
                },
                'recommendations': analysis.recommendations,
                'total_ingredients': len(extracted_ingredients),
                'analyzed_ingredients': len(extracted_ingredients),
                'processing_time': processing_time,
                'raw_matches': analysis.raw_matches
            }
            
        except Exception as e:
            logger.error(f"Error in allergen analysis for {recipe_data['title']}: {e}")
            logger.error(traceback.format_exc())
            return None

    def save_recipe_with_allergens(self, recipe_data: Dict[str, Any], allergen_analysis: Optional[Dict[str, Any]] = None) -> bool:
        """Save recipe to database with allergen analysis"""
        try:
            # Save the recipe
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
            
            # Save allergen analysis if available
            if allergen_analysis:
                # Update recipe with allergen information
                recipe.risk_level = allergen_analysis['risk_level']
                recipe.nlp_confidence_score = max(allergen_analysis['confidence_scores'].values()) if allergen_analysis['confidence_scores'] else 0.0
                recipe.nlp_analysis_date = django.utils.timezone.now()
                recipe.last_analyzed = django.utils.timezone.now()
                recipe.save()
                
                # Save detailed analysis result
                analysis_result, created = AllergenAnalysisResult.objects.get_or_create(
                    recipe=recipe,
                    defaults={
                        'risk_level': allergen_analysis['risk_level'],
                        'confidence_scores': allergen_analysis['confidence_scores'],
                        'detected_allergens': allergen_analysis['detected_allergens'],
                        'recommendations': allergen_analysis['recommendations'],
                        'total_ingredients': allergen_analysis['total_ingredients'],
                        'analyzed_ingredients': allergen_analysis['analyzed_ingredients'],
                        'processing_time': allergen_analysis['processing_time']
                    }
                )
                
                if not created:
                    # Update existing analysis
                    analysis_result.risk_level = allergen_analysis['risk_level']
                    analysis_result.confidence_scores = allergen_analysis['confidence_scores']
                    analysis_result.detected_allergens = allergen_analysis['detected_allergens']
                    analysis_result.recommendations = allergen_analysis['recommendations']
                    analysis_result.total_ingredients = allergen_analysis['total_ingredients']
                    analysis_result.analyzed_ingredients = allergen_analysis['analyzed_ingredients']
                    analysis_result.processing_time = allergen_analysis['processing_time']
                    analysis_result.save()
                
                logger.info(f"Saved allergen analysis for {recipe_data['title']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving recipe {recipe_data['title']}: {e}")
            logger.error(traceback.format_exc())
            return False

    def scrape_recipe_with_allergens(self, url: str) -> bool:
        """Scrape recipe and perform allergen analysis in one step"""
        try:
            # Scrape the recipe
            recipe_data = self.scrape_recipe(url)
            if not recipe_data:
                return False
            
            # Perform allergen analysis
            allergen_analysis = self.analyze_allergens(recipe_data)
            
            # Save recipe with allergen analysis
            success = self.save_recipe_with_allergens(recipe_data, allergen_analysis)
            
            if success:
                logger.info(f"Successfully processed recipe with allergens: {recipe_data['title']}")
            else:
                logger.error(f"Failed to save recipe: {recipe_data['title']}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in scrape_recipe_with_allergens for {url}: {e}")
            logger.error(traceback.format_exc())
            return False

    def scrape_page_range(self, start_page: int, end_page: int, max_workers: int = 3):
        """Scrape recipes from a range of pages with allergen detection"""
        all_urls = []
        
        # Collect all URLs first
        for page_num in range(start_page, end_page + 1):
            logger.info(f"Collecting URLs from page {page_num}")
            urls = self.get_recipe_urls_from_page(page_num)
            all_urls.extend(urls)
            
            # Add delay between pages
            time.sleep(self._get_random_delay())
        
        logger.info(f"Collected {len(all_urls)} total URLs to process")
        
        # Process URLs with threading
        successful_scrapes = 0
        failed_scrapes = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all scraping tasks
            future_to_url = {executor.submit(self.scrape_recipe_with_allergens, url): url for url in all_urls}
            
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
                time.sleep(self._get_random_delay())
        
        logger.info(f"Scraping completed: {successful_scrapes} successful, {failed_scrapes} failed")
        return successful_scrapes, failed_scrapes


def main(start_page: int = 1, end_page: int = 10, max_workers: int = 3):
    """Main function to run the scraper with allergen detection"""
    logger.info(f"Starting Food.com scraper with allergen detection")
    logger.info(f"Page range: {start_page} to {end_page}")
    logger.info(f"Max workers: {max_workers}")
    
    scraper = FoodComAllergenScraper()
    
    try:
        successful, failed = scraper.scrape_page_range(start_page, end_page, max_workers)
        
        logger.info("=" * 50)
        logger.info("SCRAPING SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Successful scrapes: {successful}")
        logger.info(f"Failed scrapes: {failed}")
        logger.info(f"Total processed: {successful + failed}")
        logger.info(f"Success rate: {(successful / (successful + failed) * 100):.1f}%" if (successful + failed) > 0 else "N/A")
        
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error during scraping: {e}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape Food.com recipes with allergen detection')
    parser.add_argument('--start-page', type=int, default=1, help='Starting page number')
    parser.add_argument('--end-page', type=int, default=10, help='Ending page number')
    parser.add_argument('--max-workers', type=int, default=3, help='Maximum number of concurrent workers')
    
    args = parser.parse_args()
    
    main(args.start_page, args.end_page, args.max_workers) 