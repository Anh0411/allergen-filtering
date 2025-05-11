from django.urls import path
from . import views

urlpatterns = [
    path('', views.recipe_search, name='recipe_search'),
    path('recipe/<int:pk>/', views.recipe_detail, name='recipe_detail'),
] 