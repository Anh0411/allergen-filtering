from django.contrib import admin
from .models import Allergen, Ingredient, Recipe, RecipeIngredientItem, AllergenCategory, AllergenAnalysisResult, AllergenSynonym, AllergenDetectionLog, AllergenDictionaryVersion, Annotation, RecipeFeedback
from scraper.allergen_analysis_manager import run_batch_analysis
from scraper.nlp_ingredient_processor import NLPIngredientProcessor

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

    actions = [
        'activate_synonyms',
        'deactivate_synonyms',
        'set_term_type_manual',
        'set_term_type_auto',
    ]

    def activate_synonyms(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} synonym(s) marked as active.")
    activate_synonyms.short_description = "Mark selected synonyms as active"

    def deactivate_synonyms(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} synonym(s) marked as inactive.")
    deactivate_synonyms.short_description = "Mark selected synonyms as inactive"

    def set_term_type_manual(self, request, queryset):
        updated = queryset.update(term_type='manual')
        self.message_user(request, f"{updated} synonym(s) set to term_type 'manual'.")
    set_term_type_manual.short_description = "Set term_type to 'manual' for selected"

    def set_term_type_auto(self, request, queryset):
        updated = queryset.update(term_type='auto')
        self.message_user(request, f"{updated} synonym(s) set to term_type 'auto'.")
    set_term_type_auto.short_description = "Set term_type to 'auto' for selected"

@admin.action(description='Re-analyze selected recipes for allergens (async)')
def reanalyze_recipes(modeladmin, request, queryset):
    recipe_ids = list(queryset.values_list('id', flat=True))
    run_batch_analysis.delay(recipe_ids)

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['title', 'risk_level', 'nlp_confidence_score', 'allergen_count', 'annotators', 'created_at']
    list_filter = ['risk_level', 'allergen_categories', 'created_at', 'nlp_analysis_date']
    search_fields = ['title', 'scraped_ingredients_text', 'original_url']
    readonly_fields = ['nlp_analysis_date', 'last_analyzed', 'created_at', 'updated_at']
    filter_horizontal = ['allergen_categories']
    actions = [reanalyze_recipes]
    
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
    
    def annotators(self, obj):
        return ", ".join(a.annotator.username for a in obj.annotations.all())
    annotators.short_description = 'Annotators'

@admin.register(AllergenAnalysisResult)
class AllergenAnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['recipe', 'risk_level', 'analysis_date', 'total_ingredients', 'processing_time', 'get_model_version']
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

    def get_model_version(self, obj):
        return getattr(obj, 'model_version', 'unknown')
    get_model_version.short_description = 'Model Version'

@admin.register(AllergenDetectionLog)
class AllergenDetectionLogAdmin(admin.ModelAdmin):
    list_display = ['recipe', 'allergen_category', 'detected_term', 'confidence_score', 'match_type', 'is_correct', 'verified_by', 'created_at']
    list_filter = ['allergen_category', 'match_type', 'is_correct', 'verified_by', 'created_at']
    search_fields = ['recipe__title', 'detected_term', 'context', 'verified_by']
    readonly_fields = ['created_at', 'verification_date']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Recipe Information', {
            'fields': ('recipe', 'allergen_category')
        }),
        ('Detection Details', {
            'fields': ('detected_term', 'confidence_score', 'match_type', 'context', 'position_start', 'position_end')
        }),
        ('Verification', {
            'fields': ('is_correct', 'verified_by', 'verification_date'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('recipe', 'allergen_category')

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

@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ['recipe', 'annotator', 'allergen_count', 'created_at', 'updated_at', 'has_notes']
    list_filter = ['annotator', 'allergens', 'created_at', 'updated_at']
    search_fields = ['recipe__title', 'annotator__username', 'notes']
    filter_horizontal = ['allergens']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Recipe Information', {
            'fields': ('recipe', 'annotator')
        }),
        ('Annotation Details', {
            'fields': ('allergens', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def allergen_count(self, obj):
        return obj.allergens.count()
    allergen_count.short_description = 'Allergens'
    
    def has_notes(self, obj):
        return bool(obj.notes.strip())
    has_notes.boolean = True
    has_notes.short_description = 'Has Notes'

@admin.action(description='Export feedback for NER retraining')
def export_feedback_for_ner(modeladmin, request, queryset):
    processor = NLPIngredientProcessor()
    processor.export_feedback_for_retraining()
    modeladmin.message_user(request, "Feedback exported for NER retraining.")

@admin.register(RecipeFeedback)
class RecipeFeedbackAdmin(admin.ModelAdmin):
    list_display = ['recipe', 'user', 'created_at', 'is_reviewed', 'reviewed_by', 'reviewed_at']
    list_filter = ['is_reviewed', 'created_at', 'reviewed_by']
    search_fields = ['recipe__title', 'user__username', 'notes']
    readonly_fields = ['created_at', 'feedback_data']
    ordering = ['-created_at']
    actions = [export_feedback_for_ner]
    
    fieldsets = (
        ('Recipe Feedback', {
            'fields': ('recipe', 'user', 'feedback_data', 'notes')
        }),
        ('Review Status', {
            'fields': ('is_reviewed', 'reviewed_by', 'reviewed_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if obj.reviewed_by or obj.reviewed_at:
            obj.is_reviewed = True
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.is_staff:
            return qs
        return qs.none()
