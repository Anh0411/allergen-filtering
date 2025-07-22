import os
import sys
import django
import time
import logging
import traceback
from typing import Optional, Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from dataclasses import dataclass
from enum import Enum

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('allergen_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from recipes.models import Recipe, AllergenAnalysisResult

class AnalysisStatus(Enum):
    """Enum for analysis status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class AnalysisConfig:
    """Configuration for allergen analysis"""
    max_workers: int = 3
    delay_range: tuple = (1, 3)
    enable_confidence_threshold: bool = True
    confidence_threshold: float = 0.5
    enable_retry_on_failure: bool = True
    max_retries: int = 2
    batch_size: int = 50

@dataclass
class AnalysisResult:
    """Data class for analysis results"""
    risk_level: str
    confidence_scores: Dict[str, float]
    detected_allergens: Dict[str, List[str]]
    recommendations: List[str]
    total_ingredients: int
    analyzed_ingredients: int
    processing_time: float
    raw_matches: List[Dict[str, Any]]
    status: AnalysisStatus = AnalysisStatus.COMPLETED
    error_message: Optional[str] = None

class AllergenAnalysisProcessor:
    """Handles the core allergen analysis logic"""
    
    def __init__(self, nlp_processor=None):
        self.nlp_processor = nlp_processor
        self._initialize_nlp_processor()

    def _initialize_nlp_processor(self):
        """Initialize NLP processor for allergen detection"""
        if self.nlp_processor is None:
            try:
                from allergen_filtering.nlp_processor import get_nlp_processor
                self.nlp_processor = get_nlp_processor()
                logger.info("NLP processor initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize NLP processor: {e}")
                self.nlp_processor = None

    def analyze_recipe_text(self, recipe_data: Dict[str, Any]) -> Optional[AnalysisResult]:
        """Analyze allergens in recipe text"""
        if not self.nlp_processor:
            logger.warning("NLP processor not available, skipping allergen analysis")
            return AnalysisResult(
                risk_level="unknown",
                confidence_scores={},
                detected_allergens={},
                recommendations=["NLP processor not available"],
                total_ingredients=0,
                analyzed_ingredients=0,
                processing_time=0.0,
                raw_matches=[],
                status=AnalysisStatus.FAILED,
                error_message="NLP processor not available"
            )
        
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
            
            return AnalysisResult(
                risk_level=analysis.risk_level,
                confidence_scores=analysis.confidence_scores,
                detected_allergens={
                    category: [match.text for match in matches] 
                    for category, matches in analysis.detected_allergens.items()
                },
                recommendations=analysis.recommendations,
                total_ingredients=len(extracted_ingredients),
                analyzed_ingredients=len(extracted_ingredients),
                processing_time=processing_time,
                raw_matches=analysis.raw_matches
            )
            
        except Exception as e:
            logger.error(f"Error in allergen analysis for {recipe_data['title']}: {e}")
            logger.error(traceback.format_exc())
            return AnalysisResult(
                risk_level="error",
                confidence_scores={},
                detected_allergens={},
                recommendations=["Analysis failed"],
                total_ingredients=0,
                analyzed_ingredients=0,
                processing_time=0.0,
                raw_matches=[],
                status=AnalysisStatus.FAILED,
                error_message=str(e)
            )

class AllergenDatabaseManager:
    """Handles database operations for allergen analysis results"""
    
    @staticmethod
    def save_analysis_result(recipe: Recipe, analysis_result: AnalysisResult) -> bool:
        """Save allergen analysis result to database"""
        try:
            # Update recipe with allergen information
            recipe.risk_level = analysis_result.risk_level
            recipe.nlp_confidence_score = max(analysis_result.confidence_scores.values()) if analysis_result.confidence_scores else 0.0
            recipe.nlp_analysis_date = django.utils.timezone.now()
            recipe.last_analyzed = django.utils.timezone.now()
            recipe.save()
            
            # Save detailed analysis result
            analysis_db_result, created = AllergenAnalysisResult.objects.get_or_create(
                recipe=recipe,
                defaults={
                    'risk_level': analysis_result.risk_level,
                    'confidence_scores': analysis_result.confidence_scores,
                    'detected_allergens': analysis_result.detected_allergens,
                    'recommendations': analysis_result.recommendations,
                    'total_ingredients': analysis_result.total_ingredients,
                    'analyzed_ingredients': analysis_result.analyzed_ingredients,
                    'processing_time': analysis_result.processing_time
                }
            )
            
            if not created:
                # Update existing analysis
                analysis_db_result.risk_level = analysis_result.risk_level
                analysis_db_result.confidence_scores = analysis_result.confidence_scores
                analysis_db_result.detected_allergens = analysis_result.detected_allergens
                analysis_db_result.recommendations = analysis_result.recommendations
                analysis_db_result.total_ingredients = analysis_result.total_ingredients
                analysis_db_result.analyzed_ingredients = analysis_result.analyzed_ingredients
                analysis_db_result.processing_time = analysis_result.processing_time
                analysis_db_result.save()
            
            logger.info(f"Saved allergen analysis for {recipe.title}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving allergen analysis for {recipe.title}: {e}")
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    def get_unanalyzed_recipes(recipe_ids: Optional[List[int]] = None) -> List[Recipe]:
        """Get recipes that need allergen analysis"""
        if recipe_ids:
            recipes = Recipe.objects.filter(
                id__in=recipe_ids, 
                original_url__icontains='food.com'
            )
        else:
            # Get all Food.com recipes without allergen analysis
            recipes = Recipe.objects.filter(
                original_url__icontains='food.com',
                risk_level__isnull=True
            )
        
        return list(recipes)

    @staticmethod
    def get_analysis_statistics() -> Dict[str, Any]:
        """Get statistics about allergen analysis coverage"""
        total_recipes = Recipe.objects.filter(original_url__icontains='food.com').count()
        analyzed_recipes = Recipe.objects.filter(
            original_url__icontains='food.com',
            risk_level__isnull=False
        ).count()
        unanalyzed_recipes = total_recipes - analyzed_recipes
        
        # Get risk level distribution
        risk_levels = Recipe.objects.filter(
            original_url__icontains='food.com',
            risk_level__isnull=False
        ).values_list('risk_level', flat=True)
        
        risk_distribution = {}
        for risk in risk_levels:
            risk_distribution[risk] = risk_distribution.get(risk, 0) + 1
        
        return {
            'total_recipes': total_recipes,
            'analyzed_recipes': analyzed_recipes,
            'unanalyzed_recipes': unanalyzed_recipes,
            'analysis_percentage': (analyzed_recipes / total_recipes * 100) if total_recipes > 0 else 0,
            'risk_distribution': risk_distribution
        }

class AllergenAnalysisManager:
    """Main manager class for allergen analysis operations"""
    
    def __init__(self, config: AnalysisConfig = None, nlp_processor=None):
        self.config = config or AnalysisConfig()
        self.processor = AllergenAnalysisProcessor(nlp_processor)
        self.db_manager = AllergenDatabaseManager()

    def _get_random_delay(self) -> float:
        """Get random delay between analyses"""
        return random.uniform(*self.config.delay_range)

    def analyze_single_recipe(self, recipe_data: Dict[str, Any]) -> bool:
        """Analyze allergens for a single recipe"""
        try:
            # Get the recipe from database
            try:
                recipe = Recipe.objects.get(original_url=recipe_data['original_url'])
            except Recipe.DoesNotExist:
                logger.error(f"Recipe not found in database: {recipe_data['original_url']}")
                return False
            
            # Perform allergen analysis
            analysis_result = self.processor.analyze_recipe_text(recipe_data)
            if not analysis_result or analysis_result.status == AnalysisStatus.FAILED:
                logger.warning(f"No allergen analysis result for {recipe_data['title']}")
                return False
            
            # Save the analysis
            success = self.db_manager.save_analysis_result(recipe, analysis_result)
            
            if success:
                logger.info(f"Successfully analyzed allergens for: {recipe_data['title']}")
            else:
                logger.error(f"Failed to save allergen analysis for: {recipe_data['title']}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in analyze_single_recipe for {recipe_data['title']}: {e}")
            logger.error(traceback.format_exc())
            return False

    def analyze_recipe_batch(self, recipe_data_list: List[Dict[str, Any]]) -> Tuple[int, int]:
        """Analyze allergens for a batch of recipes with threading"""
        logger.info(f"Starting allergen analysis for {len(recipe_data_list)} recipes")
        
        successful_analyses = 0
        failed_analyses = 0
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all analysis tasks
            future_to_recipe = {
                executor.submit(self.analyze_single_recipe, recipe_data): recipe_data['title'] 
                for recipe_data in recipe_data_list
            }
            
            # Process completed tasks
            for future in as_completed(future_to_recipe):
                recipe_title = future_to_recipe[future]
                try:
                    success = future.result()
                    if success:
                        successful_analyses += 1
                    else:
                        failed_analyses += 1
                except Exception as e:
                    logger.error(f"Exception occurred while analyzing {recipe_title}: {e}")
                    failed_analyses += 1
                
                # Add delay between analyses
                time.sleep(self._get_random_delay())
        
        logger.info(f"Batch allergen analysis completed: {successful_analyses} successful, {failed_analyses} failed")
        return successful_analyses, failed_analyses

    def analyze_existing_recipes(self, recipe_ids: Optional[List[int]] = None) -> Tuple[int, int]:
        """Analyze allergens for existing recipes in database"""
        recipes = self.db_manager.get_unanalyzed_recipes(recipe_ids)
        
        logger.info(f"Found {len(recipes)} recipes to analyze")
        
        if not recipes:
            logger.info("No recipes found for allergen analysis")
            return 0, 0
        
        # Convert recipes to recipe data format
        recipe_data_list = []
        for recipe in recipes:
            recipe_data = {
                'title': recipe.title,
                'scraped_ingredients_text': recipe.scraped_ingredients_text,
                'instructions': recipe.instructions,
                'original_url': recipe.original_url
            }
            recipe_data_list.append(recipe_data)
        
        return self.analyze_recipe_batch(recipe_data_list)

    def analyze_recipes_in_batches(self, recipe_ids: Optional[List[int]] = None) -> Tuple[int, int]:
        """Analyze recipes in configurable batches"""
        recipes = self.db_manager.get_unanalyzed_recipes(recipe_ids)
        
        logger.info(f"Found {len(recipes)} recipes to analyze in batches of {self.config.batch_size}")
        
        if not recipes:
            logger.info("No recipes found for allergen analysis")
            return 0, 0
        
        total_successful = 0
        total_failed = 0
        
        # Process in batches
        for i in range(0, len(recipes), self.config.batch_size):
            batch = recipes[i:i + self.config.batch_size]
            logger.info(f"Processing batch {i//self.config.batch_size + 1}: recipes {i+1}-{min(i+self.config.batch_size, len(recipes))}")
            
            # Convert batch to recipe data format
            recipe_data_list = []
            for recipe in batch:
                recipe_data = {
                    'title': recipe.title,
                    'scraped_ingredients_text': recipe.scraped_ingredients_text,
                    'instructions': recipe.instructions,
                    'original_url': recipe.original_url
                }
                recipe_data_list.append(recipe_data)
            
            successful, failed = self.analyze_recipe_batch(recipe_data_list)
            total_successful += successful
            total_failed += failed
            
            # Add delay between batches
            if i + self.config.batch_size < len(recipes):
                time.sleep(self._get_random_delay() * 2)  # Longer delay between batches
        
        logger.info(f"All batches completed: {total_successful} successful, {total_failed} failed")
        return total_successful, total_failed

    def get_statistics(self) -> Dict[str, Any]:
        """Get analysis statistics"""
        return self.db_manager.get_analysis_statistics()

    def retry_failed_analyses(self, max_retries: int = None) -> Tuple[int, int]:
        """Retry analysis for recipes that previously failed"""
        if max_retries is None:
            max_retries = self.config.max_retries
        
        # Get recipes with failed analysis (risk_level is 'error' or 'unknown')
        failed_recipes = Recipe.objects.filter(
            original_url__icontains='food.com',
            risk_level__in=['error', 'unknown']
        )
        
        logger.info(f"Found {failed_recipes.count()} recipes with failed analysis to retry")
        
        if not failed_recipes.exists():
            logger.info("No failed analyses to retry")
            return 0, 0
        
        # Convert to recipe data format
        recipe_data_list = []
        for recipe in failed_recipes:
            recipe_data = {
                'title': recipe.title,
                'scraped_ingredients_text': recipe.scraped_ingredients_text,
                'instructions': recipe.instructions,
                'original_url': recipe.original_url
            }
            recipe_data_list.append(recipe_data)
        
        return self.analyze_recipe_batch(recipe_data_list)

    def create_missing_analysis_results(self) -> int:
        """Create missing AllergenAnalysisResult records for recipes with risk_level but no analysis_result"""
        # Find recipes that have risk_level but no analysis_result
        recipes_without_analysis = Recipe.objects.filter(
            risk_level__isnull=False,
            analysis_result__isnull=True
        )
        
        logger.info(f"Found {recipes_without_analysis.count()} recipes with risk_level but no analysis_result")
        
        created_count = 0
        for recipe in recipes_without_analysis:
            try:
                # Create basic AllergenAnalysisResult with available data
                analysis_result = AllergenAnalysisResult.objects.create(
                    recipe=recipe,
                    risk_level=recipe.risk_level,
                    confidence_scores={'overall': recipe.nlp_confidence_score or 0.0},
                    detected_allergens={},  # Empty since we don't have detailed data
                    recommendations=['Analysis completed with basic data'],
                    total_ingredients=0,
                    analyzed_ingredients=0,
                    processing_time=0.0
                )
                created_count += 1
                logger.debug(f"Created analysis result for {recipe.title}")
            except Exception as e:
                logger.error(f"Error creating analysis result for {recipe.title}: {e}")
        
        logger.info(f"Created {created_count} missing AllergenAnalysisResult records")
        return created_count

def main(recipe_ids: Optional[List[int]] = None, max_workers: int = 3, 
         batch_size: int = 50, retry_failed: bool = False, create_missing: bool = True):
    """Main function to run allergen analysis"""
    
    # Create configuration
    config = AnalysisConfig(
        max_workers=max_workers,
        batch_size=batch_size
    )
    
    manager = AllergenAnalysisManager(config)
    
    # Create missing analysis results if requested
    if create_missing:
        logger.info("Creating missing AllergenAnalysisResult records...")
        created_count = manager.create_missing_analysis_results()
        if created_count > 0:
            logger.info(f"Created {created_count} missing analysis result records")
    
    if retry_failed:
        logger.info("Retrying failed allergen analyses")
        successful, failed = manager.retry_failed_analyses()
    elif recipe_ids:
        logger.info(f"Starting allergen analysis for specific recipe IDs: {recipe_ids}")
        successful, failed = manager.analyze_existing_recipes(recipe_ids)
    else:
        logger.info("Starting allergen analysis for all unanalyzed Food.com recipes")
        successful, failed = manager.analyze_recipes_in_batches()
    
    logger.info(f"Allergen analysis completed! {successful} successful, {failed} failed")
    
    # Show final statistics
    stats = manager.get_statistics()
    logger.info("=== FINAL STATISTICS ===")
    logger.info(f"Total Food.com recipes: {stats['total_recipes']}")
    logger.info(f"Recipes with allergen analysis: {stats['analyzed_recipes']}")
    logger.info(f"Recipes without allergen analysis: {stats['unanalyzed_recipes']}")
    logger.info(f"Analysis coverage: {stats['analysis_percentage']:.1f}%")
    
    if stats['risk_distribution']:
        logger.info("Risk level distribution:")
        for risk, count in stats['risk_distribution'].items():
            logger.info(f"  {risk}: {count}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Allergen analysis manager for Food.com recipes')
    parser.add_argument('--recipe-ids', type=int, nargs='+', help='Specific recipe IDs to analyze')
    parser.add_argument('--max-workers', type=int, default=3, help='Maximum number of worker threads')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for processing')
    parser.add_argument('--retry-failed', action='store_true', help='Retry failed analyses')
    parser.add_argument('--create-missing', action='store_true', default=True, help='Create missing AllergenAnalysisResult records')
    parser.add_argument('--no-create-missing', dest='create_missing', action='store_false', help='Skip creating missing AllergenAnalysisResult records')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    
    args = parser.parse_args()
    
    if args.stats:
        manager = AllergenAnalysisManager()
        stats = manager.get_statistics()
        logger.info("=== ALLERGEN ANALYSIS STATISTICS ===")
        logger.info(f"Total Food.com recipes: {stats['total_recipes']}")
        logger.info(f"Recipes with allergen analysis: {stats['analyzed_recipes']}")
        logger.info(f"Recipes without allergen analysis: {stats['unanalyzed_recipes']}")
        logger.info(f"Analysis coverage: {stats['analysis_percentage']:.1f}%")
        
        if stats['risk_distribution']:
            logger.info("Risk level distribution:")
            for risk, count in stats['risk_distribution'].items():
                logger.info(f"  {risk}: {count}")
    else:
        main(args.recipe_ids, args.max_workers, args.batch_size, args.retry_failed, args.create_missing) 