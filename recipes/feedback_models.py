"""
Models for user feedback system
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class UserFeedback(models.Model):
    """
    User feedback on allergen detection
    """
    FEEDBACK_TYPES = [
        ('incorrect_allergen', 'Incorrect Allergen Detected'),
        ('missing_allergen', 'Missing Allergen'),
        ('wrong_confidence', 'Wrong Confidence Score'),
        ('false_positive', 'False Positive'),
        ('false_negative', 'False Negative'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ]
    
    # Basic information
    recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    feedback_type = models.CharField(max_length=50, choices=FEEDBACK_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Feedback details
    allergen_category = models.CharField(max_length=100, blank=True)
    detected_term = models.CharField(max_length=200, blank=True)
    user_notes = models.TextField(blank=True)
    user_email = models.EmailField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='reviewed_feedback'
    )
    
    # User agent and IP for tracking
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Feedback on {self.recipe.title} - {self.feedback_type}"


class FeedbackResponse(models.Model):
    """
    Response to user feedback
    """
    feedback = models.OneToOneField(UserFeedback, on_delete=models.CASCADE)
    responder = models.ForeignKey(User, on_delete=models.CASCADE)
    response_text = models.TextField()
    action_taken = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Response to feedback {self.feedback.id}"


class FeedbackAnalytics(models.Model):
    """
    Analytics for feedback patterns
    """
    date = models.DateField()
    
    # Feedback counts
    total_feedback = models.IntegerField(default=0)
    pending_feedback = models.IntegerField(default=0)
    resolved_feedback = models.IntegerField(default=0)
    rejected_feedback = models.IntegerField(default=0)
    
    # Feedback types
    incorrect_allergen_count = models.IntegerField(default=0)
    missing_allergen_count = models.IntegerField(default=0)
    wrong_confidence_count = models.IntegerField(default=0)
    false_positive_count = models.IntegerField(default=0)
    false_negative_count = models.IntegerField(default=0)
    other_count = models.IntegerField(default=0)
    
    # Allergen categories
    allergen_category_counts = models.JSONField(default=dict)
    
    class Meta:
        unique_together = ['date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Feedback Analytics - {self.date}"


class FeedbackImpact(models.Model):
    """
    Track impact of feedback on model improvements
    """
    feedback = models.ForeignKey(UserFeedback, on_delete=models.CASCADE)
    
    # Impact metrics
    model_updated = models.BooleanField(default=False)
    dictionary_updated = models.BooleanField(default=False)
    confidence_adjusted = models.BooleanField(default=False)
    
    # Specific changes
    changes_made = models.JSONField(default=dict)
    improvement_score = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Impact of feedback {self.feedback.id}"


class UserProfile(models.Model):
    """
    Extended user profile for feedback preferences
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Feedback preferences
    email_notifications = models.BooleanField(default=True)
    feedback_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('never', 'Never'),
        ],
        default='daily'
    )
    
    # Allergen preferences
    primary_allergens = models.JSONField(default=list)
    secondary_allergens = models.JSONField(default=list)
    
    # Feedback history
    total_feedback_submitted = models.IntegerField(default=0)
    feedback_accuracy_score = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    last_feedback_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Profile for {self.user.username}"


class FeedbackTemplate(models.Model):
    """
    Templates for common feedback responses
    """
    name = models.CharField(max_length=200)
    feedback_type = models.CharField(max_length=50, choices=UserFeedback.FEEDBACK_TYPES)
    template_text = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class FeedbackBatch(models.Model):
    """
    Batch processing of feedback
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Batch settings
    feedback_items = models.ManyToManyField(UserFeedback)
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Processing results
    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    errors = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.created_at.date()}"
    
    def get_completion_rate(self):
        """Get completion rate for this batch"""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100


class FeedbackExport(models.Model):
    """
    Exported feedback data
    """
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
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    feedback_types = models.JSONField(default=list)
    status_filter = models.CharField(max_length=20, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Feedback export - {self.format} - {self.created_at.date()}" 