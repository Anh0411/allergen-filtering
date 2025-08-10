from django.core.management.base import BaseCommand
from django.db import transaction
from recipes.models import AllergenCategory, AllergenSynonym
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Populate enhanced allergen synonyms with different term types and confidence scores'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting enhanced allergen synonym population...'))
        
        with transaction.atomic():
            # Clear existing synonyms
            AllergenSynonym.objects.all().delete()
            self.stdout.write('Cleared existing synonyms')
            
            # Enhanced allergen data with term types and confidence scores
            enhanced_allergens = {
                'milk': {
                    'main_ingredients': [
                        ('milk', 1.0),
                        ('cheese', 1.0),
                        ('yogurt', 1.0),
                        ('cream', 1.0),
                        ('butter', 1.0),
                        ('eggs', 1.0),
                    ],
                    'scientific_names': [
                        ('lactose', 0.9),
                        ('casein', 0.9),
                        ('whey protein', 0.9),
                        ('lactalbumin', 0.9),
                        ('lactoglobulin', 0.9),
                    ],
                    'synonyms': [
                        ('dairy', 0.8),
                        ('dairy products', 0.8),
                        ('milk solids', 0.8),
                        ('milk protein', 0.8),
                        ('milk powder', 0.8),
                        ('evaporated milk', 0.8),
                        ('condensed milk', 0.8),
                        ('buttermilk', 0.8),
                        ('sour cream', 0.8),
                        ('heavy cream', 0.8),
                        ('half and half', 0.8),
                        ('whipping cream', 0.8),
                        ('ice cream', 0.8),
                        ('milk chocolate', 0.8),
                        ('white chocolate', 0.8),
                    ],
                    'hidden_sources': [
                        ('casein', 0.7),
                        ('whey', 0.7),
                        ('lactose', 0.7),
                        ('milk protein isolate', 0.7),
                        ('milk protein concentrate', 0.7),
                        ('milk protein hydrolysate', 0.7),
                        ('lactalbumin', 0.7),
                        ('lactoglobulin', 0.7),
                        ('milk fat', 0.7),
                        ('milk sugar', 0.7),
                    ]
                },
                'nuts': {
                    'main_ingredients': [
                        ('almond', 1.0),
                        ('almonds', 1.0),
                        ('walnut', 1.0),
                        ('walnuts', 1.0),
                        ('pecan', 1.0),
                        ('pecans', 1.0),
                        ('cashew', 1.0),
                        ('cashews', 1.0),
                        ('pistachio', 1.0),
                        ('pistachios', 1.0),
                        ('hazelnut', 1.0),
                        ('hazelnuts', 1.0),
                        ('macadamia', 1.0),
                        ('macadamias', 1.0),
                        ('brazil nut', 1.0),
                        ('brazil nuts', 1.0),
                        ('pine nut', 1.0),
                        ('pine nuts', 1.0),
                        ('chestnut', 1.0),
                        ('chestnuts', 1.0),
                    ],
                    'scientific_names': [
                        ('prunus dulcis', 0.9),  # almond
                        ('juglans regia', 0.9),  # walnut
                        ('carya illinoinensis', 0.9),  # pecan
                        ('anacardium occidentale', 0.9),  # cashew
                        ('pistacia vera', 0.9),  # pistachio
                        ('corylus avellana', 0.9),  # hazelnut
                        ('macadamia integrifolia', 0.9),  # macadamia
                        ('bertholletia excelsa', 0.9),  # brazil nut
                        ('pinus pinea', 0.9),  # pine nut
                        ('castanea sativa', 0.9),  # chestnut
                    ],
                    'synonyms': [
                        ('almond milk', 0.8),
                        ('almond butter', 0.8),
                        ('almond flour', 0.8),
                        ('almond extract', 0.8),
                        ('walnut oil', 0.8),
                        ('pecan oil', 0.8),
                        ('hazelnut oil', 0.8),
                        ('nut butter', 0.8),
                        ('nut milk', 0.8),
                        ('mixed nuts', 0.8),
                        ('tree nuts', 0.8),
                    ],
                    'hidden_sources': [
                        ('almond protein', 0.7),
                        ('walnut protein', 0.7),
                        ('cashew protein', 0.7),
                        ('nut protein isolate', 0.7),
                        ('nut protein concentrate', 0.7),
                        ('almond oil', 0.7),
                        ('walnut oil', 0.7),
                        ('pecan oil', 0.7),
                        ('hazelnut oil', 0.7),
                        ('nut extract', 0.7),
                    ]
                },
                'peanuts': {
                    'main_ingredients': [
                        ('peanut', 1.0),
                        ('peanuts', 1.0),
                        ('groundnut', 1.0),
                        ('groundnuts', 1.0),
                    ],
                    'scientific_names': [
                        ('arachis hypogaea', 0.9),
                        ('arachis oil', 0.9),
                    ],
                    'synonyms': [
                        ('peanut butter', 0.8),
                        ('peanut oil', 0.8),
                        ('peanut flour', 0.8),
                        ('peanut protein', 0.8),
                        ('peanut extract', 0.8),
                        ('peanut sauce', 0.8),
                        ('peanut paste', 0.8),
                        ('peanut milk', 0.8),
                    ],
                    'hidden_sources': [
                        ('peanut protein isolate', 0.7),
                        ('peanut protein concentrate', 0.7),
                        ('peanut protein hydrolysate', 0.7),
                        ('arachis oil', 0.7),
                        ('peanut lecithin', 0.7),
                    ]
                },
                'soybeans': {
                    'main_ingredients': [
                        ('soy', 1.0),
                        ('soya', 1.0),
                        ('soybean', 1.0),
                        ('soybeans', 1.0),
                    ],
                    'scientific_names': [
                        ('glycine max', 0.9),
                        ('soy protein isolate', 0.9),
                        ('soy protein concentrate', 0.9),
                    ],
                    'synonyms': [
                        ('soy milk', 0.8),
                        ('soy sauce', 0.8),
                        ('soy oil', 0.8),
                        ('soy flour', 0.8),
                        ('soy protein', 0.8),
                        ('soy lecithin', 0.8),
                        ('soy isolate', 0.8),
                        ('soy concentrate', 0.8),
                        ('soy fiber', 0.8),
                        ('soy nuts', 0.8),
                        ('soy yogurt', 0.8),
                        ('soy cheese', 0.8),
                        ('tofu', 0.8),
                        ('tempeh', 0.8),
                        ('miso', 0.8),
                        ('edamame', 0.8),
                        ('soybean oil', 0.8),
                        ('soybean flour', 0.8),
                        ('soybean protein', 0.8),
                        ('soybean lecithin', 0.8),
                        ('soybean isolate', 0.8),
                    ],
                    'hidden_sources': [
                        ('soy protein isolate', 0.7),
                        ('soy protein concentrate', 0.7),
                        ('soy protein hydrolysate', 0.7),
                        ('soy lecithin', 0.7),
                        ('soy fiber', 0.7),
                        ('soy flour', 0.7),
                        ('soy oil', 0.7),
                        ('soy extract', 0.7),
                    ]
                },
                'wheat': {
                    'main_ingredients': [
                        ('wheat', 1.0),
                        ('rye', 1.0),
                        ('barley', 1.0),
                        ('oats', 1.0),
                        ('gluten', 1.0),
                    ],
                    'scientific_names': [
                        ('triticum aestivum', 0.9),  # wheat
                        ('secale cereale', 0.9),     # rye
                        ('hordeum vulgare', 0.9),    # barley
                        ('avena sativa', 0.9),       # oats
                        ('wheat protein isolate', 0.9),
                        ('rye protein isolate', 0.9),
                        ('barley protein isolate', 0.9),
                        ('oat protein isolate', 0.9),
                    ],
                    'synonyms': [
                        ('wheat flour', 0.8),
                        ('rye flour', 0.8),
                        ('barley flour', 0.8),
                        ('oat flour', 0.8),
                        ('wheat bread', 0.8),
                        ('rye bread', 0.8),
                        ('barley bread', 0.8),
                        ('oat bread', 0.8),
                        ('wheat pasta', 0.8),
                        ('rye pasta', 0.8),
                        ('barley pasta', 0.8),
                        ('oat pasta', 0.8),
                        ('wheat cereal', 0.8),
                        ('rye cereal', 0.8),
                        ('barley cereal', 0.8),
                        ('oat cereal', 0.8),
                        ('semolina', 0.8),
                        ('bulgur', 0.8),
                        ('couscous', 0.8),
                        ('farro', 0.8),
                        ('spelt', 0.8),
                        ('kamut', 0.8),
                        ('triticale', 0.8),
                        ('durum wheat', 0.8),
                        ('wheat bran', 0.8),
                        ('wheat germ', 0.8),
                        ('wheat starch', 0.8),
                        ('wheat protein', 0.8),
                        ('wheat gluten', 0.8),
                        ('rye bran', 0.8),
                        ('rye germ', 0.8),
                        ('rye starch', 0.8),
                        ('rye protein', 0.8),
                        ('rye gluten', 0.8),
                        ('barley bran', 0.8),
                        ('barley germ', 0.8),
                        ('barley starch', 0.8),
                        ('barley protein', 0.8),
                        ('barley gluten', 0.8),
                        ('oat bran', 0.8),
                        ('oat germ', 0.8),
                        ('oat starch', 0.8),
                        ('oat protein', 0.8),
                        ('oat gluten', 0.8),
                        ('oatmeal', 0.8),
                        ('rolled oats', 0.8),
                        ('steel cut oats', 0.8),
                        ('pearl barley', 0.8),
                        ('barley malt', 0.8),
                        ('rye malt', 0.8),
                        ('wheat malt', 0.8),
                        ('oat malt', 0.8),
                    ],
                    'hidden_sources': [
                        ('wheat protein isolate', 0.7),
                        ('rye protein isolate', 0.7),
                        ('barley protein isolate', 0.7),
                        ('oat protein isolate', 0.7),
                        ('wheat protein concentrate', 0.7),
                        ('rye protein concentrate', 0.7),
                        ('barley protein concentrate', 0.7),
                        ('oat protein concentrate', 0.7),
                        ('wheat protein hydrolysate', 0.7),
                        ('rye protein hydrolysate', 0.7),
                        ('barley protein hydrolysate', 0.7),
                        ('oat protein hydrolysate', 0.7),
                        ('vital wheat gluten', 0.7),
                        ('vital rye gluten', 0.7),
                        ('vital barley gluten', 0.7),
                        ('vital oat gluten', 0.7),
                        ('seitan', 0.7),
                        ('wheat protein derivative', 0.7),
                        ('rye protein derivative', 0.7),
                        ('barley protein derivative', 0.7),
                        ('oat protein derivative', 0.7),
                        ('all purpose flour', 0.7),
                        ('bread flour', 0.7),
                        ('cake flour', 0.7),
                        ('cereal extract', 0.7),
                        ('club wheat', 0.7),
                        ('common wheat', 0.7),
                        ('durum wheat', 0.7),
                        ('farina', 0.7),
                        ('graham flour', 0.7),
                        ('high gluten flour', 0.7),
                        ('high protein flour', 0.7),
                        ('whole wheat flour', 0.7),
                        ('whole wheat bread', 0.7),
                        ('whole rye flour', 0.7),
                        ('whole rye bread', 0.7),
                        ('whole barley flour', 0.7),
                        ('whole barley bread', 0.7),
                        ('whole oat flour', 0.7),
                        ('whole oat bread', 0.7),
                    ]
                }
            }
            
            # Create synonyms for each allergen category
            for category_name, term_data in enhanced_allergens.items():
                try:
                    # Get or create allergen category
                    category, created = AllergenCategory.objects.get_or_create(
                        name=category_name.title(),
                        defaults={
                            'slug': category_name.lower(),
                            'description': f'Enhanced {category_name} allergen category',
                            'is_major_allergen': True
                        }
                    )
                    
                    if created:
                        self.stdout.write(f'Created category: {category.name}')
                    
                    # Create synonyms for each term type
                    for term_type, terms in term_data.items():
                        for term, confidence in terms:
                            synonym, created = AllergenSynonym.objects.get_or_create(
                                allergen_category=category,
                                term=term,
                                defaults={
                                    'term_type': term_type,
                                    'confidence_score': confidence,
                                    'is_active': True
                                }
                            )
                            
                            if created:
                                self.stdout.write(f'Created {term_type}: {term} (confidence: {confidence})')
                            else:
                                # Update existing synonym
                                synonym.term_type = term_type
                                synonym.confidence_score = confidence
                                synonym.is_active = True
                                synonym.save()
                                self.stdout.write(f'Updated {term_type}: {term} (confidence: {confidence})')
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error processing {category_name}: {e}'))
                    continue
            
            # Summary
            total_synonyms = AllergenSynonym.objects.count()
            total_categories = AllergenCategory.objects.count()
            
            self.stdout.write(self.style.SUCCESS(f'Enhanced allergen synonyms population completed!'))
            self.stdout.write(f'Total categories: {total_categories}')
            self.stdout.write(f'Total synonyms: {total_synonyms}')
            
            # Show breakdown by term type
            for term_type in ['main_ingredient', 'scientific_name', 'synonym', 'hidden_source']:
                count = AllergenSynonym.objects.filter(term_type=term_type).count()
                self.stdout.write(f'{term_type}: {count} terms')
