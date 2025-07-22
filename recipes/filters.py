"""
Django filters for the recipes app
"""

import django_filters
from django.db.models import Q
from .models import Recipe, AllergenAnalysisResult


class RecipeFilter(django_filters.FilterSet):
    """
    Filter for Recipe model
    """
    search = django_filters.CharFilter(method='search_filter')
    risk_level = django_filters.ChoiceFilter(
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ]
    )
    allergens = django_filters.CharFilter(method='allergen_filter')
    min_confidence = django_filters.NumberFilter(
        field_name='nlp_confidence_score',
        lookup_expr='gte'
    )
    max_confidence = django_filters.NumberFilter(
        field_name='nlp_confidence_score',
        lookup_expr='lte'
    )
    has_image = django_filters.BooleanFilter(method='has_image_filter')
    has_analysis = django_filters.BooleanFilter(method='has_analysis_filter')
    source = django_filters.CharFilter(method='source_filter')
    created_after = django_filters.DateTimeFilter(
        field_name='last_analyzed',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='last_analyzed',
        lookup_expr='lte'
    )
    
    class Meta:
        model = Recipe
        fields = {
            'title': ['icontains', 'istartswith', 'iendswith'],
            'times': ['icontains'],
            'risk_level': ['exact'],
            'nlp_confidence_score': ['gte', 'lte'],
        }
    
    def search_filter(self, queryset, name, value):
        """Search across title, ingredients, and instructions"""
        if value:
            return queryset.filter(
                Q(title__icontains=value) |
                Q(scraped_ingredients_text__icontains=value) |
                Q(instructions__icontains=value)
            )
        return queryset
    
    def allergen_filter(self, queryset, name, value):
        """Filter by allergens (exclude recipes containing these allergens)"""
        if value:
            allergens = [allergen.strip() for allergen in value.split(',')]
            for allergen in allergens:
                queryset = queryset.exclude(
                    analysis_result__detected_allergens__icontains=allergen
                )
        return queryset
    
    def has_image_filter(self, queryset, name, value):
        """Filter recipes that have/don't have images"""
        if value is True:
            return queryset.exclude(image_url__isnull=True).exclude(image_url='')
        elif value is False:
            return queryset.filter(Q(image_url__isnull=True) | Q(image_url=''))
        return queryset
    
    def has_analysis_filter(self, queryset, name, value):
        """Filter recipes that have/don't have allergen analysis"""
        if value is True:
            return queryset.filter(risk_level__isnull=False)
        elif value is False:
            return queryset.filter(risk_level__isnull=True)
        return queryset
    
    def source_filter(self, queryset, name, value):
        """Filter by recipe source (domain)"""
        if value:
            return queryset.filter(original_url__icontains=value)
        return queryset


class AllergenAnalysisFilter(django_filters.FilterSet):
    """
    Filter for AllergenAnalysisResult model
    """
    risk_level = django_filters.ChoiceFilter(
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ]
    )
    min_processing_time = django_filters.NumberFilter(
        field_name='processing_time',
        lookup_expr='gte'
    )
    max_processing_time = django_filters.NumberFilter(
        field_name='processing_time',
        lookup_expr='lte'
    )
    min_ingredients = django_filters.NumberFilter(
        field_name='total_ingredients',
        lookup_expr='gte'
    )
    max_ingredients = django_filters.NumberFilter(
        field_name='total_ingredients',
        lookup_expr='lte'
    )
    analysis_date_after = django_filters.DateTimeFilter(
        field_name='analysis_date',
        lookup_expr='gte'
    )
    analysis_date_before = django_filters.DateTimeFilter(
        field_name='analysis_date',
        lookup_expr='lte'
    )
    
    class Meta:
        model = AllergenAnalysisResult
        fields = {
            'risk_level': ['exact'],
            'processing_time': ['gte', 'lte'],
            'total_ingredients': ['gte', 'lte'],
            'analyzed_ingredients': ['gte', 'lte'],
            'analysis_date': ['gte', 'lte'],
        } 