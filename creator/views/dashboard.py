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


@login_required
def dashboard(request):
    """Main creator dashboard – overview of exams and courses."""
    courses = Course.objects.all()
    exams = Exam.objects.filter(is_deleted=False) \
        .select_related('course') \
        .order_by('-created_at')[:10]

    stats = {
        'exams': Exam.objects.filter(is_deleted=False).count(),
        'archived_exams': Exam.objects.filter(is_deleted=True).count(),
        'active_sessions': ExamSession.objects.filter(
            exam__is_deleted=False, status='in_progress'
        ).count(),
        'draft_exams': Exam.objects.filter(status='draft', is_deleted=False).count(),
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
