#!/usr/bin/env python3
"""
Test script for the integrated allergen scraper
"""

import os
import sys
import django
import logging

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from scraper.scrape_foodcom_with_allergen_detection import FoodComAllergenScraper
from recipes.models import Recipe, AllergenAnalysisResult
from django.db import models

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_allergen_scraper():
    """Test the integrated allergen scraper with a small sample"""
    
    logger.info("Testing integrated allergen scraper...")
    
    # Initialize scraper
    scraper = FoodComAllergenScraper()
    
    # Check if NLP processor is available
    if not scraper.nlp_processor:
        logger.error("NLP processor not available. Please check your installation.")
        return False
    
    logger.info("NLP processor initialized successfully")
    
    # Test with a single page
    logger.info("Testing with page 1...")
    
    try:
        # Get URLs from page 1
        urls = scraper.get_recipe_urls_from_page(1)
        logger.info(f"Found {len(urls)} URLs on page 1")
        
        if not urls:
            logger.warning("No URLs found on page 1")
            return False
        
        # Test with first 2 URLs
        test_urls = urls[:2]
        logger.info(f"Testing with {len(test_urls)} URLs: {test_urls}")
        
        successful = 0
        failed = 0
        
        for url in test_urls:
            logger.info(f"Processing: {url}")
            try:
                success = scraper.scrape_recipe_with_allergens(url)
                if success:
                    successful += 1
                    logger.info(f"✓ Successfully processed: {url}")
                else:
                    failed += 1
                    logger.warning(f"✗ Failed to process: {url}")
            except Exception as e:
                failed += 1
                logger.error(f"✗ Exception processing {url}: {e}")
        
        logger.info(f"Test completed: {successful} successful, {failed} failed")
        
        # Check database for results
        if successful > 0:
            recent_recipes = Recipe.objects.filter(
                original_url__in=test_urls
            ).order_by('-created_at')[:successful]
            
            logger.info(f"Found {recent_recipes.count()} recipes in database")
            
            for recipe in recent_recipes:
                logger.info(f"Recipe: {recipe.title}")
                logger.info(f"  Risk Level: {recipe.risk_level}")
                logger.info(f"  Confidence Score: {recipe.nlp_confidence_score}")
                
                # Check for analysis results
                try:
                    analysis = recipe.analysis_result
                    logger.info(f"  Analysis Date: {analysis.analysis_date}")
                    logger.info(f"  Detected Allergens: {list(analysis.detected_allergens.keys())}")
                    logger.info(f"  Recommendations: {len(analysis.recommendations)} items")
                except AllergenAnalysisResult.DoesNotExist:
                    logger.warning(f"  No detailed analysis found for {recipe.title}")
        
        return successful > 0
        
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        return False

def check_database_stats():
    """Check database statistics"""
    logger.info("Checking database statistics...")
    
    total_recipes = Recipe.objects.count()
    recipes_with_analysis = Recipe.objects.filter(analysis_result__isnull=False).count()
    recipes_with_allergens = Recipe.objects.filter(risk_level__in=['medium', 'high', 'critical']).count()
    
    logger.info(f"Total recipes: {total_recipes}")
    logger.info(f"Recipes with allergen analysis: {recipes_with_analysis}")
    logger.info(f"Recipes with detected allergens: {recipes_with_allergens}")
    
    # Check risk level distribution
    risk_levels = Recipe.objects.values('risk_level').annotate(
        count=models.Count('id')
    ).order_by('risk_level')
    
    logger.info("Risk level distribution:")
    for level in risk_levels:
        logger.info(f"  {level['risk_level']}: {level['count']}")

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("ALLERGEN SCRAPER TEST")
    logger.info("=" * 50)
    
    # Check database stats before test
    check_database_stats()
    
    # Run test
    success = test_allergen_scraper()
    
    logger.info("=" * 50)
    if success:
        logger.info("✓ Test completed successfully!")
    else:
        logger.error("✗ Test failed!")
    
    # Check database stats after test
    logger.info("Final database statistics:")
    check_database_stats() 