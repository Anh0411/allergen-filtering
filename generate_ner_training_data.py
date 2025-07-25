import os
import django
import json
from allergen_filtering.fsa_allergen_dictionary import FSAAllergenDictionary

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from recipes.models import Recipe

OUTPUT_PATH = 'auto_ner_training_data.json'
allergen_dict = FSAAllergenDictionary()

training_data = []
count = 0

for recipe in Recipe.objects.all():
    # Use scraped_ingredients_text if available, else skip
    text = recipe.scraped_ingredients_text if hasattr(recipe, 'scraped_ingredients_text') else None
    if not text:
        continue
    if isinstance(text, list):
        text = ', '.join(text)
    text_lower = text.lower()
    # For each allergen category, find all terms
    for category, pattern in allergen_dict.regex_patterns.items():
        for match in pattern.finditer(text_lower):
            start, end = match.start(), match.end()
            # Use the original text for indices
            matched_text = text[start:end]
            # Add the example
            training_data.append((text, {"entities": [(start, end, category.upper())]}))
            count += 1

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(training_data, f, indent=2, ensure_ascii=False)

print(f"Generated {count} NER training examples from recipes. Output: {OUTPUT_PATH}") 