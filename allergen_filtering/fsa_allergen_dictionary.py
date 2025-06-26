"""
FSA-Aligned Allergen Dictionary for NLP Model Training
Contains the 14 allergen groups as specified by the UK Food Standards Agency
Reference: https://www.food.gov.uk/business-guidance/allergen-guidance-for-food-businesses
"""

import json
import re
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AllergenCategory:
    """Represents an allergen category with its main ingredients and synonyms"""
    name: str
    main_ingredients: List[str]
    synonyms: List[str]
    scientific_names: List[str]
    hidden_sources: List[str]
    description: str


class FSAAllergenDictionary:
    """
    FSA-aligned allergen dictionary for NLP model training
    Contains the 14 allergens that must be declared according to UK food law
    """
    
    def __init__(self):
        self.allergens = self._initialize_allergens()
        self.allergen_map = self._build_allergen_map()
        self.regex_patterns = self._build_regex_patterns()
    
    def _initialize_allergens(self) -> Dict[str, AllergenCategory]:
        """Initialize the FSA-aligned allergen dictionary"""
        return {
            "celery": AllergenCategory(
                name="Celery",
                main_ingredients=["celery", "celery root", "celeriac", "celery stalk", "celery leaves"],
                synonyms=["celery seed", "celery salt", "celery powder", "celery extract", "celery oil", "tahini"],
                scientific_names=["apium graveolens"],
                hidden_sources=["celery salt", "celery seed", "celery powder", "celery extract"],
                description="Celery and celery derivatives"
            ),
            
            "gluten": AllergenCategory(
                name="Gluten",
                main_ingredients=["wheat", "rye", "barley", "oats", "wheat flour", "rye flour", "barley flour", "oat flour"],
                synonyms=["wheat gluten", "rye gluten", "barley gluten", "spelt", "kamut", "triticale", "einkorn", "emmer"],
                scientific_names=["triticum aestivum", "secale cereale", "hordeum vulgare", "avena sativa"],
                hidden_sources=["flour", "pasta", "seitan", "semolina", "vital wheat gluten"],
                description="Cereals containing gluten (wheat, rye, barley, oats) and their derivatives"
            ),
            
            "crustaceans": AllergenCategory(
                name="Crustaceans",
                main_ingredients=["shrimp", "prawn", "crab", "lobster", "crayfish", "crawfish"],
                synonyms=["shrimp protein", "prawn protein", "crab protein", "lobster protein", "crustacean protein"],
                scientific_names=["crustacean protein"],
                hidden_sources=["shrimp", "prawn", "crab", "lobster", "crayfish", "crawfish"],
                description="Crustaceans (prawns, crabs, lobsters) and their derivatives"
            ),
            
            "egg": AllergenCategory(
                name="Egg",
                main_ingredients=["egg", "eggs", "egg white", "egg yolk", "egg protein"],
                synonyms=["albumin", "albumen", "egg albumin", "egg white protein", "egg protein"],
                scientific_names=["ovalbumin", "ovomucoid", "ovotransferrin", "lysozyme"],
                hidden_sources=["albumin", "albumen", "egg lecithin", "mayonnaise", "meringue"],
                description="Eggs and egg derivatives"
            ),
            
            "fish": AllergenCategory(
                name="Fish",
                main_ingredients=["fish", "salmon", "tuna", "cod", "haddock", "mackerel"],
                synonyms=["fish oil", "fish protein", "fish sauce", "fish paste", "fish meal"],
                scientific_names=["fish protein isolate", "fish protein concentrate"],
                hidden_sources=["anchovy", "bass", "cod", "fish oil", "fish protein", "fish sauce"],
                description="Fish and fish derivatives"
            ),
            
            "lupin": AllergenCategory(
                name="Lupin",
                main_ingredients=["lupin", "lupine", "lupini", "lupin bean", "lupin flour"],
                synonyms=["lupine", "lupini", "lupin protein", "lupin protein isolate"],
                scientific_names=["lupinus"],
                hidden_sources=["lupin", "lupine", "lupini", "lupin bean", "lupin flour"],
                description="Lupin beans and lupin derivatives"
            ),
            
            "milk": AllergenCategory(
                name="Milk",
                main_ingredients=["milk", "dairy", "cream", "butter", "cheese", "yogurt"],
                synonyms=["casein", "caseinate", "lactose", "lactalbumin", "whey", "whey protein"],
                scientific_names=["casein", "caseinate", "lactalbumin", "beta-lactoglobulin"],
                hidden_sources=["casein", "lactose", "whey", "whey protein", "milk protein"],
                description="Milk and milk derivatives"
            ),
            
            "molluscs": AllergenCategory(
                name="Molluscs",
                main_ingredients=["clam", "mussel", "mussels", "oyster", "oysters", "scallop", "scallops", "abalone", "cockle", "conch", "limpet", "periwinkle", "sea urchin", "whelk", "snail"],
                synonyms=["mollusc protein", "mollusk protein", "clam protein", "mussel protein", "oyster protein"],
                scientific_names=["mollusk protein"],
                hidden_sources=["clam", "mussel", "mussels", "oyster", "oysters", "scallop", "scallops", "abalone", "cockle", "conch", "limpet", "periwinkle", "sea urchin", "whelk", "snail"],
                description="Molluscs (mussels, oysters) and their derivatives"
            ),
            
            "mustard": AllergenCategory(
                name="Mustard",
                main_ingredients=["mustard", "mustard seed", "mustard seeds", "mustard oil", "mustard powder"],
                synonyms=["mustard seed", "mustard seeds", "mustard oil", "mustard powder", "mustard paste"],
                scientific_names=["brassica juncea", "brassica nigra", "sinapis alba"],
                hidden_sources=["mustard seed", "mustard seeds", "mustard oil", "mustard powder"],
                description="Mustard and mustard derivatives"
            ),
            
            "peanuts": AllergenCategory(
                name="Peanuts",
                main_ingredients=["peanut", "peanuts", "peanut butter", "peanut oil"],
                synonyms=["arachis hypogaea", "ground nut", "groundnut", "monkey nut", "goober pea"],
                scientific_names=["arachis hypogaea"],
                hidden_sources=["arachis oil", "ground nuts", "monkey nuts", "peanut butter", "peanut flour"],
                description="Peanuts and peanut derivatives"
            ),
            
            "sesame": AllergenCategory(
                name="Sesame",
                main_ingredients=["sesame", "sesame seed", "sesame seeds", "sesame oil"],
                synonyms=["sesame seed", "sesame seeds", "sesame oil", "sesame paste", "tahini", "benne"],
                scientific_names=["sesamum indicum"],
                hidden_sources=["benne", "sesame flour", "sesame oil", "sesame paste", "tahini"],
                description="Sesame seeds and sesame derivatives"
            ),
            
            "soy": AllergenCategory(
                name="Soy",
                main_ingredients=["soy", "soya", "soybean", "soybeans", "soy protein"],
                synonyms=["soy flour", "soy protein", "soy oil", "soy lecithin", "soy sauce", "edamame", "miso", "tempeh", "tofu"],
                scientific_names=["glycine max"],
                hidden_sources=["edamame", "miso", "soy flour", "soy lecithin", "soy protein", "soy sauce", "tempeh", "tofu"],
                description="Soybeans and soy derivatives"
            ),
            
            "sulfites": AllergenCategory(
                name="Sulfites",
                main_ingredients=["sulfite", "sulfites", "sulfur dioxide", "sulfurous acid"],
                synonyms=["sulfur dioxide", "sulfurous acid", "sodium sulfite", "sodium bisulfite", "sodium metabisulfite"],
                scientific_names=["sulfur dioxide", "sulfurous acid"],
                hidden_sources=["dried fruit", "wine", "beer", "cider", "vinegar", "pickled foods"],
                description="Sulphur dioxide and sulphites (if concentration > 10 parts per million)"
            ),
            
            "tree_nuts": AllergenCategory(
                name="Tree Nuts",
                main_ingredients=["almond", "almonds", "walnut", "walnuts", "cashew", "cashews", "pecan", "pecans", "pistachio", "pistachios", "hazelnut", "hazelnuts", "macadamia", "macadamias", "brazil nut", "brazil nuts", "pine nut", "pine nuts"],
                synonyms=["almond butter", "almond flour", "walnut oil", "cashew butter", "hazelnut oil", "filbert", "filberts", "nut butter", "nut oil", "nut flour"],
                scientific_names=["prunus dulcis", "juglans regia", "anacardium occidentale", "corylus avellana", "macadamia integrifolia", "bertholletia excelsa"],
                hidden_sources=["almond", "cashew", "hazelnut", "macadamia", "pecan", "pine nut", "pistachio", "walnut", "marzipan", "praline"],
                description="Tree nuts (almonds, hazelnuts, walnuts, brazil nuts, cashews, pecans, pistachios, macadamia nuts) and their derivatives"
            )
        }
    
    def _build_allergen_map(self) -> Dict[str, str]:
        """Build a mapping from allergen terms to their main category"""
        allergen_map = {}
        
        for category_name, allergen in self.allergens.items():
            # Add main ingredients
            for ingredient in allergen.main_ingredients:
                allergen_map[ingredient.lower()] = category_name
            
            # Add synonyms
            for synonym in allergen.synonyms:
                allergen_map[synonym.lower()] = category_name
            
            # Add scientific names
            for scientific_name in allergen.scientific_names:
                allergen_map[scientific_name.lower()] = category_name
            
            # Add hidden sources
            for hidden_source in allergen.hidden_sources:
                allergen_map[hidden_source.lower()] = category_name
        
        return allergen_map
    
    def _build_regex_patterns(self) -> Dict[str, re.Pattern]:
        """Build regex patterns for each allergen category"""
        patterns = {}
        
        for category_name, allergen in self.allergens.items():
            # Combine all terms for this allergen
            all_terms = (
                allergen.main_ingredients + 
                allergen.synonyms + 
                allergen.scientific_names + 
                allergen.hidden_sources
            )
            
            # Create regex pattern that matches whole words
            pattern_string = r'\b(' + '|'.join(map(re.escape, all_terms)) + r')\b'
            patterns[category_name] = re.compile(pattern_string, re.IGNORECASE)
        
        return patterns
    
    def detect_allergens(self, text: str) -> Dict[str, List[str]]:
        """
        Detect allergens in text and return categorized matches
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dictionary mapping allergen categories to lists of detected terms
        """
        text_lower = text.lower()
        detected_allergens = {}
        
        for category_name, pattern in self.regex_patterns.items():
            matches = pattern.findall(text_lower)
            if matches:
                detected_allergens[category_name] = list(set(matches))
        
        return detected_allergens
    
    def get_allergen_info(self, category: str) -> AllergenCategory:
        """Get detailed information about a specific allergen category"""
        return self.allergens.get(category.lower())
    
    def get_all_categories(self) -> List[str]:
        """Get list of all allergen categories"""
        return list(self.allergens.keys())
    
    def export_to_json(self, filepath: str) -> None:
        """Export allergen dictionary to JSON file"""
        export_data = {}
        
        for category_name, allergen in self.allergens.items():
            export_data[category_name] = {
                "name": allergen.name,
                "main_ingredients": allergen.main_ingredients,
                "synonyms": allergen.synonyms,
                "scientific_names": allergen.scientific_names,
                "hidden_sources": allergen.hidden_sources,
                "description": allergen.description
            }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_json(cls, filepath: str) -> 'FSAAllergenDictionary':
        """Load allergen dictionary from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        instance = cls()
        instance.allergens = {}
        
        for category_name, category_data in data.items():
            instance.allergens[category_name] = AllergenCategory(
                name=category_data["name"],
                main_ingredients=category_data["main_ingredients"],
                synonyms=category_data["synonyms"],
                scientific_names=category_data["scientific_names"],
                hidden_sources=category_data["hidden_sources"],
                description=category_data["description"]
            )
        
        # Rebuild maps and patterns
        instance.allergen_map = instance._build_allergen_map()
        instance.regex_patterns = instance._build_regex_patterns()
        
        return instance


def get_fsa_allergen_dictionary() -> FSAAllergenDictionary:
    """Get the FSA-aligned allergen dictionary instance"""
    return FSAAllergenDictionary() 