from django.core.management.base import BaseCommand
from scraper.nlp_ingredient_processor import NLPIngredientProcessor
import subprocess
import sys
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Export feedback and retrain the spaCy NER model for allergen detection.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Exporting feedback for NER retraining...'))
        processor = NLPIngredientProcessor()
        processor.export_feedback_for_retraining()
        self.stdout.write(self.style.SUCCESS('Feedback exported to feedback_training_data.json.'))

        self.stdout.write(self.style.NOTICE('Running spaCy NER training script...'))
        try:
            result = subprocess.run([sys.executable, 'train_allergen_ner.py'], capture_output=True, text=True, check=True)
            self.stdout.write(self.style.SUCCESS('NER model retrained successfully.'))
            self.stdout.write(result.stdout)
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR('NER training failed!'))
            self.stdout.write(e.stdout)
            self.stdout.write(e.stderr)
        self.stdout.write(self.style.SUCCESS('Retraining process complete.')) 