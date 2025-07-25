import os
import sys
import logging
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import spacy
from spacy.matcher import Matcher, PhraseMatcher
from spacy.tokens import Doc, Span
import pandas as pd
from django.utils import timezone
from django.db.models import Count, Avg
from django.core.cache import cache
from django.apps import apps

# Setup Django environment for model imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')

try:
    from recipes.models import AllergenCategory, AllergenSynonym, AllergenDetectionLog, AllergenDictionaryVersion
except ImportError:
    # If Django models are not available, create placeholder classes
    class AllergenCategory:
        objects = None
        def __init__(self, name):
            self.name = name
    
    class AllergenSynonym:
        objects = None
        def __init__(self, **kwargs):
            pass
    
    class AllergenDetectionLog:
        objects = None
        def __init__(self, **kwargs):
            pass
    
    class AllergenDictionaryVersion:
        objects = None
        def __init__(self, **kwargs):
            pass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nlp_ingredient_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AllergenCategoryEnum(Enum):
    """Enum for allergen categories - aligned with FSA 14 major allergens"""
    CELERY = "celery"
    CEREALS_GLUTEN = "cereals_gluten"  # Wheat, rye, barley, oats
    CRUSTACEANS = "crustaceans"  # Crabs, lobsters, prawns
    EGGS = "eggs"
    FISH = "fish"
    LUPIN = "lupin"
    MILK = "milk"
    MOLLUSCS = "molluscs"  # Mussels, oysters, squid
    MUSTARD = "mustard"
    NUTS = "nuts"  # Tree nuts (almonds, hazelnuts, walnuts, etc.)
    PEANUTS = "peanuts"
    SESAME = "sesame"
    SOYBEANS = "soybeans"
    SULPHITES = "sulphites"  # Sulphur dioxide/sulphites

@dataclass
class IngredientMatch:
    """Data class for ingredient matches"""
    text: str
    category: AllergenCategoryEnum
    confidence: float
    start_char: int
    end_char: int
    context: str

@dataclass
class AllergenAnalysisResult:
    """Data class for allergen analysis results"""
    risk_level: str
    confidence_scores: Dict[str, float]
    detected_allergens: Dict[AllergenCategoryEnum, List[IngredientMatch]]
    recommendations: List[str]
    raw_matches: List[Dict[str, Any]]
    total_ingredients: int
    analyzed_ingredients: int
    model_version: str

