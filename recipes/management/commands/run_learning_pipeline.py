from django.core.management.base import BaseCommand
from scraper.nlp_ingredient_processor import get_nlp_processor
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Run the complete learning pipeline using existing NLP processor methods'

    def add_arguments(self, parser):
        parser.add_argument(
            '--discover-terms',
            action='store_true',
            help='Discover new terms from detection logs'
        )
        parser.add_argument(
            '--learn-patterns',
            action='store_true',
            help='Learn from detection patterns'
        )
        parser.add_argument(
            '--export-training',
            action='store_true',
            help='Export feedback for NER retraining'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all learning steps'
        )

    def handle(self, *args, **options):
        processor = get_nlp_processor()
        
        self.stdout.write(
            self.style.SUCCESS('Starting learning pipeline...')
        )
        
        # Discover new terms
        if options['discover_terms'] or options['all']:
            self.stdout.write('Discovering new terms...')
            new_terms = processor.discover_new_terms()
            self.stdout.write(
                self.style.SUCCESS(f'Found {len(new_terms)} potential new terms')
            )
            
            if new_terms:
                self.stdout.write('New terms found:')
                for term_data in new_terms[:10]:  # Show first 10
                    self.stdout.write(f"  - {term_data['term']} (frequency: {term_data['frequency']})")
        
        # Learn from patterns
        if options['learn_patterns'] or options['all']:
            self.stdout.write('Learning from patterns...')
            processor.learn_from_patterns()
            self.stdout.write(
                self.style.SUCCESS('Pattern learning completed')
            )
        
        # Export training data
        if options['export_training'] or options['all']:
            self.stdout.write('Exporting feedback for NER retraining...')
            processor.export_feedback_for_retraining()
            self.stdout.write(
                self.style.SUCCESS('Training data exported')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Learning pipeline completed!')
        ) 