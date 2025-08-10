from django.core.management.base import BaseCommand
from scraper.nlp_ingredient_processor import NLPIngredientProcessor
import subprocess
import sys
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Export feedback and retrain the spaCy NER model using the scalable docbin workflow.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-merge',
            action='store_true',
            help='Skip merging with auto-generated data (use only feedback data)'
        )
        parser.add_argument(
            '--config',
            type=str,
            default='config.cfg',
            help='Path to spaCy config file (default: config.cfg)'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='./output/spacy_ner_model',
            help='Output directory for trained model (default: ./output/spacy_ner_model)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting scalable NER retraining pipeline...'))
        
        # Step 1: Export feedback data
        self.stdout.write('Step 1: Exporting feedback for NER retraining...')
        processor = NLPIngredientProcessor()
        processor.export_feedback_for_retraining()
        self.stdout.write(self.style.SUCCESS('✓ Feedback exported to feedback_training_data.json'))

        # Step 2: Merge with auto-generated data (optional)
        if not options['skip_merge']:
            self.stdout.write('Step 2: Merging with auto-generated training data...')
            try:
                result = subprocess.run([sys.executable, 'merge_ner_training_data.py'], 
                                      capture_output=True, text=True, check=True)
                self.stdout.write(self.style.SUCCESS('✓ Data merged to merged_ner_training_data.json'))
                self.stdout.write(result.stdout.strip())
            except subprocess.CalledProcessError as e:
                self.stdout.write(self.style.WARNING('⚠ Merge failed, using only feedback data'))
                self.stdout.write(e.stderr.strip())
        else:
            self.stdout.write(self.style.NOTICE('Step 2: Skipping merge (using only feedback data)'))

        # Step 3: Convert to DocBin format
        self.stdout.write('Step 3: Converting to spaCy DocBin format...')
        try:
            result = subprocess.run([sys.executable, 'convert_json_to_docbin.py'], 
                                  capture_output=True, text=True, check=True)
            self.stdout.write(self.style.SUCCESS('✓ Converted to ner_training_data.spacy'))
            self.stdout.write(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR('✗ DocBin conversion failed!'))
            self.stdout.write(e.stderr.strip())
            return

        # Step 4: Split into train/dev sets
        self.stdout.write('Step 4: Splitting into train/dev sets...')
        try:
            result = subprocess.run([sys.executable, 'split_docbin_train_dev.py'], 
                                  capture_output=True, text=True, check=True)
            self.stdout.write(self.style.SUCCESS('✓ Split into train.spacy and dev.spacy'))
            self.stdout.write(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR('✗ Data splitting failed!'))
            self.stdout.write(e.stderr.strip())
            return

        # Step 5: Train with spaCy config
        self.stdout.write('Step 5: Training NER model with professional config...')
        try:
            cmd = [
                'spacy', 'train', options['config'],
                '--paths.train', 'train.spacy',
                '--paths.dev', 'dev.spacy',
                '--output', options['output']
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.stdout.write(self.style.SUCCESS('✓ NER model trained successfully'))
            self.stdout.write(f'Model saved to: {options["output"]}')
            
            # Show final evaluation results
            if 'ents_f' in result.stdout:
                lines = result.stdout.split('\n')
                for line in lines[-10:]:  # Show last 10 lines (usually contains final metrics)
                    if 'ents_f' in line or 'ents_p' in line or 'ents_r' in line:
                        self.stdout.write(line.strip())
                        
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR('✗ NER training failed!'))
            self.stdout.write(e.stderr.strip())
            return

        self.stdout.write(self.style.SUCCESS('🎉 Scalable NER retraining pipeline completed successfully!'))
        self.stdout.write(f'New model available at: {options["output"]}') 