#!/usr/bin/env python3
"""
Test script for scraping a single known recipe URL.

This script tests:
1. Scraping a specific recipe URL
2. Parsing recipe data
3. Saving to database

Usage:
    python test_single_recipe.py
"""

import os
import sys
import time
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_single_recipe.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')

from recipes.models import Recipe

def test_single_recipe_scraping():
    """Test scraping a single known recipe URL"""
    logger.info("=== Testing Single Recipe Scraping ===")
    
    # Test with a known working recipe URL from the database
    test_urls = [
        "https://www.food.com/recipe/better-than-olive-garden-alfredo-sauce-141983",
        "https://www.food.com/recipe/barbs-gumbo-82288",
        "https://www.food.com/recipe/to-die-for-crock-pot-roast-27208"
    ]
    
    try:
        from foodcom_optimized_scraper import FoodComOptimizedScraper, ScrapingConfig, ScrapingStrategy
        
        # Create configuration for testing
        config = ScrapingConfig(
            max_retries=2,
            delay_range=(1, 2),
            timeout=20,
            max_workers=1,
            strategy=ScrapingStrategy.DUAL,
            min_html_size=1000,
            enable_duplicate_check=False  # Allow re-scraping for testing
        )
        
        scraper = FoodComOptimizedScraper(config)
        logger.info("✅ Scraper initialized successfully")
        
        for i, url in enumerate(test_urls, 1):
            logger.info(f"Testing recipe {i}/{len(test_urls)}: {url}")
            
            try:
                # Check if recipe already exists
                existing_recipe = Recipe.objects.filter(original_url=url).first()
                if existing_recipe:
                    logger.info(f"Recipe already exists: {existing_recipe.title}")
                    logger.info(f"  Ingredients: {len(existing_recipe.scraped_ingredients_text)}")
                    logger.info(f"  Risk Level: {existing_recipe.risk_level}")
                    continue
                
                # Scrape the recipe
                recipe_data = scraper.scrape_recipe(url)
                
                if recipe_data:
                    logger.info(f"✅ Successfully scraped: {recipe_data['title']}")
                    logger.info(f"   Ingredients: {len(recipe_data['scraped_ingredients_text'])}")
                    logger.info(f"   Instructions: {len(recipe_data['instructions'])}")
                    logger.info(f"   Sample ingredients: {recipe_data['scraped_ingredients_text'][:3]}")
                    
                    # Save to database
                    success = scraper.db_manager.save_recipe(recipe_data)
                    if success:
                        logger.info(f"✅ Successfully saved to database: {recipe_data['title']}")
                    else:
                        logger.warning(f"⚠️ Failed to save to database: {recipe_data['title']}")
                else:
                    logger.warning(f"⚠️ Failed to scrape recipe from {url}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing {url}: {e}")
                continue
            
            # Add delay between requests
            time.sleep(2)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Single recipe scraping test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_html_fetching():
    """Test HTML fetching with different strategies"""
    logger.info("=== Testing HTML Fetching ===")
    
    test_url = "https://www.food.com/recipe/better-than-olive-garden-alfredo-sauce-141983"
    
    try:
        from foodcom_optimized_scraper import HTMLFetcher, ScrapingConfig, ScrapingStrategy
        
        config = ScrapingConfig(
            max_retries=2,
            delay_range=(1, 2),
            timeout=20,
            strategy=ScrapingStrategy.DUAL
        )
        
        html_fetcher = HTMLFetcher(config)
        
        # Test simple request
        logger.info("Testing simple request...")
        html_simple = html_fetcher.fetch_simple(test_url)
        if html_simple:
            logger.info(f"✅ Simple request successful: {len(html_simple)} characters")
        else:
            logger.warning("⚠️ Simple request failed")
        
        # Test Playwright
        logger.info("Testing Playwright...")
        html_playwright = html_fetcher.fetch_with_playwright(test_url)
        if html_playwright:
            logger.info(f"✅ Playwright successful: {len(html_playwright)} characters")
        else:
            logger.warning("⚠️ Playwright failed")
        
        # Test dual strategy
        logger.info("Testing dual strategy...")
        html_dual = html_fetcher.fetch_html(test_url)
        if html_dual:
            logger.info(f"✅ Dual strategy successful: {len(html_dual)} characters")
        else:
            logger.warning("⚠️ Dual strategy failed")
        
        return html_dual is not None
        
    except Exception as e:
        logger.error(f"❌ HTML fetching test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_url_discovery_alternative():
    """Test alternative URL discovery methods"""
    logger.info("=== Testing Alternative URL Discovery ===")
    
    try:
        from foodcom_optimized_scraper import HTMLFetcher, ScrapingConfig, ScrapingStrategy
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        config = ScrapingConfig(
            max_retries=2,
            delay_range=(1, 2),
            timeout=20,
            strategy=ScrapingStrategy.DUAL
        )
        
        html_fetcher = HTMLFetcher(config)
        
        # Test different Food.com URLs
        test_urls = [
            "https://www.food.com/recipe",
            "https://www.food.com/recipe/all",
            "https://www.food.com/recipe/popular",
            "https://www.food.com/recipe/trending"
        ]
        
        for url in test_urls:
            logger.info(f"Testing URL discovery from: {url}")
            
            try:
                html = html_fetcher.fetch_html(url)
                if not html:
                    logger.warning(f"⚠️ Failed to fetch HTML from {url}")
                    continue
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for recipe links
                recipe_links = []
                selectors = [
                    'a[href*="/recipe/"]',
                    '.recipe-card a[href]',
                    '.recipe-item a[href]',
                    'article a[href*="/recipe/"]',
                    '.card a[href*="/recipe/"]'
                ]
                
                for selector in selectors:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href')
                        if href and '/recipe/' in href:
                            if href.startswith('/'):
                                href = urljoin("https://www.food.com", href)
                            if href not in recipe_links:
                                recipe_links.append(href)
                
                logger.info(f"Found {len(recipe_links)} recipe links from {url}")
                if recipe_links:
                    logger.info(f"Sample links: {recipe_links[:3]}")
                    break  # Found links, stop testing
                    
            except Exception as e:
                logger.error(f"Error testing {url}: {e}")
                continue
        
        return len(recipe_links) > 0
        
    except Exception as e:
        logger.error(f"❌ Alternative URL discovery test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main test function"""
    logger.info("🚀 Starting single recipe scraping test")
    logger.info("=" * 60)
    
    try:
        # Step 1: Test HTML fetching
        html_success = test_html_fetching()
        
        # Step 2: Test single recipe scraping
        scraping_success = test_single_recipe_scraping()
        
        # Step 3: Test alternative URL discovery
        discovery_success = test_url_discovery_alternative()
        
        # Final results
        logger.info("=" * 60)
        logger.info("=== FINAL RESULTS ===")
        logger.info(f"HTML fetching: {'✅ Success' if html_success else '❌ Failed'}")
        logger.info(f"Recipe scraping: {'✅ Success' if scraping_success else '❌ Failed'}")
        logger.info(f"URL discovery: {'✅ Success' if discovery_success else '❌ Failed'}")
        
        if scraping_success:
            logger.info("🎉 Single recipe scraping test completed successfully!")
        else:
            logger.warning("⚠️ Single recipe scraping test had issues")
        
    except KeyboardInterrupt:
        logger.info("⏹️ Test interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error during testing: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 