"""
Creator API – Session endpoints (status, activate, deactivate, complete, delete, restore).
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from core.models import (
    ExamSession, SessionStudent, Path, Station, ExaminerAssignment, StationScore,
)
from core.models.mixins import TimestampMixin


@login_required
@require_GET
def get_session_status(request, session_id):
    """GET /api/creator/sessions/<id>/status"""
    session = get_object_or_404(ExamSession, pk=session_id)
    students = SessionStudent.objects.filter(session=session)

    status_counts = {}
    for s in students:
        st = s.status or 'registered'
        status_counts[st] = status_counts.get(st, 0) + 1

    return JsonResponse({
        'id': str(session.id),
        'status': session.status,
        'total_students': students.count(),
        'student_status': status_counts,
        'exam_name': session.exam.name if session.exam else None,
    })


@login_required
@require_POST
def activate_session(request, session_id):
    """POST /api/creator/sessions/<id>/activate"""
    session = get_object_or_404(ExamSession, pk=session_id)
    warnings = []

    paths = Path.objects.filter(session=session, is_deleted=False)
    station_count = 0
    for p in paths:
        station_count += p.stations.filter(active=True, is_deleted=False).count()

    if station_count == 0:
        return JsonResponse(
            {'error': 'Cannot activate: No stations defined in any path for this session'},
            status=400,
        )

    student_count = SessionStudent.objects.filter(session=session).count()
    if student_count == 0:
        warnings.append('No students registered for this session')

    assignment_count = ExaminerAssignment.objects.filter(session=session).count()
    if assignment_count == 0:
        warnings.append('No examiners assigned to stations')

    path_count = paths.count()
    if path_count == 0:
        warnings.append('No paths defined – create paths first')

    session.status = 'in_progress'
    session.actual_start = TimestampMixin.utc_timestamp()
    session.save()

    resp = {
        'message': 'Session activated',
        'status': 'in_progress',
        'station_count': station_count,
        'student_count': student_count,
        'assignment_count': assignment_count,
        'path_count': path_count,
    }
    if warnings:
        resp['warnings'] = warnings
    return JsonResponse(resp)


@login_required
@require_POST
def deactivate_session(request, session_id):
    """POST /api/creator/sessions/<id>/deactivate"""
    session = get_object_or_404(ExamSession, pk=session_id)
    if session.status == 'completed':
        return JsonResponse({'error': 'Cannot deactivate completed session'}, status=400)

    session.status = 'scheduled'
    session.save()
    return JsonResponse({'message': 'Session deactivated', 'status': 'scheduled'})


@login_required
@require_POST
def complete_session(request, session_id):
    """POST /api/creator/sessions/<id>/complete"""
    session = get_object_or_404(ExamSession, pk=session_id)
    session.status = 'completed'
    session.save()
    return JsonResponse({'message': 'Session completed', 'status': 'completed'})


@login_required
@require_POST
def delete_session_api(request, session_id):
    """DELETE (POST) /api/creator/sessions/<id>/delete"""
    session = get_object_or_404(ExamSession, pk=session_id)

    score_count = StationScore.objects.filter(
        session_student__session=session
    ).count()
    if score_count > 0 and session.status != 'completed':
        return JsonResponse(
            {'error': f'Cannot delete: {score_count} scores recorded. Complete the session first.'},
            status=400,
        )

    session.status = 'archived'
    session.save()
    return JsonResponse({'message': f"Session '{session.name}' archived"})


@login_required
@require_POST
def restore_session_api(request, session_id):
    """POST /api/creator/sessions/<id>/restore"""
    session = get_object_or_404(ExamSession, pk=session_id)
    if session.status != 'archived':
        return JsonResponse({'error': 'Session is not archived'}, status=400)

    session.status = 'completed'
    session.save()
    return JsonResponse({'message': f"Session '{session.name}' restored"})