class AllergenPatterns:
    """Contains patterns for allergen detection - aligned with FSA 14 major allergens"""
    
    # Celery patterns
    CELERY_PATTERNS = [
        "celery", "celery seed", "celery seeds", "celery salt", "celery powder",
        "celery extract", "celery juice", "celery root", "celeriac", "celery leaf",
        "celery stalk", "celery heart", "celery soup", "celery stock"
    ]
    
    # Cereals containing gluten patterns (wheat, rye, barley, oats)
    CEREALS_GLUTEN_PATTERNS = [
        "wheat", "wheat flour", "wheat bran", "wheat germ", "wheat starch",
        "wheat protein", "wheat gluten", "wheat bread", "wheat pasta",
        "wheat cereal", "durum wheat", "semolina", "bulgur", "couscous", "farro", "spelt",
        "kamut", "triticale", "wheatgrass", "rye", "rye flour", "rye bread", "rye cereal",
        "barley", "barley flour", "barley malt", "barley cereal", "pearl barley",
        "oats", "oat flour", "oatmeal", "oat cereal", "rolled oats", "steel cut oats",
        "gluten", "gluten-free", "gluten containing", "gluten protein", "gluten flour",
        "gluten bread", "gluten pasta", "gluten cereal", "gluten beer", "gluten sauce"
    ]
    
    # Crustaceans patterns (crabs, lobsters, prawns)
    CRUSTACEANS_PATTERNS = [
        "shrimp", "prawn", "prawns", "crab", "crabs", "lobster", "lobsters", "crayfish", "crawfish",
        "crustacean", "crustaceans", "shrimp paste", "crab meat", "lobster meat",
        "prawn meat", "shrimp stock", "crab stock", "lobster stock"
    ]
    
    # Egg patterns
    EGG_PATTERNS = [
        "egg", "eggs", "egg white", "egg yolk", "egg powder", "dried egg",
        "egg substitute", "egg replacer", "albumin", "ovalbumin", "lysozyme",
        "egg wash"
    ]
    
    # Fish patterns
    FISH_PATTERNS = [
        "fish", "salmon", "tuna", "cod", "haddock", "mackerel", "sardines",
        "anchovies", "trout", "bass", "perch", "tilapia", "swordfish",
        "halibut", "flounder", "sole", "catfish", "fish oil", "fish sauce",
        "fish stock", "fish broth", "fish paste", "fish powder"
    ]
    
    # Lupin patterns
    LUPIN_PATTERNS = [
        "lupin", "lupine", "lupini", "lupin bean", "lupin beans", "lupin flour",
        "lupin protein", "lupin extract", "lupin seed", "lupin seeds"
    ]
    
    # Milk patterns
    MILK_PATTERNS = [
        "milk", "cheese", "yogurt", "cream", "butter", "ghee", "casein", "whey",
        "lactose", "lactose-free", "dairy-free", "non-dairy", "milk powder",
        "evaporated milk", "condensed milk", "buttermilk", "sour cream",
        "heavy cream", "half and half", "whipping cream", "ice cream",
        "milk chocolate", "white chocolate", "milk solids", "milk protein"
    ]
    
    # Molluscs patterns (mussels, oysters, squid)
    MOLLUSCS_PATTERNS = [
        "mollusc", "molluscs", "mollusk", "mollusks", "abalone", "clam", "clams",
        "mussel", "mussels", "oyster", "oysters", "scallop", "scallops",
        "snail", "snails", "escargot", "conch", "conchs", "whelk", "whelks",
        "squid", "calamari", "octopus", "octopi"
    ]
    
    # Mustard patterns
    MUSTARD_PATTERNS = [
        "mustard", "mustard seed", "mustard seeds", "mustard oil", "mustard powder",
        "mustard flour", "mustard protein", "mustard extract", "mustard sauce",
        "mustard dressing", "mustard condiment", "mustard spread"
    ]
    
    # Nuts patterns (tree nuts: almonds, hazelnuts, walnuts, cashews, pecans, brazils, pistachios, macadamia nuts)
    NUTS_PATTERNS = [
        "almond", "almonds", "walnut", "walnuts", "pecan", "pecans",
        "cashew", "cashews", "pistachio", "pistachios", "hazelnut", "hazelnuts",
        "macadamia", "macadamias", "brazil nut", "brazil nuts", "pine nut",
        "pine nuts", "chestnut", "chestnuts", "filbert", "filberts",
        "almond milk", "almond butter", "almond flour", "almond extract",
        "walnut oil", "pecan oil", "hazelnut oil", "nut butter", "nut milk"
    ]
    
    # Peanut patterns
    PEANUT_PATTERNS = [
        "peanut", "peanuts", "peanut butter", "peanut oil", "peanut flour",
        "peanut protein", "peanut extract", "peanut sauce", "peanut paste",
        "groundnut", "groundnuts", "arachis", "arachis oil", "peanut milk"
    ]
    
    # Sesame patterns
    SESAME_PATTERNS = [
        "sesame", "sesame seed", "sesame seeds", "sesame oil", "sesame paste",
        "sesame butter", "sesame flour", "sesame protein", "sesame extract",
        "tahini", "sesame milk", "sesame sauce", "sesame dressing"
    ]
    
    # Soybean patterns
    SOYBEAN_PATTERNS = [
        "soy", "soya", "soybean", "soybeans", "soy milk", "soy sauce",
        "soy oil", "soy flour", "soy protein", "soy lecithin", "soy isolate",
        "soy concentrate", "soy fiber", "soy nuts", "soy yogurt", "soy cheese",
        "tofu", "tempeh", "miso", "edamame", "soybean oil", "soybean flour",
        "soybean protein", "soybean lecithin", "soybean isolate"
    ]
    
    # Sulphites patterns (sulphur dioxide/sulphites)
    SULPHITES_PATTERNS = [
        "sulfite", "sulfites", "sulphite", "sulphites", "sulfur dioxide",
        "sodium sulfite", "sodium bisulfite", "sodium metabisulfite",
        "potassium sulfite", "potassium bisulfite", "potassium metabisulfite",
        "calcium sulfite", "calcium bisulfite", "calcium metabisulfite"
    ]

