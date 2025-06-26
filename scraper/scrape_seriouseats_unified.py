#!/usr/bin/env python3
"""
UNIFIED Serious Eats Recipe Scraper
Combines the best features from all previous scrapers:
- Comprehensive URL discovery from multiple sources
- Fixed CSS selectors that actually work with Serious Eats
- Performance optimizations (short timeouts, validated URLs)
- Enhanced navigation pages and sitemap exploration
- Proper error handling and logging
"""

import os
import sys
import django
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import re
import random
from urllib.parse import urlparse, urljoin
import argparse
import requests
from xml.etree import ElementTree

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from recipes.models import Recipe

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping_seriouseats_unified.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_rendered_html_fast(url, timeout=8000):
    """Fast HTML rendering with optimized timeout"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = context.new_page()
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            
            # Quick check for basic content
            try:
                page.wait_for_selector("body", timeout=2000)
            except:
                pass  # Continue anyway
            
            html = page.content()
            context.close()
            browser.close()
            return html
    except Exception as e:
        logger.error(f"Error loading {url}: {e}")
        return None

def is_valid_recipe_url(url):
    """Comprehensive recipe URL validation"""
    if not url or not isinstance(url, str):
        return False
    
    # Must be Serious Eats
    if not url.startswith('https://www.seriouseats.com/'):
        return False
    
    # Recipe URLs typically have these patterns
    recipe_patterns = [
        r'-recipe-\d{8,}$',  # Most common: ends with -recipe-XXXXXXXX
        r'-\d{8,}$',         # Sometimes just ends with numbers
        r'-recipe$'          # Some end with just -recipe
    ]
    
    if not any(re.search(pattern, url) for pattern in recipe_patterns):
        return False
    
    # Skip non-recipe pages
    skip_patterns = [
        '/about', '/contact', '/privacy', '/terms', '/newsletter',
        '/author/', '/tag/', '/category/', '/page/', '?page=', 
        '#', '.jpg', '.png', '.pdf', '.css', '.js',
        '/equipment/', '/how-to/', '/techniques/', '/features/',
        'seriously-good-gear', 'taste-tests', 'recipes-5117',
        '/food-lab/', '/drinks/', '/the-food-lab'
    ]
    
    return not any(pattern in url for pattern in skip_patterns)

def extract_recipe_links_from_html(html, base_url):
    """Extract recipe links from HTML using multiple strategies"""
    if not html:
        return set()
    
    soup = BeautifulSoup(html, 'html.parser')
    recipe_links = set()
    
    # Multiple selector strategies
    selectors = [
        'a[href*="-recipe-"]',  # Most specific
        'a[href*="recipe"]',
        'article a',
        '.recipe-card a',
        'h2 a',
        'h3 a',
        '.entry-title a',
        '.post-title a'
    ]
    
    for selector in selectors:
        try:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                if href:
                    # Make absolute URL
                    if href.startswith('/'):
                        href = urljoin(base_url, href)
                    elif not href.startswith('http'):
                        continue
                    
                    if is_valid_recipe_url(href):
                        recipe_links.add(href)
        except Exception as e:
            continue
    
    return recipe_links

def get_recipe_links_comprehensive(max_recipes=1000):
    """Comprehensive recipe link collection from multiple sources"""
    all_links = set()
    base_url = "https://www.seriouseats.com"
    
    # MAIN NAVIGATION PAGES (verified working)
    main_pages = [
        "https://www.seriouseats.com/all-recipes-5117985",
        "https://www.seriouseats.com/recipes-by-course-5117906",
        "https://www.seriouseats.com/recipes-by-ingredient-recipes-5117749",
        "https://www.seriouseats.com/recipes-by-world-cuisine-5117277",
        "https://www.seriouseats.com/recipes-by-method-5117399",
        "https://www.seriouseats.com/recipes-by-diet-5117779",
        "https://www.seriouseats.com/holiday-season-recipes-5117984"
    ]
    
    # CATEGORY PAGES (enhanced navigation)
    category_pages = [
        "https://www.seriouseats.com/desserts-5117579",
        "https://www.seriouseats.com/appetizers-5117578", 
        "https://www.seriouseats.com/drinks-5117580",
        "https://www.seriouseats.com/breakfast-5117583",
        "https://www.seriouseats.com/lunch-5117582",
        "https://www.seriouseats.com/dinner-5117581",
        "https://www.seriouseats.com/salads-5117584",
        "https://www.seriouseats.com/soups-5117585",
        "https://www.seriouseats.com/pasta-noodles-5117586",
        "https://www.seriouseats.com/chicken-5117587",
        "https://www.seriouseats.com/beef-5117588",
        "https://www.seriouseats.com/pork-5117589",
        "https://www.seriouseats.com/fish-seafood-5117590",
        "https://www.seriouseats.com/vegetarian-5117591",
        "https://www.seriouseats.com/baking-5117592",
        "https://www.seriouseats.com/grilling-5117593",
        "https://www.seriouseats.com/italian-5117594",
        "https://www.seriouseats.com/asian-5117595",
        "https://www.seriouseats.com/mexican-5117596",
        "https://www.seriouseats.com/american-5117597",
        "https://www.seriouseats.com/pizza-5117601",
        "https://www.seriouseats.com/burgers-5117602",
        "https://www.seriouseats.com/ice-cream-5117603"
    ]
    
    all_pages = main_pages + category_pages
    
    logger.info(f"Starting comprehensive link collection from {len(all_pages)} page categories")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        page = context.new_page()
        
        # Process all page categories with pagination
        for page_url in all_pages:
            if len(all_links) >= max_recipes:
                break
                
            logger.info(f"Processing page category: {page_url}")
            
            # Try up to 50 pages per category for main pages, 20 for others
            max_pages = 50 if page_url in main_pages else 20
            
            for page_num in range(1, max_pages + 1):
                if len(all_links) >= max_recipes:
                    break
                
                if page_num == 1:
                    current_url = page_url
                else:
                    current_url = f"{page_url}?page={page_num}"
                
                try:
                    page.goto(current_url, timeout=5000, wait_until="domcontentloaded")
                    
                    # Quick wait for content
                    try:
                        page.wait_for_selector("body", timeout=2000)
                    except:
                        pass
                    
                    html = page.content()
                    new_links = extract_recipe_links_from_html(html, base_url)
                    
                    if new_links:
                        before_count = len(all_links)
                        all_links.update(new_links)
                        added_count = len(all_links) - before_count
                        logger.info(f"Page {page_num}: Found {len(new_links)} links, added {added_count} new (total: {len(all_links)})")
                    else:
                        logger.info(f"No new links found on page {page_num}, stopping pagination")
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing {current_url}: {e}")
                    continue
                
                time.sleep(0.5)  # Brief delay
        
        browser.close()
    
    # SITEMAP EXPLORATION (if still need more recipes)
    if len(all_links) < max_recipes:
        logger.info(f"Still need more recipes ({len(all_links)}/{max_recipes}), trying sitemap...")
        sitemap_links = get_links_from_sitemap()
        all_links.update(sitemap_links)
        logger.info(f"Added {len(sitemap_links)} links from sitemap (total: {len(all_links)})")
    
    logger.info(f"Comprehensive collection complete! Found {len(all_links)} total recipe links")
    return list(all_links)

def get_links_from_sitemap():
    """Extract recipe links from Serious Eats sitemap"""
    sitemap_links = set()
    
    sitemap_urls = [
        "https://www.seriouseats.com/sitemap.xml",
        "https://www.seriouseats.com/sitemap-recipes.xml",
        "https://www.seriouseats.com/sitemap-posts.xml"
    ]
    
    for sitemap_url in sitemap_urls:
        try:
            logger.info(f"Checking sitemap: {sitemap_url}")
            response = requests.get(sitemap_url, timeout=10)
            
            if response.status_code == 200:
                # Parse XML sitemap
                root = ElementTree.fromstring(response.content)
                
                # Handle different sitemap formats
                for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                    loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                    if loc_elem is not None:
                        url = loc_elem.text
                        if is_valid_recipe_url(url):
                            sitemap_links.add(url)
                
                logger.info(f"Found {len(sitemap_links)} recipe links in {sitemap_url}")
                
        except Exception as e:
            logger.warning(f"Could not process sitemap {sitemap_url}: {e}")
            continue
    
    return sitemap_links

def scrape_recipe_unified(url):
    """Unified recipe scraping with all the best selectors"""
    try:
        logger.info(f"Scraping recipe: {url}")
        
        html = get_rendered_html_fast(url)
        if not html:
            logger.warning(f"Failed to load {url}")
            return None
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # TITLE EXTRACTION (multiple selectors)
        title = None
        title_selectors = [
            'h1.entry-title',
            'h1.recipe-title', 
            'h1[class*="title"]',
            '.recipe-header h1',
            'article h1',
            'h1',
            '.recipe-summary h1',
            '.structured-recipe__header h1'
        ]
        
        for selector in title_selectors:
            try:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    if title:
                        break
            except:
                continue
        
        if not title:
            logger.warning(f"Could not find title for {url}")
            return None
        
        # INGREDIENTS EXTRACTION (Serious Eats specific + fallbacks)
        ingredients = []
        ingredient_selectors = [
            # Serious Eats specific selectors (found in debug)
            '.structured-ingredients__list li',
            'ul.structured-ingredients__list li',
            # Original selectors
            '.recipe-ingredients li',
            '.ingredients li',
            '[class*="ingredient"] li',
            '.structured-ingredients li',
            '.recipe-ingredient',
            '.structured-recipe__ingredients li',
            '.recipe-ingredients__item',
            '.ingredient-list li',
            '.recipe-card-ingredients li',
            'ul[class*="ingredient"] li',
            '.recipe-ingredients p'
        ]
        
        for selector in ingredient_selectors:
            try:
                ingredient_elems = soup.select(selector)
                for elem in ingredient_elems:
                    text = elem.get_text().strip()
                    if text and len(text) > 2:
                        ingredients.append(text)
                if ingredients:
                    break
            except:
                continue
        
        if not ingredients:
            logger.warning(f"Could not find ingredients for {url}")
            return None
        
        # INSTRUCTIONS EXTRACTION (Serious Eats specific + fallbacks)
        instructions = []
        instruction_selectors = [
            # Serious Eats specific selectors (found in debug)
            'ol.mntl-sc-block-group--OL li',
            '.mntl-sc-block-group--OL li',
            'ol[class*="mntl-sc-block"] li',
            # Original selectors
            '.recipe-instructions li',
            '.instructions li', 
            '.recipe-method li',
            '.directions li',
            '[class*="instruction"] li',
            '.structured-instructions li',
            '.structured-recipe__instructions li',
            '.recipe-instructions__item',
            '.instruction-list li',
            '.recipe-procedure li',
            '.recipe-instructions p',
            'ol li',
            '.recipe-directions li'
        ]
        
        for selector in instruction_selectors:
            try:
                instruction_elems = soup.select(selector)
                for elem in instruction_elems:
                    text = elem.get_text().strip()
                    if text and len(text) > 10:
                        instructions.append(text)
                if instructions:
                    break
            except:
                continue
        
        if not instructions:
            instructions = ["Instructions not found"]
            logger.warning(f"Could not find instructions for {url}")
        
        # TIMES EXTRACTION (multiple selectors)
        times = ""
        time_selectors = [
            '.recipe-time',
            '.prep-time',
            '.cook-time',
            '.total-time',
            '[class*="time"]',
            '.recipe-meta time',
            '.recipe-summary time',
            '.structured-recipe__time'
        ]
        
        time_texts = []
        for selector in time_selectors:
            try:
                time_elems = soup.select(selector)
                for elem in time_elems:
                    text = elem.get_text().strip()
                    if text and any(word in text.lower() for word in ['min', 'hour', 'prep', 'cook', 'total']):
                        time_texts.append(text)
            except:
                continue
        
        times = ' | '.join(time_texts) if time_texts else ""
        
        # IMAGE URL EXTRACTION
        image_url = ""
        image_selectors = [
            '.recipe-image img',
            '.featured-image img',
            'article img',
            '.recipe-card img',
            'img[src*="recipe"]',
            'img'
        ]
        
        for selector in image_selectors:
            try:
                img_elem = soup.select_one(selector)
                if img_elem:
                    src = img_elem.get('src') or img_elem.get('data-src')
                    if src and ('http' in src or src.startswith('/')):
                        if src.startswith('/'):
                            image_url = urljoin(url, src)
                        else:
                            image_url = src
                        break
            except:
                continue
        
        # Prepare recipe data
        recipe_data = {
            'title': title[:200],  # Truncate if too long
            'ingredients': ingredients,
            'instructions': instructions,
            'times': times[:300],  # Truncate if too long
            'image_url': image_url[:500],  # Truncate if too long
            'original_url': url
        }
        
        logger.info(f"Successfully scraped recipe: {title}")
        return recipe_data
        
    except Exception as e:
        logger.error(f"Error scraping recipe {url}: {e}")
        return None

def save_recipe_unified(recipe_data):
    """Save recipe to database with comprehensive validation"""
    try:
        # Check if recipe already exists
        if Recipe.objects.filter(original_url=recipe_data['original_url']).exists():
            logger.info(f"Recipe already exists: {recipe_data['original_url']}")
            return False
        
        # Prepare ingredients and instructions text
        scraped_ingredients_text = '\n'.join(recipe_data['ingredients'])
        instructions_text = '\n'.join(recipe_data['instructions'])
        
        # Field length validation and logging
        title = recipe_data['title'][:200] if len(recipe_data['title']) > 200 else recipe_data['title']
        times = recipe_data['times'][:300] if len(recipe_data['times']) > 300 else recipe_data['times']
        image_url = recipe_data['image_url'][:500] if len(recipe_data['image_url']) > 500 else recipe_data['image_url']
        
        logger.info(f"Field lengths - Title: {len(title)}, Times: {len(times)}, Image URL: {len(image_url)}, Original URL: {len(recipe_data['original_url'])}")
        
        # Create and save recipe
        recipe = Recipe(
            title=title,
            scraped_ingredients=scraped_ingredients_text,
            instructions=instructions_text,
            times=times,
            image_url=image_url,
            original_url=recipe_data['original_url']
        )
        
        recipe.save()
        logger.info(f"Successfully saved recipe: {title}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving recipe {recipe_data.get('title', 'Unknown')}: {e}")
        return False

def main():
    """Main scraper function"""
    parser = argparse.ArgumentParser(description='Unified Serious Eats Recipe Scraper')
    parser.add_argument('--max-recipes', type=int, default=1000, help='Maximum number of recipes to scrape')
    parser.add_argument('--test', action='store_true', help='Test mode - scrape only one recipe')
    
    args = parser.parse_args()
    
    logger.info("Starting Unified Serious Eats Recipe Scraper...")
    logger.info(f"Target: {args.max_recipes} recipes")
    
    if args.test:
        # Test with a single known recipe
        test_url = "https://www.seriouseats.com/the-secret-ingredient-parsley-spaghetti-with-pesto-recipe"
        logger.info(f"TEST MODE: Scraping single recipe: {test_url}")
        
        recipe_data = scrape_recipe_unified(test_url)
        if recipe_data:
            logger.info(f"Test successful! Recipe: {recipe_data['title']}")
            logger.info(f"Ingredients: {len(recipe_data['ingredients'])}")
            logger.info(f"Instructions: {len(recipe_data['instructions'])}")
        else:
            logger.error("Test failed!")
        return
    
    # Get recipe links
    logger.info("Collecting recipe links...")
    recipe_links = get_recipe_links_comprehensive(args.max_recipes)
    logger.info(f"Found {len(recipe_links)} recipe links")
    
    if not recipe_links:
        logger.error("No recipe links found!")
        return
    
    # Scrape recipes
    logger.info("Starting recipe scraping...")
    scraped_count = 0
    failed_count = 0
    
    for i, recipe_url in enumerate(recipe_links, 1):
        if scraped_count >= args.max_recipes:
            break
            
        logger.info(f"Processing recipe {i}/{len(recipe_links)}: {recipe_url}")
        
        # Check if already exists
        if Recipe.objects.filter(original_url=recipe_url).exists():
            logger.info(f"Recipe already exists in database: {recipe_url}")
            continue
        
        # Scrape recipe
        recipe_data = scrape_recipe_unified(recipe_url)
        if recipe_data:
            if save_recipe_unified(recipe_data):
                scraped_count += 1
                logger.info(f"Progress: {scraped_count}/{args.max_recipes} recipes scraped successfully")
            else:
                failed_count += 1
        else:
            failed_count += 1
            logger.warning(f"Failed to scrape recipe: {recipe_url}")
        
        # Brief delay between requests
        time.sleep(random.uniform(1, 3))
    
    # Final summary
    total_in_db = Recipe.objects.filter(original_url__contains='seriouseats.com').count()
    
    logger.info("Scraping completed!")
    logger.info(f"Successfully scraped: {scraped_count} recipes")
    logger.info(f"Failed to scrape: {failed_count} recipes")
    logger.info(f"Total Serious Eats recipes in database: {total_in_db}")

if __name__ == "__main__":
    main() 