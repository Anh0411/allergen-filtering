"""
API URL patterns for the recipes app
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from .api_views import (
    RecipeViewSet, AllergenAnalysisViewSet, AllergenCategoryViewSet,
    HealthCheckViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'recipes', RecipeViewSet, basename='recipe')
router.register(r'analysis', AllergenAnalysisViewSet, basename='analysis')
router.register(r'allergen-categories', AllergenCategoryViewSet, basename='allergen-category')
router.register(r'health', HealthCheckViewSet, basename='health')

# Schema view for API documentation
schema_view = get_schema_view(
    openapi.Info(
        title="Allergen Filtering API",
        default_version='v1',
        description="API for filtering recipes based on allergen content",
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

# URL patterns
urlpatterns = [
    # API endpoints
    path('api/v1/', include(router.urls)),
    
    # JWT authentication
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # API documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API root
    path('api/v1/', include('rest_framework.urls', namespace='rest_framework')),
] 