from django import forms
from django.contrib.auth.models import User
from .models import Recipe, AllergenCategory, AllergenDetectionLog

class RecipeSearchForm(forms.Form):
    """Form for searching recipes with allergen filters"""
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search recipes...'
        })
    )
    
    allergens = forms.ModelMultipleChoiceField(
        queryset=AllergenCategory.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-checkbox text-blue-600'
        })
    )
    
    risk_level = forms.ChoiceField(
        choices=[
            ('', 'Any Risk Level'),
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical Risk'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )

class FeedbackForm(forms.Form):
    """Form for user feedback on allergen detection accuracy"""
    
    def __init__(self, detection_logs=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if detection_logs:
            for log in detection_logs:
                # Create a choice field for each detection log
                field_name = f'feedback_{log.id}'
                self.fields[field_name] = forms.ChoiceField(
                    choices=[
                        ('', 'Select feedback'),
                        ('correct', 'Correct detection'),
                        ('incorrect', 'Incorrect detection'),
                        ('unsure', 'Not sure'),
                    ],
                    required=False,
                    widget=forms.Select(attrs={
                        'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                    })
                )
                
                # Add a notes field for each detection
                notes_field_name = f'notes_{log.id}'
                self.fields[notes_field_name] = forms.CharField(
                    max_length=500,
                    required=False,
                    widget=forms.Textarea(attrs={
                        'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                        'rows': 2,
                        'placeholder': 'Additional comments (optional)'
                    })
                )
    
    general_notes = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'rows': 4,
            'placeholder': 'Please provide any additional comments or suggestions for improving our allergen detection...'
        })
    )
    
    overall_accuracy = forms.ChoiceField(
        choices=[
            ('', 'Select rating'),
            ('excellent', 'Excellent - Very accurate'),
            ('good', 'Good - Mostly accurate'),
            ('fair', 'Fair - Some inaccuracies'),
            ('poor', 'Poor - Many inaccuracies'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )

class AnnotationForm(forms.ModelForm):
    """Form for creating/editing recipe annotations"""
    
    class Meta:
        model = Recipe
        fields = ['allergen_categories']
        widgets = {
            'allergen_categories': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-checkbox text-blue-600'
            })
        }

class DetectionLogFeedbackForm(forms.ModelForm):
    """Form for providing feedback on individual detection logs"""
    
    class Meta:
        model = AllergenDetectionLog
        fields = ['is_correct']
        widgets = {
            'is_correct': forms.RadioSelect(choices=[
                (True, 'Correct detection'),
                (False, 'Incorrect detection'),
            ], attrs={
                'class': 'form-radio text-blue-600'
            })
        }
    
    notes = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'rows': 2,
            'placeholder': 'Additional comments (optional)'
        })
    ) 