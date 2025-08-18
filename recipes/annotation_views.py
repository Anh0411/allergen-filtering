"""
Views for the annotation interface
"""

import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg

from .models import (
    Recipe, AnnotationProject, AnnotationTask, Annotation,
    AnnotationDispute, AnnotationQuality
)
from .annotation_models import AnnotationBatch, AnnotationGuideline

logger = logging.getLogger(__name__)


@login_required
def annotation_dashboard(request):
    """Main annotation dashboard"""
    # Get user's annotation projects
    projects = AnnotationProject.objects.filter(
        Q(created_by=request.user) | 
        Q(annotationtask__assigned_to=request.user)
    ).distinct()
    
    # Get user's annotation statistics
    user_stats = AnnotationQuality.objects.filter(annotator=request.user)
    
    # Get recent tasks
    recent_tasks = AnnotationTask.objects.filter(
        assigned_to=request.user,
        status__in=['pending', 'in_progress']
    ).order_by('priority', '-created_at')[:10]
    
    context = {
        'projects': projects,
        'user_stats': user_stats,
        'recent_tasks': recent_tasks,
    }
    
    return render(request, 'recipes/annotation/dashboard.html', context)


@login_required
def project_detail(request, project_id):
    """Project detail view"""
    project = get_object_or_404(AnnotationProject, id=project_id)
    
    # Check if user has access to this project
    if not (project.created_by == request.user or 
            project.annotationtask_set.filter(assigned_to=request.user).exists()):
        messages.error(request, "You don't have access to this project.")
        return redirect('annotation_dashboard')
    
    # Get project statistics
    total_tasks = project.annotationtask_set.count()
    completed_tasks = project.annotationtask_set.filter(status='completed').count()
    pending_tasks = project.annotationtask_set.filter(status='pending').count()
    disputed_tasks = project.annotationtask_set.filter(status='disputed').count()
    
    # Get user's tasks for this project
    user_tasks = project.annotationtask_set.filter(assigned_to=request.user)
    user_completed = user_tasks.filter(status='completed').count()
    user_pending = user_tasks.filter(status='pending').count()
    
    # Get recent annotations
    recent_annotations = Annotation.objects.filter(
        task__project=project
    ).select_related('task__recipe', 'annotator').order_by('-created_at')[:10]
    
    context = {
        'project': project,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'disputed_tasks': disputed_tasks,
        'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
        'user_completed': user_completed,
        'user_pending': user_pending,
        'recent_annotations': recent_annotations,
    }
    
    return render(request, 'recipes/annotation/project_detail.html', context)


