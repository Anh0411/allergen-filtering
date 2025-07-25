#!/usr/bin/env python3
"""
Analyze all Food.com recipes in the database using the NLP pipeline and save results to AllergenAnalysisResult.
"""

import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')

from recipes.models import Recipe, AllergenAnalysisResult
from allergen_filtering.nlp_processor import get_nlp_processor


def analyze_and_save():
    nlp = get_nlp_processor()
    
    # Query all Food.com recipes
    recipes = Recipe.objects.filter(original_url__icontains='food.com')
    print(f"Found {recipes.count()} Food.com recipes to analyze.")
    analyzed = 0
    skipped = 0
    errors = 0
    for recipe in recipes:
        # Skip if already analyzed
        if hasattr(recipe, 'analysis_result'):
            skipped += 1
            continue
        try:
            # Combine ingredients and instructions for analysis
            text = f"Ingredients: {recipe.scraped_ingredients_text}\nInstructions: {recipe.instructions}"
            analysis = nlp.analyze_allergens(text)
            
            # Save analysis result
            AllergenAnalysisResult.objects.create(
                recipe=recipe,
                risk_level=analysis.risk_level,
                confidence_scores=analysis.confidence_scores,
                detected_allergens={k: [m.text for m in v] for k, v in analysis.detected_allergens.items()},
                recommendations=analysis.recommendations,
                total_ingredients=len(nlp.extract_ingredients(text)),
                analyzed_ingredients=len(nlp.extract_ingredients(text)),
                processing_time=None  # Could time the analysis if desired
            )
            analyzed += 1
            print(f"Analyzed: {recipe.title} (risk: {analysis.risk_level})")
        except Exception as e:
            print(f"Error analyzing {recipe.title}: {e}")
            errors += 1
    print(f"\nDone! {analyzed} recipes analyzed, {skipped} skipped (already analyzed), {errors} errors.")


if __name__ == "__main__":
    analyze_and_save() 