#!/usr/bin/env python
import os
import sys
import django
import re
import logging
from typing import List, Dict, Tuple, Optional

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

from recipes.models import Recipe, RecipeIngredientItem, Ingredient
from django.db import transaction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IngredientParser:
    """
    Parser for converting scraped ingredient text into structured RecipeIngredientItem records
    """
    
    def __init__(self):
        # Common measurement units
        self.units = {
            # Volume
            'cup', 'cups', 'tablespoon', 'tablespoons', 'tbsp', 'teaspoon', 'teaspoons', 'tsp',
            'ounce', 'ounces', 'oz', 'pint', 'pints', 'quart', 'quarts', 'gallon', 'gallons',
            'ml', 'milliliter', 'milliliters', 'liter', 'liters', 'l',
            # Weight
            'pound', 'pounds', 'lb', 'lbs', 'gram', 'grams', 'g', 'kilogram', 'kilograms', 'kg',
            # Count
            'piece', 'pieces', 'slice', 'slices', 'clove', 'cloves', 'bunch', 'bunches',
            'head', 'heads', 'can', 'cans', 'jar', 'jars', 'package', 'packages',
            # Special
            'pinch', 'dash', 'to taste', 'as needed', 'optional'
        }
        
        # Common quantity patterns
        self.quantity_patterns = [
            r'^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)',  # Range: "1-2 cups"
            r'^(\d+(?:\.\d+)?)\s*to\s*(\d+(?:\.\d+)?)',  # Range: "1 to 2 cups"
            r'^(\d+(?:\.\d+)?)\s*(\d+/\d+)',  # Mixed: "1 1/2 cups"
            r'^(\d+/\d+)',  # Fraction: "1/2 cup"
            r'^(\d+(?:\.\d+)?)',  # Decimal: "1.5 cups"
        ]
        
        # Clean up patterns
        self.cleanup_patterns = [
            r'^\s*[-•*]\s*',  # Remove bullet points
            r'^\s*\[\s*',  # Remove opening brackets
            r'\s*\]\s*$',  # Remove closing brackets
            r'^\s*[\'"`]',  # Remove quotes
            r'[\'"`]\s*$',  # Remove quotes
        ]
    
    def parse_ingredient_line(self, line: str) -> Dict[str, str]:
        """
        Parse a single ingredient line into quantity, unit, and name
        
        Args:
            line: Raw ingredient text line
            
        Returns:
            Dictionary with 'quantity', 'unit', 'name', and 'raw_text'
        """
        if not line or not line.strip():
            return {'quantity': '', 'unit': '', 'name': '', 'raw_text': line}
        
        # Clean up the line
        cleaned_line = line.strip()
        for pattern in self.cleanup_patterns:
            cleaned_line = re.sub(pattern, '', cleaned_line)
        
        # Initialize result
        result = {
            'quantity': '',
            'unit': '',
            'name': '',
            'raw_text': line.strip()
        }
        
        # Try to extract quantity and unit
        quantity, unit, remaining_text = self._extract_quantity_and_unit(cleaned_line)
        
        if quantity:
            result['quantity'] = quantity
        if unit:
            result['unit'] = unit
        
        # The remaining text is the ingredient name
        result['name'] = remaining_text.strip()
        
        return result
    
    def _extract_quantity_and_unit(self, text: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Extract quantity and unit from the beginning of ingredient text
        
        Returns:
            Tuple of (quantity, unit, remaining_text)
        """
        text = text.strip()
        
        # Try different quantity patterns
        for pattern in self.quantity_patterns:
            match = re.match(pattern, text)
            if match:
                if len(match.groups()) == 2:  # Range pattern
                    quantity = f"{match.group(1)}-{match.group(2)}"
                    remaining = text[match.end():].strip()
                else:  # Single quantity
                    quantity = match.group(1)
                    remaining = text[match.end():].strip()
                
                # Look for unit after quantity
                unit, name = self._extract_unit(remaining)
                return quantity, unit, name
        
        # If no quantity pattern found, try to extract just unit
        unit, name = self._extract_unit(text)
        return None, unit, name
    
    def _extract_unit(self, text: str) -> Tuple[Optional[str], str]:
        """
        Extract unit from the beginning of text
        
        Returns:
            Tuple of (unit, remaining_text)
        """
        text = text.strip()
        
        # Split by whitespace and check first word
        words = text.split()
        if not words:
            return None, text
        
        first_word = words[0].lower()
        
        # Check if first word is a unit
        if first_word in self.units:
            unit = words[0]  # Keep original case
            remaining = ' '.join(words[1:])
            return unit, remaining
        
        # Check if first word + second word is a unit (e.g., "extra virgin")
        if len(words) >= 2:
            two_words = f"{words[0]} {words[1]}".lower()
            if two_words in self.units:
                unit = f"{words[0]} {words[1]}"  # Keep original case
                remaining = ' '.join(words[2:])
                return unit, remaining
        
        return None, text
    
    def parse_recipe_ingredients(self, recipe: Recipe) -> List[Dict[str, str]]:
        """
        Parse all ingredients for a single recipe
        
        Args:
            recipe: Recipe object with scraped_ingredients_text
            
        Returns:
            List of parsed ingredient dictionaries
        """
        if not recipe.scraped_ingredients_text:
            return []
        
        # Check if this recipe has obviously bad ingredient data
        if self._has_bad_ingredient_data(recipe.scraped_ingredients_text):
            logger.warning(f"Recipe {recipe.id} has bad ingredient data, skipping")
            return []
        
        # First try to split by newlines
        lines = recipe.scraped_ingredients_text.split('\n')
        parsed_ingredients = []
        
        for line in lines:
            if line.strip():
                # If line contains multiple ingredients (separated by commas, etc.), split them
                if ',' in line and len(line) > 100:  # Likely multiple ingredients in one line
                    # Try to split by common separators
                    ingredients = self._split_ingredient_line(line)
                    for ingredient in ingredients:
                        if ingredient.strip():
                            parsed = self.parse_ingredient_line(ingredient)
                            if parsed['name'] and self._is_valid_ingredient(parsed['name']):
                                parsed_ingredients.append(parsed)
                else:
                    # Single ingredient per line
                    parsed = self.parse_ingredient_line(line)
                    if parsed['name'] and self._is_valid_ingredient(parsed['name']):
                        parsed_ingredients.append(parsed)
        
        return parsed_ingredients
    
    def _has_bad_ingredient_data(self, ingredient_text: str) -> bool:
        """
        Check if ingredient text contains obviously bad data
        
        Args:
            ingredient_text: Raw ingredient text to check
            
        Returns:
            True if text contains bad data, False otherwise
        """
        if not ingredient_text:
            return True
        
        # Check for navigation/menu patterns
        navigation_patterns = [
            r'home\s*about\s*recipes', r'start\s*here', r'contact\s*us',
            r'privacy\s*policy', r'terms\s*of\s*service', r'search\s*recipes',
            r'subscribe\s*to\s*newsletter', r'follow\s*us', r'share\s*this'
        ]
        
        text_lower = ingredient_text.lower()
        for pattern in navigation_patterns:
            if re.search(pattern, text_lower):
                return True
        
        # Check if text is too long (likely scraped wrong content)
        if len(ingredient_text) > 5000:
            return True
        
        # Check if text contains too many navigation-like words
        navigation_words = ['home', 'about', 'recipes', 'contact', 'privacy', 'terms', 'search', 'menu']
        word_count = sum(1 for word in navigation_words if word in text_lower)
        if word_count >= 3:
            return True
        
        return False
    
    def _split_ingredient_line(self, line: str) -> List[str]:
        """
        Split a line that contains multiple ingredients
        
        Args:
            line: Line that may contain multiple ingredients
            
        Returns:
            List of individual ingredient strings
        """
        # Remove common prefixes and suffixes
        line = re.sub(r'^\[?\s*', '', line)  # Remove opening brackets
        line = re.sub(r'\s*\]?\s*$', '', line)  # Remove closing brackets
        
        # Split by common separators, but be careful not to split within parentheses
        ingredients = []
        
        # Try to split by comma, but respect parentheses
        current_ingredient = ""
        paren_count = 0
        
        for char in line:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            
            if char == ',' and paren_count == 0:
                # Safe to split here
                if current_ingredient.strip():
                    ingredients.append(current_ingredient.strip())
                current_ingredient = ""
            else:
                current_ingredient += char
        
        # Add the last ingredient
        if current_ingredient.strip():
            ingredients.append(current_ingredient.strip())
        
        # If no commas found, try other separators
        if len(ingredients) <= 1:
            # Try splitting by 'and' or '&'
            ingredients = re.split(r'\s+and\s+|\s*&\s*', line)
            ingredients = [ing.strip() for ing in ingredients if ing.strip()]
        
        # Clean up ingredients
        cleaned_ingredients = []
        for ingredient in ingredients:
            # Remove quotes and extra whitespace
            ingredient = re.sub(r'^[\'"`]\s*', '', ingredient)
            ingredient = re.sub(r'\s*[\'"`]\s*$', '', ingredient)
            ingredient = ingredient.strip()
            
            # Filter out obviously bad ingredients
            if self._is_valid_ingredient(ingredient):
                cleaned_ingredients.append(ingredient)
        
        return cleaned_ingredients
    
    def _is_valid_ingredient(self, ingredient: str) -> bool:
        """
        Check if an ingredient string is valid
        
        Args:
            ingredient: Ingredient string to validate
            
        Returns:
            True if ingredient is valid, False otherwise
        """
        if not ingredient or len(ingredient) < 3:
            return False
        
        # Filter out navigation/menu items
        invalid_patterns = [
            r'^home$', r'^about$', r'^recipes$', r'^start here$', r'^contact$',
            r'^privacy$', r'^terms$', r'^search$', r'^menu$', r'^navigation$',
            r'^subscribe$', r'^newsletter$', r'^follow$', r'^share$', r'^pin$',
            r'^facebook$', r'^twitter$', r'^instagram$', r'^pinterest$'
        ]
        
        ingredient_lower = ingredient.lower()
        for pattern in invalid_patterns:
            if re.match(pattern, ingredient_lower):
                return False
        
        # Filter out very short or very long ingredients
        if len(ingredient) < 3 or len(ingredient) > 200:
            return False
        
        # Filter out ingredients that are just punctuation or numbers
        if re.match(r'^[\d\s\-\+\.\,\;\:\!\?\(\)\[\]\{\}\"\']+$', ingredient):
            return False
        
        return True
    
    def create_ingredient_item(self, recipe: Recipe, parsed_ingredient: Dict[str, str]) -> Optional[RecipeIngredientItem]:
        """
        Create a RecipeIngredientItem from parsed ingredient data
        
        Args:
            recipe: Recipe object
            parsed_ingredient: Parsed ingredient dictionary
            
        Returns:
            RecipeIngredientItem object or None if creation fails
        """
        try:
            # Try to find existing Ingredient object
            ingredient_obj = None
            if parsed_ingredient['name']:
                ingredient_obj, created = Ingredient.objects.get_or_create(
                    name=parsed_ingredient['name'][:200]  # Truncate to fit field limit
                )
            
            # Create RecipeIngredientItem
            ingredient_item = RecipeIngredientItem.objects.create(
                recipe=recipe,
                ingredient=ingredient_obj,
                raw_text=parsed_ingredient['raw_text'][:300],  # Truncate to fit field limit
                quantity=parsed_ingredient['quantity'][:50],    # Truncate to fit field limit
                unit=parsed_ingredient['unit'][:50],           # Truncate to fit field limit
                name=parsed_ingredient['name'][:200]           # Truncate to fit field limit
            )
            
            return ingredient_item
            
        except Exception as e:
            logger.error(f"Error creating ingredient item for recipe {recipe.id}: {e}")
            return None
    
    def process_recipe(self, recipe: Recipe) -> int:
        """
        Process a single recipe and create ingredient items
        
        Args:
            recipe: Recipe object to process
            
        Returns:
            Number of ingredient items created
        """
        try:
            # Parse ingredients
            parsed_ingredients = self.parse_recipe_ingredients(recipe)
            
            if not parsed_ingredients:
                logger.warning(f"No ingredients parsed for recipe {recipe.id}: {recipe.title}")
                return 0
            
            # Create ingredient items
            created_count = 0
            for parsed in parsed_ingredients:
                if self.create_ingredient_item(recipe, parsed):
                    created_count += 1
            
            logger.info(f"Created {created_count} ingredient items for recipe {recipe.id}: {recipe.title}")
            return created_count
            
        except Exception as e:
            logger.error(f"Error processing recipe {recipe.id}: {e}")
            return 0
    
    def process_recipes_batch(self, recipes: List[Recipe], batch_size: int = 100) -> Dict[str, int]:
        """
        Process a batch of recipes
        
        Args:
            recipes: List of Recipe objects
            batch_size: Number of recipes to process in each transaction
            
        Returns:
            Dictionary with processing statistics
        """
        total_processed = 0
        total_ingredients_created = 0
        total_errors = 0
        
        # Process in batches
        for i in range(0, len(recipes), batch_size):
            batch = recipes[i:i + batch_size]
            
            try:
                with transaction.atomic():
                    for recipe in batch:
                        try:
                            ingredients_created = self.process_recipe(recipe)
                            total_ingredients_created += ingredients_created
                            total_processed += 1
                        except Exception as e:
                            logger.error(f"Error processing recipe {recipe.id}: {e}")
                            total_errors += 1
                            total_processed += 1
                
                logger.info(f"Processed batch {i//batch_size + 1}: {len(batch)} recipes")
                
            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                total_errors += len(batch)
                total_processed += len(batch)
        
        return {
            'total_processed': total_processed,
            'total_ingredients_created': total_ingredients_created,
            'total_errors': total_errors
        }

def main():
    """Test the ingredient parser with a small batch"""
    parser = IngredientParser()
    
    # Test with a few recipes first
    test_recipes = Recipe.objects.filter(
        scraped_ingredients_text__isnull=False
    ).exclude(scraped_ingredients_text='')[:5]
    
    print(f"Testing ingredient parser with {test_recipes.count()} recipes...")
    print()
    
    for recipe in test_recipes:
        print(f"Recipe: {recipe.title}")
        print(f"ID: {recipe.id}")
        print(f"URL: {recipe.original_url}")
        print("Parsed ingredients:")
        
        parsed_ingredients = parser.parse_recipe_ingredients(recipe)
        
        for i, parsed in enumerate(parsed_ingredients[:3], 1):  # Show first 3
            print(f"  {i}. Quantity: '{parsed['quantity']}' | Unit: '{parsed['unit']}' | Name: '{parsed['name']}'")
        
        if len(parsed_ingredients) > 3:
            print(f"  ... and {len(parsed_ingredients) - 3} more")
        
        print(f"Total parsed: {len(parsed_ingredients)}")
        print("-" * 60)
    
    print("\nParser test complete!")
    print("To process all recipes, use the management command.")

if __name__ == "__main__":
    main()
