from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Case, When, IntegerField, Value
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Recipe, AllergenCategory, AllergenAnalysisResult, Allergen
import json
import ast

# Create your views here.

def recipe_search(request):
    """Enhanced recipe search with allergen filtering and analysis"""
    # Get all allergen categories for filtering
    allergen_categories = AllergenCategory.objects.all().order_by('name')
    allergens = Allergen.objects.all()  # Keep for backward compatibility
    
    # Get filter parameters
    selected_allergens = request.GET.getlist('allergens')
    search_query = request.GET.get('search', '').strip()
    risk_level = request.GET.get('risk_level', '')
    sort_by = request.GET.get('sort', 'title')
    
    # Start with all recipes
    recipes = Recipe.objects.select_related('analysis_result').prefetch_related('allergen_categories').all()
    
    # Apply allergen filtering
    if selected_allergens:
        # Filter out recipes that contain selected allergens based on AllergenAnalysisResult
        for allergen in selected_allergens:
            # Use JSON field lookup to check if allergen is in detected_allergens
            recipes = recipes.exclude(
                analysis_result__detected_allergens__has_key=allergen.lower()
            ).distinct()
    
    # Apply search filtering
    if search_query:
        recipes = recipes.filter(
            Q(title__icontains=search_query) |
            Q(scraped_ingredients_text__icontains=search_query) |
            Q(instructions__icontains=search_query)
        )
    
    # Apply risk level filtering
    if risk_level:
        recipes = recipes.filter(analysis_result__risk_level=risk_level)
    
    # Calculate statistics before any sorting that might convert to list
    total_recipes = recipes.count()
    recipes_with_allergens = recipes.exclude(analysis_result__risk_level='low').count()
    
    # Risk level distribution
    risk_distribution = recipes.values('analysis_result__risk_level').annotate(
        count=Count('id')
    ).order_by('analysis_result__risk_level')
    
    # Apply sorting
    if sort_by == 'risk_level':
        # Use Case/When for proper risk level ordering in QuerySet
        recipes = recipes.annotate(
            risk_order=Case(
                When(analysis_result__risk_level='low', then=Value(1)),
                When(analysis_result__risk_level='medium', then=Value(2)),
                When(analysis_result__risk_level='high', then=Value(3)),
                When(analysis_result__risk_level='critical', then=Value(4)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by('risk_order')
    elif sort_by == 'confidence':
        recipes = recipes.order_by('-analysis_result__confidence_scores')
    elif sort_by == 'date':
        recipes = recipes.order_by('-created_at')
    else:
        recipes = recipes.order_by('title')
    
    # Pagination
    paginator = Paginator(recipes, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'allergen_categories': allergen_categories,
        'allergens': allergens,  # Keep for backward compatibility
        'selected_allergens': selected_allergens,
        'page_obj': page_obj,
        'search_query': search_query,
        'risk_level': risk_level,
        'sort_by': sort_by,
        'total_recipes': total_recipes,
        'recipes_with_allergens': recipes_with_allergens,
        'risk_distribution': risk_distribution,
    }
    return render(request, 'recipes/recipe_search.html', context)

def recipe_detail(request, pk):
    """Enhanced recipe detail view with allergen analysis"""
    recipe = get_object_or_404(Recipe.objects.select_related('analysis_result').prefetch_related('allergen_categories'), pk=pk)
    
    # Parse instructions and ingredients
    instructions = parse_array_field(recipe.instructions)
    ingredients = parse_array_field(recipe.scraped_ingredients_text)
    
    # Get allergen analysis
    allergen_analysis = None
    if hasattr(recipe, 'analysis_result'):
        allergen_analysis = recipe.analysis_result
    
    # Get detected allergens with details
    detected_allergens = []
    if allergen_analysis and allergen_analysis.detected_allergens:
        # Mapping from lowercase JSON keys to proper AllergenCategory names
        allergen_name_mapping = {
            'egg': 'Egg',
            'fish': 'Fish',
            'milk': 'Milk',
            'gluten': 'Gluten',
            'sulfites': 'Sulfites',
            'peanuts': 'Peanuts',
            'tree_nuts': 'Tree Nuts',
            'soy': 'Soy',
            'shellfish': 'Crustaceans',
            'crustaceans': 'Crustaceans',
            'molluscs': 'Molluscs',
            'sesame': 'Sesame',
            'mustard': 'Mustard',
            'celery': 'Celery',
            'lupin': 'Lupin',
        }
        
        for category_name, terms in allergen_analysis.detected_allergens.items():
            # Convert lowercase JSON key to proper AllergenCategory name
            proper_name = allergen_name_mapping.get(category_name, category_name.title())
            
            try:
                category = AllergenCategory.objects.get(name=proper_name)
                confidence = allergen_analysis.confidence_scores.get(category_name, 0.0)
                detected_allergens.append({
                    'category': category,
                    'terms': terms,
                    'confidence': confidence,
                    'description': category.description
                })
            except AllergenCategory.DoesNotExist:
                # If category doesn't exist, still show the allergen with basic info
                detected_allergens.append({
                    'category': type('MockCategory', (), {'name': proper_name, 'description': ''})(),
                    'terms': terms,
                    'confidence': allergen_analysis.confidence_scores.get(category_name, 0.0),
                    'description': f'Allergen: {proper_name}'
                })
                continue
    
    # Sort allergens by confidence
    detected_allergens.sort(key=lambda x: x['confidence'], reverse=True)
    
    context = {
        'recipe': recipe,
        'instructions': instructions,
        'ingredients': ingredients,
        'allergen_analysis': allergen_analysis,
        'detected_allergens': detected_allergens,
    }
    return render(request, 'recipes/recipe_detail.html', context)

def allergen_dashboard(request):
    """Dashboard showing allergen statistics and insights"""
    # Get overall statistics
    total_recipes = Recipe.objects.count()
    recipes_with_analysis = Recipe.objects.filter(analysis_result__isnull=False).count()
    recipes_with_allergens = Recipe.objects.exclude(analysis_result__risk_level='low').count()
    
    # Risk level distribution
    risk_distribution = Recipe.objects.values('analysis_result__risk_level').annotate(
        count=Count('id')
    ).order_by('analysis_result__risk_level')
    
    # Allergen category distribution
    allergen_distribution = AllergenCategory.objects.annotate(
        recipe_count=Count('recipes')
    ).order_by('-recipe_count')
    
    # Recent recipes with allergens
    recent_allergen_recipes = Recipe.objects.exclude(
        analysis_result__risk_level='low'
    ).select_related('analysis_result').order_by('-created_at')[:10]
    
    # Top allergens by frequency
    top_allergens = AllergenCategory.objects.annotate(
        recipe_count=Count('recipes')
    ).filter(recipe_count__gt=0).order_by('-recipe_count')[:10]
    
    context = {
        'total_recipes': total_recipes,
        'recipes_with_analysis': recipes_with_analysis,
        'recipes_with_allergens': recipes_with_allergens,
        'risk_distribution': risk_distribution,
        'allergen_distribution': allergen_distribution,
        'recent_allergen_recipes': recent_allergen_recipes,
        'top_allergens': top_allergens,
    }
    return render(request, 'recipes/allergen_dashboard.html', context)

@require_http_methods(["GET"])
def api_recipe_stats(request):
    """API endpoint for recipe statistics"""
    risk_distribution = Recipe.objects.values('analysis_result__risk_level').annotate(
        count=Count('id')
    ).order_by('analysis_result__risk_level')
    
    allergen_distribution = AllergenCategory.objects.annotate(
        recipe_count=Count('recipes')
    ).order_by('-recipe_count')
    
    return JsonResponse({
        'risk_distribution': list(risk_distribution),
        'allergen_distribution': list(allergen_distribution.values('name', 'recipe_count')),
    })

def parse_array_field(field_value):
    """Parse array fields from database"""
    if not field_value:
        return []
        
    try:
        return json.loads(field_value)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(field_value)
        except (ValueError, SyntaxError):
            return [field_value]
