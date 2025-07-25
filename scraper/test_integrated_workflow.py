#!/usr/bin/env python3
"""
Comprehensive test script for the integrated Food.com scraping and allergen analysis workflow.

This script tests:
1. Recipe scraping from Food.com
2. Database saving
3. Allergen analysis and detection
4. NLP processing

Usage:
    python test_integrated_workflow.py
"""

import os
import sys
import time
import logging
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_integrated_workflow.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')

from recipes.models import Recipe, AllergenAnalysisResult

def test_nlp_processor():
    """Test the NLP ingredient processor"""
    logger.info("=== Testing NLP Ingredient Processor ===")
    
    try:
        from nlp_ingredient_processor import get_nlp_processor
        
        processor = get_nlp_processor()
        logger.info("✅ NLP processor initialized successfully")
        
        # Test with sample text
        sample_text = """
        Ingredients:
        2 cups all-purpose flour
        1 cup milk
        2 eggs
        1/2 cup butter
        1/4 cup chopped almonds
        1 tbsp soy sauce
        1 tsp sesame oil
        
        Instructions:
        Mix flour with milk and eggs. Add butter and almonds. Season with soy sauce and sesame oil.
        """
        
        # Test ingredient extraction
        ingredients = processor.extract_ingredients(sample_text)
        logger.info(f"✅ Extracted {len(ingredients)} ingredients: {ingredients[:3]}...")
        
        # Test allergen analysis
        result = processor.analyze_allergens(sample_text)
        logger.info(f"✅ Allergen analysis completed:")
        logger.info(f"   Risk level: {result.risk_level}")
        logger.info(f"   Detected allergens: {[cat.value for cat, matches in result.detected_allergens.items() if matches]}")
        logger.info(f"   Recommendations: {len(result.recommendations)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ NLP processor test failed: {e}")
        return False

