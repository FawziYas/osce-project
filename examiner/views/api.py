"""
Examiner API views – JSON endpoints for the tablet interface.
Designed for offline-first operation with sync support.
"""
import json
import uuid

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from core.models import (
    SessionStudent, Station, ChecklistItem, ExaminerAssignment,
    StationScore, ItemScore, Path,
)
from core.models.mixins import TimestampMixin
from core.utils.audit import log_action


def utc_timestamp():
    return TimestampMixin.utc_timestamp()


def _parse_json_body(request):
    """Safely parse JSON request body. Returns (data, error_response)."""
    try:
        return json.loads(request.body), None
    except (json.JSONDecodeError, ValueError):
        return None, JsonResponse({'error': 'Invalid JSON body'}, status=400)


# ── Student endpoints ──────────────────────────────────────────────

@login_required
@require_GET
def get_session_students(request, session_id):
    """Get all students for a session (for offline caching)."""
    # S3: Verify examiner has an assignment in this session
    has_assignment = ExaminerAssignment.objects.filter(
        session_id=session_id,
        examiner=request.user,
    ).exists()
    if not has_assignment and not request.user.is_staff:
        return JsonResponse({'error': 'Not assigned to this session'}, status=403)

    students = SessionStudent.objects.filter(
        session_id=session_id,
    ).order_by('rotation_group', 'sequence_number')

    return JsonResponse([{
        'id': str(s.id),
        'student_number': s.student_number,
        'full_name': s.full_name,
        'rotation_group': s.rotation_group,
        'sequence_number': s.sequence_number,
        'status': s.status,
        'photo_url': s.photo_url,
    } for s in students], safe=False)


# ── Checklist endpoints ────────────────────────────────────────────

@login_required
@require_GET
def get_station_checklist(request, station_id):
    """Get station info and all checklist items for marking."""
    station = get_object_or_404(Station, pk=station_id)

    items = ChecklistItem.objects.filter(
        station_id=station_id,
    ).select_related('ilo', 'ilo__theme').order_by('item_number')

    def build_item_response(item):
        response = {
            'id': item.id,
            'item_number': item.item_number,
            'description': item.description,
            'points': item.points,
            'category': item.category or 'General',
            'interaction_type': item.interaction_type,
            'expected_response': item.expected_response,
            'rubric_type': item.rubric_type or 'binary',
            'rubric_levels': None,
            'ilo_name': item.ilo.theme_name if item.ilo else None,
            'ilo_number': item.ilo.number if item.ilo else None,
        }

        # Parse rubric levels
        if item.rubric_levels:
            if isinstance(item.rubric_levels, list):
                response['rubric_levels'] = item.rubric_levels
            else:
                try:
                    response['rubric_levels'] = json.loads(item.rubric_levels)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Generate defaults based on type
        if not response['rubric_levels']:
            rubric_type = response['rubric_type']
            max_pts = item.points
            if rubric_type == 'binary':
                response['rubric_levels'] = [
                    {'score': 0, 'label': 'Not Done', 'color': 'danger'},
                    {'score': max_pts, 'label': 'Done', 'color': 'success'},
                ]
            elif rubric_type == 'partial':
                response['rubric_levels'] = [
                    {'score': 0, 'label': 'Not Done', 'color': 'danger'},
                    {'score': max_pts * 0.5, 'label': 'Partial', 'color': 'warning'},
                    {'score': max_pts, 'label': 'Complete', 'color': 'success'},
                ]
            elif rubric_type == 'scale':
                response['rubric_levels'] = [
                    {'score': i, 'label': str(i), 'color': 'secondary'}
                    for i in range(max_pts + 1)
                ]

        return response

    return JsonResponse({
        'station': {
            'id': str(station.id),
            'name': station.name,
            'scenario': station.scenario,
            'instructions': station.instructions,
            'duration_minutes': station.duration_minutes,
            'max_score': station.get_max_score(),
        },
        'items': [build_item_response(item) for item in items],
    })


# ── Scoring endpoints ─────────────────────────────────────────────

