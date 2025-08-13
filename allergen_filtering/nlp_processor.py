"""
NLP Processor for Allergen Detection
Integrates with allergen dictionary for advanced text analysis and ingredient extraction
"""

import re
import sys
import spacy
import nltk
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
from enum import Enum
import logging

from allergen_filtering.allergen_dictionary import AllergenDictionary, get_allergen_dictionary
from allergen_filtering.fsa_allergen_dictionary import FSAAllergenDictionary, get_fsa_allergen_dictionary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class IngredientMatch:
    """Represents a detected ingredient with its context and confidence"""
    text: str
    allergen_category: str
    confidence: float
    position: Tuple[int, int]
    context: str
    match_type: str  # 'exact', 'fuzzy', 'contextual'


@dataclass
class AllergenAnalysis:
    """Represents the complete allergen analysis of a text"""
    text: str
    detected_allergens: Dict[str, List[IngredientMatch]]
    confidence_scores: Dict[str, float]
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    recommendations: List[str]
    raw_matches: Dict[str, List[str]] | Dict[str, Dict[str, List[str]]]
    model_version: str = ""
    dictionary_version: str = ""


class ConflictPolicy(Enum):
    FLAG_IF_EITHER = "flag_if_either"
    REQUIRE_BOTH = "require_both"
    PREFER_RULE = "prefer_rule"
    PREFER_MODEL = "prefer_model"
    WEIGHTED_FUSION = "weighted_fusion"