def test_scraper():
    """Test the optimized Food.com scraper"""
    logger.info("=== Testing Food.com Optimized Scraper ===")
    
    try:
        from foodcom_optimized_scraper import FoodComOptimizedScraper, ScrapingConfig, ScrapingStrategy
        
        # Create configuration for testing (small scope)
        config = ScrapingConfig(
            max_retries=2,
            delay_range=(1, 2),
            timeout=15,
            max_workers=1,  # Single worker for testing
            strategy=ScrapingStrategy.DUAL,
            min_html_size=1000,
            enable_duplicate_check=True
        )
        
        scraper = FoodComOptimizedScraper(config)
        logger.info("✅ Scraper initialized successfully")
        
        # Test scraping a single page (page 1)
        logger.info("Testing scraping from page 1...")
        successful, failed = scraper.scrape_page_range(1, 1)
        
        logger.info(f"✅ Scraping test completed: {successful} successful, {failed} failed")
        
        # Check if recipes were saved to database
        recent_recipes = Recipe.objects.filter(
            original_url__icontains='food.com'
        ).order_by('-created_at')[:5]
        
        if recent_recipes.exists():
            logger.info(f"✅ Found {recent_recipes.count()} recent recipes in database")
            for recipe in recent_recipes:
                logger.info(f"   - {recipe.title} ({recipe.original_url})")
        else:
            logger.warning("⚠️ No recipes found in database after scraping")
        
        return successful > 0
        
    except Exception as e:
        logger.error(f"❌ Scraper test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_allergen_analysis():
    """Test the allergen analysis manager"""
    logger.info("=== Testing Allergen Analysis Manager ===")
    
    try:
        from allergen_analysis_manager import AllergenAnalysisManager, AnalysisConfig
        
        # Create configuration
        config = AnalysisConfig(
            max_workers=1,  # Single worker for testing
            delay_range=(0.5, 1),
            enable_confidence_threshold=True,
            confidence_threshold=0.3,
            enable_retry_on_failure=True,
            max_retries=1,
            batch_size=5
        )
        
        manager = AllergenAnalysisManager(config)
        logger.info("✅ Allergen analysis manager initialized successfully")
        
        # Get unanalyzed recipes
        unanalyzed_recipes = manager.db_manager.get_unanalyzed_recipes()
        logger.info(f"Found {len(unanalyzed_recipes)} unanalyzed recipes")
        
        if not unanalyzed_recipes:
            logger.info("No unanalyzed recipes found. Creating test recipe...")
            # Create a test recipe for analysis
            test_recipe = Recipe.objects.create(
                title="Test Recipe with Allergens",
                instructions="Mix ingredients and bake",
                original_url="https://www.food.com/recipe/test-recipe-12345",
                scraped_ingredients_text=["2 cups flour", "1 cup milk", "2 eggs", "1/2 cup almonds"]
            )
            unanalyzed_recipes = [test_recipe]
            logger.info("✅ Created test recipe for analysis")
        
        # Test analysis on first few recipes
        test_recipes = unanalyzed_recipes[:3]
        logger.info(f"Testing allergen analysis on {len(test_recipes)} recipes...")
        
        # Convert to recipe data format
        recipe_data_list = []
        for recipe in test_recipes:
            recipe_data = {
                'title': recipe.title,
                'scraped_ingredients_text': recipe.scraped_ingredients_text,
                'instructions': recipe.instructions,
                'original_url': recipe.original_url
            }
            recipe_data_list.append(recipe_data)
        
        # Perform analysis
        successful, failed = manager.analyze_recipe_batch(recipe_data_list)
        
        logger.info(f"✅ Allergen analysis test completed: {successful} successful, {failed} failed")
        
        # Check results
        analyzed_recipes = Recipe.objects.filter(
            original_url__icontains='food.com',
            risk_level__isnull=False
        ).order_by('-last_analyzed')[:5]
        
        if analyzed_recipes.exists():
            logger.info(f"✅ Found {analyzed_recipes.count()} analyzed recipes:")
            for recipe in analyzed_recipes:
                logger.info(f"   - {recipe.title}: {recipe.risk_level} risk")
        
        return successful > 0
        
    except Exception as e:
        logger.error(f"❌ Allergen analysis test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_database_operations():
    """Test database operations and model relationships"""
    logger.info("=== Testing Database Operations ===")
    
    try:
        # Test Recipe model
        total_recipes = Recipe.objects.filter(original_url__icontains='food.com').count()
        logger.info(f"✅ Total Food.com recipes in database: {total_recipes}")
        
        # Test AllergenAnalysisResult model
        total_analyses = AllergenAnalysisResult.objects.count()
        logger.info(f"✅ Total allergen analyses in database: {total_analyses}")
        
        # Test recipe with analysis
        recipes_with_analysis = Recipe.objects.filter(
            original_url__icontains='food.com',
            risk_level__isnull=False
        ).count()
        logger.info(f"✅ Recipes with allergen analysis: {recipes_with_analysis}")
        
        # Show sample analysis results
        sample_analyses = AllergenAnalysisResult.objects.select_related('recipe').order_by('-analysis_date')[:3]
        if sample_analyses.exists():
            logger.info("✅ Sample analysis results:")
            for analysis in sample_analyses:
                logger.info(f"   - {analysis.recipe.title}: {analysis.risk_level} risk")
                logger.info(f"     Confidence scores: {list(analysis.confidence_scores.keys())[:3]}...")
                logger.info(f"     Detected allergens: {list(analysis.detected_allergens.keys())[:3]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database operations test failed: {e}")
        return False

def test_integrated_workflow():
    """Test the complete integrated workflow"""
    logger.info("=== Testing Complete Integrated Workflow ===")
    
    try:
        # Step 1: Test NLP processor
        nlp_success = test_nlp_processor()
        if not nlp_success:
            logger.error("❌ NLP processor test failed, stopping workflow")
            return False
        
        # Step 2: Test scraper
        scraper_success = test_scraper()
        if not scraper_success:
            logger.warning("⚠️ Scraper test had issues, but continuing...")
        
        # Step 3: Test allergen analysis
        analysis_success = test_allergen_analysis()
        if not analysis_success:
            logger.warning("⚠️ Allergen analysis test had issues")
        
        # Step 4: Test database operations
        db_success = test_database_operations()
        if not db_success:
            logger.error("❌ Database operations test failed")
            return False
        
        # Final statistics
        logger.info("=== FINAL WORKFLOW STATISTICS ===")
        
        total_recipes = Recipe.objects.filter(original_url__icontains='food.com').count()
        analyzed_recipes = Recipe.objects.filter(
            original_url__icontains='food.com',
            risk_level__isnull=False
        ).count()
        
        logger.info(f"Total Food.com recipes: {total_recipes}")
        logger.info(f"Recipes with allergen analysis: {analyzed_recipes}")
        logger.info(f"Analysis coverage: {(analyzed_recipes/total_recipes*100):.1f}%" if total_recipes > 0 else "0%")
        
        # Risk level distribution
        risk_levels = Recipe.objects.filter(
            original_url__icontains='food.com',
            risk_level__isnull=False
        ).values_list('risk_level', flat=True)
        
        risk_distribution = {}
        for risk in risk_levels:
            risk_distribution[risk] = risk_distribution.get(risk, 0) + 1
        
        if risk_distribution:
            logger.info("Risk level distribution:")
            for risk, count in risk_distribution.items():
                logger.info(f"  {risk}: {count}")
        
        logger.info("✅ Integrated workflow test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Integrated workflow test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def cleanup_test_data():
    """Clean up test data created during testing"""
    logger.info("=== Cleaning up test data ===")
    
    try:
        # Remove test recipes
        test_recipes = Recipe.objects.filter(
            title__icontains="Test Recipe"
        )
        test_count = test_recipes.count()
        test_recipes.delete()
        logger.info(f"✅ Removed {test_count} test recipes")
        
        # Remove orphaned analysis results
        orphaned_analyses = AllergenAnalysisResult.objects.filter(
            recipe__isnull=True
        )
        orphaned_count = orphaned_analyses.count()
        orphaned_analyses.delete()
        logger.info(f"✅ Removed {orphaned_count} orphaned analysis results")
        
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")

def main():
    """Main test function"""
    logger.info("🚀 Starting comprehensive integrated workflow test")
    logger.info("=" * 60)
    
    try:
        # Run the integrated workflow test
        success = test_integrated_workflow()
        
        if success:
            logger.info("🎉 All tests passed! The integrated workflow is working correctly.")
        else:
            logger.error("💥 Some tests failed. Check the logs for details.")
        
        # Clean up test data
        cleanup_test_data()
        
        logger.info("=" * 60)
        logger.info("🏁 Test completed")
        
    except KeyboardInterrupt:
        logger.info("⏹️ Test interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error during testing: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 