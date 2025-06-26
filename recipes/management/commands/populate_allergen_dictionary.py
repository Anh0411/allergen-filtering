#!/usr/bin/env python3
"""
Django management command to populate the allergen dictionary
"""

import sys
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone

# Add the allergen_filtering directory to the path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'allergen_filtering'))

from allergen_dictionary import get_allergen_dictionary
from recipes.models import AllergenCategory, AllergenSynonym, AllergenDictionaryVersion


class Command(BaseCommand):
    help = 'Populate the allergen dictionary with comprehensive allergen data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dict-version',
            type=str,
            default='1.0.0',
            help='Version number for the allergen dictionary'
        )
        parser.add_argument(
            '--description',
            type=str,
            default='Initial allergen dictionary population',
            help='Description for the allergen dictionary version'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of existing allergen categories'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting allergen dictionary population...')
        )

        version = options['dict_version']
        description = options['description']
        force = options['force']

        try:
            with transaction.atomic():
                # Get the allergen dictionary
                allergen_dict = get_allergen_dictionary()
                
                # Create or update allergen dictionary version
                dict_version, created = AllergenDictionaryVersion.objects.get_or_create(
                    version=version,
                    defaults={
                        'description': description,
                        'total_categories': len(allergen_dict.allergens),
                        'total_terms': sum(
                            len(allergen.main_ingredients) + 
                            len(allergen.synonyms) + 
                            len(allergen.scientific_names) + 
                            len(allergen.hidden_sources)
                            for allergen in allergen_dict.allergens.values()
                        ),
                        'is_active': True,
                        'activated_at': timezone.now()
                    }
                )

                if not created:
                    if force:
                        self.stdout.write(
                            self.style.WARNING(f'Updating existing version {version}')
                        )
                        dict_version.description = description
                        dict_version.save()
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'Version {version} already exists. Use --force to update.')
                        )
                        return

                # Deactivate other versions
                AllergenDictionaryVersion.objects.exclude(id=dict_version.id).update(is_active=False)

                # Process each allergen category
                total_categories = 0
                total_synonyms = 0

                for category_key, allergen_data in allergen_dict.allergens.items():
                    self.stdout.write(f'Processing {allergen_data.name}...')

                    # Create or update allergen category
                    category, created = AllergenCategory.objects.get_or_create(
                        slug=slugify(category_key),
                        defaults={
                            'name': allergen_data.name,
                            'description': allergen_data.description,
                            'is_major_allergen': True
                        }
                    )

                    if not created and force:
                        category.name = allergen_data.name
                        category.description = allergen_data.description
                        category.save()

                    if created or force:
                        # Clear existing synonyms if forcing update
                        if force:
                            AllergenSynonym.objects.filter(allergen_category=category).delete()

                        # Add main ingredients
                        for ingredient in allergen_data.main_ingredients:
                            AllergenSynonym.objects.get_or_create(
                                allergen_category=category,
                                term=ingredient.lower(),
                                defaults={
                                    'term_type': 'main_ingredient',
                                    'confidence_score': 1.0,
                                    'is_active': True
                                }
                            )
                            total_synonyms += 1

                        # Add synonyms
                        for synonym in allergen_data.synonyms:
                            AllergenSynonym.objects.get_or_create(
                                allergen_category=category,
                                term=synonym.lower(),
                                defaults={
                                    'term_type': 'synonym',
                                    'confidence_score': 0.8,
                                    'is_active': True
                                }
                            )
                            total_synonyms += 1

                        # Add scientific names
                        for scientific_name in allergen_data.scientific_names:
                            AllergenSynonym.objects.get_or_create(
                                allergen_category=category,
                                term=scientific_name.lower(),
                                defaults={
                                    'term_type': 'scientific_name',
                                    'confidence_score': 0.9,
                                    'is_active': True
                                }
                            )
                            total_synonyms += 1

                        # Add hidden sources
                        for hidden_source in allergen_data.hidden_sources:
                            AllergenSynonym.objects.get_or_create(
                                allergen_category=category,
                                term=hidden_source.lower(),
                                defaults={
                                    'term_type': 'hidden_source',
                                    'confidence_score': 0.7,
                                    'is_active': True
                                }
                            )
                            total_synonyms += 1

                    total_categories += 1

                # Update version with actual counts
                dict_version.total_categories = total_categories
                dict_version.total_terms = total_synonyms
                dict_version.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully populated allergen dictionary!\n'
                        f'Version: {version}\n'
                        f'Categories: {total_categories}\n'
                        f'Total terms: {total_synonyms}'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error populating allergen dictionary: {e}')
            )
            raise


if __name__ == '__main__':
    # For testing outside of Django
    import django
    django.setup()
    
    command = Command()
    command.handle(dict_version='1.0.0', description='Test population', force=True) 