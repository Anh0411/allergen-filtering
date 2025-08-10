from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from django.utils import timezone
from recipes.models import RecipeFeedback, UserFeedback, AllergenDetectionLog
from recipes.feedback_models import FeedbackAnalytics, UserProfile
import logging
from typing import Dict, List, Any
from datetime import timedelta

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Validate feedback quality and identify high-quality feedback for learning'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-agreement',
            type=float,
            default=0.8,
            help='Minimum agreement threshold for feedback validation'
        )
        parser.add_argument(
            '--min-user-score',
            type=float,
            default=0.7,
            help='Minimum user accuracy score for feedback validation'
        )
        parser.add_argument(
            '--auto-approve',
            action='store_true',
            help='Automatically approve high-quality feedback'
        )
        parser.add_argument(
            '--generate-report',
            action='store_true',
            help='Generate detailed quality report'
        )

    def handle(self, *args, **options):
        self.min_agreement = options['min_agreement']
        self.min_user_score = options['min_user_score']
        self.auto_approve = options['auto_approve']
        self.generate_report = options['generate_report']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting feedback quality validation...\n'
                f'Min agreement threshold: {self.min_agreement}\n'
                f'Min user score: {self.min_user_score}\n'
                f'Auto-approve: {self.auto_approve}'
            )
        )
        
        # Validate feedback quality
        validation_results = self.validate_feedback_quality()
        
        # Generate report if requested
        if self.generate_report:
            self.generate_quality_report(validation_results)
        
        self.stdout.write(
            self.style.SUCCESS('Feedback quality validation completed!')
        )

    def validate_feedback_quality(self) -> Dict[str, Any]:
        """Validate feedback quality using multiple criteria"""
        results = {
            'total_feedback': 0,
            'high_quality': 0,
            'medium_quality': 0,
            'low_quality': 0,
            'auto_approved': 0,
            'flagged_for_review': 0,
            'validation_details': []
        }
        
        # Process RecipeFeedback
        recipe_feedback = RecipeFeedback.objects.filter(
            is_reviewed=False
        ).select_related('recipe', 'user')
        
        for feedback in recipe_feedback:
            quality_score = self.calculate_feedback_quality(feedback)
            validation_detail = self.validate_single_feedback(feedback, quality_score)
            results['validation_details'].append(validation_detail)
            
            if quality_score >= 0.8:
                results['high_quality'] += 1
                if self.auto_approve:
                    self.auto_approve_feedback(feedback)
                    results['auto_approved'] += 1
            elif quality_score >= 0.6:
                results['medium_quality'] += 1
            else:
                results['low_quality'] += 1
                results['flagged_for_review'] += 1
            
            results['total_feedback'] += 1
        
        # Process UserFeedback
        user_feedback = UserFeedback.objects.filter(
            status='pending'
        ).select_related('recipe', 'user')
        
        for feedback in user_feedback:
            quality_score = self.calculate_user_feedback_quality(feedback)
            validation_detail = self.validate_user_feedback(feedback, quality_score)
            results['validation_details'].append(validation_detail)
            
            if quality_score >= 0.8:
                results['high_quality'] += 1
                if self.auto_approve:
                    self.auto_approve_user_feedback(feedback)
                    results['auto_approved'] += 1
            elif quality_score >= 0.6:
                results['medium_quality'] += 1
            else:
                results['low_quality'] += 1
                results['flagged_for_review'] += 1
            
            results['total_feedback'] += 1
        
        return results

    def calculate_feedback_quality(self, feedback: RecipeFeedback) -> float:
        """Calculate quality score for RecipeFeedback"""
        quality_factors = []
        
        # Factor 1: User credibility (if authenticated)
        if feedback.user:
            user_profile = UserProfile.objects.filter(user=feedback.user).first()
            if user_profile and user_profile.feedback_accuracy_score:
                quality_factors.append(user_profile.feedback_accuracy_score)
            else:
                quality_factors.append(0.5)  # Default for new users
        else:
            quality_factors.append(0.3)  # Lower score for anonymous feedback
        
        # Factor 2: Feedback completeness
        feedback_data = feedback.feedback_data
        if isinstance(feedback_data, dict) and feedback_data:
            completeness = min(1.0, len(feedback_data) / 3.0)  # Normalize to 0-1
            quality_factors.append(completeness)
        else:
            quality_factors.append(0.2)
        
        # Factor 3: Notes quality
        if feedback.notes and len(feedback.notes.strip()) > 10:
            quality_factors.append(0.8)
        else:
            quality_factors.append(0.4)
        
        # Factor 4: Consistency with detection logs
        consistency_score = self.calculate_consistency_score(feedback)
        quality_factors.append(consistency_score)
        
        # Factor 5: Recipe complexity (more complex recipes might have more errors)
        complexity_score = self.calculate_recipe_complexity_score(feedback.recipe)
        quality_factors.append(complexity_score)
        
        # Calculate weighted average
        weights = [0.3, 0.2, 0.15, 0.25, 0.1]  # User credibility, completeness, notes, consistency, complexity
        weighted_score = sum(factor * weight for factor, weight in zip(quality_factors, weights))
        
        return min(1.0, max(0.0, weighted_score))

    def calculate_user_feedback_quality(self, feedback: UserFeedback) -> float:
        """Calculate quality score for UserFeedback"""
        quality_factors = []
        
        # Factor 1: User credibility
        if feedback.user:
            user_profile = UserProfile.objects.filter(user=feedback.user).first()
            if user_profile and user_profile.feedback_accuracy_score:
                quality_factors.append(user_profile.feedback_accuracy_score)
            else:
                quality_factors.append(0.5)
        else:
            quality_factors.append(0.3)
        
        # Factor 2: Feedback type specificity
        type_scores = {
            'missing_allergen': 0.9,
            'incorrect_allergen': 0.8,
            'false_positive': 0.7,
            'false_negative': 0.8,
            'wrong_confidence': 0.6,
            'other': 0.4
        }
        quality_factors.append(type_scores.get(feedback.feedback_type, 0.5))
        
        # Factor 3: Notes quality
        if feedback.user_notes and len(feedback.user_notes.strip()) > 20:
            quality_factors.append(0.9)
        elif feedback.user_notes and len(feedback.user_notes.strip()) > 5:
            quality_factors.append(0.6)
        else:
            quality_factors.append(0.3)
        
        # Factor 4: Specificity of feedback
        if feedback.allergen_category and feedback.detected_term:
            quality_factors.append(0.8)
        else:
            quality_factors.append(0.4)
        
        # Calculate weighted average
        weights = [0.4, 0.25, 0.2, 0.15]
        weighted_score = sum(factor * weight for factor, weight in zip(quality_factors, weights))
        
        return min(1.0, max(0.0, weighted_score))

    def calculate_consistency_score(self, feedback: RecipeFeedback) -> float:
        """Calculate consistency between feedback and detection logs"""
        try:
            detection_logs = AllergenDetectionLog.objects.filter(recipe=feedback.recipe)
            feedback_data = feedback.feedback_data
            
            if not isinstance(feedback_data, dict) or not detection_logs.exists():
                return 0.5
            
            consistency_matches = 0
            total_comparisons = 0
            
            for log in detection_logs:
                log_id_str = str(log.id)
                if log_id_str in feedback_data:
                    feedback_info = feedback_data[log_id_str]
                    if isinstance(feedback_info, dict):
                        # Check if feedback matches detection log
                        if (feedback_info.get('allergen_category') == log.allergen_category.name and
                            feedback_info.get('detected_term') == log.detected_term):
                            consistency_matches += 1
                        total_comparisons += 1
            
            if total_comparisons == 0:
                return 0.5
            
            return consistency_matches / total_comparisons
            
        except Exception as e:
            logger.error(f"Error calculating consistency score: {e}")
            return 0.5

    def calculate_recipe_complexity_score(self, recipe) -> float:
        """Calculate recipe complexity score (simpler recipes might have fewer errors)"""
        try:
            # Count ingredients
            ingredients_text = recipe.scraped_ingredients_text
            if isinstance(ingredients_text, list):
                ingredient_count = len(ingredients_text)
            else:
                ingredient_count = len(ingredients_text.split(',')) if ingredients_text else 0
            
            # Count detection logs
            detection_count = AllergenDetectionLog.objects.filter(recipe=recipe).count()
            
            # Complexity score (more ingredients/detections = higher complexity)
            complexity = (ingredient_count + detection_count) / 20.0  # Normalize
            
            # Invert: higher complexity = lower quality score (more room for errors)
            return max(0.3, 1.0 - complexity)
            
        except Exception as e:
            logger.error(f"Error calculating recipe complexity: {e}")
            return 0.5

    def validate_single_feedback(self, feedback: RecipeFeedback, quality_score: float) -> Dict[str, Any]:
        """Validate a single RecipeFeedback item"""
        return {
            'feedback_id': feedback.id,
            'feedback_type': 'recipe',
            'recipe_title': feedback.recipe.title,
            'user': feedback.user.username if feedback.user else 'Anonymous',
            'quality_score': quality_score,
            'quality_level': self.get_quality_level(quality_score),
            'created_at': feedback.created_at,
            'recommendation': self.get_validation_recommendation(quality_score),
            'issues': self.identify_feedback_issues(feedback)
        }

    def validate_user_feedback(self, feedback: UserFeedback, quality_score: float) -> Dict[str, Any]:
        """Validate a single UserFeedback item"""
        return {
            'feedback_id': feedback.id,
            'feedback_type': 'user',
            'recipe_title': feedback.recipe.title,
            'user': feedback.user.username if feedback.user else 'Anonymous',
            'feedback_type_category': feedback.feedback_type,
            'quality_score': quality_score,
            'quality_level': self.get_quality_level(quality_score),
            'created_at': feedback.created_at,
            'recommendation': self.get_validation_recommendation(quality_score),
            'issues': self.identify_user_feedback_issues(feedback)
        }

    def get_quality_level(self, score: float) -> str:
        """Get quality level based on score"""
        if score >= 0.8:
            return 'high'
        elif score >= 0.6:
            return 'medium'
        else:
            return 'low'

    def get_validation_recommendation(self, score: float) -> str:
        """Get validation recommendation based on quality score"""
        if score >= 0.8:
            return 'auto_approve'
        elif score >= 0.6:
            return 'manual_review'
        else:
            return 'flag_for_review'

    def identify_feedback_issues(self, feedback: RecipeFeedback) -> List[str]:
        """Identify potential issues with feedback"""
        issues = []
        
        if not feedback.user:
            issues.append('Anonymous feedback')
        
        feedback_data = feedback.feedback_data
        if not isinstance(feedback_data, dict) or not feedback_data:
            issues.append('Empty or invalid feedback data')
        
        if not feedback.notes or len(feedback.notes.strip()) < 10:
            issues.append('Insufficient notes')
        
        # Check for consistency issues
        detection_logs = AllergenDetectionLog.objects.filter(recipe=feedback.recipe)
        if detection_logs.exists() and isinstance(feedback_data, dict):
            feedback_count = len(feedback_data)
            log_count = detection_logs.count()
            if feedback_count < log_count * 0.5:  # Less than 50% of detections have feedback
                issues.append('Incomplete feedback coverage')
        
        return issues

    def identify_user_feedback_issues(self, feedback: UserFeedback) -> List[str]:
        """Identify potential issues with user feedback"""
        issues = []
        
        if not feedback.user:
            issues.append('Anonymous feedback')
        
        if not feedback.allergen_category or not feedback.detected_term:
            issues.append('Missing allergen category or detected term')
        
        if not feedback.user_notes or len(feedback.user_notes.strip()) < 10:
            issues.append('Insufficient user notes')
        
        if feedback.feedback_type == 'other':
            issues.append('Generic feedback type')
        
        return issues

    def auto_approve_feedback(self, feedback: RecipeFeedback):
        """Automatically approve high-quality feedback"""
        try:
            feedback.is_reviewed = True
            feedback.reviewed_at = timezone.now()
            feedback.reviewed_by = None  # System approval
            feedback.save()
            
            self.stdout.write(f"Auto-approved RecipeFeedback {feedback.id}")
            
        except Exception as e:
            logger.error(f"Error auto-approving feedback {feedback.id}: {e}")

    def auto_approve_user_feedback(self, feedback: UserFeedback):
        """Automatically approve high-quality user feedback"""
        try:
            feedback.status = 'resolved'
            feedback.reviewed_at = timezone.now()
            feedback.reviewed_by = None  # System approval
            feedback.save()
            
            self.stdout.write(f"Auto-approved UserFeedback {feedback.id}")
            
        except Exception as e:
            logger.error(f"Error auto-approving user feedback {feedback.id}: {e}")

    def generate_quality_report(self, results: Dict[str, Any]):
        """Generate detailed quality report"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('FEEDBACK QUALITY VALIDATION REPORT'))
        self.stdout.write('='*60)
        
        # Summary statistics
        self.stdout.write(f"Total feedback processed: {results['total_feedback']}")
        self.stdout.write(f"High quality: {results['high_quality']} ({results['high_quality']/results['total_feedback']*100:.1f}%)")
        self.stdout.write(f"Medium quality: {results['medium_quality']} ({results['medium_quality']/results['total_feedback']*100:.1f}%)")
        self.stdout.write(f"Low quality: {results['low_quality']} ({results['low_quality']/results['total_feedback']*100:.1f}%)")
        self.stdout.write(f"Auto-approved: {results['auto_approved']}")
        self.stdout.write(f"Flagged for review: {results['flagged_for_review']}")
        
        # Quality distribution
        self.stdout.write('\nQUALITY DISTRIBUTION:')
        quality_levels = {}
        for detail in results['validation_details']:
            level = detail['quality_level']
            quality_levels[level] = quality_levels.get(level, 0) + 1
        
        for level, count in sorted(quality_levels.items()):
            percentage = count / results['total_feedback'] * 100
            self.stdout.write(f"  {level.title()}: {count} ({percentage:.1f}%)")
        
        # Common issues
        self.stdout.write('\nCOMMON ISSUES:')
        issue_counts = {}
        for detail in results['validation_details']:
            for issue in detail.get('issues', []):
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = count / results['total_feedback'] * 100
            self.stdout.write(f"  {issue}: {count} ({percentage:.1f}%)")
        
        # Recommendations
        self.stdout.write('\nRECOMMENDATIONS:')
        recommendation_counts = {}
        for detail in results['validation_details']:
            rec = detail['recommendation']
            recommendation_counts[rec] = recommendation_counts.get(rec, 0) + 1
        
        for rec, count in sorted(recommendation_counts.items()):
            percentage = count / results['total_feedback'] * 100
            self.stdout.write(f"  {rec.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")
        
        self.stdout.write('='*60) 