#!/usr/bin/env python3
"""
Analyze allergen term coverage between FSA and comprehensive dictionaries
"""

import sys
import os
from typing import Dict, List, Set

# Add the allergen_filtering directory to the path
sys.path.append('allergen_filtering')

from allergen_filtering.fsa_allergen_dictionary import get_fsa_allergen_dictionary
from allergen_filtering.allergen_dictionary import get_allergen_dictionary

def get_all_terms_from_dict(allergen_dict) -> Dict[str, Set[str]]:
    """Extract all terms from an allergen dictionary"""
    terms_by_category = {}
    
    for category_name, allergen in allergen_dict.allergens.items():
        all_terms = set()
        
        # Add main ingredients
        all_terms.update(term.lower() for term in allergen.main_ingredients)
        
        # Add synonyms
        all_terms.update(term.lower() for term in allergen.synonyms)
        
        # Add scientific names
        all_terms.update(term.lower() for term in allergen.scientific_names)
        
        # Add hidden sources
        all_terms.update(term.lower() for term in allergen.hidden_sources)
        
        terms_by_category[category_name] = all_terms
    
    return terms_by_category

def analyze_coverage():
    """Analyze the coverage of allergen terms"""
    print("Analyzing allergen term coverage...\n")
    
    # Get both dictionaries
    fsa_dict = get_fsa_allergen_dictionary()
    comprehensive_dict = get_allergen_dictionary()
    
    # Extract all terms
    fsa_terms = get_all_terms_from_dict(fsa_dict)
    comprehensive_terms = get_all_terms_from_dict(comprehensive_dict)
    
    print("=" * 80)
    print("ALLERGEN TERM COVERAGE ANALYSIS")
    print("=" * 80)
    
    total_fsa_terms = sum(len(terms) for terms in fsa_terms.values())
    total_comprehensive_terms = sum(len(terms) for terms in comprehensive_terms.values())
    
    print(f"FSA Dictionary: {total_fsa_terms} total terms")
    print(f"Comprehensive Dictionary: {total_comprehensive_terms} total terms")
    print(f"Coverage: {total_fsa_terms/total_comprehensive_terms*100:.1f}%\n")
    
    # Analyze each category
    for category in fsa_terms.keys():
        if category in comprehensive_terms:
            fsa_category_terms = fsa_terms[category]
            comp_category_terms = comprehensive_terms[category]
            
            missing_terms = comp_category_terms - fsa_category_terms
            extra_terms = fsa_category_terms - comp_category_terms
            
            print(f"{category.upper()}:")
            print(f"  FSA terms: {len(fsa_category_terms)}")
            print(f"  Comprehensive terms: {len(comp_category_terms)}")
            print(f"  Coverage: {len(fsa_category_terms)/len(comp_category_terms)*100:.1f}%")
            
            if missing_terms:
                print(f"  MISSING TERMS ({len(missing_terms)}):")
                for term in sorted(missing_terms):
                    print(f"    - {term}")
            
            if extra_terms:
                print(f"  EXTRA TERMS ({len(extra_terms)}):")
                for term in sorted(extra_terms):
                    print(f"    - {term}")
            
            print()
    
    # Identify categories that might be missing
    missing_categories = set(comprehensive_terms.keys()) - set(fsa_terms.keys())
    if missing_categories:
        print("MISSING CATEGORIES:")
        for category in missing_categories:
            print(f"  - {category}: {len(comprehensive_terms[category])} terms")
        print()

def generate_missing_terms_report():
    """Generate a detailed report of missing terms"""
    print("=" * 80)
    print("MISSING TERMS REPORT")
    print("=" * 80)
    
    fsa_dict = get_fsa_allergen_dictionary()
    comprehensive_dict = get_allergen_dictionary()
    
    fsa_terms = get_all_terms_from_dict(fsa_dict)
    comprehensive_terms = get_all_terms_from_dict(comprehensive_dict)
    
    missing_terms_by_category = {}
    
    for category in comprehensive_terms.keys():
        if category in fsa_terms:
            missing = comprehensive_terms[category] - fsa_terms[category]
            if missing:
                missing_terms_by_category[category] = missing
    
    if not missing_terms_by_category:
        print("No missing terms found!")
        return
    
    print("Terms missing from FSA dictionary that are present in comprehensive dictionary:\n")
    
    for category, missing_terms in missing_terms_by_category.items():
        print(f"{category.upper()} ({len(missing_terms)} missing terms):")
        for term in sorted(missing_terms):
            print(f"  - {term}")
        print()

if __name__ == "__main__":
    analyze_coverage()
    generate_missing_terms_report() 