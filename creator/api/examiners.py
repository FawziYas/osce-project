"""
Creator API – Examiner endpoints.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from core.models import Examiner, ExaminerAssignment


@login_required
@require_GET
def get_examiners(request):
    """GET /api/creator/examiners"""
    examiners = Examiner.objects.filter(is_active=True, role='examiner').order_by('full_name')
    return JsonResponse([{
        'id': e.id,
        'username': e.username,
        'full_name': e.full_name,
        'title': e.title,
        'department': e.department,
        'display_name': e.display_name,
    } for e in examiners], safe=False)


@login_required
@require_POST
def create_examiner_api(request):
    """POST /api/creator/examiners"""
    data = json.loads(request.body)
    if not data.get('username') or not data.get('full_name'):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    if Examiner.objects.filter(username=data['username']).exists():
        return JsonResponse({'error': 'Username already exists'}, status=400)

    examiner = Examiner(
        username=data['username'],
        email=data.get('email', f"{data['username']}@osce.local"),
        full_name=data['full_name'],
        title=data.get('title', ''),
        department=data.get('department', ''),
        is_active=True,
    )
    examiner.set_password(data.get('password', data['username']))
    examiner.save()

    return JsonResponse({
        'id': examiner.id,
        'username': examiner.username,
        'message': 'Examiner created',
    }, status=201)


@login_required
@require_GET
def get_session_assignments(request, session_id):
    """GET /api/creator/sessions/<id>/assignments"""
    assignments = ExaminerAssignment.objects.filter(
        session_id=session_id
    ).select_related('station', 'examiner')

    return JsonResponse([{
        'id': str(a.id),
        'station_id': str(a.station_id),
        'station_name': a.station.name if a.station else None,
        'station_number': a.station.station_number if a.station else None,
        'examiner_id': a.examiner_id,
        'examiner_name': a.examiner.display_name if a.examiner else None,
        'is_primary': a.is_primary,
    } for a in assignments], safe=False)


@login_required
@require_POST
def create_assignment(request, session_id):
    """POST /api/creator/sessions/<id>/assignments"""
    data = json.loads(request.body)
    if not data.get('station_id') or not data.get('examiner_id'):
        return JsonResponse({'error': 'Missing station_id or examiner_id'}, status=400)

    if ExaminerAssignment.objects.filter(
        session_id=session_id,
        station_id=data['station_id'],
        examiner_id=data['examiner_id'],
    ).exists():
        return JsonResponse({'error': 'Assignment already exists'}, status=400)

    assignment = ExaminerAssignment.objects.create(
        session_id=session_id,
        station_id=data['station_id'],
        examiner_id=data['examiner_id'],
        is_primary=data.get('is_primary', True),
    )
    return JsonResponse({'id': str(assignment.id), 'message': 'Examiner assigned'}, status=201)
