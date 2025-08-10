from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from recipes.models import RecipeFeedback, UserFeedback, AllergenCategory, AllergenSynonym
from recipes.feedback_models import FeedbackImpact, FeedbackAnalytics
from scraper.nlp_ingredient_processor import NLPIngredientProcessor
import json
import logging
from collections import defaultdict
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process reviewed feedback and apply learning to improve allergen dictionary and NLP model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of feedback items to process in each batch'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes'
        )
        parser.add_argument(
            '--feedback-type',
            choices=['recipe', 'user', 'all'],
            default='all',
            help='Type of feedback to process'
        )
        parser.add_argument(
            '--min-confidence',
            type=float,
            default=0.7,
            help='Minimum confidence threshold for applying changes'
        )

    def handle(self, *args, **options):
        self.batch_size = options['batch_size']
        self.dry_run = options['dry_run']
        self.feedback_type = options['feedback_type']
        self.min_confidence = options['min_confidence']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting feedback learning processing...\n'
                f'Batch size: {self.batch_size}\n'
                f'Dry run: {self.dry_run}\n'
                f'Feedback type: {self.feedback_type}\n'
                f'Min confidence: {self.min_confidence}'
            )
        )
        
        # Process feedback
        stats = self.process_feedback_learning()
        
        # Generate report
        self.generate_learning_report(stats)
        
        self.stdout.write(
            self.style.SUCCESS('Feedback learning processing completed!')
        )

    def process_feedback_learning(self) -> Dict[str, Any]:
        """Process feedback and apply learning improvements"""
        stats = {
            'total_processed': 0,
            'dictionary_updates': 0,
            'synonym_additions': 0,
            'confidence_adjustments': 0,
            'model_improvements': 0,
            'errors': 0
        }
        
        # Get feedback to process
        feedback_items = self.get_feedback_to_process()
        
        if not feedback_items:
            self.stdout.write(self.style.WARNING('No feedback items to process'))
            return stats
        
        self.stdout.write(f'Processing {len(feedback_items)} feedback items...')
        
        # Process in batches
        for i in range(0, len(feedback_items), self.batch_size):
            batch = feedback_items[i:i + self.batch_size]
            batch_stats = self.process_feedback_batch(batch)
            
            # Update overall stats
            for key in stats:
                stats[key] += batch_stats.get(key, 0)
            
            self.stdout.write(f'Processed batch {i//self.batch_size + 1}: {batch_stats}')
        
        return stats

    def get_feedback_to_process(self) -> List[Any]:
        """Get feedback items ready for learning processing"""
        feedback_items = []
        
        if self.feedback_type in ['recipe', 'all']:
            # Get reviewed RecipeFeedback items
            recipe_feedback = RecipeFeedback.objects.filter(
                is_reviewed=True,
                reviewed_at__isnull=False
            ).select_related('recipe', 'reviewed_by')
            
            for feedback in recipe_feedback:
                feedback_items.append({
                    'type': 'recipe',
                    'feedback': feedback,
                    'data': feedback.feedback_data,
                    'notes': feedback.notes
                })
        
        if self.feedback_type in ['user', 'all']:
            # Get resolved UserFeedback items
            user_feedback = UserFeedback.objects.filter(
                status__in=['resolved', 'reviewed']
            ).select_related('recipe', 'reviewed_by')
            
            for feedback in user_feedback:
                feedback_items.append({
                    'type': 'user',
                    'feedback': feedback,
                    'data': {
                        'feedback_type': feedback.feedback_type,
                        'allergen_category': feedback.allergen_category,
                        'detected_term': feedback.detected_term,
                        'user_notes': feedback.user_notes
                    },
                    'notes': feedback.user_notes
                })
        
        return feedback_items

    def process_feedback_batch(self, batch: List[Dict]) -> Dict[str, int]:
        """Process a batch of feedback items"""
        batch_stats = {
            'dictionary_updates': 0,
            'synonym_additions': 0,
            'confidence_adjustments': 0,
            'model_improvements': 0,
            'errors': 0
        }
        
        for item in batch:
            try:
                if item['type'] == 'recipe':
                    item_stats = self.process_recipe_feedback(item)
                else:
                    item_stats = self.process_user_feedback(item)
                
                # Update batch stats
                for key in batch_stats:
                    batch_stats[key] += item_stats.get(key, 0)
                    
            except Exception as e:
                logger.error(f"Error processing feedback item: {e}")
                batch_stats['errors'] += 1
        
        return batch_stats

    def process_recipe_feedback(self, item: Dict) -> Dict[str, int]:
        """Process RecipeFeedback item for learning"""
        stats = {
            'dictionary_updates': 0,
            'synonym_additions': 0,
            'confidence_adjustments': 0,
            'model_improvements': 0
        }
        
        feedback_data = item['data']
        recipe = item['feedback'].recipe
        
        # Process each detection feedback
        for log_id, detection_feedback in feedback_data.items():
            if not isinstance(detection_feedback, dict):
                continue
            
            allergen_category = detection_feedback.get('allergen_category')
            detected_term = detection_feedback.get('detected_term')
            is_correct = detection_feedback.get('is_correct')
            confidence_score = detection_feedback.get('confidence_score', 0.0)
            
            if not all([allergen_category, detected_term, is_correct is not None]):
                continue
            
            # Apply learning based on feedback
            if is_correct:
                # Correct detection - strengthen the term
                if self.add_or_strengthen_synonym(allergen_category, detected_term, confidence_score):
                    stats['synonym_additions'] += 1
            else:
                # Incorrect detection - weaken or remove the term
                if self.weaken_or_remove_synonym(allergen_category, detected_term):
                    stats['dictionary_updates'] += 1
            
            # Adjust confidence scoring
            if self.adjust_confidence_scoring(allergen_category, detected_term, is_correct, confidence_score):
                stats['confidence_adjustments'] += 1
        
        # Create impact record
        self.create_feedback_impact(item['feedback'], stats)
        
        return stats

    def process_user_feedback(self, item: Dict) -> Dict[str, int]:
        """Process UserFeedback item for learning"""
        stats = {
            'dictionary_updates': 0,
            'synonym_additions': 0,
            'confidence_adjustments': 0,
            'model_improvements': 0
        }
        
        feedback_data = item['data']
        feedback_type = feedback_data.get('feedback_type')
        allergen_category = feedback_data.get('allergen_category')
        detected_term = feedback_data.get('detected_term')
        user_notes = feedback_data.get('user_notes', '')
        
        if not allergen_category or not detected_term:
            return stats
        
        # Process based on feedback type
        if feedback_type == 'missing_allergen':
            # User found a missing allergen - add to dictionary
            if self.add_missing_allergen(allergen_category, detected_term, user_notes):
                stats['synonym_additions'] += 1
        
        elif feedback_type == 'incorrect_allergen':
            # User found incorrect detection - remove or weaken
            if self.remove_incorrect_allergen(allergen_category, detected_term):
                stats['dictionary_updates'] += 1
        
        elif feedback_type == 'false_positive':
            # False positive - reduce confidence or remove
            if self.handle_false_positive(allergen_category, detected_term):
                stats['confidence_adjustments'] += 1
        
        elif feedback_type == 'false_negative':
            # False negative - add or strengthen
            if self.handle_false_negative(allergen_category, detected_term, user_notes):
                stats['synonym_additions'] += 1
        
        # Create impact record
        self.create_feedback_impact(item['feedback'], stats)
        
        return stats

    def add_or_strengthen_synonym(self, allergen_category: str, term: str, confidence: float) -> bool:
        """Add or strengthen a synonym in the allergen dictionary"""
        try:
            category = AllergenCategory.objects.filter(name__iexact=allergen_category).first()
            if not category:
                logger.warning(f"Allergen category not found: {allergen_category}")
                return False
            
            # Check if synonym already exists
            synonym, created = AllergenSynonym.objects.get_or_create(
                allergen_category=category,
                term=term.lower(),
                defaults={
                    'term_type': 'synonym',
                    'confidence_score': confidence,
                    'is_active': True
                }
            )
            
            if not created:
                # Strengthen existing synonym
                synonym.confidence_score = min(1.0, synonym.confidence_score + 0.1)
                synonym.is_active = True
                synonym.save()
            
            if not self.dry_run:
                synonym.save()
            
            self.stdout.write(f"{'[DRY RUN] ' if self.dry_run else ''}Added/strengthened synonym: {term} -> {allergen_category}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding/strengthening synonym: {e}")
            return False

    def weaken_or_remove_synonym(self, allergen_category: str, term: str) -> bool:
        """Weaken or remove a synonym from the allergen dictionary"""
        try:
            category = AllergenCategory.objects.filter(name__iexact=allergen_category).first()
            if not category:
                return False
            
            synonym = AllergenSynonym.objects.filter(
                allergen_category=category,
                term=term.lower()
            ).first()
            
            if synonym:
                if synonym.confidence_score > 0.3:
                    # Weaken the synonym
                    synonym.confidence_score = max(0.0, synonym.confidence_score - 0.2)
                    if not self.dry_run:
                        synonym.save()
                    self.stdout.write(f"{'[DRY RUN] ' if self.dry_run else ''}Weakened synonym: {term} -> {allergen_category}")
                else:
                    # Remove the synonym
                    if not self.dry_run:
                        synonym.delete()
                    self.stdout.write(f"{'[DRY RUN] ' if self.dry_run else ''}Removed synonym: {term} -> {allergen_category}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error weakening/removing synonym: {e}")
            return False

    def add_missing_allergen(self, allergen_category: str, term: str, notes: str) -> bool:
        """Add a missing allergen term to the dictionary"""
        try:
            category = AllergenCategory.objects.filter(name__iexact=allergen_category).first()
            if not category:
                return False
            
            # Check if term already exists
            existing = AllergenSynonym.objects.filter(
                allergen_category=category,
                term=term.lower()
            ).exists()
            
            if not existing:
                synonym = AllergenSynonym(
                    allergen_category=category,
                    term=term.lower(),
                    term_type='synonym',
                    confidence_score=0.8,  # High confidence for user-reported terms
                    is_active=True
                )
                
                if not self.dry_run:
                    synonym.save()
                
                self.stdout.write(f"{'[DRY RUN] ' if self.dry_run else ''}Added missing allergen: {term} -> {allergen_category}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error adding missing allergen: {e}")
            return False

    def remove_incorrect_allergen(self, allergen_category: str, term: str) -> bool:
        """Remove an incorrect allergen term"""
        try:
            category = AllergenCategory.objects.filter(name__iexact=allergen_category).first()
            if not category:
                return False
            
            synonym = AllergenSynonym.objects.filter(
                allergen_category=category,
                term=term.lower()
            ).first()
            
            if synonym:
                if not self.dry_run:
                    synonym.delete()
                self.stdout.write(f"{'[DRY RUN] ' if self.dry_run else ''}Removed incorrect allergen: {term} -> {allergen_category}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing incorrect allergen: {e}")
            return False

    def handle_false_positive(self, allergen_category: str, term: str) -> bool:
        """Handle false positive feedback"""
        return self.weaken_or_remove_synonym(allergen_category, term)

    def handle_false_negative(self, allergen_category: str, term: str, notes: str) -> bool:
        """Handle false negative feedback"""
        return self.add_missing_allergen(allergen_category, term, notes)

    def adjust_confidence_scoring(self, allergen_category: str, term: str, is_correct: bool, confidence: float) -> bool:
        """Adjust confidence scoring based on feedback"""
        try:
            category = AllergenCategory.objects.filter(name__iexact=allergen_category).first()
            if not category:
                return False
            
            synonym = AllergenSynonym.objects.filter(
                allergen_category=category,
                term=term.lower()
            ).first()
            
            if synonym:
                if is_correct and confidence < 0.8:
                    # Increase confidence for correct detections with low confidence
                    synonym.confidence_score = min(1.0, synonym.confidence_score + 0.1)
                elif not is_correct and confidence > 0.6:
                    # Decrease confidence for incorrect detections with high confidence
                    synonym.confidence_score = max(0.0, synonym.confidence_score - 0.1)
                
                if not self.dry_run:
                    synonym.save()
                
                self.stdout.write(f"{'[DRY RUN] ' if self.dry_run else ''}Adjusted confidence: {term} -> {synonym.confidence_score:.2f}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error adjusting confidence scoring: {e}")
            return False

    def create_feedback_impact(self, feedback, stats: Dict[str, int]):
        """Create feedback impact record"""
        try:
            if not self.dry_run:
                impact = FeedbackImpact.objects.create(
                    feedback=feedback,
                    model_updated=stats['model_improvements'] > 0,
                    dictionary_updated=stats['dictionary_updates'] > 0,
                    confidence_adjusted=stats['confidence_adjustments'] > 0,
                    changes_made=stats,
                    improvement_score=self.calculate_improvement_score(stats)
                )
        except Exception as e:
            logger.error(f"Error creating feedback impact: {e}")

    def calculate_improvement_score(self, stats: Dict[str, int]) -> float:
        """Calculate improvement score based on changes made"""
        total_changes = sum(stats.values())
        if total_changes == 0:
            return 0.0
        
        # Weight different types of changes
        weighted_score = (
            stats['synonym_additions'] * 0.3 +
            stats['dictionary_updates'] * 0.2 +
            stats['confidence_adjustments'] * 0.3 +
            stats['model_improvements'] * 0.2
        )
        
        return min(1.0, weighted_score / total_changes)

    def generate_learning_report(self, stats: Dict[str, Any]):
        """Generate a report of the learning process"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('FEEDBACK LEARNING REPORT'))
        self.stdout.write('='*60)
        
        self.stdout.write(f"Total feedback processed: {stats['total_processed']}")
        self.stdout.write(f"Dictionary updates: {stats['dictionary_updates']}")
        self.stdout.write(f"Synonym additions: {stats['synonym_additions']}")
        self.stdout.write(f"Confidence adjustments: {stats['confidence_adjustments']}")
        self.stdout.write(f"Model improvements: {stats['model_improvements']}")
        self.stdout.write(f"Errors: {stats['errors']}")
        
        if stats['total_processed'] > 0:
            success_rate = ((stats['total_processed'] - stats['errors']) / stats['total_processed']) * 100
            self.stdout.write(f"Success rate: {success_rate:.1f}%")
        
        self.stdout.write('='*60) 