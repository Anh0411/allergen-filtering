from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
import logging
import time

from recipes.models import Recipe, AllergenAnalysisResult
from allergen_filtering.nlp_processor import get_nlp_processor

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Re-analyze all recipes in the database with the FSA allergen dictionary'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of recipes to process in each batch (default: 100)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be analyzed without making changes'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-analysis even if recipes already have analysis results'
        )
        parser.add_argument(
            '--recipe-ids',
            nargs='+',
            type=int,
            help='Specific recipe IDs to re-analyze'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        force = options['force']
        recipe_ids = options['recipe_ids']

        self.stdout.write(
            self.style.SUCCESS(
                f'Starting recipe re-analysis with FSA allergen dictionary\n'
                f'Batch size: {batch_size}\n'
                f'Dry run: {dry_run}\n'
                f'Force re-analysis: {force}'
            )
        )

        try:
            # Initialize NLP processor with FSA dictionary
            nlp_processor = get_nlp_processor()
            self.stdout.write(
                self.style.SUCCESS(f'✅ Using NLP processor with {type(nlp_processor.allergen_dict).__name__}')
            )

            # Get recipes to analyze
            if recipe_ids:
                recipes = Recipe.objects.filter(id__in=recipe_ids)
                self.stdout.write(f'Analyzing specific recipes: {recipe_ids}')
            else:
                if force:
                    recipes = Recipe.objects.all()
                    self.stdout.write('Analyzing ALL recipes (force mode)')
                else:
                    # Only analyze recipes without existing analysis results
                    recipes = Recipe.objects.filter(analysis_result__isnull=True)
                    self.stdout.write('Analyzing recipes without existing analysis results')

            total_recipes = recipes.count()
            self.stdout.write(f'Total recipes to analyze: {total_recipes}')

            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
                self._show_analysis_preview(nlp_processor, recipes[:5])
                return

            if total_recipes == 0:
                self.stdout.write(self.style.WARNING('No recipes to analyze'))
                return

            # Process recipes in batches
            processed = 0
            updated = 0
            errors = 0
            start_time = time.time()

            for i in range(0, total_recipes, batch_size):
                batch = recipes[i:i + batch_size]
                self.stdout.write(f'\nProcessing batch {i//batch_size + 1}/{(total_recipes + batch_size - 1)//batch_size}')
                
                batch_processed, batch_updated, batch_errors = self._process_batch(
                    nlp_processor, batch, force
                )
                
                processed += batch_processed
                updated += batch_updated
                errors += batch_errors

                # Progress update
                progress = (i + len(batch)) / total_recipes * 100
                elapsed_time = time.time() - start_time
                avg_time_per_recipe = elapsed_time / processed if processed > 0 else 0
                estimated_remaining = (total_recipes - processed) * avg_time_per_recipe

                self.stdout.write(
                    f'Progress: {progress:.1f}% ({processed}/{total_recipes}) | '
                    f'Updated: {updated} | Errors: {errors} | '
                    f'ETA: {estimated_remaining/60:.1f} minutes'
                )

            # Final summary
            total_time = time.time() - start_time
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('RE-ANALYSIS SUMMARY'))
            self.stdout.write('=' * 60)
            self.stdout.write(f'Total recipes processed: {processed}')
            self.stdout.write(f'Analysis results updated: {updated}')
            self.stdout.write(f'Errors: {errors}')
            self.stdout.write(f'Total time: {total_time/60:.1f} minutes')
            self.stdout.write(f'Average time per recipe: {total_time/processed:.2f} seconds')

            # Show statistics
            self._show_final_statistics()

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\nRe-analysis interrupted by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nUnexpected error during re-analysis: {e}')
            )
            raise CommandError(f'Re-analysis failed: {e}')

    def _process_batch(self, nlp_processor, recipes, force):
        """Process a batch of recipes"""
        processed = 0
        updated = 0
        errors = 0

        for recipe in recipes:
            try:
                # Check if recipe already has analysis
                existing_analysis = AllergenAnalysisResult.objects.filter(recipe=recipe).first()
                
                if existing_analysis and not force:
                    # Skip if already analyzed and not forcing
                    continue

                # Combine ingredients and instructions for analysis
                text = f"Ingredients: {recipe.scraped_ingredients_text}\nInstructions: {recipe.instructions}"
                
                # Analyze with FSA dictionary
                analysis = nlp_processor.analyze_allergens(text)
                
                # Prepare data for saving
                analysis_data = {
                    'recipe': recipe,
                    'risk_level': analysis.risk_level,
                    'confidence_scores': analysis.confidence_scores,
                    'detected_allergens': {k: [m.text for m in v] for k, v in analysis.detected_allergens.items()},
                    'recommendations': analysis.recommendations,
                    'total_ingredients': len(nlp_processor.extract_ingredients(text)),
                    'analyzed_ingredients': len(nlp_processor.extract_ingredients(text)),
                    'analysis_date': timezone.now()
                }

                if existing_analysis and force:
                    # Update existing analysis
                    for field, value in analysis_data.items():
                        if field != 'recipe':  # Don't update the recipe field
                            setattr(existing_analysis, field, value)
                    existing_analysis.save()
                    updated += 1
                else:
                    # Create new analysis
                    AllergenAnalysisResult.objects.create(**analysis_data)
                    updated += 1

                processed += 1

                # Show progress for first few recipes
                if processed <= 5:
                    self.stdout.write(
                        f'  ✓ {recipe.title[:50]}... -> {analysis.risk_level} '
                        f'({len(analysis.detected_allergens)} allergens)'
                    )

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error analyzing {recipe.title}: {e}')
                )

        return processed, updated, errors

    def _show_analysis_preview(self, nlp_processor, recipes):
        """Show preview of what analysis would look like"""
        self.stdout.write('\nAnalysis Preview:')
        self.stdout.write('-' * 40)
        
        for recipe in recipes:
            try:
                text = f"Ingredients: {recipe.scraped_ingredients_text}\nInstructions: {recipe.instructions}"
                analysis = nlp_processor.analyze_allergens(text)
                
                self.stdout.write(
                    f'{recipe.title[:40]}... -> {analysis.risk_level} '
                    f'({list(analysis.detected_allergens.keys())})'
                )
            except Exception as e:
                self.stdout.write(f'{recipe.title[:40]}... -> ERROR: {e}')

    def _show_final_statistics(self):
        """Show final database statistics"""
        total_recipes = Recipe.objects.count()
        recipes_with_analysis = Recipe.objects.filter(analysis_result__isnull=False).count()
        
        # Risk level distribution
        risk_levels = Recipe.objects.values('risk_level').annotate(
            count=Count('id')
        ).order_by('risk_level')
        
        self.stdout.write('\nDATABASE STATISTICS')
        self.stdout.write('-' * 30)
        self.stdout.write(f'Total recipes: {total_recipes}')
        self.stdout.write(f'Recipes with analysis: {recipes_with_analysis}')
        
        self.stdout.write('\nRisk level distribution:')
        for level in risk_levels:
            if level['risk_level']:
                self.stdout.write(f'  {level["risk_level"]}: {level["count"]}')
        
        # FSA allergen detection summary
        self.stdout.write('\nFSA Allergen Detection Summary:')
        allergen_counts = {}
        for recipe in Recipe.objects.filter(analysis_result__isnull=False):
            if recipe.analysis_result and recipe.analysis_result.detected_allergens:
                for allergen in recipe.analysis_result.detected_allergens.keys():
                    allergen_counts[allergen] = allergen_counts.get(allergen, 0) + 1
        
        for allergen, count in sorted(allergen_counts.items(), key=lambda x: x[1], reverse=True):
            self.stdout.write(f'  {allergen}: {count} recipes') 