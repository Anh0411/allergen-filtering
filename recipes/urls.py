from django.urls import path
from . import views

urlpatterns = [
    path('', views.recipe_search, name='recipe_search'),
    path('recipe/<int:pk>/', views.recipe_detail, name='recipe_detail'),
    path('dashboard/', views.allergen_dashboard, name='allergen_dashboard'),
    path('api/stats/', views.api_recipe_stats, name='api_recipe_stats'),
    path('annotate/recipe/<int:recipe_id>/', views.annotate_recipe, name='annotate_recipe'),
    path('feedback/<int:recipe_id>/', views.feedback_form, name='feedback_form'),
    path('feedback/<int:recipe_id>/submit/', views.submit_feedback_ajax, name='submit_feedback_ajax'),
] 