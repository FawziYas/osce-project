"""
Creator API – Exam endpoints.
"""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from core.models import (
    Course, Exam, Station, ChecklistItem, ILO, ExamSession,
)


@login_required
@require_GET
def get_exams(request):
    """GET /api/creator/exams – with optional ?include_deleted=true"""
    include_deleted = request.GET.get('include_deleted', 'false').lower() == 'true'

    qs = Exam.objects.select_related('course')
    if not include_deleted:
        qs = qs.filter(is_deleted=False)

    exams = qs.order_by('-created_at')
    # P2: Use annotate to eliminate N+1 count queries
    exams = exams.annotate(
        _station_count=Count('stations', distinct=True),
        _session_count=Count('sessions', distinct=True),
    )
    return JsonResponse([{
        'id': str(e.id),
        'name': e.name,
        'course_code': e.course.code if e.course else None,
        'status': e.status,
        'station_count': e._station_count,
        'session_count': e._session_count,
        'exam_date': e.exam_date.isoformat() if e.exam_date else None,
        'is_deleted': e.is_deleted,
    } for e in exams], safe=False)


@login_required
@require_GET
def get_exam_stations(request, exam_id):
    """GET /api/creator/exams/<id>/stations"""
    # P2: Use annotate to eliminate N+1 per station
    stations = Station.objects.filter(
        exam_id=exam_id
    ).annotate(
        _item_count=Count('checklist_items'),
    ).order_by('station_number')
    return JsonResponse([{
        'id': str(s.id),
        'station_number': s.station_number,
        'name': s.name,
        'scenario': (s.scenario[:100] + '...') if s.scenario and len(s.scenario) > 100 else s.scenario,
        'duration_minutes': s.duration_minutes,
        'max_score': s.get_max_score(),
        'item_count': s._item_count,
    } for s in stations], safe=False)


@login_required
@require_GET
def get_station_items(request, station_id):
    """GET /api/creator/stations/<id>/items"""
    ILO_THEMES = getattr(settings, 'ILO_THEMES', {})

    items = ChecklistItem.objects.filter(
        station_id=station_id
    ).select_related('ilo', 'ilo__theme').order_by('item_number')

    result = []
    for item in items:
        ilo = item.ilo
        theme = {}
        if ilo and ilo.theme:
            theme = {
                'name': ilo.theme.name,
                'color': ilo.theme.color,
            }

        result.append({
            'id': item.id,
            'item_number': item.item_number,
            'description': item.description,
            'points': item.points,
            'is_critical': item.is_critical,
            'interaction_type': item.interaction_type,
            'ilo_id': item.ilo_id,
            'ilo_number': ilo.number if ilo else None,
            'theme_name': theme.get('name', 'Unknown'),
            'theme_color': theme.get('color', '#6c757d'),
            'library_item_id': item.library_item_id,
        })

    return JsonResponse(result, safe=False)


@login_required
@require_GET
def get_exam_summary(request, exam_id):
    """GET /api/creator/exams/<id>/summary"""
    exam = get_object_or_404(Exam, pk=exam_id)
    stations = Station.objects.filter(exam=exam).order_by('station_number')

    theme_summary = {}
    total_marks = 0

    for station in stations:
        for item in station.checklist_items.select_related('ilo', 'ilo__theme').all():
            ilo = item.ilo
            theme_id = ilo.theme_id if ilo else 0
            if theme_id not in theme_summary:
                theme_name = ilo.theme.name if ilo and ilo.theme else 'Unknown'
                theme_color = ilo.theme.color if ilo and ilo.theme else '#6c757d'
                theme_summary[theme_id] = {
                    'theme_id': theme_id,
                    'name': theme_name,
                    'color': theme_color,
                    'total_points': 0,
                    'item_count': 0,
                }
            theme_summary[theme_id]['total_points'] += item.points or 0
            theme_summary[theme_id]['item_count'] += 1
            total_marks += item.points or 0

    return JsonResponse({
        'exam_id': str(exam.id),
        'exam_name': exam.name,
        'course_code': exam.course.code if exam.course else None,
        'station_count': stations.count(),
        'total_marks': total_marks,
        'theme_breakdown': list(theme_summary.values()),
    })


# ---------------------------------------------------------------------------
# Delete / Archive / Restore via API
# ---------------------------------------------------------------------------

@login_required
@require_POST
def delete_exam_api(request, exam_id):
    """DELETE (POST) /api/creator/exams/<id>/delete"""
    exam = get_object_or_404(Exam, pk=exam_id)
    active = ExamSession.objects.filter(
        exam=exam, status__in=['in_progress', 'scheduled']
    ).count()
    if active:
        return JsonResponse({'error': f'Cannot delete: {active} active sessions exist'}, status=400)

    exam.soft_delete()
    return JsonResponse({'message': f"Exam '{exam.name}' archived"})


@login_required
@require_POST
def restore_exam_api(request, exam_id):
    """POST /api/creator/exams/<id>/restore"""
    exam = get_object_or_404(Exam, pk=exam_id)
    if not exam.is_deleted:
        return JsonResponse({'error': 'Exam is not deleted'}, status=400)
    exam.restore()
    return JsonResponse({'message': f"Exam '{exam.name}' restored"})
