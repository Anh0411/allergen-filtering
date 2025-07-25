"""
Allergen Dictionary for NLP Model Training
Contains lists of allergens and their synonyms for ingredient analysis
"""

import json
import re
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from pathlib import Path
import spacy
from spacy.training.example import Example
import random


@dataclass
class AllergenCategory:
    """Represents an allergen category with its main ingredients and synonyms"""
    name: str
    main_ingredients: List[str]
    synonyms: List[str]
    scientific_names: List[str]
    hidden_sources: List[str]
    description: str


class AllergenDictionary:
    """
    Comprehensive allergen dictionary for NLP model training
    Contains major allergens and their synonyms for ingredient analysis
    """
    
    def __init__(self):
        self.allergens = self._initialize_allergens()
        self.allergen_map = self._build_allergen_map()
        self.regex_patterns = self._build_regex_patterns()
    
    def _initialize_allergens(self) -> Dict[str, AllergenCategory]:
        """Initialize the comprehensive allergen dictionary aligned with FSA 14 allergens"""
        return {
            "celery": AllergenCategory(
                name="Celery",
                main_ingredients=["celery", "celery root", "celeriac", "celery stalk", "celery leaves"],
                synonyms=[
                    "celery seed", "celery salt", "celery powder", "celery extract", "celery oil",
                    "celery juice", "celery puree", "celery paste", "celery concentrate",
                    "celery protein", "celery fiber", "celery flour", "celery meal"
                ],
                scientific_names=[
                    "apium graveolens", "celery protein isolate", "celery protein concentrate",
                    "celery extract", "celery oil", "celery seed oil"
                ],
                hidden_sources=[
                    "celery salt", "celery seed", "celery powder", "celery extract", "celery oil",
                    "celery juice", "celery puree", "celery paste", "celery concentrate",
                    "celery protein", "celery fiber", "celery flour", "celery meal",
                    "celery root", "celeriac", "celery stalk", "celery leaves"
                ],
                description="Celery and celery derivatives"
            ),
            
            "gluten": AllergenCategory(
                name="Gluten",
                main_ingredients=[
                    "wheat", "rye", "barley", "oats", "wheat flour", "rye flour", "barley flour", "oat flour",
                    "wheat gluten", "rye gluten", "barley gluten", "oat protein"
                ],
                synonyms=[
                    "wheat flour", "rye flour", "barley flour", "oat flour", "wheat protein", "rye protein",
                    "barley protein", "oat protein", "wheat gluten", "rye gluten", "barley gluten",
                    "wheat starch", "rye starch", "barley starch", "oat starch", "wheat bran", "rye bran",
                    "barley bran", "oat bran", "wheat germ", "rye germ", "barley germ", "oat germ",
                    "wheat semolina", "rye semolina", "barley semolina", "oat semolina", "wheat durum",
                    "rye durum", "barley durum", "oat durum", "wheat bread", "rye bread", "barley bread",
                    "oat bread", "wheat pasta", "rye pasta", "barley pasta", "oat pasta", "wheat noodles",
                    "rye noodles", "barley noodles", "oat noodles", "wheat cereal", "rye cereal", "barley cereal",
                    "oat cereal", "wheat flakes", "rye flakes", "barley flakes", "oat flakes", "wheat crackers",
                    "rye crackers", "barley crackers", "oat crackers", "wheat protein isolate", "rye protein isolate",
                    "barley protein isolate", "oat protein isolate", "wheat protein concentrate", "rye protein concentrate",
                    "barley protein concentrate", "oat protein concentrate", "wheat protein hydrolysate", "rye protein hydrolysate",
                    "barley protein hydrolysate", "oat protein hydrolysate", "vital wheat gluten", "vital rye gluten",
                    "vital barley gluten", "vital oat gluten", "seitan", "wheat protein derivative", "rye protein derivative",
                    "barley protein derivative", "oat protein derivative", "spelt", "kamut", "triticale", "einkorn", "emmer"
                ],
                scientific_names=[
                    "triticum aestivum", "triticum durum", "secale cereale", "hordeum vulgare", "avena sativa",
                    "wheat protein isolate", "rye protein isolate", "barley protein isolate", "oat protein isolate",
                    "wheat protein concentrate", "rye protein concentrate", "barley protein concentrate", "oat protein concentrate",
                    "wheat gluten", "rye gluten", "barley gluten", "oat gluten", "wheat protein hydrolysate", "rye protein hydrolysate",
                    "barley protein hydrolysate", "oat protein hydrolysate"
                ],
                hidden_sources=[
                    "all purpose flour", "bread flour", "cake flour", "cereal extract", "club wheat", "common wheat",
                    "durum wheat", "einkorn", "emmer", "farina", "flour", "graham flour", "high gluten flour", "high protein flour",
                    "kamut", "pasta", "seitan", "semolina", "spelt", "triticale", "vital wheat gluten", "wheat bran", "wheat flour",
                    "wheat germ", "wheat gluten", "wheat meal", "wheat protein", "wheat protein concentrate", "wheat protein isolate",
                    "wheat starch", "whole wheat flour", "whole wheat bread", "rye bran", "rye flour", "rye germ", "rye gluten",
                    "rye meal", "rye protein", "rye protein concentrate", "rye protein isolate", "rye starch", "whole rye flour",
                    "whole rye bread", "barley bran", "barley flour", "barley germ", "barley gluten", "barley meal", "barley protein",
                    "barley protein concentrate", "barley protein isolate", "barley starch", "whole barley flour", "whole barley bread",
                    "oat bran", "oat flour", "oat germ", "oat gluten", "oat meal", "oat protein", "oat protein concentrate",
                    "oat protein isolate", "oat starch", "whole oat flour", "whole oat bread"
                ],
                description="Cereals containing gluten (wheat, rye, barley, oats) and their derivatives"
            ),
            
            "crustaceans": AllergenCategory(
                name="Crustaceans",
                main_ingredients=[
                    "shrimp", "prawn", "crab", "lobster", "crayfish", "crawfish", "krill"
                ],
                synonyms=[
                    "shrimp", "prawn", "crab", "lobster", "crayfish", "crawfish", "krill", "barnacle",
                    "shrimp protein", "prawn protein", "crab protein", "lobster protein", "crayfish protein",
                    "crawfish protein", "krill protein", "shrimp oil", "prawn oil", "crab oil", "lobster oil",
                    "crayfish oil", "crawfish oil", "krill oil", "shrimp extract", "prawn extract", "crab extract",
                    "lobster extract", "crayfish extract", "crawfish extract", "krill extract", "shrimp broth",
                    "prawn broth", "crab broth", "lobster broth", "crayfish broth", "crawfish broth", "krill broth",
                    "shrimp stock", "prawn stock", "crab stock", "lobster stock", "crayfish stock", "crawfish stock",
                    "krill stock", "shrimp sauce", "prawn sauce", "crab sauce", "lobster sauce", "crayfish sauce",
                    "crawfish sauce", "krill sauce", "shrimp paste", "prawn paste", "crab paste", "lobster paste",
                    "crayfish paste", "crawfish paste", "krill paste", "shrimp meal", "prawn meal", "crab meal",
                    "lobster meal", "crayfish meal", "crawfish meal", "krill meal", "shrimp protein isolate",
                    "prawn protein isolate", "crab protein isolate", "lobster protein isolate", "crayfish protein isolate",
                    "crawfish protein isolate", "krill protein isolate", "shrimp protein concentrate", "prawn protein concentrate",
                    "crab protein concentrate", "lobster protein concentrate", "crayfish protein concentrate", "crawfish protein concentrate",
                    "krill protein concentrate", "shrimp protein hydrolysate", "prawn protein hydrolysate", "crab protein hydrolysate",
                    "lobster protein hydrolysate", "crayfish protein hydrolysate", "crawfish protein hydrolysate", "krill protein hydrolysate"
                ],
                scientific_names=[
                    "crustacean protein", "crustacean protein isolate", "crustacean protein concentrate",
                    "crustacean protein hydrolysate", "crustacean collagen", "crustacean gelatin", "crustacean oil"
                ],
                hidden_sources=[
                    "barnacle", "crab", "crawfish", "crayfish", "krill", "lobster", "prawn", "shrimp",
                    "shrimp protein", "prawn protein", "crab protein", "lobster protein", "crayfish protein",
                    "crawfish protein", "krill protein", "shrimp oil", "prawn oil", "crab oil", "lobster oil",
                    "crayfish oil", "crawfish oil", "krill oil", "shrimp extract", "prawn extract", "crab extract",
                    "lobster extract", "crayfish extract", "crawfish extract", "krill extract", "shrimp broth",
                    "prawn broth", "crab broth", "lobster broth", "crayfish broth", "crawfish broth", "krill broth",
                    "shrimp stock", "prawn stock", "crab stock", "lobster stock", "crayfish stock", "crawfish stock",
                    "krill stock", "shrimp sauce", "prawn sauce", "crab sauce", "lobster sauce", "crayfish sauce",
                    "crawfish sauce", "krill sauce", "shrimp paste", "prawn paste", "crab paste", "lobster paste",
                    "crayfish paste", "crawfish paste", "krill paste", "shrimp meal", "prawn meal", "crab meal",
                    "lobster meal", "crayfish meal", "crawfish meal", "krill meal"
                ],
                description="Crustaceans (prawns, crabs, lobsters) and their derivatives"
            ),
            
            "egg": AllergenCategory(
                name="Egg",
                main_ingredients=["egg", "eggs", "egg white", "egg yolk", "egg protein"],
                synonyms=[
                    "albumin", "albumen", "egg albumin", "egg white protein", "egg yolk",
                    "egg protein", "egg solids", "egg powder", "dried egg", "egg substitute",
                    "egg replacer", "egg white powder", "egg yolk powder", "egg protein isolate",
                    "egg protein concentrate", "egg protein hydrolysate", "egg protein derivative"
                ],
                scientific_names=[
                    "ovalbumin", "ovomucoid", "ovotransferrin", "lysozyme", "avidin",
                    "egg albumin", "egg globulin", "egg protein isolate", "egg protein concentrate"
                ],
                hidden_sources=[
                    "albumin", "albumen", "apovitellenin", "avidin", "egg lecithin",
                    "egg white", "egg yolk", "globulin", "livetin", "lysozyme", "mayonnaise",
                    "meringue", "ovalbumin", "ovomucin", "ovomucoid", "ovotransferrin",
                    "ovovitellin", "silici albuminate", "simplesse", "surimi", "vitellin"
                ],
                description="Eggs and egg derivatives"
            ),
            
            "fish": AllergenCategory(
                name="Fish",
                main_ingredients=["fish", "salmon", "tuna", "cod", "haddock", "mackerel"],
                synonyms=[
                    "fish oil", "fish protein", "fish sauce", "fish paste", "fish meal",
                    "fish protein isolate", "fish protein concentrate", "fish protein hydrolysate",
                    "fish collagen", "fish gelatin", "fish broth", "fish stock", "fish extract",
                    "anchovy", "bass", "catfish", "cod", "flounder", "grouper", "haddock",
                    "hake", "halibut", "herring", "mackerel", "mahi mahi", "perch", "pike",
                    "pollock", "salmon", "sardine", "sea bass", "shark", "snapper", "sole",
                    "swordfish", "tilapia", "trout", "tuna", "whitefish"
                ],
                scientific_names=[
                    "fish protein isolate", "fish protein concentrate", "fish protein hydrolysate",
                    "fish collagen", "fish gelatin", "fish oil", "fish extract"
                ],
                hidden_sources=[
                    "anchovy", "bass", "bouillabaisse", "catfish", "cod", "fish oil",
                    "fish protein", "fish sauce", "flounder", "grouper", "haddock", "hake",
                    "halibut", "herring", "mackerel", "mahi mahi", "perch", "pike", "pollock",
                    "salmon", "sardine", "sea bass", "shark", "snapper", "sole", "swordfish",
                    "tilapia", "trout", "tuna", "whitefish", "worcestershire sauce"
                ],
                description="Fish and fish derivatives"
            ),
            
            "lupin": AllergenCategory(
                name="Lupin",
                main_ingredients=["lupin", "lupine", "lupini", "lupin bean", "lupin flour"],
                synonyms=[
                    "lupine", "lupini", "lupin bean", "lupin flour", "lupin protein",
                    "lupin protein isolate", "lupin protein concentrate", "lupin protein hydrolysate",
                    "lupin oil", "lupin extract", "lupin powder", "lupin meal", "lupin paste",
                    "lupin butter", "lupin milk", "lupin yogurt", "lupin cheese", "lupin bread",
                    "lupin pasta", "lupin noodles", "lupin cereal", "lupin flakes", "lupin crackers"
                ],
                scientific_names=[
                    "lupinus", "lupin protein isolate", "lupin protein concentrate",
                    "lupin protein hydrolysate", "lupin flour", "lupin meal", "lupin oil"
                ],
                hidden_sources=[
                    "lupin", "lupine", "lupini", "lupin bean", "lupin flour", "lupin protein",
                    "lupin protein isolate", "lupin protein concentrate", "lupin protein hydrolysate",
                    "lupin oil", "lupin extract", "lupin powder", "lupin meal", "lupin paste",
                    "lupin butter", "lupin milk", "lupin yogurt", "lupin cheese", "lupin bread",
                    "lupin pasta", "lupin noodles", "lupin cereal", "lupin flakes", "lupin crackers"
                ],
                description="Lupin beans and lupin derivatives"
            ),
            
            "milk": AllergenCategory(
                name="Milk",
                main_ingredients=["milk", "dairy", "cream", "butter", "cheese", "yogurt"],
                synonyms=[
                    "casein", "caseinate", "lactose", "lactalbumin", "lactoglobulin",
                    "whey", "whey protein", "milk protein", "milk solids", "milk powder",
                    "skim milk", "whole milk", "buttermilk", "evaporated milk", "condensed milk",
                    "milk fat", "milk sugar", "lactose", "galactose", "curd", "rennet",
                    "ghee", "clarified butter", "milk derivative", "milk byproduct"
                ],
                scientific_names=[
                    "casein", "caseinate", "lactalbumin", "beta-lactoglobulin", "alpha-lactalbumin",
                    "lactose", "galactose", "milk protein isolate", "milk protein concentrate"
                ],
                hidden_sources=[
                    "artificial butter flavor", "butter flavor", "caramel color", "chocolate",
                    "high protein flour", "lactose", "lactic acid starter culture", "lactose",
                    "margarine", "natural flavoring", "non-dairy creamer", "nougat", "pudding",
                    "simplesse", "sour cream", "sour milk solids", "whey", "whey protein"
                ],
                description="Milk and milk derivatives"
            ),
            
            "molluscs": AllergenCategory(
                name="Molluscs",
                main_ingredients=[
                    "clam", "mussel", "oyster", "scallop", "abalone", "cockle", "conch", "limpet", "periwinkle", "sea urchin", "whelk", "snail"
                ],
                synonyms=[
                    "clam", "mussel", "oyster", "scallop", "abalone", "cockle", "conch", "limpet", "periwinkle", "sea urchin", "whelk", "snail",
                    "mollusc protein", "mollusk protein", "clam protein", "mussel protein", "oyster protein", "scallop protein",
                    "abalone protein", "cockle protein", "conch protein", "limpet protein", "periwinkle protein", "sea urchin protein",
                    "whelk protein", "snail protein", "mollusc oil", "mollusk oil", "clam oil", "mussel oil", "oyster oil", "scallop oil",
                    "abalone oil", "cockle oil", "conch oil", "limpet oil", "periwinkle oil", "sea urchin oil", "whelk oil", "snail oil",
                    "mollusc extract", "mollusk extract", "clam extract", "mussel extract", "oyster extract", "scallop extract",
                    "abalone extract", "cockle extract", "conch extract", "limpet extract", "periwinkle extract", "sea urchin extract",
                    "whelk extract", "snail extract", "mollusc broth", "mollusk broth", "clam broth", "mussel broth", "oyster broth",
                    "scallop broth", "abalone broth", "cockle broth", "conch broth", "limpet broth", "periwinkle broth", "sea urchin broth",
                    "whelk broth", "snail broth", "mollusc stock", "mollusk stock", "clam stock", "mussel stock", "oyster stock",
                    "scallop stock", "abalone stock", "cockle stock", "conch stock", "limpet stock", "periwinkle stock", "sea urchin stock",
                    "whelk stock", "snail stock", "mollusc sauce", "mollusk sauce", "clam sauce", "mussel sauce", "oyster sauce",
                    "scallop sauce", "abalone sauce", "cockle sauce", "conch sauce", "limpet sauce", "periwinkle sauce", "sea urchin sauce",
                    "whelk sauce", "snail sauce", "mollusc paste", "mollusk paste", "clam paste", "mussel paste", "oyster paste",
                    "scallop paste", "abalone paste", "cockle paste", "conch paste", "limpet paste", "periwinkle paste", "sea urchin paste",
                    "whelk paste", "snail paste", "mollusc meal", "mollusk meal", "clam meal", "mussel meal", "oyster meal",
                    "scallop meal", "abalone meal", "cockle meal", "conch meal", "limpet meal", "periwinkle meal", "sea urchin meal",
                    "whelk meal", "snail meal", "mollusc protein isolate", "mollusk protein isolate", "clam protein isolate",
                    "mussel protein isolate", "oyster protein isolate", "scallop protein isolate", "abalone protein isolate",
                    "cockle protein isolate", "conch protein isolate", "limpet protein isolate", "periwinkle protein isolate",
                    "sea urchin protein isolate", "whelk protein isolate", "snail protein isolate", "mollusc protein concentrate",
                    "mollusk protein concentrate", "clam protein concentrate", "mussel protein concentrate", "oyster protein concentrate",
                    "scallop protein concentrate", "abalone protein concentrate", "cockle protein concentrate", "conch protein concentrate",
                    "limpet protein concentrate", "periwinkle protein concentrate", "sea urchin protein concentrate", "whelk protein concentrate",
                    "snail protein concentrate", "mollusc protein hydrolysate", "mollusk protein hydrolysate", "clam protein hydrolysate",
                    "mussel protein hydrolysate", "oyster protein hydrolysate", "scallop protein hydrolysate", "abalone protein hydrolysate",
                    "cockle protein hydrolysate", "conch protein hydrolysate", "limpet protein hydrolysate", "periwinkle protein hydrolysate",
                    "sea urchin protein hydrolysate", "whelk protein hydrolysate", "snail protein hydrolysate"
                ],
                scientific_names=[
                    "mollusk protein", "mollusc protein isolate", "mollusk protein isolate",
                    "mollusc protein concentrate", "mollusk protein concentrate", "mollusc protein hydrolysate",
                    "mollusk protein hydrolysate", "mollusc collagen", "mollusk collagen", "mollusc gelatin",
                    "mollusk gelatin", "mollusc oil", "mollusk oil"
                ],
                hidden_sources=[
                    "abalone", "cockle", "conch", "limpet", "mussel", "oyster", "periwinkle", "scallop", "sea urchin", "snail", "whelk",
                    "mollusc protein", "mollusk protein", "clam protein", "mussel protein", "oyster protein", "scallop protein",
                    "abalone protein", "cockle protein", "conch protein", "limpet protein", "periwinkle protein", "sea urchin protein",
                    "whelk protein", "snail protein", "mollusc oil", "mollusk oil", "clam oil", "mussel oil", "oyster oil", "scallop oil",
                    "abalone oil", "cockle oil", "conch oil", "limpet oil", "periwinkle oil", "sea urchin oil", "whelk oil", "snail oil",
                    "mollusc extract", "mollusk extract", "clam extract", "mussel extract", "oyster extract", "scallop extract",
                    "abalone extract", "cockle extract", "conch extract", "limpet extract", "periwinkle extract", "sea urchin extract",
                    "whelk extract", "snail extract", "mollusc broth", "mollusk broth", "clam broth", "mussel broth", "oyster broth",
                    "scallop broth", "abalone broth", "cockle broth", "conch broth", "limpet broth", "periwinkle broth", "sea urchin broth",
                    "whelk broth", "snail broth", "mollusc stock", "mollusk stock", "clam stock", "mussel stock", "oyster stock",
                    "scallop stock", "abalone stock", "cockle stock", "conch stock", "limpet stock", "periwinkle stock", "sea urchin stock",
                    "whelk stock", "snail stock", "mollusc sauce", "mollusk sauce", "clam sauce", "mussel sauce", "oyster sauce",
                    "scallop sauce", "abalone sauce", "cockle sauce", "conch sauce", "limpet sauce", "periwinkle sauce", "sea urchin sauce",
                    "whelk sauce", "snail sauce", "mollusc paste", "mollusk paste", "clam paste", "mussel paste", "oyster paste",
                    "scallop paste", "abalone paste", "cockle paste", "conch paste", "limpet paste", "periwinkle paste", "sea urchin paste",
                    "whelk paste", "snail paste", "mollusc meal", "mollusk meal", "clam meal", "mussel meal", "oyster meal",
                    "scallop meal", "abalone meal", "cockle meal", "conch meal", "limpet meal", "periwinkle meal", "sea urchin meal",
                    "whelk meal", "snail meal"
                ],
                description="Molluscs (mussels, oysters) and their derivatives"
            ),
            
            "mustard": AllergenCategory(
                name="Mustard",
                main_ingredients=["mustard", "mustard seed", "mustard seeds", "mustard oil", "mustard powder"],
                synonyms=[
                    "mustard seed", "mustard seeds", "mustard oil", "mustard powder", "mustard paste",
                    "mustard sauce", "mustard extract", "mustard protein", "mustard protein isolate",
                    "mustard protein concentrate", "mustard protein hydrolysate", "mustard flour",
                    "mustard meal", "mustard butter", "mustard spread", "mustard dressing",
                    "mustard vinaigrette", "mustard marinade", "mustard glaze", "mustard rub"
                ],
                scientific_names=[
                    "brassica juncea", "brassica nigra", "sinapis alba", "mustard protein isolate",
                    "mustard protein concentrate", "mustard protein hydrolysate", "mustard oil",
                    "mustard paste", "mustard powder"
                ],
                hidden_sources=[
                    "mustard seed", "mustard seeds", "mustard oil", "mustard powder", "mustard paste",
                    "mustard sauce", "mustard extract", "mustard protein", "mustard protein isolate",
                    "mustard protein concentrate", "mustard protein hydrolysate", "mustard flour",
                    "mustard meal", "mustard butter", "mustard spread", "mustard dressing",
                    "mustard vinaigrette", "mustard marinade", "mustard glaze", "mustard rub",
                    "brassica juncea", "brassica nigra", "sinapis alba"
                ],
                description="Mustard and mustard derivatives"
            ),
            
            "peanuts": AllergenCategory(
                name="Peanuts",
                main_ingredients=["peanut", "peanuts", "peanut butter", "peanut oil"],
                synonyms=[
                    "arachis hypogaea", "ground nut", "groundnut", "monkey nut", "goober pea",
                    "peanut flour", "peanut protein", "peanut meal", "peanut paste", "peanut butter",
                    "peanut oil", "cold pressed peanut oil", "expeller pressed peanut oil",
                    "extruded peanut oil", "peanut protein isolate", "peanut protein concentrate"
                ],
                scientific_names=[
                    "arachis hypogaea", "peanut protein isolate", "peanut protein concentrate",
                    "peanut flour", "peanut meal", "peanut paste"
                ],
                hidden_sources=[
                    "arachis oil", "artificial nuts", "beer nuts", "cold pressed peanut oil",
                    "expeller pressed peanut oil", "extruded peanut oil", "goober nuts",
                    "goober peas", "ground nuts", "lupin", "mandelonas", "mixed nuts",
                    "monkey nuts", "nut meat", "nut pieces", "peanut butter", "peanut flour",
                    "peanut protein", "peanut protein isolate", "peanut protein concentrate"
                ],
                description="Peanuts and peanut derivatives"
            ),
            
            "sesame": AllergenCategory(
                name="Sesame",
                main_ingredients=["sesame", "sesame seed", "sesame seeds", "sesame oil"],
                synonyms=[
                    "sesame seed", "sesame seeds", "sesame oil", "sesame paste", "sesame butter",
                    "tahini", "sesame flour", "sesame meal", "sesame protein", "sesame protein isolate",
                    "sesame protein concentrate", "sesame protein hydrolysate", "sesame extract",
                    "sesame powder", "sesame salt", "gomasio", "benne", "benne seed", "benne seeds"
                ],
                scientific_names=[
                    "sesamum indicum", "sesame protein isolate", "sesame protein concentrate",
                    "sesame protein hydrolysate", "sesame oil", "sesame paste", "tahini"
                ],
                hidden_sources=[
                    "benne", "benne seed", "gomasio", "halvah", "sesame flour", "sesame oil",
                    "sesame paste", "sesame salt", "sesame seed", "sesame seeds", "sesame protein",
                    "sesame protein isolate", "sesame protein concentrate", "sesame protein hydrolysate",
                    "sesame extract", "sesame powder", "tahini", "sesame butter"
                ],
                description="Sesame seeds and sesame derivatives"
            ),
            
            "soy": AllergenCategory(
                name="Soy",
                main_ingredients=["soy", "soya", "soybean", "soybeans", "soy protein"],
                synonyms=[
                    "soy flour", "soy protein", "soy protein isolate", "soy protein concentrate",
                    "soy oil", "soy lecithin", "soy sauce", "soy milk", "soy yogurt", "soy cheese",
                    "soy butter", "soy paste", "soy meal", "soy fiber", "soy grits", "soy nuts",
                    "edamame", "miso", "tempeh", "tofu", "soy protein hydrolysate", "soy protein derivative"
                ],
                scientific_names=[
                    "glycine max", "soy protein isolate", "soy protein concentrate",
                    "soy flour", "soy meal", "soy lecithin", "soy protein hydrolysate"
                ],
                hidden_sources=[
                    "edamame", "hydrolyzed soy protein", "miso", "mono-diglyceride",
                    "monosodium glutamate", "msg", "natural flavoring", "soy albumin",
                    "soy fiber", "soy flour", "soy grits", "soy lecithin", "soy meal",
                    "soy milk", "soy nuts", "soy oil", "soy protein", "soy protein concentrate",
                    "soy protein isolate", "soy sauce", "soy yogurt", "soybean oil",
                    "soybean paste", "soybean protein", "soybean protein concentrate",
                    "soybean protein isolate", "soybean protein hydrolysate", "tempeh", "tofu"
                ],
                description="Soybeans and soy derivatives"
            ),
            
            "sulfites": AllergenCategory(
                name="Sulfites",
                main_ingredients=["sulfite", "sulfites", "sulfur dioxide", "sulfurous acid"],
                synonyms=[
                    "sulfur dioxide", "sulfurous acid", "sodium sulfite", "sodium bisulfite",
                    "sodium metabisulfite", "potassium sulfite", "potassium bisulfite",
                    "potassium metabisulfite", "calcium sulfite", "calcium bisulfite",
                    "calcium metabisulfite", "sulfite preservative", "sulfite antioxidant",
                    "sulfite additive", "sulfite preservative", "sulfite antioxidant"
                ],
                scientific_names=[
                    "sulfur dioxide", "sulfurous acid", "sodium sulfite", "sodium bisulfite",
                    "sodium metabisulfite", "potassium sulfite", "potassium bisulfite",
                    "potassium metabisulfite", "calcium sulfite", "calcium bisulfite",
                    "calcium metabisulfite"
                ],
                hidden_sources=[
                    "dried fruit", "dried apricots", "dried peaches", "dried pears", "dried apples",
                    "dried cranberries", "dried raisins", "dried prunes", "dried figs",
                    "wine", "beer", "cider", "vinegar", "pickled foods", "canned foods",
                    "frozen foods", "processed foods", "preserved foods", "sulfite preservative",
                    "sulfite antioxidant", "sulfite additive"
                ],
                description="Sulphur dioxide and sulphites (if concentration > 10 parts per million)"
            ),
            
            "tree_nuts": AllergenCategory(
                name="Tree Nuts",
                main_ingredients=[
                    "almond", "almonds", "walnut", "walnuts", "cashew", "cashews",
                    "pecan", "pecans", "pistachio", "pistachios", "hazelnut", "hazelnuts",
                    "macadamia", "macadamias", "brazil nut", "brazil nuts", "pine nut", "pine nuts"
                ],
                synonyms=[
                    "almond butter", "almond flour", "almond meal", "almond oil", "almond paste",
                    "walnut oil", "cashew butter", "cashew oil", "pecan oil", "pistachio oil",
                    "hazelnut oil", "filbert", "filberts", "macadamia oil", "brazil nut oil",
                    "pine nut oil", "pignolia", "pignoli", "nut butter", "nut oil", "nut flour",
                    "nut meal", "nut paste", "mixed nuts", "tree nut protein", "tree nut flour"
                ],
                scientific_names=[
                    "prunus dulcis", "juglans regia", "anacardium occidentale", "carya illinoinensis",
                    "pistacia vera", "corylus avellana", "macadamia integrifolia", "bertholletia excelsa",
                    "pinus pinea", "tree nut protein isolate", "tree nut protein concentrate"
                ],
                hidden_sources=[
                    "artificial nuts", "beechnut", "black walnut hull extract", "butternut",
                    "cashew", "chestnut", "chinquapin", "coconut", "filbert", "ginkgo nut",
                    "hazelnut", "hickory nut", "litchi nut", "lychee nut", "macadamia nut",
                    "marzipan", "nangai nut", "natural nut extract", "nut butters", "nut meal",
                    "nut meat", "nut oil", "nut paste", "pecan", "pesto", "pignolia",
                    "pine nut", "pistachio", "praline", "shea nut", "walnut"
                ],
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
    def load_from_json(cls, filepath: str) -> 'AllergenDictionary':
        """Load allergen dictionary from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        instance = cls()
        instance.allergens = {}
        
        for category_name, allergen_data in data.items():
            instance.allergens[category_name] = AllergenCategory(
                name=allergen_data["name"],
                main_ingredients=allergen_data["main_ingredients"],
                synonyms=allergen_data["synonyms"],
                scientific_names=allergen_data["scientific_names"],
                hidden_sources=allergen_data["hidden_sources"],
                description=allergen_data["description"]
            )
        
        instance.allergen_map = instance._build_allergen_map()
        instance.regex_patterns = instance._build_regex_patterns()
        
        return instance


# Convenience function to get the default allergen dictionary
def get_allergen_dictionary() -> AllergenDictionary:
    """Get the default allergen dictionary instance"""
    return AllergenDictionary()


if __name__ == "__main__":
    # Example usage and testing
    allergen_dict = AllergenDictionary()
    
    # Test allergen detection
    test_text = """
    This recipe contains milk, casein, egg albumin, peanut butter, 
    wheat flour, soy protein, fish oil, shrimp, sesame seeds, 
    and sulfites as preservatives.
    """
    
    detected = allergen_dict.detect_allergens(test_text)
    print("Detected allergens:")
    for category, terms in detected.items():
        print(f"{category}: {terms}")
    
    # Export to JSON
    allergen_dict.export_to_json("allergen_dictionary.json")
    print("\nAllergen dictionary exported to allergen_dictionary.json")

# Load your exported feedback/annotation data
with open("feedback_training_data.json") as f:
    TRAIN_DATA = json.load(f)

# Create blank English model
nlp = spacy.blank("en")
ner = nlp.add_pipe("ner")

# Add labels from your data
labels = set()
for text, ann in TRAIN_DATA:
    for start, end, label in ann["entities"]:
        labels.add(label)
for label in labels:
    ner.add_label(label)

# Training loop
optimizer = nlp.begin_training()
for i in range(20):
    random.shuffle(TRAIN_DATA)
    losses = {}
    for text, ann in TRAIN_DATA:
        example = Example.from_dict(nlp.make_doc(text), ann)
        nlp.update([example], drop=0.5, losses=losses)
    print(f"Iteration {i+1}, Losses: {losses}")

# Save the trained model with a version
model_version = "v1.1"
output_dir = f"allergen_ner_model_{model_version}"
nlp.to_disk(output_dir)
print(f"Model saved to {output_dir}") 