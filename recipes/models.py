from django.db import models

# Create your models here.

class Allergen(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Ingredient(models.Model):
    name = models.CharField(max_length=200, unique=True)
    potential_allergens = models.ManyToManyField(Allergen, blank=True, related_name='ingredients')

    def __str__(self):
        return self.name

class Recipe(models.Model):
    title = models.CharField(max_length=300)
    instructions = models.TextField()
    times = models.CharField(max_length=100, blank=True)
    image_url = models.URLField(blank=True)
    original_url = models.URLField(unique=True)
    scraped_ingredients_text = models.TextField()
    contains_allergens = models.ManyToManyField(Allergen, blank=True, related_name='recipes')

    def __str__(self):
        return self.title

class RecipeIngredientItem(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='ingredient_items')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.SET_NULL, null=True, blank=True, related_name='recipe_items')
    raw_text = models.CharField(max_length=300)
    quantity = models.CharField(max_length=50, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.quantity} {self.unit} {self.name} ({self.raw_text})"
