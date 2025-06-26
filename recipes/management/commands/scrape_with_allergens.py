from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.utils import timezone
import logging
import sys
import os

# Add the scraper directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'scraper'))

from scraper.scrape_foodcom_with_allergen_detection import FoodComAllergenScraper

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Scrape Food.com recipes with integrated allergen detection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-page',
            type=int,
            default=1,
            help='Starting page number (default: 1)'
        )
        parser.add_argument(
            '--end-page',
            type=int,
            default=10,
            help='Ending page number (default: 10)'
        )
        parser.add_argument(
            '--max-workers',
            type=int,
            default=3,
            help='Maximum number of concurrent workers (default: 3)'
        )
        parser.add_argument(
            '--test-mode',
            action='store_true',
            help='Run in test mode with limited URLs'
        )

    def handle(self, *args, **options):
        start_page = options['start_page']
        end_page = options['end_page']
        max_workers = options['max_workers']
        test_mode = options['test_mode']

        self.stdout.write(
            self.style.SUCCESS(
                f'Starting Food.com scraper with allergen detection\n'
                f'Page range: {start_page} to {end_page}\n'
                f'Max workers: {max_workers}\n'
                f'Test mode: {test_mode}'
            )
        )

        try:
            # Initialize scraper
            scraper = FoodComAllergenScraper()
            
            # Check if NLP processor is available
            if not scraper.nlp_processor:
                self.stdout.write(
                    self.style.ERROR(
                        'NLP processor not available. Please check your installation.'
                    )
                )
                return

            if test_mode:
                # Test mode: scrape just one page with limited URLs
                self.stdout.write('Running in test mode...')
                successful, failed = self._run_test_mode(scraper, start_page, max_workers)
            else:
                # Normal mode: scrape the full range
                successful, failed = scraper.scrape_page_range(start_page, end_page, max_workers)

            # Print summary
            self.stdout.write('\n' + '=' * 50)
            self.stdout.write(self.style.SUCCESS('SCRAPING SUMMARY'))
            self.stdout.write('=' * 50)
            self.stdout.write(f'Successful scrapes: {successful}')
            self.stdout.write(f'Failed scrapes: {failed}')
            self.stdout.write(f'Total processed: {successful + failed}')
            
            if successful + failed > 0:
                success_rate = (successful / (successful + failed) * 100)
                self.stdout.write(f'Success rate: {success_rate:.1f}%')
            
            # Print database statistics
            self._print_database_stats()

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\nScraping interrupted by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nUnexpected error during scraping: {e}')
            )
            raise CommandError(f'Scraping failed: {e}')

    def _run_test_mode(self, scraper, page_num, max_workers):
        """Run scraper in test mode with limited URLs"""
        self.stdout.write(f'Testing with page {page_num}...')
        
        # Get URLs from the page
        urls = scraper.get_recipe_urls_from_page(page_num)
        self.stdout.write(f'Found {len(urls)} URLs on page {page_num}')
        
        if not urls:
            self.stdout.write(self.style.WARNING('No URLs found'))
            return 0, 0
        
        # Limit to first 3 URLs for testing
        test_urls = urls[:3]
        self.stdout.write(f'Testing with {len(test_urls)} URLs')
        
        successful = 0
        failed = 0
        
        for url in test_urls:
            self.stdout.write(f'Processing: {url}')
            try:
                success = scraper.scrape_recipe_with_allergens(url)
                if success:
                    successful += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Successfully processed: {url}')
                    )
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.WARNING(f'✗ Failed to process: {url}')
                    )
            except Exception as e:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ Exception processing {url}: {e}')
                )
        
        return successful, failed

    def _print_database_stats(self):
        """Print database statistics"""
        from recipes.models import Recipe, AllergenAnalysisResult
        
        total_recipes = Recipe.objects.count()
        recipes_with_analysis = Recipe.objects.filter(analysis_result__isnull=False).count()
        recipes_with_allergens = Recipe.objects.filter(
            risk_level__in=['medium', 'high', 'critical']
        ).count()
        
        self.stdout.write('\nDATABASE STATISTICS')
        self.stdout.write('-' * 30)
        self.stdout.write(f'Total recipes: {total_recipes}')
        self.stdout.write(f'Recipes with allergen analysis: {recipes_with_analysis}')
        self.stdout.write(f'Recipes with detected allergens: {recipes_with_allergens}')
        
        # Check risk level distribution
        risk_levels = Recipe.objects.values('risk_level').annotate(
            count=models.Count('id')
        ).order_by('risk_level')
        
        self.stdout.write('\nRisk level distribution:')
        for level in risk_levels:
            self.stdout.write(f'  {level["risk_level"]}: {level["count"]}')
        
        # Show recent recipes with allergens
        recent_allergen_recipes = Recipe.objects.filter(
            risk_level__in=['medium', 'high', 'critical']
        ).order_by('-created_at')[:5]
        
        if recent_allergen_recipes.exists():
            self.stdout.write('\nRecent recipes with allergens:')
            for recipe in recent_allergen_recipes:
                self.stdout.write(
                    f'  - {recipe.title} ({recipe.risk_level})'
                ) 