@login_required
@csrf_exempt
@require_POST
def start_marking(request):
    """Start a marking session for a student at a station."""
    data, err = _parse_json_body(request)
    if err:
        return err

    session_student_id = data.get('session_student_id')
    station_id = data.get('station_id')
    client_id = data.get('client_id', str(uuid.uuid4()))

    # S3: Verify examiner is assigned to this station in the session
    student = get_object_or_404(SessionStudent, pk=session_student_id)
    has_assignment = ExaminerAssignment.objects.filter(
        session_id=student.session_id,
        station_id=station_id,
        examiner=request.user,
    ).exists()
    if not has_assignment and not request.user.is_staff:
        return JsonResponse({'error': 'Not assigned to this station'}, status=403)

    # S7: Verify session is active
    session = student.session
    if hasattr(session, 'status') and session.status not in ('in_progress', 'active'):
        return JsonResponse({'error': 'Session is not active'}, status=400)

    existing = StationScore.objects.filter(
        session_student_id=session_student_id,
        station_id=station_id,
        examiner=request.user,
    ).first()

    if existing:
        item_scores = [{
            'checklist_item_id': i.checklist_item_id,
            'score': i.score,
            'notes': i.notes,
        } for i in existing.item_scores.all()]

        return JsonResponse({
            'id': str(existing.id),
            'local_uuid': str(existing.local_uuid),
            'status': existing.status,
            'total_score': existing.total_score,
            'message': 'Resuming existing marking session',
            'item_scores': item_scores,
        })

    score = StationScore(
        session_student_id=session_student_id,
        station_id=station_id,
        examiner=request.user,
        started_at=utc_timestamp(),
        status='in_progress',
        client_id=client_id,
        local_timestamp=data.get('local_timestamp', utc_timestamp()),
        sync_status='synced',
    )
    score.save()

    log_action(request, 'CREATE', 'StationScore', str(score.id),
               f'Started marking student {session_student_id} at station {station_id}')

    return JsonResponse({
        'id': str(score.id),
        'local_uuid': str(score.local_uuid),
        'status': 'created',
        'message': 'Marking session started',
    })


@login_required
@require_POST
def mark_item(request, station_score_id):
    """Mark a single checklist item (auto-save on each tap)."""
    data, err = _parse_json_body(request)
    if err:
        return err

    score = get_object_or_404(StationScore, pk=station_score_id)

    if score.examiner_id != request.user.id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    checklist_item_id = data.get('checklist_item_id')
    item_score_val = data.get('score', 0)
    notes = data.get('notes', '')
    max_points = data.get('max_points', 1)

    existing = ItemScore.objects.filter(
        station_score_id=station_score_id,
        checklist_item_id=checklist_item_id,
    ).first()

    if existing:
        existing.score = item_score_val
        existing.notes = notes
        existing.marked_at = utc_timestamp()
        existing.save()
    else:
        ItemScore.objects.create(
            station_score_id=station_score_id,
            checklist_item_id=checklist_item_id,
            score=item_score_val,
            max_points=max_points,
            notes=notes,
            marked_at=utc_timestamp(),
        )

    score.calculate_total()
    score.updated_at = utc_timestamp()
    score.save()

    return JsonResponse({
        'success': True,
        'total_score': round(score.total_score, 2),
        'item_score': item_score_val,
    })


@login_required
@require_POST
def submit_score(request, station_score_id):
    """Submit final score for a station."""
    data, err = _parse_json_body(request)
    if err:
        return err

    score = get_object_or_404(StationScore, pk=station_score_id)

    if score.examiner_id != request.user.id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    is_correction = score.unlocked_for_correction  # capture before clearing
    old_score = score.total_score                  # capture before recalculation

    score.calculate_total()
    score.global_rating = data.get('global_rating')
    score.comments = data.get('comments', '')
    score.completed_at = utc_timestamp()
    score.status = 'submitted'
    score.unlocked_for_correction = False  # clear any coordinator unlock on re-submit
    score.updated_at = utc_timestamp()
    score.save()

    # Update student status
    student = score.session_student
    completed_count = student.station_scores.filter(status='submitted').count()

    if student.path_id:
        try:
            path = Path.objects.get(pk=student.path_id)
            total_stations = path.station_count
            if completed_count >= total_stations:
                student.status = 'completed'
                student.completed_at = utc_timestamp()
            elif completed_count > 0:
                student.status = 'in_progress'
        except Path.DoesNotExist:
            if completed_count > 0:
                student.status = 'in_progress'
    else:
        if completed_count > 0:
            student.status = 'in_progress'
    student.save()

    if is_correction:
        log_action(request, 'CORRECTION', 'StationScore', str(score.id),
                   f'Corrected score: {old_score} → {score.total_score}/{score.max_score} '
                   f'| Examiner: {request.user.display_name}',
                   extra_data={
                       'examiner': request.user.username,
                       'examiner_display': request.user.display_name,
                       'old_score': old_score,
                       'new_score': score.total_score,
                       'max_score': score.max_score,
                   })
    else:
        log_action(request, 'SUBMIT', 'StationScore', str(score.id),
                   f'Submitted score {score.total_score}/{score.max_score}')

    return JsonResponse({
        'success': True,
        'total_score': round(score.total_score, 2),
        'max_score': round(score.max_score, 2) if score.max_score else 0,
        'percentage': round(score.percentage, 2) if score.percentage else 0,
        'passed_critical': score.passed_critical,
    })


