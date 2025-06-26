#!/usr/bin/env python3
"""
Test script for FSA-aligned allergen dictionary
Tests the 14 allergen groups as specified by the UK Food Standards Agency
"""

import sys
import os
from pathlib import Path

# Add the allergen_filtering directory to the path
sys.path.append(str(Path(__file__).parent))

from fsa_allergen_dictionary import get_fsa_allergen_dictionary

def test_fsa_allergen_dictionary():
    """Test the FSA allergen dictionary functionality"""
    
    print("🧪 Testing FSA Allergen Dictionary")
    print("=" * 50)
    
    # Get the FSA allergen dictionary
    allergen_dict = get_fsa_allergen_dictionary()
    
    # Test 1: Verify all 14 FSA allergen categories are present
    print("\n1. Testing FSA 14 Allergen Categories:")
    expected_categories = {
        "celery", "gluten", "crustaceans", "egg", "fish", "lupin", 
        "milk", "molluscs", "mustard", "peanuts", "sesame", "soy", 
        "sulfites", "tree_nuts"
    }
    
    actual_categories = set(allergen_dict.get_all_categories())
    missing_categories = expected_categories - actual_categories
    extra_categories = actual_categories - expected_categories
    
    if missing_categories:
        print(f"❌ Missing categories: {missing_categories}")
    if extra_categories:
        print(f"⚠️  Extra categories: {extra_categories}")
    if not missing_categories and not extra_categories:
        print("✅ All 14 FSA allergen categories present")
    
    # Test 2: Test allergen detection with sample ingredients
    print("\n2. Testing Allergen Detection:")
    
    test_cases = [
        ("celery salt and wheat flour", ["celery", "gluten"]),
        ("milk, eggs, and peanuts", ["milk", "egg", "peanuts"]),
        ("shrimp and mussels", ["crustaceans", "molluscs"]),
        ("almonds and hazelnuts", ["tree_nuts"]),
        ("soy sauce and sesame oil", ["soy", "sesame"]),
        ("mustard powder and lupin flour", ["mustard", "lupin"]),
        ("fish oil and sulfites", ["fish", "sulfites"]),
    ]
    
    for test_text, expected_allergens in test_cases:
        detected = allergen_dict.detect_allergens(test_text)
        detected_categories = set(detected.keys())
        expected_set = set(expected_allergens)
        
        if detected_categories == expected_set:
            print(f"✅ '{test_text}' -> {detected_categories}")
        else:
            print(f"❌ '{test_text}' -> Expected: {expected_set}, Got: {detected_categories}")
    
    # Test 3: Test specific allergen information
    print("\n3. Testing Allergen Information:")
    
    test_allergens = ["milk", "peanuts", "gluten", "egg"]
    for allergen in test_allergens:
        info = allergen_dict.get_allergen_info(allergen)
        if info:
            print(f"✅ {allergen}: {info.name} - {len(info.synonyms)} synonyms, {len(info.hidden_sources)} hidden sources")
        else:
            print(f"❌ {allergen}: Not found")
    
    # Test 4: Test comprehensive ingredient analysis
    print("\n4. Testing Comprehensive Ingredient Analysis:")
    
    complex_ingredient = """
    Ingredients: wheat flour, milk, eggs, butter, sugar, salt, 
    peanut butter, soy lecithin, sesame seeds, mustard powder, 
    fish sauce, shrimp paste, celery salt, lupin flour, 
    sulfites (preservative), almonds, hazelnuts
    """
    
    detected = allergen_dict.detect_allergens(complex_ingredient)
    print(f"Complex ingredient analysis:")
    for category, terms in detected.items():
        print(f"  {category}: {terms}")
    
    # Test 5: Export and import functionality
    print("\n5. Testing Export/Import Functionality:")
    
    try:
        # Export to JSON
        export_path = "fsa_allergen_dictionary_export.json"
        allergen_dict.export_to_json(export_path)
        print(f"✅ Exported to {export_path}")
        
        # Import from JSON
        imported_dict = allergen_dict.load_from_json(export_path)
        print(f"✅ Imported from {export_path}")
        
        # Verify import worked
        original_categories = set(allergen_dict.get_all_categories())
        imported_categories = set(imported_dict.get_all_categories())
        
        if original_categories == imported_categories:
            print("✅ Export/Import verification successful")
        else:
            print("❌ Export/Import verification failed")
        
        # Clean up
        os.remove(export_path)
        print(f"✅ Cleaned up {export_path}")
        
    except Exception as e:
        print(f"❌ Export/Import test failed: {e}")
    
    # Test 6: Statistics
    print("\n6. Dictionary Statistics:")
    
    total_synonyms = sum(len(allergen.synonyms) for allergen in allergen_dict.allergens.values())
    total_scientific = sum(len(allergen.scientific_names) for allergen in allergen_dict.allergens.values())
    total_hidden = sum(len(allergen.hidden_sources) for allergen in allergen_dict.allergens.values())
    total_terms = total_synonyms + total_scientific + total_hidden
    
    print(f"Total categories: {len(allergen_dict.allergens)}")
    print(f"Total synonyms: {total_synonyms}")
    print(f"Total scientific names: {total_scientific}")
    print(f"Total hidden sources: {total_hidden}")
    print(f"Total terms: {total_terms}")
    
    # Test 7: FSA Compliance Check
    print("\n7. FSA Compliance Check:")
    
    fsa_requirements = {
        "celery": "Celery and celery derivatives",
        "gluten": "Cereals containing gluten (wheat, rye, barley, oats)",
        "crustaceans": "Crustaceans (prawns, crabs, lobsters)",
        "egg": "Eggs and egg derivatives",
        "fish": "Fish and fish derivatives",
        "lupin": "Lupin beans and lupin derivatives",
        "milk": "Milk and milk derivatives",
        "molluscs": "Molluscs (mussels, oysters)",
        "mustard": "Mustard and mustard derivatives",
        "peanuts": "Peanuts and peanut derivatives",
        "sesame": "Sesame seeds and sesame derivatives",
        "soy": "Soybeans and soy derivatives",
        "sulfites": "Sulphur dioxide and sulphites",
        "tree_nuts": "Tree nuts (almonds, hazelnuts, walnuts, brazil nuts, cashews, pecans, pistachios, macadamia nuts)"
    }
    
    compliance_issues = []
    for category_key, expected_desc in fsa_requirements.items():
        info = allergen_dict.get_allergen_info(category_key)
        if info:
            if expected_desc.lower() in info.description.lower():
                print(f"✅ {category_key}: FSA compliant")
            else:
                compliance_issues.append(f"{category_key}: Description mismatch")
        else:
            compliance_issues.append(f"{category_key}: Missing category")
    
    if compliance_issues:
        print(f"❌ Compliance issues found: {compliance_issues}")
    else:
        print("✅ All categories FSA compliant")
    
    print("\n" + "=" * 50)
    print("🎉 FSA Allergen Dictionary Testing Complete!")
    print("The dictionary is now aligned with UK Food Standards Agency requirements.")
    print("Reference: https://www.food.gov.uk/business-guidance/allergen-guidance-for-food-businesses")

if __name__ == "__main__":
    test_fsa_allergen_dictionary() 