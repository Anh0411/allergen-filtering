from django.shortcuts import render, get_object_or_404
from .models import Recipe, Allergen
from django.core.paginator import Paginator
from django.db.models import Q

# Create your views here.

def recipe_search(request):
    allergens = Allergen.objects.all()
    selected_allergens = request.GET.getlist('allergens')
    search_query = request.GET.get('search', '').strip()
    recipes = Recipe.objects.all()
    if selected_allergens:
        recipes = recipes.exclude(contains_allergens__in=selected_allergens).distinct()
    if search_query:
        recipes = recipes.filter(
            Q(title__icontains=search_query) |
            Q(scraped_ingredients_text__icontains=search_query)
        )
    paginator = Paginator(recipes, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'allergens': allergens,
        'selected_allergens': list(map(int, selected_allergens)),
        'page_obj': page_obj,
        'search_query': search_query,
    }
    return render(request, 'recipes/recipe_search.html', context)

def recipe_detail(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    return render(request, 'recipes/recipe_detail.html', {'recipe': recipe})
