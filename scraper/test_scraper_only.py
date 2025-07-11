#!/usr/bin/env python3
"""
Focused test script for the Food.com scraper only.

This script tests:
1. URL discovery from Food.com pages
2. Recipe scraping and parsing
3. Database saving

Usage:
    python test_scraper_only.py
"""

import os
import sys
import django
import time
import logging
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_scraper_only.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from recipes.models import Recipe

def test_url_discovery():
    """Test URL discovery from Food.com pages"""
    logger.info("=== Testing URL Discovery ===")
    
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
            enable_duplicate_check=True
        )
        
        scraper = FoodComOptimizedScraper(config)
        
        # Test different page numbers to find recipes
        test_pages = [1, 2, 3, 10, 20]
        all_urls = []
        
        for page_num in test_pages:
            logger.info(f"Testing URL discovery on page {page_num}...")
            
            try:
                urls = scraper.url_discovery.get_recipe_urls_from_page(page_num, scraper.html_fetcher)
                logger.info(f"Found {len(urls)} URLs on page {page_num}")
                
                if urls:
                    all_urls.extend(urls)
                    logger.info(f"Sample URLs from page {page_num}:")
                    for url in urls[:3]:
                        logger.info(f"  - {url}")
                    break  # Found URLs, stop testing
                else:
                    logger.warning(f"No URLs found on page {page_num}")
                    
            except Exception as e:
                logger.error(f"Error testing page {page_num}: {e}")
                continue
        
        logger.info(f"Total URLs discovered: {len(all_urls)}")
        return all_urls
        
    except Exception as e:
        logger.error(f"❌ URL discovery test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def test_recipe_scraping(urls: List[str]):
    """Test recipe scraping from discovered URLs"""
    logger.info("=== Testing Recipe Scraping ===")
    
    if not urls:
        logger.warning("No URLs to test scraping")
        return []
    
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
            enable_duplicate_check=True
        )
        
        scraper = FoodComOptimizedScraper(config)
        
        # Test scraping first few URLs
        test_urls = urls[:3]
        scraped_recipes = []
        
        for i, url in enumerate(test_urls, 1):
            logger.info(f"Testing recipe scraping {i}/{len(test_urls)}: {url}")
            
            try:
                recipe_data = scraper.scrape_recipe(url)
                
                if recipe_data:
                    logger.info(f"✅ Successfully scraped: {recipe_data['title']}")
                    logger.info(f"   Ingredients: {len(recipe_data['scraped_ingredients_text'])}")
                    logger.info(f"   Instructions: {len(recipe_data['instructions'])}")
                    scraped_recipes.append(recipe_data)
                else:
                    logger.warning(f"⚠️ Failed to scrape recipe from {url}")
                    
            except Exception as e:
                logger.error(f"❌ Error scraping {url}: {e}")
                continue
            
            # Add delay between requests
            time.sleep(2)
        
        logger.info(f"Successfully scraped {len(scraped_recipes)} recipes")
        return scraped_recipes
        
    except Exception as e:
        logger.error(f"❌ Recipe scraping test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def test_database_saving(recipes: List[Dict[str, Any]]):
    """Test saving scraped recipes to database"""
    logger.info("=== Testing Database Saving ===")
    
    if not recipes:
        logger.warning("No recipes to save")
        return 0
    
    try:
        from foodcom_optimized_scraper import DatabaseManager
        
        db_manager = DatabaseManager()
        saved_count = 0
        
        for i, recipe_data in enumerate(recipes, 1):
            logger.info(f"Testing database save {i}/{len(recipes)}: {recipe_data['title']}")
            
            try:
                success = db_manager.save_recipe(recipe_data)
                
                if success:
                    logger.info(f"✅ Successfully saved: {recipe_data['title']}")
                    saved_count += 1
                else:
                    logger.warning(f"⚠️ Failed to save: {recipe_data['title']}")
                    
            except Exception as e:
                logger.error(f"❌ Error saving {recipe_data['title']}: {e}")
                continue
        
        logger.info(f"Successfully saved {saved_count}/{len(recipes)} recipes to database")
        return saved_count
        
    except Exception as e:
        logger.error(f"❌ Database saving test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0

def test_existing_recipes():
    """Check existing recipes in database"""
    logger.info("=== Checking Existing Recipes ===")
    
    try:
        # Get recent recipes
        recent_recipes = Recipe.objects.filter(
            original_url__icontains='food.com'
        ).order_by('-created_at')[:10]
        
        logger.info(f"Found {recent_recipes.count()} recent Food.com recipes")
        
        if recent_recipes.exists():
            logger.info("Recent recipes:")
            for recipe in recent_recipes:
                logger.info(f"  - {recipe.title}")
                logger.info(f"    URL: {recipe.original_url}")
                logger.info(f"    Created: {recipe.created_at}")
                logger.info(f"    Ingredients: {len(recipe.scraped_ingredients_text)}")
                logger.info(f"    Risk Level: {recipe.risk_level or 'Not analyzed'}")
                logger.info("")
        
        # Get total count
        total_count = Recipe.objects.filter(original_url__icontains='food.com').count()
        logger.info(f"Total Food.com recipes in database: {total_count}")
        
        return total_count
        
    except Exception as e:
        logger.error(f"❌ Error checking existing recipes: {e}")
        return 0

def main():
    """Main test function"""
    logger.info("🚀 Starting focused scraper test")
    logger.info("=" * 60)
    
    try:
        # Step 1: Check existing recipes
        existing_count = test_existing_recipes()
        
        # Step 2: Test URL discovery
        urls = test_url_discovery()
        
        if not urls:
            logger.warning("⚠️ No URLs discovered, cannot test scraping")
            return
        
        # Step 3: Test recipe scraping
        recipes = test_recipe_scraping(urls)
        
        if not recipes:
            logger.warning("⚠️ No recipes scraped, cannot test database saving")
            return
        
        # Step 4: Test database saving
        saved_count = test_database_saving(recipes)
        
        # Final results
        logger.info("=" * 60)
        logger.info("=== FINAL RESULTS ===")
        logger.info(f"URLs discovered: {len(urls)}")
        logger.info(f"Recipes scraped: {len(recipes)}")
        logger.info(f"Recipes saved: {saved_count}")
        
        # Check if new recipes were added
        new_count = Recipe.objects.filter(original_url__icontains='food.com').count()
        logger.info(f"Total recipes before: {existing_count}")
        logger.info(f"Total recipes after: {new_count}")
        logger.info(f"New recipes added: {new_count - existing_count}")
        
        if saved_count > 0:
            logger.info("🎉 Scraper test completed successfully!")
        else:
            logger.warning("⚠️ Scraper test completed but no new recipes were saved")
        
    except KeyboardInterrupt:
        logger.info("⏹️ Test interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error during testing: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 