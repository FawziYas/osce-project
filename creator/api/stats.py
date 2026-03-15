"""
Creator API – Statistics overview endpoint.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from core.models import (
    ChecklistLibrary,
    Course,
    Exam,
    ExamSession,
    Examiner,
    ILO,
    Path,
    SessionStudent,
    Station,
    StationScore,
)
from core.utils.roles import scope_queryset


@login_required
def get_stats_overview(request):
    """GET /api/creator/stats/overview"""
    user = request.user
    return JsonResponse({
        'courses': scope_queryset(user, Course.objects.all(), dept_field='department').count(),
        'ilos': scope_queryset(user, ILO.objects.all(), dept_field='course__department').count(),
        'exams': scope_queryset(user, Exam.objects.filter(is_deleted=False), dept_field='course__department').count(),
        'stations': scope_queryset(user, Station.objects.filter(
            active=True,
            is_deleted=False,
            path__session__exam__is_deleted=False,
        ), dept_field='path__session__exam__course__department').count(),
        'library_items': scope_queryset(user, ChecklistLibrary.objects.all(), dept_field='ilo__course__department').count(),
        'examiners': scope_queryset(user, Examiner.objects.filter(role='examiner', is_deleted=False), dept_field='department').count(),
        'sessions': scope_queryset(user, ExamSession.objects.filter(
            exam__is_deleted=False,
        ), dept_field='exam__course__department').count(),
        'students_registered': scope_queryset(user, SessionStudent.objects.filter(
            session__exam__is_deleted=False,
        ), dept_field='session__exam__course__department').count(),
        'scores_recorded': scope_queryset(user, StationScore.objects.all(), dept_field='station__path__session__exam__course__department').count(),
    })
