"""
Creator Dashboard view.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.db.models import Q

from core.models import Course, Exam, ExamSession
from core.utils.audit import log_action
from core.utils.roles import scope_queryset


@login_required
def dashboard(request):
    """Main creator dashboard – overview of exams and courses. Dept-scoped."""
    courses = scope_queryset(request.user, Course.objects.all(), dept_field='department')
    exams = scope_queryset(
        request.user,
        Exam.objects.filter(is_deleted=False).select_related('course'),
        dept_field='course__department',
    ).order_by('-created_at')[:10]

    # Stats scoped to user's department
    all_exams = scope_queryset(
        request.user,
        Exam.objects.all(),
        dept_field='course__department',
    )
    all_sessions = scope_queryset(
        request.user,
        ExamSession.objects.filter(exam__is_deleted=False),
        dept_field='exam__course__department',
    )

    stats = {
        'exams': all_exams.filter(is_deleted=False).count(),
        'archived_exams': all_exams.filter(is_deleted=True).count(),
        'active_sessions': all_sessions.filter(status='in_progress').count(),
        'draft_exams': all_exams.filter(status='draft', is_deleted=False).count(),
    }

    return render(request, 'creator/dashboard.html', {
        'courses': courses,
        'exams': exams,
        'stats': stats,
    })


@login_required
def logout_view(request):
    """Logout creator/coordinator user."""
    log_action(request, 'LOGOUT', 'Examiner', request.user.id,
               f'{request.user.display_name} logged out from creator interface')
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('/login/')