@login_required
def annotation_interface(request, task_id):
    """Main annotation interface"""
    task = get_object_or_404(AnnotationTask, id=task_id)
    
    # Check if user is assigned to this task
    if task.assigned_to != request.user:
        messages.error(request, "You are not assigned to this task.")
        return redirect('annotation_dashboard')
    
    # Check if task is already completed
    if task.status == 'completed':
        messages.warning(request, "This task is already completed.")
        return redirect('project_detail', project_id=task.project.id)
    
    # Get or create annotation
    annotation, created = Annotation.objects.get_or_create(
        task=task,
        annotator=request.user,
        defaults={'created_at': timezone.now()}
    )
    
    # Update task status
    if task.status == 'pending':
        task.status = 'in_progress'
        task.save()
    
    # Get guidelines
    guidelines = AnnotationGuideline.objects.filter(
        project=task.project,
        is_active=True
    ).order_by('-version')
    
    # Get allergen categories for the interface
    from .models import AllergenCategory
    allergen_categories = AllergenCategory.objects.filter(is_major_allergen=True).order_by('name')
    
    context = {
        'task': task,
        'annotation': annotation,
        'recipe': task.recipe,
        'guidelines': guidelines,
        'allergen_categories': allergen_categories,
    }
    
    return render(request, 'recipes/annotation/interface.html', context)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def save_annotation(request, task_id):
    """Save annotation via AJAX"""
    try:
        task = get_object_or_404(AnnotationTask, id=task_id, assigned_to=request.user)
        
        # Parse JSON data
        data = json.loads(request.body)
        
        # Get or create annotation
        annotation, created = Annotation.objects.get_or_create(
            task=task,
            annotator=request.user
        )
        
        # Update allergen fields - the existing Annotation model uses ManyToManyField
        if 'allergens' in data:
            # Clear existing allergens and set new ones
            annotation.allergens.clear()
            for allergen_id in data['allergens']:
                try:
                    from .models import AllergenCategory
                    allergen = AllergenCategory.objects.get(id=allergen_id)
                    annotation.allergens.add(allergen)
                except AllergenCategory.DoesNotExist:
                    logger.warning(f"Allergen category {allergen_id} not found")
        
        # Update notes field
        if 'notes' in data:
            annotation.notes = data['notes']
        
        annotation.save()
        
        # Update task status if complete
        if data.get('is_complete', False):
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.save()
            
            # Update quality metrics
            quality, _ = AnnotationQuality.objects.get_or_create(
                annotator=request.user,
                project=task.project
            )
            quality.completed_annotations += 1
            quality.last_annotation_at = timezone.now()
            quality.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Annotation saved successfully',
            'annotation_id': annotation.id
        })
        
    except Exception as e:
        logger.error(f"Error saving annotation: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def task_list(request, project_id):
    """List of tasks for a project"""
    project = get_object_or_404(AnnotationProject, id=project_id)
    
    # Check access
    if not (project.created_by == request.user or 
            project.annotationtask_set.filter(assigned_to=request.user).exists()):
        messages.error(request, "You don't have access to this project.")
        return redirect('annotation_dashboard')
    
    # Get tasks
    tasks = project.annotationtask_set.select_related('recipe', 'assigned_to').order_by('priority', '-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    # Filter by assignee
    assignee_filter = request.GET.get('assignee')
    if assignee_filter:
        tasks = tasks.filter(assigned_to__username=assignee_filter)
    
    # Pagination
    paginator = Paginator(tasks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'project': project,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'assignee_filter': assignee_filter,
    }
    
    return render(request, 'recipes/annotation/task_list.html', context)


@login_required
def annotation_review(request, task_id):
    """Review annotation and check for agreement"""
    task = get_object_or_404(AnnotationTask, id=task_id)
    
    # Check if user has access
    if not (task.project.created_by == request.user or 
            task.assigned_to == request.user):
        messages.error(request, "You don't have access to this task.")
        return redirect('annotation_dashboard')
    
    # Get all annotations for this task
    annotations = Annotation.objects.filter(task=task).select_related('annotator')
    
    # Check for agreement
    agreement_data = check_annotation_agreement(annotations)
    
    context = {
        'task': task,
        'annotations': annotations,
        'agreement_data': agreement_data,
    }
    
    return render(request, 'recipes/annotation/review.html', context)


@login_required
@require_http_methods(["POST"])
def create_dispute(request, task_id):
    """Create a dispute for conflicting annotations"""
    task = get_object_or_404(AnnotationTask, id=task_id)
    
    # Check if user has access
    if not (task.project.created_by == request.user or 
            task.assigned_to == request.user):
        messages.error(request, "You don't have access to this task.")
        return redirect('annotation_dashboard')
    
    description = request.POST.get('description')
    if not description:
        messages.error(request, "Description is required.")
        return redirect('annotation_review', task_id=task_id)
    
    # Create dispute
    dispute = AnnotationDispute.objects.create(
        task=task,
        created_by=request.user,
        description=description
    )
    
    # Update task status
    task.status = 'disputed'
    task.save()
    
    messages.success(request, "Dispute created successfully.")
    return redirect('annotation_review', task_id=task_id)


@login_required
def dispute_list(request, project_id):
    """List of disputes for a project"""
    project = get_object_or_404(AnnotationProject, id=project_id)
    
    # Check if user is project creator
    if project.created_by != request.user:
        messages.error(request, "Only project creators can view disputes.")
        return redirect('annotation_dashboard')
    
    disputes = AnnotationDispute.objects.filter(
        task__project=project
    ).select_related('task__recipe', 'created_by', 'resolved_by').order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        disputes = disputes.filter(status=status_filter)
    
    context = {
        'project': project,
        'disputes': disputes,
        'status_filter': status_filter,
    }
    
    return render(request, 'recipes/annotation/dispute_list.html', context)


@login_required
@require_http_methods(["POST"])
def resolve_dispute(request, dispute_id):
    """Resolve a dispute"""
    dispute = get_object_or_404(AnnotationDispute, id=dispute_id)
    
    # Check if user is project creator
    if dispute.task.project.created_by != request.user:
        messages.error(request, "Only project creators can resolve disputes.")
        return redirect('annotation_dashboard')
    
    resolution_notes = request.POST.get('resolution_notes', '')
    
    # Update dispute
    dispute.status = 'resolved'
    dispute.resolved_by = request.user
    dispute.resolved_at = timezone.now()
    dispute.resolution_notes = resolution_notes
    dispute.save()
    
    # Update task status
    dispute.task.status = 'resolved'
    dispute.task.save()
    
    messages.success(request, "Dispute resolved successfully.")
    return redirect('dispute_list', project_id=dispute.task.project.id)


@login_required
def quality_dashboard(request, project_id):
    """Quality metrics dashboard"""
    project = get_object_or_404(AnnotationProject, id=project_id)
    
    # Check if user is project creator
    if project.created_by != request.user:
        messages.error(request, "Only project creators can view quality metrics.")
        return redirect('annotation_dashboard')
    
    # Get quality metrics for all annotators
    quality_metrics = AnnotationQuality.objects.filter(
        project=project
    ).select_related('annotator').order_by('-completed_annotations')
    
    # Get project statistics
    total_annotations = Annotation.objects.filter(task__project=project).count()
    total_disputes = AnnotationDispute.objects.filter(task__project=project).count()
    resolved_disputes = AnnotationDispute.objects.filter(
        task__project=project,
        status='resolved'
    ).count()
    
    # Calculate average agreement rate
    avg_agreement = quality_metrics.aggregate(Avg('agreement_rate'))['agreement_rate__avg'] or 0
    
    context = {
        'project': project,
        'quality_metrics': quality_metrics,
        'total_annotations': total_annotations,
        'total_disputes': total_disputes,
        'resolved_disputes': resolved_disputes,
        'avg_agreement': avg_agreement,
    }
    
    return render(request, 'recipes/annotation/quality_dashboard.html', context)


def check_annotation_agreement(annotations):
    """Check agreement between annotations"""
    if len(annotations) < 2:
        return {'agreement': 1.0, 'conflicts': []}
    
    # Get all allergen categories
    from .models import AllergenCategory
    allergen_categories = AllergenCategory.objects.filter(is_major_allergen=True)
    
    conflicts = []
    total_fields = allergen_categories.count()
    agreed_fields = 0
    
    for allergen_category in allergen_categories:
        # Check if this allergen is present in all annotations
        values = [allergen_category in ann.allergens.all() for ann in annotations]
        if len(set(values)) > 1:  # Conflict detected
            conflicts.append({
                'field': allergen_category.name,
                'values': values,
                'annotators': [ann.annotator.username for ann in annotations]
            })
        else:
            agreed_fields += 1
    
    agreement_rate = agreed_fields / total_fields if total_fields > 0 else 0
    
    return {
        'agreement': agreement_rate,
        'conflicts': conflicts,
        'total_fields': total_fields,
        'agreed_fields': agreed_fields
    }


@login_required
def export_annotations(request, project_id):
    """Export annotations for a project"""
    project = get_object_or_404(AnnotationProject, id=project_id)
    
    # Check if user is project creator
    if project.created_by != request.user:
        messages.error(request, "Only project creators can export annotations.")
        return redirect('annotation_dashboard')
    
    # Get all completed annotations
    annotations = Annotation.objects.filter(
        task__project=project
    ).select_related('task__recipe', 'annotator')
    
    # Prepare data for export
    export_data = []
    for annotation in annotations:
        data = {
            'recipe_id': annotation.task.recipe.id,
            'recipe_title': annotation.task.recipe.title,
            'annotator': annotation.annotator.username,
            'notes': annotation.notes,
            'created_at': annotation.created_at.isoformat(),
            'allergens': [allergen.name for allergen in annotation.allergens.all()],
        }
        export_data.append(data)
    
    # Create response
    response = HttpResponse(
        json.dumps(export_data, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="{project.name}_annotations.json"'
    
    return response 