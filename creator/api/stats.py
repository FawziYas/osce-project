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


@login_required
def get_stats_overview(request):
    """GET /api/creator/stats/overview"""
    return JsonResponse({
        'courses': Course.objects.count(),
        'ilos': ILO.objects.count(),
        'exams': Exam.objects.filter(is_deleted=False).count(),
        'stations': Station.objects.filter(
            active=True,
            is_deleted=False,
            path__session__exam__is_deleted=False,
        ).count(),
        'library_items': ChecklistLibrary.objects.count(),
        'examiners': Examiner.objects.count(),
        'sessions': ExamSession.objects.filter(
            exam__is_deleted=False,
        ).count(),
        'students_registered': SessionStudent.objects.filter(
            session__exam__is_deleted=False,
        ).count(),
        'scores_recorded': StationScore.objects.count(),
    })
