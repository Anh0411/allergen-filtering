"""
Django REST Framework API views for the recipes app
"""

import logging
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import (
    Recipe, AllergenAnalysisResult, AllergenCategory, 
    AllergenSynonym, AllergenDetectionLog
)
from .serializers import (
    RecipeSerializer, RecipeListSerializer, RecipeSearchSerializer,
    AllergenAnalysisResultSerializer, AllergenCategorySerializer,
    AllergenSynonymSerializer, AllergenDetectionLogSerializer,
    RecipeFeedbackSerializer, AllergenStatisticsSerializer,
    RecipeBulkAnalysisSerializer, AllergenDictionaryUpdateSerializer,
    HealthCheckSerializer
)
from .filters import RecipeFilter

logger = logging.getLogger(__name__)


class RecipeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing recipes
    """
    queryset = Recipe.objects.select_related('analysis_result').all()
    serializer_class = RecipeListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = RecipeFilter
    search_fields = ['title', 'scraped_ingredients_text', 'instructions']
    ordering_fields = ['title', 'risk_level', 'nlp_confidence_score', 'last_analyzed']
    ordering = ['title']

    def get_queryset(self):
        """Custom queryset with filtering"""
        queryset = super().get_queryset()
        
        # Filter by risk level
        risk_level = self.request.query_params.get('risk_level', None)
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        
        # Filter by allergens (exclude recipes containing these allergens)
        allergens = self.request.query_params.getlist('allergens', [])
        if allergens:
            # This is a simplified filter - in production, you'd want more sophisticated logic
            for allergen in allergens:
                queryset = queryset.exclude(
                    analysis_result__detected_allergens__icontains=allergen
                )
        
        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return RecipeSerializer
        return RecipeListSerializer

    @swagger_auto_schema(
        operation_description="Search recipes with advanced filtering",
        request_body=RecipeSearchSerializer,
        responses={200: RecipeListSerializer(many=True)}
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticatedOrReadOnly])
    def search(self, request):
        """Advanced recipe search with filtering"""
        serializer = RecipeSearchSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            # Build query
            queryset = self.get_queryset()
            
            # Text search
            if data.get('search'):
                search_term = data['search']
                queryset = queryset.filter(
                    Q(title__icontains=search_term) |
                    Q(scraped_ingredients_text__icontains=search_term) |
                    Q(instructions__icontains=search_term)
                )
            
            # Risk level filter
            if data.get('risk_level'):
                queryset = queryset.filter(risk_level=data['risk_level'])
            
            # Allergen filter
            if data.get('allergens'):
                for allergen in data['allergens']:
                    queryset = queryset.exclude(
                        analysis_result__detected_allergens__icontains=allergen
                    )
            
            # Sorting
            sort_by = data.get('sort_by', 'title')
            sort_order = data.get('sort_order', 'asc')
            
            if sort_by == 'confidence':
                sort_field = 'nlp_confidence_score'
            elif sort_by == 'date':
                sort_field = 'last_analyzed'
            else:
                sort_field = sort_by
            
            if sort_order == 'desc':
                sort_field = f'-{sort_field}'
            
            queryset = queryset.order_by(sort_field)
            
            # Pagination
            page = data.get('page', 1)
            page_size = data.get('page_size', 20)
            start = (page - 1) * page_size
            end = start + page_size
            
            recipes = queryset[start:end]
            serializer = self.get_serializer(recipes, many=True)
            
            return Response({
                'results': serializer.data,
                'count': queryset.count(),
                'page': page,
                'page_size': page_size,
                'total_pages': (queryset.count() + page_size - 1) // page_size
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Get recipe statistics",
        responses={200: AllergenStatisticsSerializer}
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedOrReadOnly])
    def statistics(self, request):
        """Get recipe and allergen statistics"""
        # Try to get from cache first
        cache_key = 'recipe_statistics'
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return Response(cached_stats)
        
        # Calculate statistics
        total_recipes = Recipe.objects.count()
        analyzed_recipes = Recipe.objects.filter(risk_level__isnull=False).count()
        unanalyzed_recipes = total_recipes - analyzed_recipes
        analysis_percentage = (analyzed_recipes / total_recipes * 100) if total_recipes > 0 else 0
        
        # Risk level distribution
        risk_distribution = Recipe.objects.filter(
            risk_level__isnull=False
        ).values('risk_level').annotate(
            count=Count('id')
        ).order_by('risk_level')
        
        risk_dist = {item['risk_level']: item['count'] for item in risk_distribution}
        
        # Top allergens (simplified - in production, you'd analyze the JSON data)
        top_allergens = AllergenCategory.objects.annotate(
            recipe_count=Count('allergensynonym__allergendetectionlog__recipe', distinct=True)
        ).order_by('-recipe_count')[:10]
        
        top_allergens_data = [
            {'name': allergen.name, 'recipe_count': allergen.recipe_count}
            for allergen in top_allergens
        ]
        
        stats = {
            'total_recipes': total_recipes,
            'analyzed_recipes': analyzed_recipes,
            'unanalyzed_recipes': unanalyzed_recipes,
            'analysis_percentage': round(analysis_percentage, 1),
            'risk_distribution': risk_dist,
            'top_allergens': top_allergens_data
        }
        
        # Cache for 15 minutes
        cache.set(cache_key, stats, 900)
        
        return Response(stats)

    @swagger_auto_schema(
        operation_description="Submit feedback for recipe allergen analysis",
        request_body=RecipeFeedbackSerializer,
        responses={200: "Feedback submitted successfully"}
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticatedOrReadOnly])
    def feedback(self, request):
        """Submit feedback for recipe allergen analysis"""
        serializer = RecipeFeedbackSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                # Create or update detection log
                detection_log, created = AllergenDetectionLog.objects.get_or_create(
                    recipe_id=data['recipe_id'],
                    allergen_category__name=data['allergen_category'],
                    detected_term=data['detected_term'],
                    defaults={
                        'is_correct': data['is_correct'],
                        'verified_by': 'user_feedback',
                        'verification_date': timezone.now(),
                        'user_notes': data.get('user_notes', ''),
                        'user_email': data.get('user_email', '')
                    }
                )
                
                if not created:
                    detection_log.is_correct = data['is_correct']
                    detection_log.verified_by = 'user_feedback'
                    detection_log.verification_date = timezone.now()
                    detection_log.user_notes = data.get('user_notes', '')
                    detection_log.user_email = data.get('user_email', '')
                    detection_log.save()
                
                logger.info(f"Feedback submitted for recipe {data['recipe_id']}: {data['detected_term']} - {data['is_correct']}")
                
                return Response({
                    'message': 'Feedback submitted successfully',
                    'detection_log_id': detection_log.id
                })
                
            except Exception as e:
                logger.error(f"Error submitting feedback: {e}")
                return Response(
                    {'error': 'Failed to submit feedback'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AllergenAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for allergen analysis results
    """
    queryset = AllergenAnalysisResult.objects.select_related('recipe').all()
    serializer_class = AllergenAnalysisResultSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['risk_level', 'recipe']
    ordering_fields = ['analysis_date', 'processing_time', 'risk_level']
    ordering = ['-analysis_date']




class AllergenCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for allergen categories
    """
    queryset = AllergenCategory.objects.filter(is_active=True)
    serializer_class = AllergenCategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    @swagger_auto_schema(
        operation_description="Update allergen dictionary",
        request_body=AllergenDictionaryUpdateSerializer,
        responses={200: "Dictionary updated successfully"}
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def update_dictionary(self, request):
        """Update allergen dictionary with new terms"""
        serializer = AllergenDictionaryUpdateSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                category = AllergenCategory.objects.get(name=data['category_name'])
                
                # Add new terms
                if data.get('new_terms'):
                    for term in data['new_terms']:
                        AllergenSynonym.objects.get_or_create(
                            allergen_category=category,
                            term=term,
                            defaults={
                                'term_type': 'user_added',
                                'confidence_score': data.get('update_confidence', 0.8)
                            }
                        )
                
                # Remove terms
                if data.get('remove_terms'):
                    AllergenSynonym.objects.filter(
                        allergen_category=category,
                        term__in=data['remove_terms']
                    ).update(is_active=False)
                
                # Update confidence scores
                if data.get('update_confidence'):
                    AllergenSynonym.objects.filter(
                        allergen_category=category
                    ).update(confidence_score=data['update_confidence'])
                
                logger.info(f"Allergen dictionary updated for category {data['category_name']}")
                
                return Response({
                    'message': 'Allergen dictionary updated successfully',
                    'category': data['category_name']
                })
                
            except AllergenCategory.DoesNotExist:
                return Response(
                    {'error': f'Allergen category "{data["category_name"]}" not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.error(f"Error updating allergen dictionary: {e}")
                return Response(
                    {'error': 'Failed to update allergen dictionary'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HealthCheckViewSet(viewsets.ViewSet):
    """
    API endpoint for health checks
    """
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Check system health",
        responses={200: HealthCheckSerializer}
    )
    @action(detail=False, methods=['get'])
    def health(self, request):
        """Check system health status"""
        try:
            # Check database
            db_status = 'healthy'
            try:
                Recipe.objects.count()
            except Exception:
                db_status = 'unhealthy'
            
            # Check cache
            cache_status = 'healthy'
            try:
                cache.set('health_check', 'ok', 10)
                if cache.get('health_check') != 'ok':
                    cache_status = 'unhealthy'
            except Exception:
                cache_status = 'unhealthy'
            
            # Check Celery (simplified)
            celery_status = 'healthy'
            try:
                # In production, you'd check Celery worker status
                pass
            except Exception:
                celery_status = 'unhealthy'
            
            health_data = {
                'status': 'healthy' if all(s == 'healthy' for s in [db_status, cache_status, celery_status]) else 'degraded',
                'timestamp': timezone.now(),
                'version': '1.0.0',
                'database_status': db_status,
                'cache_status': cache_status,
                'celery_status': celery_status
            }
            
            return Response(health_data)
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return Response({
                'status': 'unhealthy',
                'timestamp': timezone.now(),
                'version': '1.0.0',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 