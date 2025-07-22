"""
Models for dataset annotation system
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class AnnotationProject(models.Model):
    """
    Project for organizing recipe annotations
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Annotation settings
    recipes_per_annotator = models.IntegerField(default=100)
    require_agreement = models.BooleanField(default=True)
    min_agreement_threshold = models.FloatField(
        default=0.8,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class AnnotationTask(models.Model):
    """
    Individual annotation task for a recipe
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
        ('resolved', 'Resolved'),
    ]
    
    project = models.ForeignKey(AnnotationProject, on_delete=models.CASCADE)
    recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Priority and difficulty
    priority = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    difficulty_score = models.FloatField(null=True, blank=True)
    
    class Meta:
        unique_together = ['project', 'recipe']
        ordering = ['priority', '-created_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.recipe.title}"


class RecipeAnnotation(models.Model):
    """
    Individual annotation for a recipe
    """
    task = models.ForeignKey(AnnotationTask, on_delete=models.CASCADE)
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Allergen annotations
    celery = models.BooleanField(default=False)
    cereals_gluten = models.BooleanField(default=False)
    crustaceans = models.BooleanField(default=False)
    eggs = models.BooleanField(default=False)
    fish = models.BooleanField(default=False)
    lupin = models.BooleanField(default=False)
    milk = models.BooleanField(default=False)
    molluscs = models.BooleanField(default=False)
    mustard = models.BooleanField(default=False)
    nuts = models.BooleanField(default=False)
    peanuts = models.BooleanField(default=False)
    sesame = models.BooleanField(default=False)
    soybeans = models.BooleanField(default=False)
    sulphites = models.BooleanField(default=False)
    
    # Confidence and notes
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=1.0
    )
    notes = models.TextField(blank=True)
    
    # Quality indicators
    time_spent_seconds = models.IntegerField(null=True, blank=True)
    is_complete = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['task', 'annotator']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task.recipe.title} - {self.annotator.username}"
    
    def get_allergen_list(self):
        """Get list of detected allergens"""
        allergens = []
        allergen_fields = [
            'celery', 'cereals_gluten', 'crustaceans', 'eggs', 'fish',
            'lupin', 'milk', 'molluscs', 'mustard', 'nuts', 'peanuts',
            'sesame', 'soybeans', 'sulphites'
        ]
        
        for field in allergen_fields:
            if getattr(self, field):
                allergens.append(field)
        
        return allergens
    
    def get_risk_level(self):
        """Calculate risk level based on detected allergens"""
        allergens = self.get_allergen_list()
        
        if not allergens:
            return 'low'
        
        # High-risk allergens
        high_risk = ['peanuts', 'nuts', 'crustaceans', 'fish']
        high_risk_count = sum(1 for allergen in allergens if allergen in high_risk)
        
        if high_risk_count >= 2 or (high_risk_count >= 1 and len(allergens) >= 4):
            return 'critical'
        elif high_risk_count > 0:
            return 'high'
        elif len(allergens) >= 1:
            return 'medium'
        else:
            return 'low'


class AnnotationDispute(models.Model):
    """
    Dispute resolution for conflicting annotations
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    task = models.ForeignKey(AnnotationTask, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_disputes'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    description = models.TextField()
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Dispute for {self.task.recipe.title}"


class AnnotationGuideline(models.Model):
    """
    Guidelines for annotators
    """
    project = models.ForeignKey(AnnotationProject, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    version = models.CharField(max_length=20, default='1.0')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.title} v{self.version}"


class AnnotationQuality(models.Model):
    """
    Quality metrics for annotations
    """
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(AnnotationProject, on_delete=models.CASCADE)
    
    # Quality metrics
    total_annotations = models.IntegerField(default=0)
    completed_annotations = models.IntegerField(default=0)
    average_confidence = models.FloatField(default=0.0)
    average_time_per_annotation = models.FloatField(default=0.0)
    
    # Agreement metrics
    agreement_rate = models.FloatField(default=0.0)
    disputes_created = models.IntegerField(default=0)
    disputes_resolved = models.IntegerField(default=0)
    
    # Timestamps
    last_annotation_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['annotator', 'project']
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.annotator.username} - {self.project.name}"


class AnnotationBatch(models.Model):
    """
    Batch of recipes for annotation
    """
    project = models.ForeignKey(AnnotationProject, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Batch settings
    recipes = models.ManyToManyField('Recipe', through='AnnotationTask')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"
    
    def get_completion_rate(self):
        """Get completion rate for this batch"""
        total_tasks = self.annotationtask_set.count()
        completed_tasks = self.annotationtask_set.filter(status='completed').count()
        
        if total_tasks == 0:
            return 0.0
        
        return (completed_tasks / total_tasks) * 100


class AnnotationExport(models.Model):
    """
    Exported annotation data
    """
    project = models.ForeignKey(AnnotationProject, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Export details
    format = models.CharField(max_length=20, choices=[
        ('json', 'JSON'),
        ('csv', 'CSV'),
        ('excel', 'Excel'),
    ])
    file_path = models.CharField(max_length=500)
    file_size = models.IntegerField(null=True, blank=True)
    
    # Export filters
    include_disputed = models.BooleanField(default=False)
    include_notes = models.BooleanField(default=True)
    include_quality_metrics = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.format} export - {self.created_at.date()}"


class AllergenCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)


class Recipe(models.Model):
    title = models.CharField(max_length=255)
    # ... other fields ...


class Annotation(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)
    allergens = models.ManyToManyField(AllergenCategory)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True) 