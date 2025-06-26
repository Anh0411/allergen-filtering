from django.contrib import admin
from .models import Allergen, Ingredient, Recipe, RecipeIngredientItem, AllergenCategory, AllergenAnalysisResult, AllergenSynonym, AllergenDetectionLog, AllergenDictionaryVersion

@admin.register(AllergenCategory)
class AllergenCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_major_allergen', 'created_at']
    list_filter = ['is_major_allergen', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']

@admin.register(AllergenSynonym)
class AllergenSynonymAdmin(admin.ModelAdmin):
    list_display = ['allergen_category', 'term', 'term_type', 'confidence_score', 'is_active']
    list_filter = ['allergen_category', 'term_type', 'is_active', 'created_at']
    search_fields = ['term', 'allergen_category__name']
    ordering = ['allergen_category', 'term_type', 'term']

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['title', 'risk_level', 'nlp_confidence_score', 'allergen_count', 'created_at']
    list_filter = ['risk_level', 'allergen_categories', 'created_at', 'nlp_analysis_date']
    search_fields = ['title', 'scraped_ingredients_text', 'original_url']
    readonly_fields = ['nlp_analysis_date', 'last_analyzed', 'created_at', 'updated_at']
    filter_horizontal = ['allergen_categories']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'original_url', 'image_url', 'times')
        }),
        ('Recipe Content', {
            'fields': ('scraped_ingredients_text', 'instructions')
        }),
        ('Allergen Analysis', {
            'fields': ('risk_level', 'nlp_confidence_score', 'allergen_categories'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'nlp_analysis_date', 'last_analyzed'),
            'classes': ('collapse',)
        }),
    )
    
    def allergen_count(self, obj):
        return obj.allergen_categories.count()
    allergen_count.short_description = 'Allergens'

@admin.register(AllergenAnalysisResult)
class AllergenAnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['recipe', 'risk_level', 'analysis_date', 'total_ingredients', 'processing_time']
    list_filter = ['risk_level', 'analysis_date']
    search_fields = ['recipe__title']
    readonly_fields = ['analysis_date', 'processing_time']
    
    fieldsets = (
        ('Recipe Information', {
            'fields': ('recipe', 'analysis_date')
        }),
        ('Analysis Results', {
            'fields': ('risk_level', 'confidence_scores', 'detected_allergens', 'recommendations')
        }),
        ('Processing Details', {
            'fields': ('total_ingredients', 'analyzed_ingredients', 'processing_time'),
            'classes': ('collapse',)
        }),
    )

@admin.register(AllergenDetectionLog)
class AllergenDetectionLogAdmin(admin.ModelAdmin):
    list_display = ['recipe', 'allergen_category', 'detected_term', 'confidence_score', 'match_type', 'is_correct']
    list_filter = ['allergen_category', 'match_type', 'is_correct', 'created_at']
    search_fields = ['recipe__title', 'detected_term', 'allergen_category__name']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

@admin.register(AllergenDictionaryVersion)
class AllergenDictionaryVersionAdmin(admin.ModelAdmin):
    list_display = ['version', 'description', 'total_categories', 'total_terms', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['version', 'description']
    readonly_fields = ['created_at', 'activated_at']
    ordering = ['-created_at']

# Legacy models (keeping for backward compatibility)
@admin.register(Allergen)
class AllergenAdmin(admin.ModelAdmin):
    list_display = ['name', 'allergen_category', 'description']
    list_filter = ['allergen_category']
    search_fields = ['name', 'description']
    ordering = ['name']

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_verified', 'verification_date', 'created_at']
    list_filter = ['is_verified', 'allergen_categories', 'created_at']
    search_fields = ['name']
    filter_horizontal = ['allergen_categories']
    ordering = ['name']

@admin.register(RecipeIngredientItem)
class RecipeIngredientItemAdmin(admin.ModelAdmin):
    list_display = ['recipe', 'raw_text', 'name', 'confidence_score', 'is_verified']
    list_filter = ['is_verified', 'detected_allergens']
    search_fields = ['recipe__title', 'raw_text', 'name']
    filter_horizontal = ['detected_allergens']
    ordering = ['recipe', 'raw_text']
