"""
Creator API – Path endpoints (CRUD, stations in path, reorder).
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from core.models import ExamSession, Path, Station
from core.models.mixins import TimestampMixin


@login_required
@require_GET
def get_session_paths(request, session_id):
    """GET /api/creator/sessions/<id>/paths"""
    paths = Path.objects.filter(
        session_id=session_id, is_deleted=False
    ).order_by('name')
    return JsonResponse(
        [p.to_dict(include_stations=True, include_students=True) for p in paths],
        safe=False,
    )


@login_required
@require_POST
def create_session_path(request, session_id):
    """POST /api/creator/sessions/<id>/paths"""
    session = get_object_or_404(ExamSession, pk=session_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    if not data.get('path_name'):
        return JsonResponse({'error': 'path_name is required'}, status=400)

    if Path.objects.filter(session=session, name=data['path_name']).exists():
        return JsonResponse(
            {'error': f"Path '{data['path_name']}' already exists in this session"},
            status=400,
        )

    path = Path.objects.create(
        session=session,
        name=data['path_name'],
        rotation_minutes=data.get('rotation_minutes', 8),
        is_active=True,
    )
    return JsonResponse({
        'id': str(path.id),
        'path_name': path.name,
        'message': f"Path '{path.name}' created successfully",
    }, status=201)


@login_required
@require_GET
def get_path(request, path_id):
    """GET /api/creator/paths/<id>"""
    path = get_object_or_404(Path, pk=path_id)
    return JsonResponse(path.to_dict(include_stations=True, include_students=True))


@login_required
def update_path(request, path_id):
    """PUT /api/creator/paths/<id>"""
    if request.method != 'PUT':
        return JsonResponse({'error': 'PUT required'}, status=405)

    path = get_object_or_404(Path, pk=path_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    if data.get('name'):
        if Path.objects.filter(
            session=path.session, name=data['name']
        ).exclude(pk=path_id).exists():
            return JsonResponse({'error': f"Path '{data['name']}' already exists"}, status=400)
        path.name = data['name']

    if 'rotation_minutes' in data:
        path.rotation_minutes = data['rotation_minutes']

    path.save()
    return JsonResponse({'message': 'Path updated', 'path': path.to_dict()})


@login_required
def delete_path_api(request, path_id):
    """DELETE /api/creator/paths/<id>"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE required'}, status=405)

    path = get_object_or_404(Path, pk=path_id)
    session = path.session

    if session and session.actual_start:
        return JsonResponse(
            {'error': 'Cannot delete paths after session has been activated.'},
            status=403,
        )

    student_count = path.students.count()
    if student_count > 0:
        return JsonResponse(
            {'error': f'Cannot delete: {student_count} students assigned to this path'},
            status=400,
        )

    path.is_deleted = True
    path.deleted_at = TimestampMixin.utc_timestamp()
    path.save()
    return JsonResponse({'message': f"Path '{path.name}' deleted"})


@login_required
@require_GET
def get_path_stations(request, path_id):
    """GET /api/creator/paths/<id>/stations"""
    stations = Station.objects.filter(
        path_id=path_id, active=True, is_deleted=False
    ).order_by('station_number')
    return JsonResponse([s.to_dict() for s in stations], safe=False)


@login_required
@require_POST
def add_station_to_path(request, path_id):
    """POST /api/creator/paths/<id>/stations – add a station to this path."""
    path = get_object_or_404(Path, pk=path_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    station_id = data.get('station_id')
    if not station_id:
        return JsonResponse({'error': 'station_id is required'}, status=400)

    station = get_object_or_404(Station, pk=station_id)

    # Verify station belongs to the same exam
    if path.session and station.exam_id:
        if str(station.exam_id) != str(path.session.exam_id):
            return JsonResponse({'error': 'Station does not belong to this exam'}, status=400)

    # Check if station already assigned to this path
    if str(station.path_id) == str(path_id):
        return JsonResponse({'error': 'Station already in this path'}, status=400)

    # Determine station_number (sequence position)
    if data.get('sequence_order'):
        seq = data['sequence_order']
    else:
        max_num = Station.objects.filter(
            path_id=path_id, active=True, is_deleted=False,
        ).order_by('-station_number').values_list('station_number', flat=True).first() or 0
        seq = max_num + 1

    station.path_id = path_id
    station.station_number = seq
    station.save()

    return JsonResponse({
        'id': str(station.id),
        'message': f"Station added to path at position {seq}",
    }, status=201)


@login_required
def remove_station_from_path(request, path_id, station_id):
    """DELETE /api/creator/paths/<id>/stations/<id> – remove station from path."""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE required'}, status=405)

    station = get_object_or_404(Station, pk=station_id, path_id=path_id)
    removed_num = station.station_number

    # Unlink the station from the path
    station.path_id = None
    station.station_number = 0
    station.save()

    # Re-sequence remaining stations
    remaining = Station.objects.filter(
        path_id=path_id, active=True, is_deleted=False, station_number__gt=removed_num,
    ).order_by('station_number')
    for s in remaining:
        s.station_number -= 1
        s.save()

    return JsonResponse({'message': 'Station removed from path'})


@login_required
@require_POST
def reorder_path_stations(request, path_id):
    """POST /api/creator/paths/<id>/stations/reorder"""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)
    if not data.get('station_order'):
        return JsonResponse({'error': 'station_order array required'}, status=400)

    for seq, sid in enumerate(data['station_order'], start=1):
        Station.objects.filter(path_id=path_id, pk=sid).update(station_number=seq)

    return JsonResponse({'message': 'Stations reordered successfully'})
