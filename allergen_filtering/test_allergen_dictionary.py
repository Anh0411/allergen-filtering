#!/usr/bin/env python3
"""
Test script for the Allergen Dictionary
Demonstrates functionality and validates detection capabilities
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from allergen_dictionary import AllergenDictionary, get_allergen_dictionary


def test_basic_functionality():
    """Test basic allergen dictionary functionality"""
    print("=== Testing Basic Functionality ===")
    
    allergen_dict = get_allergen_dictionary()
    
    # Test getting all categories
    categories = allergen_dict.get_all_categories()
    print(f"Available allergen categories: {categories}")
    print(f"Total categories: {len(categories)}")
    
    # Test getting allergen info
    milk_info = allergen_dict.get_allergen_info("milk")
    print(f"\nMilk allergen info:")
    print(f"Name: {milk_info.name}")
    print(f"Description: {milk_info.description}")
    print(f"Main ingredients: {milk_info.main_ingredients}")
    print(f"Synonyms count: {len(milk_info.synonyms)}")
    print(f"Scientific names count: {len(milk_info.scientific_names)}")
    print(f"Hidden sources count: {len(milk_info.hidden_sources)}")


def test_allergen_detection():
    """Test allergen detection in various text samples"""
    print("\n=== Testing Allergen Detection ===")
    
    allergen_dict = get_allergen_dictionary()
    
    # Test cases with different types of allergen mentions
    test_cases = [
        {
            "name": "Basic allergen names",
            "text": "This recipe contains milk, eggs, peanuts, and wheat flour."
        },
        {
            "name": "Scientific names and synonyms",
            "text": "Ingredients include casein, albumin, arachis hypogaea, and triticum aestivum."
        },
        {
            "name": "Hidden sources",
            "text": "Contains whey protein, egg lecithin, peanut flour, and vital wheat gluten."
        },
        {
            "name": "Complex recipe ingredients",
            "text": """
            Ingredients: 2 cups all-purpose flour, 1 cup milk, 2 eggs, 1/2 cup peanut butter,
            1/4 cup soy sauce, 1 tbsp sesame oil, 1 tsp fish sauce, 1/2 cup shrimp,
            natural flavoring, caramel color, and sulfites as preservatives.
            """
        },
        {
            "name": "No allergens",
            "text": "This recipe contains only vegetables: carrots, broccoli, and spinach."
        },
        {
            "name": "Mixed allergens with common names",
            "text": """
            Recipe ingredients: butter, cheese, yogurt, egg whites, almond flour,
            walnut oil, cashew butter, soy milk, wheat bread, salmon, crab meat,
            tahini, and dried apricots (contains sulfites).
            """
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---")
        print(f"Text: {test_case['text'].strip()}")
        
        detected = allergen_dict.detect_allergens(test_case['text'])
        
        if detected:
            print("Detected allergens:")
            for category, terms in detected.items():
                allergen_info = allergen_dict.get_allergen_info(category)
                print(f"  {allergen_info.name} ({category}): {terms}")
        else:
            print("No allergens detected")


def test_edge_cases():
    """Test edge cases and boundary conditions"""
    print("\n=== Testing Edge Cases ===")
    
    allergen_dict = get_allergen_dictionary()
    
    edge_cases = [
        {
            "name": "Empty text",
            "text": ""
        },
        {
            "name": "Single allergen word",
            "text": "milk"
        },
        {
            "name": "Allergen as part of other words",
            "text": "milkshake, eggnog, peanutbutter, wheatgrass"
        },
        {
            "name": "Case sensitivity",
            "text": "MILK, Milk, milk, MiLk"
        },
        {
            "name": "Punctuation and spacing",
            "text": "milk,egg,peanut;wheat.soy:fish"
        },
        {
            "name": "Very long text with allergens",
            "text": "This is a very long text that contains many words and some allergens like milk and eggs scattered throughout the content. The text continues with more words and eventually mentions other allergens such as peanuts and wheat. The purpose is to test how the allergen detection works with longer texts that have allergens embedded within them."
        }
    ]
    
    for edge_case in edge_cases:
        print(f"\n--- {edge_case['name']} ---")
        print(f"Text: {repr(edge_case['text'])}")
        
        detected = allergen_dict.detect_allergens(edge_case['text'])
        
        if detected:
            print("Detected allergens:")
            for category, terms in detected.items():
                allergen_info = allergen_dict.get_allergen_info(category)
                print(f"  {allergen_info.name} ({category}): {terms}")
        else:
            print("No allergens detected")


def test_statistics():
    """Test and display statistics about the allergen dictionary"""
    print("\n=== Allergen Dictionary Statistics ===")
    
    allergen_dict = get_allergen_dictionary()
    
    total_terms = 0
    category_stats = {}
    
    for category_name, allergen in allergen_dict.allergens.items():
        total_main = len(allergen.main_ingredients)
        total_synonyms = len(allergen.synonyms)
        total_scientific = len(allergen.scientific_names)
        total_hidden = len(allergen.hidden_sources)
        total_category = total_main + total_synonyms + total_scientific + total_hidden
        
        category_stats[category_name] = {
            "main_ingredients": total_main,
            "synonyms": total_synonyms,
            "scientific_names": total_scientific,
            "hidden_sources": total_hidden,
            "total": total_category
        }
        
        total_terms += total_category
    
    print(f"Total allergen categories: {len(category_stats)}")
    print(f"Total allergen terms: {total_terms}")
    print("\nBreakdown by category:")
    
    for category, stats in category_stats.items():
        allergen_info = allergen_dict.get_allergen_info(category)
        print(f"  {allergen_info.name} ({category}):")
        print(f"    Main ingredients: {stats['main_ingredients']}")
        print(f"    Synonyms: {stats['synonyms']}")
        print(f"    Scientific names: {stats['scientific_names']}")
        print(f"    Hidden sources: {stats['hidden_sources']}")
        print(f"    Total terms: {stats['total']}")


def test_json_export_import():
    """Test JSON export and import functionality"""
    print("\n=== Testing JSON Export/Import ===")
    
    allergen_dict = get_allergen_dictionary()
    
    # Export to JSON
    export_file = "test_allergen_dictionary.json"
    allergen_dict.export_to_json(export_file)
    print(f"Exported allergen dictionary to {export_file}")
    
    # Import from JSON
    imported_dict = AllergenDictionary.load_from_json(export_file)
    print(f"Imported allergen dictionary from {export_file}")
    
    # Test that imported dictionary works the same
    test_text = "This contains milk, eggs, and peanuts."
    original_detected = allergen_dict.detect_allergens(test_text)
    imported_detected = imported_dict.detect_allergens(test_text)
    
    print(f"Original detection: {original_detected}")
    print(f"Imported detection: {imported_detected}")
    print(f"Detections match: {original_detected == imported_detected}")
    
    # Clean up
    if os.path.exists(export_file):
        os.remove(export_file)
        print(f"Cleaned up {export_file}")


def main():
    """Run all tests"""
    print("Allergen Dictionary Test Suite")
    print("=" * 50)
    
    try:
        test_basic_functionality()
        test_allergen_detection()
        test_edge_cases()
        test_statistics()
        test_json_export_import()
        
        print("\n" + "=" * 50)
        print("All tests completed successfully!")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 