class NLPIngredientProcessor:
    """NLP processor for ingredient analysis and allergen detection"""
    
    def __init__(self, model_path: str = None, conflict_policy: str = 'flag_if_either', model_version: str = "v1.0"):
        if model_path and os.path.exists(model_path):
            self.nlp = spacy.load(model_path)
        else:
            self.nlp = spacy.load("en_core_web_sm")
        self.conflict_policy = conflict_policy
        self.model_version = model_version
        self.matcher = None
        self.phrase_matcher = None
        self.allergen_patterns = {}
        self._initialize_nlp()
        self._setup_patterns()

    def _initialize_nlp(self):
        """Initialize spaCy NLP model"""
        try:
            self.matcher = Matcher(self.nlp.vocab)
            self.phrase_matcher = PhraseMatcher(self.nlp.vocab)
            logger.info("NLP model loaded successfully")
        except OSError:
            logger.warning(f"Model '{self.nlp.name}' not found. Installing...")
            try:
                import subprocess
                subprocess.run([sys.executable, "-m", "spacy", "download", self.nlp.name], check=True)
                self.nlp = spacy.load(self.nlp.name)
                self.matcher = Matcher(self.nlp.vocab)
                self.phrase_matcher = PhraseMatcher(self.nlp.vocab)
                logger.info(f"NLP model '{self.nlp.name}' installed and loaded successfully")
            except Exception as e:
                logger.error(f"Failed to install/load NLP model: {e}")
                # Fallback to a basic model or raise the error
                raise RuntimeError(f"Could not load or install spaCy model: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading NLP model: {e}")
            raise

    def _setup_patterns(self):
        """Setup allergen detection patterns"""
        patterns = AllergenPatterns()
        
        # Create pattern dictionaries
        self.allergen_patterns = {
            AllergenCategoryEnum.CELERY: patterns.CELERY_PATTERNS,
            AllergenCategoryEnum.CEREALS_GLUTEN: patterns.CEREALS_GLUTEN_PATTERNS,
            AllergenCategoryEnum.CRUSTACEANS: patterns.CRUSTACEANS_PATTERNS,
            AllergenCategoryEnum.EGGS: patterns.EGG_PATTERNS,
            AllergenCategoryEnum.FISH: patterns.FISH_PATTERNS,
            AllergenCategoryEnum.LUPIN: patterns.LUPIN_PATTERNS,
            AllergenCategoryEnum.MILK: patterns.MILK_PATTERNS,
            AllergenCategoryEnum.MOLLUSCS: patterns.MOLLUSCS_PATTERNS,
            AllergenCategoryEnum.MUSTARD: patterns.MUSTARD_PATTERNS,
            AllergenCategoryEnum.NUTS: patterns.NUTS_PATTERNS,
            AllergenCategoryEnum.PEANUTS: patterns.PEANUT_PATTERNS,
            AllergenCategoryEnum.SESAME: patterns.SESAME_PATTERNS,
            AllergenCategoryEnum.SOYBEANS: patterns.SOYBEAN_PATTERNS,
            AllergenCategoryEnum.SULPHITES: patterns.SULPHITES_PATTERNS
        }
        
        # Add patterns to matchers
        for category, patterns_list in self.allergen_patterns.items():
            # Add to phrase matcher for exact matches
            self.phrase_matcher.add(category.value, [self.nlp(text) for text in patterns_list])
            
            # Add to regular matcher for variations
            for pattern in patterns_list:
                # Create pattern variations
                variations = [
                    [{"LOWER": pattern}],
                    [{"LOWER": pattern + "s"}],  # plural
                    [{"LOWER": pattern.replace(" ", "")}],  # no spaces
                    [{"LOWER": pattern.replace(" ", "-")}],  # hyphenated
                ]
                
                for variation in variations:
                    self.matcher.add(f"{category.value}_{pattern}", [variation])

    def extract_ingredients(self, text: str) -> List[str]:
        """Extract individual ingredients from text"""
        doc = self.nlp(text.lower())
        ingredients = []
        
        # Look for ingredient patterns
        ingredient_patterns = [
            r'\d+\s*(?:cup|tbsp|tsp|oz|lb|g|kg|ml|l|pound|ounce|gram|kilogram|liter|milliliter)s?\s+[a-zA-Z\s]+',
            r'[a-zA-Z\s]+\s+\d+\s*(?:cup|tbsp|tsp|oz|lb|g|kg|ml|l|pound|ounce|gram|kilogram|liter|milliliter)s?',
            r'\d+\s*-\s*\d+\s*(?:cup|tbsp|tsp|oz|lb|g|kg|ml|l|pound|ounce|gram|kilogram|liter|milliliter)s?\s+[a-zA-Z\s]+',
            r'[a-zA-Z\s]+\s+\d+\s*-\s*\d+\s*(?:cup|tbsp|tsp|oz|lb|g|kg|ml|l|pound|ounce|gram|kilogram|liter|milliliter)s?'
        ]
        
        for pattern in ingredient_patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                ingredient = match.group().strip()
                if len(ingredient) > 3:  # Filter out very short matches
                    ingredients.append(ingredient)
        
        # Also extract simple ingredient names
        simple_ingredients = re.findall(r'\b[a-zA-Z]+\s+[a-zA-Z]+\s+[a-zA-Z]+\b', text.lower())
        ingredients.extend(simple_ingredients)
        
        # Remove duplicates and clean up
        unique_ingredients = list(set(ingredients))
        cleaned_ingredients = [ing.strip() for ing in unique_ingredients if len(ing.strip()) > 2]
        
        return cleaned_ingredients

    def detect_allergens(self, text: str) -> Dict[AllergenCategoryEnum, List[IngredientMatch]]:
        """Detect allergens in text with conflict resolution policy"""
        doc = self.nlp(text.lower())
        detected_allergens = {category: [] for category in AllergenCategoryEnum}
        rule_matches = {}
        nlp_matches = {}

        # Use phrase matcher for exact matches (rule-based)
        phrase_matches = self.phrase_matcher(doc)
        for match_id, start, end in phrase_matches:
            category_name = self.nlp.vocab.strings[match_id]
            category = AllergenCategoryEnum(category_name)
            span = doc[start:end]
            match = IngredientMatch(
                text=span.text,
                category=category,
                confidence=1.0,
                start_char=span.start_char,
                end_char=span.end_char,
                context=span.sent.text if span.sent else span.text
            )
            rule_matches.setdefault(category, []).append(match)

        # Use regular matcher for variations (NLP-based)
        regular_matches = self.matcher(doc)
        for match_id, start, end in regular_matches:
            category_name = self.nlp.vocab.strings[match_id]
            category = AllergenCategoryEnum(category_name)
            span = doc[start:end]
            match = IngredientMatch(
                text=span.text,
                category=category,
                confidence=0.8,  # Lower confidence for NLP-based
                start_char=span.start_char,
                end_char=span.end_char,
                context=span.sent.text if span.sent else span.text
            )
            nlp_matches.setdefault(category, []).append(match)

        # Conflict resolution
        for category in AllergenCategoryEnum:
            rule_set = set(m.text for m in rule_matches.get(category, []))
            nlp_set = set(m.text for m in nlp_matches.get(category, []))
            if self.conflict_policy == 'flag_if_both':
                if rule_set and nlp_set:
                    detected_allergens[category] = rule_matches[category] + nlp_matches[category]
            elif self.conflict_policy == 'manual_review_if_conflict':
                if (rule_set and not nlp_set) or (nlp_set and not rule_set):
                    # Optionally, log or flag for manual review
                    logger.warning(f"Conflict for {category.value}: rule={rule_set}, nlp={nlp_set}")
                if rule_set or nlp_set:
                    detected_allergens[category] = rule_matches.get(category, []) + nlp_matches.get(category, [])
            else:  # Default: flag if either
                if rule_set or nlp_set:
                    detected_allergens[category] = rule_matches.get(category, []) + nlp_matches.get(category, [])
        return detected_allergens

    def calculate_risk_level(self, detected_allergens: Dict[AllergenCategoryEnum, List[IngredientMatch]]) -> str:
        """Calculate overall risk level based on detected allergens"""
        if not detected_allergens:
            return "low"  # Changed from "none" to "low" for consistency
        
        # Count allergens by category
        allergen_counts = {category: len(matches) for category, matches in detected_allergens.items() if matches}
        
        # High-risk allergens (most severe reactions)
        high_risk_categories = {
            AllergenCategoryEnum.PEANUTS, AllergenCategoryEnum.NUTS, 
            AllergenCategoryEnum.CRUSTACEANS, AllergenCategoryEnum.FISH
        }
        
        # Medium-risk allergens (can be severe, less common, often outgrown)
        medium_risk_categories = {
            AllergenCategoryEnum.EGGS, AllergenCategoryEnum.MILK, AllergenCategoryEnum.CEREALS_GLUTEN,
            AllergenCategoryEnum.SOYBEANS, AllergenCategoryEnum.SESAME, AllergenCategoryEnum.MOLLUSCS, AllergenCategoryEnum.LUPIN
        }
        
        # Count high and medium risk allergens
        high_risk_count = sum(1 for category in high_risk_categories if category in allergen_counts)
        medium_risk_count = sum(1 for category in medium_risk_categories if category in allergen_counts)
        total_allergens = len(allergen_counts)
        
        # Determine risk level with CRITICAL level added
        if high_risk_count >= 2 or (high_risk_count >= 1 and total_allergens >= 4):
            return "critical"  # Multiple high-risk allergens or high-risk + many others
        elif high_risk_count > 0:
            return "high"  # Any high-risk allergen
        elif medium_risk_count >= 1:
            return "medium"  # Any medium-risk allergen
        elif total_allergens >= 1:
            return "low"  # 1+ allergen present
        else:
            return "low"  # No allergens detected (safe)

    def calculate_confidence_scores(self, detected_allergens: Dict[AllergenCategoryEnum, List[IngredientMatch]]) -> Dict[str, float]:
        """Calculate confidence scores for each allergen category"""
        confidence_scores = {}
        
        for category, matches in detected_allergens.items():
            if matches:
                # Calculate average confidence for this category
                avg_confidence = sum(match.confidence for match in matches) / len(matches)
                confidence_scores[category.value] = avg_confidence
            else:
                confidence_scores[category.value] = 0.0
        
        return confidence_scores

    def generate_recommendations(self, detected_allergens: Dict[AllergenCategoryEnum, List[IngredientMatch]], risk_level: str) -> List[str]:
        """Generate recommendations based on detected allergens"""
        recommendations = []
        
        if risk_level == "critical":
            recommendations.append("🚨 CRITICAL RISK: This recipe contains multiple high-risk allergens. AVOID if you have food allergies.")
            recommendations.append("Consult with a medical professional immediately if you have any food allergies.")
            recommendations.append("Consider finding an alternative recipe without these allergens.")
        elif risk_level == "high":
            recommendations.append("⚠️ HIGH RISK: This recipe contains high-risk allergens. Exercise extreme caution.")
            recommendations.append("Consider consulting with a medical professional before consumption.")
        elif risk_level == "medium":
            recommendations.append("⚠️ MEDIUM RISK: This recipe contains multiple allergens. Review ingredients carefully.")
        elif risk_level == "low":
            recommendations.append("ℹ️ LOW RISK: This recipe appears to be allergen-free or contains minimal allergens.")
        else:
            recommendations.append("✅ SAFE: This recipe appears to be allergen-free based on our analysis.")
        
        # Add specific allergen recommendations
        allergen_names = [category.value.replace('_', ' ').title() for category, matches in detected_allergens.items() if matches]
        if allergen_names:
            recommendations.append(f"Detected allergens: {', '.join(allergen_names)}")
        
        # Add general recommendations
        recommendations.append("Always read ingredient labels carefully and consult with healthcare providers if you have food allergies.")
        
        return recommendations

    def analyze_allergens(self, text: str, conflict_policy: str = 'flag_if_either', cache_key: Optional[str] = None) -> AllergenAnalysisResult:
        """Complete allergen analysis of text, with caching support and conflict policy"""
        if cache_key:
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"Returning cached analysis for {cache_key}")
                return cached
        logger.info("Starting allergen analysis")
        ingredients = self.extract_ingredients(text)
        detected_allergens = self.detect_allergens(text) if conflict_policy == 'flag_if_either' else self.detect_allergens(text)
        risk_level = self.calculate_risk_level(detected_allergens)
        confidence_scores = self.calculate_confidence_scores(detected_allergens)
        recommendations = self.generate_recommendations(detected_allergens, risk_level)
        raw_matches = []
        for category, matches in detected_allergens.items():
            for match in matches:
                raw_matches.append({
                    'text': match.text,
                    'category': match.category.value,
                    'confidence': match.confidence,
                    'start_char': match.start_char,
                    'end_char': match.end_char,
                    'context': match.context,
                    'match_type': 'rule' if match.confidence == 1.0 else 'nlp'  # Explainability
                })
        result = AllergenAnalysisResult(
            risk_level=risk_level,
            confidence_scores=confidence_scores,
            detected_allergens=detected_allergens,
            recommendations=recommendations,
            raw_matches=raw_matches,
            total_ingredients=len(ingredients),
            analyzed_ingredients=len(ingredients)
        )
        # Attach model version for reproducibility
        result.model_version = self.model_version
        if cache_key:
            cache.set(cache_key, result, 60*60)  # Cache for 1 hour
        logger.info(f"Allergen analysis completed. Risk level: {risk_level}")
        logger.info(f"Detected {len(raw_matches)} allergen matches across {len([c for c, m in detected_allergens.items() if m])} categories")
        return result

    def get_allergen_statistics(self, text: str) -> Dict[str, Any]:
        """Get detailed statistics about allergen detection"""
        result = self.analyze_allergens(text)
        
        # Count matches by category
        category_counts = {}
        for category, matches in result.detected_allergens.items():
            category_counts[category.value] = len(matches)
        
        # Calculate average confidence
        avg_confidence = sum(result.confidence_scores.values()) / len(result.confidence_scores) if result.confidence_scores else 0
        
        return {
            'risk_level': result.risk_level,
            'total_matches': len(result.raw_matches),
            'category_counts': category_counts,
            'average_confidence': avg_confidence,
            'total_ingredients': result.total_ingredients,
            'analyzed_ingredients': result.analyzed_ingredients,
            'detected_categories': [cat.value for cat, matches in result.detected_allergens.items() if matches]
        }

    def process_user_feedback(self, recipe_id, detected_term, is_correct, user_notes):
        """Process user feedback on allergen detection"""
        try:
            # Find the detection log
            detection_log = AllergenDetectionLog.objects.filter(
                recipe_id=recipe_id,
                detected_term=detected_term
            ).first()
            
            if detection_log:
                # Mark as correct/incorrect
                detection_log.is_correct = is_correct
                detection_log.verified_by = "user_feedback"
                detection_log.verification_date = timezone.now()
                detection_log.save()
                
                # Flag for review if incorrect
                if not is_correct:
                    self._flag_term_for_review(detected_term, user_notes)
        except Exception as e:
            logger.error(f"Error processing user feedback: {e}")

    def _flag_term_for_review(self, detected_term: str, user_notes: str):
        """Flag a term for manual review"""
        try:
            # Create a review entry or update existing one
            review_entry = {
                'term': detected_term,
                'notes': user_notes,
                'flagged_at': timezone.now(),
                'status': 'pending_review'
            }
            
            # In a real implementation, you might save this to a database
            # For now, we'll just log it
            logger.info(f"Term flagged for review: {detected_term} - {user_notes}")
            
        except Exception as e:
            logger.error(f"Error flagging term for review: {e}")

    def discover_new_terms(self):
        """Analyze detection logs to find potential new terms"""
        try:
            # 1. Find terms that were detected but with low confidence
            low_confidence_detections = AllergenDetectionLog.objects.filter(
                confidence_score__lt=0.5,  # Less than 50% confidence
                is_correct__isnull=True    # Not yet verified by humans
            )
            
            # 2. Group by term and count occurrences
            term_frequency = {}
            for detection in low_confidence_detections:
                term = detection.detected_term
                if term not in term_frequency:
                    term_frequency[term] = {
                        'count': 0,
                        'total_confidence': 0,
                        'contexts': []
                    }
                
                term_frequency[term]['count'] += 1
                term_frequency[term]['total_confidence'] += detection.confidence_score
                term_frequency[term]['contexts'].append(detection.context)
            
            # 3. Find terms that appear frequently but aren't in dictionary
            new_terms = []
            for term, data in term_frequency.items():
                if data['count'] >= 3:  # Appears at least 3 times
                    avg_confidence = data['total_confidence'] / data['count']
                    
                    # Check if term is NOT already in dictionary
                    if not AllergenSynonym.objects.filter(term__iexact=term).exists():
                        new_terms.append({
                            'term': term,
                            'frequency': data['count'],
                            'avg_confidence': avg_confidence,
                            'contexts': data['contexts'][:5]  # First 5 contexts
                        })
            
            return new_terms
        except Exception as e:
            logger.error(f"Error discovering new terms: {e}")
            return []

    def update_dictionary_with_new_terms(self, approved_terms):
        """Update dictionary with newly approved terms"""
        try:
            # 1. Create new version
            new_version = AllergenDictionaryVersion.objects.create(
                version="FSA-1.1",  # Increment version
                description="Added cashew butter, tahini paste, and other discovered terms",
                total_categories=14,
                total_terms=AllergenSynonym.objects.count() + len(approved_terms),
                is_active=False  # Not active yet
            )
            
            # 2. Add each approved term
            for term_data in approved_terms:
                category = AllergenCategory.objects.get(name=term_data['category'])
                
                # Add to database
                AllergenSynonym.objects.create(
                    allergen_category=category,
                    term=term_data['term'],
                    term_type=term_data['term_type'],
                    confidence_score=term_data['confidence'],
                    is_active=True
                )
                
                logger.info(f"Added: {term_data['term']} -> {term_data['category']}")
            
            # 3. Activate new version
            # Deactivate old version
            AllergenDictionaryVersion.objects.exclude(id=new_version.id).update(is_active=False)
            
            # Activate new version
            new_version.is_active = True
            new_version.activated_at = timezone.now()
            new_version.save()
            
            logger.info(f"Dictionary updated to version {new_version.version}")
            logger.info(f"Added {len(approved_terms)} new terms")
            
        except Exception as e:
            logger.error(f"Error updating dictionary with new terms: {e}")

    def learn_from_patterns(self):
        """Learn from detection patterns"""
        try:
            # Analyze successful detections
            successful_detections = AllergenDetectionLog.objects.filter(
                is_correct=True
            ).values('detected_term', 'allergen_category').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence_score')
            )
            
            # Find terms that are consistently detected correctly
            reliable_terms = []
            for detection in successful_detections:
                if detection['count'] >= 10 and detection['avg_confidence'] >= 0.8:
                    reliable_terms.append(detection)
            
            # Increase confidence scores for reliable terms
            for term_data in reliable_terms:
                synonym = AllergenSynonym.objects.filter(
                    term=term_data['detected_term'],
                    allergen_category__name=term_data['allergen_category']
                ).first()
                
                if synonym and synonym.confidence_score < 0.9:
                    synonym.confidence_score = min(0.9, synonym.confidence_score + 0.1)
                    synonym.save()
                    logger.info(f"Increased confidence for {term_data['detected_term']}")
                    
        except Exception as e:
            logger.error(f"Error learning from patterns: {e}")

    def export_feedback_for_retraining(self, output_path: str = "feedback_training_data.json"):
        """
        Export user feedback as spaCy NER training data.
        
        """
        UserFeedback = apps.get_model('recipes', 'UserFeedback')
        feedbacks = UserFeedback.objects.filter(status__in=["reviewed", "resolved"]).exclude(detected_term="")
        training_data = []
        for fb in feedbacks:
            text = fb.recipe.scraped_ingredients_text if hasattr(fb.recipe, 'scraped_ingredients_text') else fb.recipe.title
            if isinstance(text, list):
                text = ", ".join(text)
            term = fb.detected_term
            # Find all occurrences of the term in the text
            start = text.lower().find(term.lower())
            if start != -1:
                end = start + len(term)
                training_data.append((text, {"entities": [(start, end, "ALLERGEN")]}))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(training_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Exported {len(training_data)} feedback items for NER retraining to {output_path}")

    def parse_compound_ingredients(self, text: str):
        """Parse compound ingredients using spaCy dependency parsing (placeholder)."""
        doc = self.nlp(text)
        compounds = []
        for chunk in doc.noun_chunks:
            compounds.append(chunk.text)
        return compounds

    def calibrate_confidence(self, validation_data):
        """Placeholder for confidence calibration using validation data."""
        # Implement Platt scaling or isotonic regression as needed
        # For now, just log the average confidence
        confidences = [score for _, score in validation_data]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        logger.info(f"Average model confidence on validation set: {avg_conf:.2f}")

def get_nlp_processor(model_path: str = None) -> NLPIngredientProcessor:
    """Factory function to get NLP processor instance"""
    return NLPIngredientProcessor(model_path)

def main():
    """Test the NLP processor with sample text"""
    try:
        processor = get_nlp_processor()
        
        # Sample recipe text
        sample_text = """
        Ingredients:
        1 cup milk
        1 stalk celery
        
        Instructions:
        Mix milk with chopped celery.
        """
        
        print("=== NLP Ingredient Processor Test ===")
        print(f"Sample text: {sample_text}")
        
        # Extract ingredients
        ingredients = processor.extract_ingredients(sample_text)
        print(f"\nExtracted ingredients: {ingredients}")
        
        # Analyze allergens
        result = processor.analyze_allergens(sample_text)
        print(f"\nRisk level: {result.risk_level}")
        print(f"Detected allergens: {[cat.value for cat, matches in result.detected_allergens.items() if matches]}")
        print(f"Recommendations: {result.recommendations}")
        
        # Get statistics
        stats = processor.get_allergen_statistics(sample_text)
        print(f"\nStatistics: {stats}")
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 