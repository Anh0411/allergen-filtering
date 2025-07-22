"""
Django REST Framework serializers for the recipes app
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Recipe, AllergenAnalysisResult, AllergenCategory, 
    AllergenSynonym, AllergenDetectionLog
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class AllergenCategorySerializer(serializers.ModelSerializer):
    """Serializer for AllergenCategory model"""
    class Meta:
        model = AllergenCategory
        fields = ['id', 'name', 'description', 'is_active']


class AllergenSynonymSerializer(serializers.ModelSerializer):
    """Serializer for AllergenSynonym model"""
    category = AllergenCategorySerializer(read_only=True)
    
    class Meta:
        model = AllergenSynonym
        fields = ['id', 'allergen_category', 'category', 'term', 'term_type', 'confidence_score', 'is_active']


class AllergenDetectionLogSerializer(serializers.ModelSerializer):
    """Serializer for AllergenDetectionLog model"""
    class Meta:
        model = AllergenDetectionLog
        fields = [
            'id', 'recipe', 'allergen_category', 'detected_term', 
            'confidence_score', 'context', 'is_correct', 'verified_by', 
            'verification_date', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AllergenAnalysisResultSerializer(serializers.ModelSerializer):
    """Serializer for AllergenAnalysisResult model"""
    detected_allergens = serializers.JSONField()
    confidence_scores = serializers.JSONField()
    
    class Meta:
        model = AllergenAnalysisResult
        fields = [
            'id', 'recipe', 'risk_level', 'confidence_scores', 
            'detected_allergens', 'recommendations', 'total_ingredients',
            'analyzed_ingredients', 'processing_time', 'analysis_date'
        ]
        read_only_fields = ['id', 'analysis_date']


class RecipeSerializer(serializers.ModelSerializer):
    """Serializer for Recipe model"""
    analysis_result = AllergenAnalysisResultSerializer(read_only=True)
    scraped_ingredients_text = serializers.ListField(
        child=serializers.CharField(),
        read_only=True
    )
    instructions = serializers.ListField(
        child=serializers.CharField(),
        read_only=True
    )
    
    class Meta:
        model = Recipe
        fields = [
            'id', 'title', 'scraped_ingredients_text', 'instructions', 
            'times', 'image_url', 'original_url', 'risk_level', 
            'nlp_confidence_score', 'nlp_analysis_date', 'last_analyzed',
            'analysis_result'
        ]
        read_only_fields = ['id', 'last_analyzed']


class RecipeListSerializer(serializers.ModelSerializer):
    """Simplified serializer for recipe lists"""
    analysis_result = AllergenAnalysisResultSerializer(read_only=True)
    ingredient_count = serializers.SerializerMethodField()
    instruction_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Recipe
        fields = [
            'id', 'title', 'times', 'image_url', 'risk_level',
            'nlp_confidence_score', 'analysis_result', 'ingredient_count',
            'instruction_count'
        ]
        read_only_fields = ['id']
    
    def get_ingredient_count(self, obj):
        """Get count of ingredients"""
        if obj.scraped_ingredients_text:
            return len(obj.scraped_ingredients_text)
        return 0
    
    def get_instruction_count(self, obj):
        """Get count of instructions"""
        if obj.instructions:
            return len(obj.instructions)
        return 0


class RecipeSearchSerializer(serializers.Serializer):
    """Serializer for recipe search parameters"""
    search = serializers.CharField(required=False, allow_blank=True)
    risk_level = serializers.ChoiceField(
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        required=False
    )
    allergens = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    sort_by = serializers.ChoiceField(
        choices=[('title', 'Title'), ('risk_level', 'Risk Level'), ('confidence', 'Confidence'), ('date', 'Date')],
        required=False,
        default='title'
    )
    sort_order = serializers.ChoiceField(
        choices=[('asc', 'Ascending'), ('desc', 'Descending')],
        required=False,
        default='asc'
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class RecipeFeedbackSerializer(serializers.Serializer):
    """Serializer for recipe feedback"""
    recipe_id = serializers.IntegerField()
    allergen_category = serializers.CharField()
    detected_term = serializers.CharField()
    is_correct = serializers.BooleanField()
    user_notes = serializers.CharField(required=False, allow_blank=True)
    user_email = serializers.EmailField(required=False, allow_blank=True)


class AllergenStatisticsSerializer(serializers.Serializer):
    """Serializer for allergen statistics"""
    total_recipes = serializers.IntegerField()
    analyzed_recipes = serializers.IntegerField()
    unanalyzed_recipes = serializers.IntegerField()
    analysis_percentage = serializers.FloatField()
    risk_distribution = serializers.DictField()
    top_allergens = serializers.ListField()


class RecipeBulkAnalysisSerializer(serializers.Serializer):
    """Serializer for bulk recipe analysis"""
    recipe_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100
    )
    force_reanalysis = serializers.BooleanField(default=False)


class AllergenDictionaryUpdateSerializer(serializers.Serializer):
    """Serializer for allergen dictionary updates"""
    category_name = serializers.CharField()
    new_terms = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    remove_terms = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    update_confidence = serializers.FloatField(
        min_value=0.0,
        max_value=1.0,
        required=False
    )


class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check endpoint"""
    status = serializers.CharField()
    timestamp = serializers.DateTimeField()
    version = serializers.CharField()
    database_status = serializers.CharField()
    cache_status = serializers.CharField()
    celery_status = serializers.CharField() 