class NLPProcessor:
    """
    Advanced NLP processor for allergen detection and ingredient analysis
    Integrates with allergen dictionary and uses spaCy for text processing
    """
    
    def __init__(self, allergen_dict: Optional[object] = None, spacy_model: str = "en_core_web_sm", model_version: str = "v1"):
        """
        Initialize the NLP processor
        
        Args:
            allergen_dict: Allergen dictionary instance (uses FSA by default if None)
            spacy_model: spaCy model to use for NLP processing
        """
        if allergen_dict is None:
            self.allergen_dict = get_fsa_allergen_dictionary()
        else:
            self.allergen_dict = allergen_dict
        
        # Initialize spaCy
        try:
            self.nlp = spacy.load(spacy_model)
            logger.info(f"Loaded spaCy model: {spacy_model}")
        except OSError:
            logger.warning(f"spaCy model {spacy_model} not found. Installing...")
            import subprocess
            subprocess.run([sys.executable, "-m", "spacy", "download", spacy_model])
            self.nlp = spacy.load(spacy_model)

        # Version metadata
        self.model_name = spacy_model
        self.model_version = model_version
        # Best-effort dictionary version
        self.dictionary_version = getattr(self.allergen_dict, "version", self.allergen_dict.__class__.__name__)
        
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')
        
        # Initialize ingredient patterns
        self.ingredient_patterns = self._build_ingredient_patterns()
        
        # Initialize confidence weights
        self.confidence_weights = {
            'exact_match': 1.0,
            'fuzzy_match': 0.8,
            'contextual_match': 0.6,
            'scientific_name': 0.9,
            'hidden_source': 0.7,
            'main_ingredient': 1.0,
            'synonym': 0.8
        }

        # Exceptions and negation helpers
        self.false_friend_terms_by_category = {
            'tree_nuts': {"nutmeg"},
        }
        self.negation_lemmas = {"no", "not", "without", "free", "omit", "avoid", "exclude"}
        self.free_pattern = re.compile(r"\b([a-zA-Z\-]+)\s*[- ]?free\b", re.IGNORECASE)
    
    def _build_ingredient_patterns(self) -> Dict[str, re.Pattern]:
        """Build regex patterns for ingredient detection"""
        patterns = {}
        
        # Common ingredient measurement patterns
        measurement_patterns = [
            r'\d+(?:\.\d+)?\s*(?:cup|cups|tablespoon|tbsp|teaspoon|tsp|ounce|oz|pound|lb|gram|g|kilogram|kg|ml|milliliter|liter|l)',
            r'\d+(?:\.\d+)?\s*(?:slice|slices|piece|pieces|clove|cloves|bunch|bunches|head|heads)',
            r'\d+(?:\.\d+)?\s*(?:can|cans|jar|jars|package|packages|bag|bags)',
            r'\d+(?:\.\d+)?\s*(?:to taste|as needed|optional)'
        ]
        
        # Combine patterns
        combined_pattern = '|'.join(measurement_patterns)
        patterns['measurement'] = re.compile(combined_pattern, re.IGNORECASE)
        
        # Ingredient list patterns
        patterns['ingredient_list'] = re.compile(
            r'(?:ingredients?|contains?|includes?|made with|prepared with):\s*(.+)',
            re.IGNORECASE | re.DOTALL
        )
        
        # Allergen warning patterns
        patterns['allergen_warning'] = re.compile(
            r'(?:contains?|may contain|processed in|manufactured in|packaged in).*?(?:facility|equipment|plant).*?(?:with|that also processes?|that manufactures?)',
            re.IGNORECASE
        )
        
        return patterns
    
    def extract_ingredients(self, text: str) -> List[str]:
        """
        Extract ingredients from text using NLP techniques
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of extracted ingredients
        """
        ingredients = []
        
        # Use spaCy for sentence segmentation and NER
        doc = self.nlp(text)
        
        # Extract ingredient lists
        ingredient_matches = self.ingredient_patterns['ingredient_list'].findall(text)
        for match in ingredient_matches:
            # Split by common delimiters
            potential_ingredients = re.split(r'[,;]|\band\b', match, flags=re.IGNORECASE)
            
            for ingredient in potential_ingredients:
                ingredient = ingredient.strip()
                if ingredient and len(ingredient) > 2:  # Filter out very short strings
                    # Clean up the ingredient
                    cleaned = self._clean_ingredient(ingredient)
                    if cleaned:
                        ingredients.append(cleaned)
        
        # Extract ingredients from sentences using NER and dependency parsing
        for sent in doc.sents:
            sent_ingredients = self._extract_ingredients_from_sentence(sent)
            ingredients.extend(sent_ingredients)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ingredients = []
        for ingredient in ingredients:
            if ingredient.lower() not in seen:
                seen.add(ingredient.lower())
                unique_ingredients.append(ingredient)
        
        return unique_ingredients
    
    def _clean_ingredient(self, ingredient: str) -> str:
        """Clean and normalize ingredient text"""
        # Remove measurement patterns
        ingredient = self.ingredient_patterns['measurement'].sub('', ingredient)
        
        # Remove common prefixes/suffixes
        ingredient = re.sub(r'^(?:fresh|dried|frozen|canned|organic|natural|artificial)\s+', '', ingredient, flags=re.IGNORECASE)
        ingredient = re.sub(r'\s+(?:fresh|dried|frozen|canned|organic|natural|artificial)$', '', ingredient, flags=re.IGNORECASE)
        
        # Remove extra whitespace
        ingredient = re.sub(r'\s+', ' ', ingredient).strip()
        
        # Remove punctuation at the end
        ingredient = re.sub(r'[.,;:]$', '', ingredient)
        
        return ingredient
    
    def _extract_ingredients_from_sentence(self, sent) -> List[str]:
        """Extract ingredients from a spaCy sentence"""
        ingredients = []
        
        # Look for noun phrases that might be ingredients
        for chunk in sent.noun_chunks:
            # Check if the chunk contains food-related words
            if self._is_food_related(chunk.text):
                ingredients.append(chunk.text)
        
        # Look for named entities that might be ingredients
        for ent in sent.ents:
            if ent.label_ in ['ORG', 'PRODUCT'] or self._is_food_related(ent.text):
                ingredients.append(ent.text)
        
        return ingredients
    
    def _is_food_related(self, text: str) -> bool:
        """Check if text is likely food-related"""
        food_indicators = [
            'flour', 'oil', 'sauce', 'butter', 'cheese', 'milk', 'egg', 'meat',
            'fish', 'vegetable', 'fruit', 'spice', 'herb', 'seed', 'nut', 'bean',
            'grain', 'cereal', 'bread', 'pasta', 'rice', 'sugar', 'salt', 'pepper'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in food_indicators)
    
    def analyze_allergens(self, text: str, conflict_policy: str = ConflictPolicy.FLAG_IF_EITHER.value, weighted_threshold: float = 0.7) -> AllergenAnalysis:
        """
        Perform comprehensive allergen analysis of text
        
        Args:
            text: Input text to analyze
            
        Returns:
            AllergenAnalysis object with detailed results
        """
        # Prepare doc once
        doc = self.nlp(text)

        # Rule/dictionary detection
        rule_raw_matches = self.allergen_dict.detect_allergens(text)
        # Placeholder for model-based detection
        model_raw_matches: Dict[str, List[str]] = {}

        def process_matches(source_matches: Dict[str, List[str]]) -> Dict[str, List[IngredientMatch]]:
            processed: Dict[str, List[IngredientMatch]] = defaultdict(list)
            for category, terms in source_matches.items():
                for term in terms:
                    positions = self._find_term_positions(text, term)
                    for start, end in positions:
                        span = doc.char_span(start, end, alignment_mode="expand")
                        context_start = max(0, start - 50)
                        context_end = min(len(text), end + 50)
                        context = text[context_start:context_end]

                        # Exceptions (false friends)
                        if category in self.false_friend_terms_by_category and term.lower() in self.false_friend_terms_by_category[category]:
                            continue
                        # Negation
                        if span is not None and self._is_negated(span, doc, text):
                            continue

                        match_type, confidence = self._determine_match_confidence(term, category, context)
                        processed[category].append(IngredientMatch(
                            text=term,
                            allergen_category=category,
                            confidence=confidence,
                            position=(start, end),
                            context=context,
                            match_type=match_type
                        ))
            return processed

        rule_matches = process_matches(rule_raw_matches)
        model_matches = process_matches(model_raw_matches)

        detected_allergens = self._resolve_conflicts(rule_matches, model_matches, conflict_policy, weighted_threshold)
        
        # Consolidate shellfish categories into unified "shellfish" category
        detected_allergens = self._consolidate_shellfish_categories(detected_allergens)

        # Confidence aggregation
        confidence_scores: Dict[str, float] = {}
        for category, matches in detected_allergens.items():
            confidence_scores[category] = max((m.confidence for m in matches), default=0.0)
        
        # Determine overall risk level
        risk_level = self._determine_risk_level(detected_allergens, confidence_scores)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(detected_allergens, risk_level)
        
        return AllergenAnalysis(
            text=text,
            detected_allergens=dict(detected_allergens),
            confidence_scores=dict(confidence_scores),
            risk_level=risk_level,
            recommendations=recommendations,
            raw_matches={"rule": rule_raw_matches, "model": model_raw_matches},
            model_version=self.model_version,
            dictionary_version=str(self.dictionary_version),
        )

    def _resolve_conflicts(
        self,
        rule_matches: Dict[str, List[IngredientMatch]],
        model_matches: Dict[str, List[IngredientMatch]],
        conflict_policy: str,
        weighted_threshold: float,
    ) -> Dict[str, List[IngredientMatch]]:
        policy = ConflictPolicy(conflict_policy) if not isinstance(conflict_policy, ConflictPolicy) else conflict_policy
        categories = set(rule_matches.keys()) | set(model_matches.keys())
        merged: Dict[str, List[IngredientMatch]] = {}
        for category in categories:
            r = rule_matches.get(category, [])
            m = model_matches.get(category, [])
            if policy == ConflictPolicy.FLAG_IF_EITHER:
                combined = r + [mm for mm in m if mm not in r]
            elif policy == ConflictPolicy.REQUIRE_BOTH:
                r_terms = {x.text.lower() for x in r}
                combined = [x for x in m if x.text.lower() in r_terms]
            elif policy == ConflictPolicy.PREFER_RULE:
                combined = r if r else m
            elif policy == ConflictPolicy.PREFER_MODEL:
                combined = m if m else r
            else:
                fused = r + m
                combined = [x for x in fused if x.confidence >= weighted_threshold]
            if combined:
                merged[category] = combined
        return merged
    
    def _consolidate_shellfish_categories(self, detected_allergens: Dict[str, List[IngredientMatch]]) -> Dict[str, List[IngredientMatch]]:
        """
        Consolidate individual shellfish categories (crustaceans, molluscs) into unified "shellfish" category
        """
        shellfish_categories = {"crustaceans", "molluscs"}
        consolidated = {}
        
        for category, matches in detected_allergens.items():
            if category in shellfish_categories:
                # Consolidate into shellfish category
                if "shellfish" not in consolidated:
                    consolidated["shellfish"] = []
                consolidated["shellfish"].extend(matches)
            else:
                # Keep other categories as-is
                consolidated[category] = matches
        
        return consolidated
    
    def _find_term_positions(self, text: str, term: str) -> List[Tuple[int, int]]:
        """Find all positions of a term in text"""
        positions = []
        text_lower = text.lower()
        term_lower = term.lower()
        
        start = 0
        while True:
            pos = text_lower.find(term_lower, start)
            if pos == -1:
                break
            positions.append((pos, pos + len(term)))
            start = pos + 1
        
        return positions
    
    def _determine_match_confidence(self, term: str, category: str, context: str) -> Tuple[str, float]:
        """Determine the type and confidence of a match"""
        allergen_info = self.allergen_dict.get_allergen_info(category)
        
        # If no allergen info available, return default confidence
        if not allergen_info:
            return 'exact_match', self.confidence_weights['exact_match']
        
        # Check if it's a main ingredient
        if term.lower() in [ing.lower() for ing in allergen_info.main_ingredients]:
            return 'main_ingredient', self.confidence_weights['main_ingredient']
        
        # Check if it's a scientific name
        if term.lower() in [name.lower() for name in allergen_info.scientific_names]:
            return 'scientific_name', self.confidence_weights['scientific_name']
        
        # Check if it's a hidden source
        if term.lower() in [source.lower() for source in allergen_info.hidden_sources]:
            return 'hidden_source', self.confidence_weights['hidden_source']
        
        # Check if it's a synonym
        if term.lower() in [syn.lower() for syn in allergen_info.synonyms]:
            return 'synonym', self.confidence_weights['synonym']
        
        # Default to exact match
        return 'exact_match', self.confidence_weights['exact_match']
    
    def _determine_risk_level(self, detected_allergens: Dict, confidence_scores: Dict) -> str:
        """Determine overall risk level based on detected allergens"""
        if not detected_allergens:
            return 'low'
        
        # Count high-confidence allergens
        high_confidence_count = sum(1 for score in confidence_scores.values() if score >= 0.8)
        total_allergens = len(detected_allergens)
        
        if high_confidence_count >= 3:
            return 'critical'
        elif high_confidence_count >= 2 or total_allergens >= 4:
            return 'high'
        elif high_confidence_count >= 1 or total_allergens >= 2:
            return 'medium'
        else:
            return 'low'
    
    def _generate_recommendations(self, detected_allergens: Dict, risk_level: str) -> List[str]:
        """Generate recommendations based on detected allergens and risk level"""
        recommendations = []
        
        if risk_level == 'critical':
            recommendations.append("CRITICAL: Multiple high-confidence allergens detected. Exercise extreme caution.")
            recommendations.append("Consider consulting with a medical professional before consumption.")
        
        elif risk_level == 'high':
            recommendations.append("HIGH RISK: Multiple allergens detected. Review ingredients carefully.")
            recommendations.append("Check for cross-contamination warnings on packaging.")
        
        elif risk_level == 'medium':
            recommendations.append("MEDIUM RISK: Some allergens detected. Review ingredient list thoroughly.")
            recommendations.append("Look for allergen-free alternatives if available.")
        
        else:
            recommendations.append("LOW RISK: No major allergens detected, but always verify ingredients.")
        
        # Add specific allergen recommendations
        for category, matches in detected_allergens.items():
            allergen_info = self.allergen_dict.get_allergen_info(category)
            if allergen_info:
                recommendations.append(f"Contains {allergen_info.name}: {', '.join(match.text for match in matches)}")
            else:
                # Handle consolidated categories that might not have direct allergen info
                if category == "shellfish":
                    recommendations.append(f"Contains Shellfish: {', '.join(match.text for match in matches)}")
                else:
                    recommendations.append(f"Contains {category.title()}: {', '.join(match.text for match in matches)}")
        
        return recommendations

    def _is_negated(self, span, doc, full_text: str) -> bool:
        """Return True if span is negated or part of an X-free context."""
        # Token window around span
        window_start = max(span.start - 3, 0)
        window_end = min(span.end + 3, len(doc))
        for tok in doc[window_start:window_end]:
            if tok.lemma_.lower() in self.negation_lemmas:
                return True
        # Check for '-free' patterns nearby
        context_text = full_text[max(0, span.start_char - 15): span.end_char + 15].lower()
        if "free" in context_text:
            return True
        # Simple dependency-based negation
        try:
            for tok in span.root.subtree:
                if tok.dep_ == "neg":
                    return True
        except Exception:
            pass
        return False
    
    def get_ingredient_analysis(self, text: str) -> Dict:
        """
        Get detailed ingredient analysis
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dictionary with ingredient analysis results
        """
        analysis = self.analyze_allergens(text)
        
        return {
            'ingredients': self.extract_ingredients(text),
            'allergen_analysis': analysis,
            'summary': {
                'total_ingredients': len(self.extract_ingredients(text)),
                'allergen_categories': list(analysis.detected_allergens.keys()),
                'risk_level': analysis.risk_level,
                'confidence_scores': analysis.confidence_scores
            }
        }


