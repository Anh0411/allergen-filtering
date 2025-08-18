from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count, Case, When, IntegerField, Value
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.http import require_http_methods, require_POST
from .models import Recipe, AllergenCategory, AllergenAnalysisResult, Allergen, Annotation, AllergenDetectionLog, RecipeFeedback
from django.contrib.auth.decorators import login_required
import json
import ast
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from .forms import RecipeSearchForm
import logging

logger = logging.getLogger(__name__)

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
    no_allergens = request.GET.get('no_allergens', '')
    sort_by = request.GET.get('sort', 'title')
    
    # Check for success message from annotation
    success_message = request.GET.get('success', '')
    
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
    
    # Apply no allergens filtering
    if no_allergens:
        # Filter for recipes with no detected allergens
        recipes = recipes.filter(
            Q(analysis_result__detected_allergens={}) |
            Q(analysis_result__detected_allergens__isnull=True)
        )
    
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
    
    # Check if user can annotate (is authenticated and has staff permissions)
    can_annotate = request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)
    
    # Get annotation information for internal users
    annotation_info = {}
    if can_annotate:
        # Get all annotations for the current user
        user_annotations = Annotation.objects.filter(annotator=request.user).values_list('recipe_id', flat=True)
        annotation_info = {recipe_id: True for recipe_id in user_annotations}
    
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
        'no_allergens': no_allergens,
        'sort_by': sort_by,
        'total_recipes': total_recipes,
        'recipes_with_allergens': recipes_with_allergens,
        'risk_distribution': risk_distribution,
        'success_message': success_message,
        'can_annotate': can_annotate,
        'annotation_info': annotation_info,
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
    
    # Build back to search URL with preserved parameters
    from urllib.parse import urlparse, parse_qs
    
    # Get referrer information to preserve pagination context
    back_to_search_url = '/'  # Default fallback (root level recipe search)
    referrer = request.META.get('HTTP_REFERER', '')
    
    if referrer:
        try:
            # Extract query parameters from referrer
            parsed_url = urlparse(referrer)
            query_params = parse_qs(parsed_url.query)
            
            # Check if this looks like a recipe search page (has search parameters or is root)
            is_recipe_search = (
                parsed_url.path == '/' or  # Root path
                'search_query' in query_params or  # Has search query
                'risk_level' in query_params or  # Has risk level filter
                'sort_by' in query_params  # Has sorting
            )
            
            if is_recipe_search and query_params:
                param_strings = []
                for key, values in query_params.items():
                    # Preserve ALL parameters including page number
                    for value in values:
                        param_strings.append(f"{key}={value}")
                
                if param_strings:
                    back_to_search_url = f"/?{'&'.join(param_strings)}"
        except Exception:
            # If there's any error parsing the referrer, fall back to default
            back_to_search_url = '/'
    
    # If no referrer or not from recipe search, use default
    # This handles direct links, bookmarks, etc.
    
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
    
    # Check if user can annotate (is authenticated and has staff permissions)
    can_annotate = request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)
    existing_annotation = None
    
    if can_annotate:
        # Get existing annotation for this user and recipe
        existing_annotation = Annotation.objects.filter(recipe=recipe, annotator=request.user).first()
    
    context = {
        'recipe': recipe,
        'instructions': instructions,
        'ingredients': ingredients,
        'allergen_analysis': allergen_analysis,
        'detected_allergens': detected_allergens,
        'can_annotate': can_annotate,
        'existing_annotation': existing_annotation,
        'back_to_search_url': back_to_search_url,
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
    return render(request, 'recipes/dashboard.html', context)

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

@login_required
def annotate_recipe(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    allergen_categories = AllergenCategory.objects.all()
    existing_annotation = Annotation.objects.filter(recipe=recipe, annotator=request.user).first()

    # Parse instructions and ingredients from JSON strings
    instructions = parse_array_field(recipe.instructions)
    ingredients = parse_array_field(recipe.scraped_ingredients_text)

    if request.method == 'POST':
        try:
            selected_allergens = request.POST.getlist('allergens')
            notes = request.POST.get('notes', '')

            if existing_annotation:
                annotation = existing_annotation
                annotation.notes = notes
                annotation.save()
                annotation.allergens.set(selected_allergens)
            else:
                annotation = Annotation.objects.create(
                    recipe=recipe,
                    annotator=request.user,
                    notes=notes
                )
                annotation.allergens.set(selected_allergens)

            # Show success message on the same page
            context = {
                'recipe': recipe,
                'allergen_categories': allergen_categories,
                'existing_annotation': annotation,  # Use the updated annotation
                'instructions': instructions,
                'ingredients': ingredients,
                'success_message': 'Annotation saved successfully!',
            }
            return render(request, 'annotation/annotate_recipe.html', context)
        except Exception as e:
            # Add error context for debugging
            context = {
                'recipe': recipe,
                'allergen_categories': allergen_categories,
                'existing_annotation': existing_annotation,
                'instructions': instructions,
                'ingredients': ingredients,
                'error_message': f"Error saving annotation: {str(e)}",
            }
            return render(request, 'annotation/annotate_recipe.html', context)

    context = {
        'recipe': recipe,
        'allergen_categories': allergen_categories,
        'existing_annotation': existing_annotation,
        'instructions': instructions,
        'ingredients': ingredients,
    }
    return render(request, 'annotation/annotate_recipe.html', context)

@login_required
def feedback_form(request, recipe_id):
    """Display feedback form for allergen detection accuracy and save to RecipeFeedback model only. Always allow general feedback."""
    recipe = get_object_or_404(Recipe, id=recipe_id)
    
    # Get allergen analysis result instead of detection logs
    try:
        analysis_result = recipe.analysis_result
        detected_allergens = analysis_result.detected_allergens if analysis_result else {}
        confidence_scores = analysis_result.confidence_scores if analysis_result else {}
    except Exception as e:
        logger.error(f"Error getting analysis result for recipe {recipe_id}: {e}")
        detected_allergens = {}
        confidence_scores = {}

    if request.method == 'POST':
        try:
            feedback_data = {}
            
            # Process feedback for detected allergens
            for allergen_name, details in detected_allergens.items():
                # Handle both list and dict formats
                if isinstance(details, list):
                    # If details is a list, use the first item as the detected term
                    detected_term = details[0] if details else allergen_name
                    is_correct = request.POST.get(f'correct_{allergen_name}')
                    if is_correct is not None:
                        feedback_data[allergen_name] = {
                            'allergen_category': allergen_name,
                            'detected_term': detected_term,
                            'is_correct': is_correct,
                            'confidence_score': confidence_scores.get(allergen_name, 0.0),
                            'match_type': 'detected',
                        }
                elif isinstance(details, dict) and 'term' in details:
                    # If details is a dict with 'term' field
                    is_correct = request.POST.get(f'correct_{allergen_name}')
                    if is_correct is not None:
                        feedback_data[allergen_name] = {
                            'allergen_category': allergen_name,
                            'detected_term': details.get('term', allergen_name),
                            'is_correct': is_correct,
                            'confidence_score': confidence_scores.get(allergen_name, 0.0),
                            'match_type': details.get('match_type', 'unknown'),
                        }
            
            notes = request.POST.get('notes', '')
            general_feedback = request.POST.get('general_feedback', '')
            
            # Save feedback to RecipeFeedback model
            RecipeFeedback.objects.create(
                recipe=recipe,
                user=request.user if request.user.is_authenticated else None,
                feedback_data=feedback_data,
                notes=notes + ("\nGeneral feedback: " + general_feedback if general_feedback else "")
            )
            messages.success(request, 'Thank you! Your feedback has been submitted for internal review.')
            return redirect('recipe_detail', pk=recipe_id)
            
        except Exception as e:
            logger.error(f"Error submitting feedback for recipe {recipe_id}: {e}")
            messages.error(request, f'Error submitting feedback: {str(e)}')
            # Continue to show the form with error message

    context = {
        'recipe': recipe,
        'detected_allergens': detected_allergens,
        'confidence_scores': confidence_scores,
        'allergen_categories': AllergenCategory.objects.all(),
    }
    return render(request, 'recipes/feedback_form.html', context)

@require_POST
@login_required
def submit_feedback_ajax(request, recipe_id):
    """Handle AJAX feedback submission"""
    recipe = get_object_or_404(Recipe, id=recipe_id)
    
    try:
        log_id = request.POST.get('log_id')
        is_correct = request.POST.get('is_correct') == 'true'
        notes = request.POST.get('notes', '')
        
        log = AllergenDetectionLog.objects.get(id=log_id, recipe=recipe)
        log.is_correct = is_correct
        log.verified_by = request.user.username
        log.verification_date = timezone.now()
        log.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Feedback submitted successfully'
        })
        
    except AllergenDetectionLog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Detection log not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error submitting feedback: {str(e)}'
        }, status=500)
