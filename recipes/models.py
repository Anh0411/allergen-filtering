from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

# Create your models here.

class AllergenCategory(models.Model):
    """Represents a major allergen category (e.g., milk, eggs, peanuts)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_major_allergen = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class AllergenSynonym(models.Model):
    """Represents synonyms and related terms for allergen categories"""
    allergen_category = models.ForeignKey(AllergenCategory, on_delete=models.CASCADE, related_name='synonyms')
    term = models.CharField(max_length=200)
    term_type = models.CharField(max_length=50, choices=[
        ('main_ingredient', 'Main Ingredient'),
        ('synonym', 'Synonym'),
        ('scientific_name', 'Scientific Name'),
        ('hidden_source', 'Hidden Source'),
    ])
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=1.0
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['allergen_category', 'term']
        ordering = ['allergen_category', 'term_type', 'term']

    def __str__(self):
        return f"{self.allergen_category.name}: {self.term} ({self.term_type})"


class Allergen(models.Model):
    """Legacy model - now references AllergenCategory"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    allergen_category = models.ForeignKey(AllergenCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='legacy_allergens')

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField(max_length=200, unique=True)
    potential_allergens = models.ManyToManyField(Allergen, blank=True, related_name='ingredients')
    allergen_categories = models.ManyToManyField(AllergenCategory, blank=True, related_name='ingredients')
    is_verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Recipe(models.Model):
    title = models.CharField(max_length=300)
    instructions = models.TextField()
    times = models.CharField(max_length=300, blank=True)
    image_url = models.URLField(blank=True, max_length=500)
    original_url = models.URLField(unique=True)
    scraped_ingredients_text = models.TextField()
    contains_allergens = models.ManyToManyField(Allergen, blank=True, related_name='recipes')
    allergen_categories = models.ManyToManyField(AllergenCategory, blank=True, related_name='recipes')
    
    # NLP Analysis fields
    nlp_analysis_date = models.DateTimeField(null=True, blank=True)
    nlp_confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True, blank=True
    )
    risk_level = models.CharField(max_length=20, choices=[
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ], default='low')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_analyzed = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class RecipeIngredientItem(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='ingredient_items')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.SET_NULL, null=True, blank=True, related_name='recipe_items')
    raw_text = models.CharField(max_length=300)
    quantity = models.CharField(max_length=50, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=200, blank=True)
    
    # Allergen detection fields
    detected_allergens = models.ManyToManyField(AllergenCategory, blank=True, related_name='ingredient_detections')
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True, blank=True
    )
    is_verified = models.BooleanField(default=False)
    verification_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.quantity} {self.unit} {self.name} ({self.raw_text})"


class AllergenDetectionLog(models.Model):
    """Log of allergen detection activities for auditing and improvement"""
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='detection_logs')
    allergen_category = models.ForeignKey(AllergenCategory, on_delete=models.CASCADE, related_name='detection_logs')
    detected_term = models.CharField(max_length=200)
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    match_type = models.CharField(max_length=50, choices=[
        ('exact_match', 'Exact Match'),
        ('fuzzy_match', 'Fuzzy Match'),
        ('contextual_match', 'Contextual Match'),
        ('scientific_name', 'Scientific Name'),
        ('hidden_source', 'Hidden Source'),
        ('main_ingredient', 'Main Ingredient'),
        ('synonym', 'Synonym'),
    ])
    context = models.TextField(blank=True)
    position_start = models.IntegerField()
    position_end = models.IntegerField()
    is_correct = models.BooleanField(null=True, blank=True)  # For manual verification
    verified_by = models.CharField(max_length=100, blank=True)
    verification_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipe.title}: {self.allergen_category.name} ({self.detected_term})"


class AllergenDictionaryVersion(models.Model):
    """Track versions of the allergen dictionary for updates and rollbacks"""
    version = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    total_categories = models.IntegerField()
    total_terms = models.IntegerField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Allergen Dictionary v{self.version}"


class AllergenAnalysisResult(models.Model):
    """Store detailed allergen analysis results for recipes"""
    recipe = models.OneToOneField(Recipe, on_delete=models.CASCADE, related_name='analysis_result')
    analysis_date = models.DateTimeField(auto_now_add=True)
    risk_level = models.CharField(max_length=20, choices=[
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ])
    confidence_scores = models.JSONField(default=dict)  # Store confidence scores per allergen
    detected_allergens = models.JSONField(default=dict)  # Store detailed detection results
    recommendations = models.JSONField(default=list)  # Store recommendations
    total_ingredients = models.IntegerField(default=0)
    analyzed_ingredients = models.IntegerField(default=0)
    processing_time = models.FloatField(null=True, blank=True)  # Processing time in seconds

    def __str__(self):
        return f"Analysis for {self.recipe.title} ({self.analysis_date})"