# Convenience function to get a configured NLP processor
def get_nlp_processor(allergen_dict: Optional[object] = None, spacy_model: str = "en_core_web_sm", model_version: str = "v1") -> NLPProcessor:
    """Get a configured NLP processor instance (uses FSA dictionary by default)"""
    return NLPProcessor(allergen_dict=allergen_dict, spacy_model=spacy_model, model_version=model_version)


if __name__ == "__main__":
    # Example usage
    processor = get_nlp_processor()
    
    test_text = """
    Ingredients: 2 cups all-purpose flour, 1 cup milk, 2 large eggs, 
    1/2 cup peanut butter, 1/4 cup soy sauce, 1 tbsp sesame oil, 
    1 tsp fish sauce, 1/2 cup shrimp, natural flavoring, 
    caramel color, and sulfites as preservatives.
    
    Contains: milk, eggs, peanuts, soy, fish, shellfish, sesame, sulfites.
    """
    
    analysis = processor.analyze_allergens(test_text)
    
    print("Allergen Analysis Results:")
    print(f"Risk Level: {analysis.risk_level}")
    print(f"Detected Allergens: {list(analysis.detected_allergens.keys())}")
    print(f"Confidence Scores: {analysis.confidence_scores}")
    print("\nRecommendations:")
    for rec in analysis.recommendations:
        print(f"  - {rec}")
    
    print(f"\nExtracted Ingredients: {processor.extract_ingredients(test_text)}") 