@login_required
@csrf_exempt
@require_POST
def undo_submit(request, station_score_id):
    """Undo a submission (reopen for editing) within 5 min window."""
    score = get_object_or_404(StationScore, pk=station_score_id)

    if score.examiner_id != request.user.id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if score.status != 'submitted':
        return JsonResponse({'error': 'Score is not submitted'}, status=400)

    if score.completed_at:
        elapsed = utc_timestamp() - score.completed_at
        if elapsed > 300:
            return JsonResponse({'error': 'Undo window has expired'}, status=400)

    score.status = 'in_progress'
    score.completed_at = None
    score.updated_at = utc_timestamp()
    score.save()

    log_action(request, 'UPDATE', 'StationScore', str(score.id), 'Undo submit')

    return JsonResponse({'success': True, 'message': 'Score reopened for editing'})


# ── Offline sync endpoints ─────────────────────────────────────────

@login_required
@csrf_exempt
@require_POST
def sync_offline_data(request):
    """Sync offline data from client to server with conflict resolution."""
    data, err = _parse_json_body(request)
    if err:
        return err

    synced = []
    conflicts = []
    errors = []

    # S3: Pre-fetch all examiner assignments for validation
    user_assignment_keys = set(
        ExaminerAssignment.objects.filter(examiner=request.user)
        .values_list('session_id', 'station_id')
    )

    for record in data.get('scores', []):
        local_uuid = record.get('local_uuid')

        # S3: Verify examiner is assigned (check via session_student → session)
        session_student_id = record.get('session_student_id')
        station_id = record.get('station_id')
        if session_student_id and station_id and not request.user.is_staff:
            try:
                student = SessionStudent.objects.get(pk=session_student_id)
                if (str(student.session_id), str(station_id)) not in {
                    (str(s), str(st)) for s, st in user_assignment_keys
                }:
                    errors.append({'local_uuid': local_uuid, 'error': 'Not assigned'})
                    continue
            except SessionStudent.DoesNotExist:
                errors.append({'local_uuid': local_uuid, 'error': 'Student not found'})
                continue

        existing = StationScore.objects.filter(local_uuid=local_uuid).first()

        if existing:
            # Verify ownership
            if existing.examiner_id != request.user.id:
                errors.append({'local_uuid': local_uuid, 'error': 'Unauthorized'})
                continue

            if record.get('local_timestamp', 0) > (existing.local_timestamp or 0):
                existing.total_score = record.get('total_score')
                existing.comments = record.get('comments')
                existing.status = record.get('status')
                existing.local_timestamp = record.get('local_timestamp')
                existing.synced_at = utc_timestamp()
                existing.save()
                synced.append(local_uuid)
            else:
                conflicts.append({
                    'local_uuid': local_uuid,
                    'server_timestamp': existing.local_timestamp,
                    'client_timestamp': record.get('local_timestamp'),
                })
        else:
            score = StationScore(
                session_student_id=record.get('session_student_id'),
                station_id=record.get('station_id'),
                examiner=request.user,
                local_uuid=local_uuid,
                total_score=record.get('total_score'),
                comments=record.get('comments', ''),
                status=record.get('status', 'in_progress'),
                client_id=record.get('client_id', ''),
                local_timestamp=record.get('local_timestamp'),
                synced_at=utc_timestamp(),
                sync_status='synced',
            )
            score.save()
            synced.append(local_uuid)

    log_action(request, 'SYNC', 'StationScore', '',
               f'Synced {len(synced)} scores, {len(conflicts)} conflicts, {len(errors)} rejected')

    return JsonResponse({
        'synced_count': len(synced),
        'synced_uuids': synced,
        'conflicts': conflicts,
        'errors': errors,
        'server_time': utc_timestamp(),
    })


@login_required
@require_GET
def sync_status(request):
    """Check sync status – how many records pending."""
    pending = StationScore.objects.filter(
        examiner=request.user,
        sync_status='local',
    ).count()

    return JsonResponse({
        'pending': pending,
        'server_time': utc_timestamp(),
        'online': True,
    })
