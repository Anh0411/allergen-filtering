import sys
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from recipes.models import AllergenCategory, AllergenSynonym

# Setup path to use the FSA allergen dictionary
ALLERGEN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'allergen_filtering')
sys.path.append(ALLERGEN_PATH)

try:
    from allergen_filtering.fsa_allergen_dictionary import get_fsa_allergen_dictionary
except ImportError:
    # Try alternative import path
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
    from allergen_filtering.fsa_allergen_dictionary import get_fsa_allergen_dictionary

class Command(BaseCommand):
    help = 'Populate the database with FSA-aligned allergen dictionary (14 allergen groups)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing allergen data before populating',
        )
        parser.add_argument(
            '--dict-version',
            type=str,
            default='FSA-1.0',
            help='Version identifier for the allergen dictionary',
        )

    def handle(self, *args, **options):
        clear_existing = options['clear']
        dict_version = options['dict_version']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting FSA allergen dictionary population (version: {dict_version})')
        )
        
        # Get the FSA allergen dictionary
        allergen_dict = get_fsa_allergen_dictionary()
        
        if clear_existing:
            self.stdout.write('Clearing existing allergen data...')
            AllergenCategory.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Existing allergen data cleared'))
        
        # Track statistics
        categories_created = 0
        terms_created = 0
        
        with transaction.atomic():
            for category_key, allergen_info in allergen_dict.allergens.items():
                # Create or update allergen category
                category, created = AllergenCategory.objects.get_or_create(
                    name=allergen_info.name,
                    defaults={
                        'slug': category_key,
                        'description': allergen_info.description,
                        'is_major_allergen': True
                    }
                )
                
                if created:
                    categories_created += 1
                    self.stdout.write(f'Created category: {allergen_info.name}')
                else:
                    # Update existing category
                    category.description = allergen_info.description
                    category.is_major_allergen = True
                    category.save()
                    self.stdout.write(f'Updated category: {allergen_info.name}')
                
                # Clear existing synonyms for this category
                category.synonyms.all().delete()
                
                # Track unique terms for this category
                unique_terms = set()
                
                # Add main ingredients
                for ingredient in allergen_info.main_ingredients:
                    term_lc = ingredient.lower()
                    if term_lc not in unique_terms:
                        AllergenSynonym.objects.create(
                            allergen_category=category,
                            term=ingredient,
                            term_type='main_ingredient',
                            confidence_score=1.0,
                            is_active=True
                        )
                        unique_terms.add(term_lc)
                        terms_created += 1
                
                # Add synonyms
                for synonym in allergen_info.synonyms:
                    term_lc = synonym.lower()
                    if term_lc not in unique_terms:
                        AllergenSynonym.objects.create(
                            allergen_category=category,
                            term=synonym,
                            term_type='synonym',
                            confidence_score=0.9,
                            is_active=True
                        )
                        unique_terms.add(term_lc)
                        terms_created += 1
                
                # Add scientific names
                for scientific_name in allergen_info.scientific_names:
                    term_lc = scientific_name.lower()
                    if term_lc not in unique_terms:
                        AllergenSynonym.objects.create(
                            allergen_category=category,
                            term=scientific_name,
                            term_type='scientific_name',
                            confidence_score=0.95,
                            is_active=True
                        )
                        unique_terms.add(term_lc)
                        terms_created += 1
                
                # Add hidden sources
                for hidden_source in allergen_info.hidden_sources:
                    term_lc = hidden_source.lower()
                    if term_lc not in unique_terms:
                        AllergenSynonym.objects.create(
                            allergen_category=category,
                            term=hidden_source,
                            term_type='hidden_source',
                            confidence_score=0.8,
                            is_active=True
                        )
                        unique_terms.add(term_lc)
                        terms_created += 1
        
        # Print summary
        self.stdout.write(self.style.SUCCESS('\nFSA Allergen Dictionary Population Complete!'))
        self.stdout.write(f'Version: {dict_version}')
        self.stdout.write(f'Categories: {categories_created}')
        self.stdout.write(f'Total Terms: {terms_created}')
        
        # List the 14 FSA allergen categories
        self.stdout.write('\nFSA 14 Allergen Categories:')
        for category_key, allergen_info in allergen_dict.allergens.items():
            self.stdout.write(f'  - {allergen_info.name}')
        
        self.stdout.write(
            self.style.SUCCESS('\nAllergen dictionary is now aligned with UK Food Standards Agency requirements!')
        ) 