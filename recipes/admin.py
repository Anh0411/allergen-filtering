from django.contrib import admin
from .models import Allergen, Ingredient, Recipe, RecipeIngredientItem

# Register your models here.
admin.site.register(Allergen)
admin.site.register(Ingredient)
admin.site.register(Recipe)
admin.site.register(RecipeIngredientItem)
