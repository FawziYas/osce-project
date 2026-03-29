"""
Examiner API views – JSON endpoints for the tablet interface.
Designed for offline-first operation with sync support.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from core.models import (
    SessionStudent, Station, ChecklistItem, ExaminerAssignment,
    StationScore, ItemScore, Path,
)
from core.models.mixins import TimestampMixin
from core.utils.audit import log_action, AuditLogService


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
    if not has_assignment and not request.user.is_superuser:
        return JsonResponse({'error': 'Not found'}, status=404)

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
    """Get station info and all checklist items for marking.
    Verifies the examiner is assigned to a session containing this station."""
    station = get_object_or_404(Station, pk=station_id)

    # Verify examiner has an assignment to this station (or is staff/superuser)
    if not request.user.is_staff and not request.user.is_superuser:
        has_assignment = ExaminerAssignment.objects.filter(
            station=station,
            examiner=request.user,
        ).exists()
        if not has_assignment:
            return JsonResponse({'error': 'Not assigned to this station'}, status=403)

    items = ChecklistItem.objects.filter(
        station_id=station_id,
    ).select_related('ilo', 'ilo__theme').order_by('item_number')

    def build_item_response(item):
        try:
            image_url = request.build_absolute_uri(item.image.url) if item.image and item.image.name else None
        except Exception:
            image_url = None
        response = {
            'id': item.id,
            'item_number': item.item_number,
            'description': item.description,
            'points': item.points,
            'category': item.category or 'General',
            'expected_response': item.expected_response,
            'rubric_type': item.rubric_type or 'binary',
            'rubric_levels': None,
            'ilo_name': item.ilo.theme_name if item.ilo else None,
            'ilo_number': item.ilo.number if item.ilo else None,
            'image_url': image_url,
        }

        # Parse rubric levels
        if item.rubric_levels:
            if isinstance(item.rubric_levels, (list, dict)):
                # JSONField already deserialized to Python object
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
    if not has_assignment and not request.user.is_superuser:
        return JsonResponse({'error': 'Not found'}, status=404)

    # S7: Verify session is active
    session = student.session
    if hasattr(session, 'status') and session.status not in ('in_progress', 'active'):
        return JsonResponse({'error': 'Session is not active'}, status=400)

    with transaction.atomic():
        existing = StationScore.objects.select_for_update().filter(
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

        try:
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
        except IntegrityError:
            # Race condition: another request created the score between check and save
            existing = StationScore.objects.filter(
                session_student_id=session_student_id,
                station_id=station_id,
                examiner=request.user,
            ).first()
            if existing:
                return JsonResponse({
                    'id': str(existing.id),
                    'local_uuid': str(existing.local_uuid),
                    'status': existing.status,
                    'total_score': existing.total_score,
                    'message': 'Resuming existing marking session',
                })
            return JsonResponse({'error': 'Failed to create score'}, status=500)

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

    score = get_object_or_404(
        StationScore.objects.select_related('station'),
        pk=station_score_id,
    )

    if score.examiner_id != request.user.id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    checklist_item_id = data.get('checklist_item_id')
    item_score_val = data.get('score', 0)
    notes = data.get('notes', '')

    # For essay items on dry stations, marked_at must NOT be set here.
    # It is only set by the coordinator in the dry grading view after review.
    checklist_item = get_object_or_404(ChecklistItem, pk=checklist_item_id, station=score.station)

    # Validate score bounds (0 ≤ score ≤ max allowed points)
    try:
        item_score_val = float(item_score_val)
    except (TypeError, ValueError):
        item_score_val = 0
    max_points = checklist_item.points or 1
    item_score_val = max(0, min(item_score_val, max_points))
    is_dry_essay = (
        score.station is not None
        and score.station.is_dry
        and checklist_item.rubric_type == 'essay'
    )

    defaults = {
        'score': item_score_val,
        'notes': notes,
        'max_points': max_points,
    }
    if not is_dry_essay:
        defaults['marked_at'] = utc_timestamp()

    _item, _created = ItemScore.objects.update_or_create(
        station_score_id=station_score_id,
        checklist_item_id=checklist_item_id,
        defaults=defaults,
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
@csrf_exempt
@require_POST
def batch_mark_items(request, station_score_id):
    """Batch-mark multiple checklist items in one request.

    Accepts JSON body:
        {"items": [{"checklist_item_id": 1, "score": 2.0, "notes": "", "max_points": 2}, ...]}

    Uses bulk_create with update_conflicts for optimal DB performance:
    one INSERT … ON CONFLICT UPDATE instead of N separate queries.
    """
    data, err = _parse_json_body(request)
    if err:
        return err

    items = data.get('items')
    if not items or not isinstance(items, list):
        return JsonResponse({'error': 'Missing or invalid "items" array'}, status=400)

    score = get_object_or_404(
        StationScore.objects.select_related('station'),
        pk=station_score_id,
    )

    if score.examiner_id != request.user.id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    is_dry_station = score.station is not None and score.station.is_dry

    # Pre-fetch rubric types for all checklist items in one query
    item_ids = [i['checklist_item_id'] for i in items if 'checklist_item_id' in i]

    # Validate all checklist items belong to this station
    if item_ids:
        valid_items = {
            ci.pk: ci.points
            for ci in ChecklistItem.objects.filter(pk__in=item_ids, station=score.station)
        }
        invalid = set(item_ids) - set(valid_items.keys())
        if invalid:
            return JsonResponse({'error': 'Checklist items do not belong to this station'}, status=400)
    else:
        valid_items = {}

    essay_item_ids = set()
    if is_dry_station and item_ids:
        essay_item_ids = set(
            ChecklistItem.objects.filter(
                pk__in=item_ids, rubric_type='essay'
            ).values_list('pk', flat=True)
        )

    now = utc_timestamp()
    item_scores = []
    for item in items:
        if 'checklist_item_id' not in item:
            continue
        cid = item['checklist_item_id']
        # Validate score bounds using server-side max points
        ci_max_points = valid_items.get(cid, 1)
        try:
            item_score_val = float(item.get('score', 0))
        except (TypeError, ValueError):
            item_score_val = 0
        item_score_val = max(0, min(item_score_val, ci_max_points))
        # Don't set marked_at for dry essay items — coordinator grades them later
        is_dry_essay = is_dry_station and cid in essay_item_ids
        item_scores.append(ItemScore(
            station_score_id=station_score_id,
            checklist_item_id=cid,
            score=item_score_val,
            notes=item.get('notes', ''),
            max_points=ci_max_points,
            marked_at=None if is_dry_essay else now,
        ))

    if not item_scores:
        return JsonResponse({'error': 'No valid items provided'}, status=400)

    # Split into two bulk operations: dry-essay items must NOT update marked_at
    non_essay = [s for s in item_scores if s.marked_at is not None]
    dry_essays = [s for s in item_scores if s.marked_at is None]

    if non_essay:
        ItemScore.objects.bulk_create(
            non_essay,
            update_conflicts=True,
            unique_fields=['station_score', 'checklist_item'],
            update_fields=['score', 'notes', 'max_points', 'marked_at'],
        )
    if dry_essays:
        ItemScore.objects.bulk_create(
            dry_essays,
            update_conflicts=True,
            unique_fields=['station_score', 'checklist_item'],
            update_fields=['score', 'notes', 'max_points'],  # marked_at intentionally excluded
        )

    score.calculate_total()
    score.updated_at = now
    score.save()

    return JsonResponse({
        'success': True,
        'items_saved': len(item_scores),
        'total_score': round(score.total_score, 2),
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

    if student.path_id:
        try:
            path = Path.objects.get(pk=student.path_id)
            # Count distinct stations (active & not deleted) in the student's path
            total_stations = path.stations.filter(active=True, is_deleted=False).count()
            # Count distinct path stations that have at least one submitted score
            completed_station_count = (
                student.station_scores
                .filter(
                    status='submitted',
                    station__path_id=student.path_id,
                    station__active=True,
                    station__is_deleted=False,
                )
                .values('station_id')
                .distinct()
                .count()
            )
            if total_stations > 0 and completed_station_count >= total_stations:
                student.status = 'completed'
                student.completed_at = utc_timestamp()
            elif completed_station_count > 0:
                student.status = 'in_progress'
        except Path.DoesNotExist:
            # Path gone – fall back to raw submitted count
            fallback = student.station_scores.filter(status='submitted').values('station_id').distinct().count()
            if fallback > 0:
                student.status = 'in_progress'
    else:
        # No path assigned – just track progress
        fallback = student.station_scores.filter(status='submitted').values('station_id').distinct().count()
        if fallback > 0:
            student.status = 'in_progress'
    student.save()

    if is_correction:
        from core.models.audit import SCORE_AMENDED
        AuditLogService.log(
            action=SCORE_AMENDED,
            user=request.user,
            request=request,
            resource=score,
            old_value={'total_score': old_score},
            new_value={'total_score': score.total_score, 'max_score': score.max_score},
            description=(
                f'Corrected score: {old_score} → {score.total_score}/{score.max_score} '
                f'| Examiner: {request.user.display_name}'
            ),
            extra={
                'examiner': request.user.username,
                'examiner_display': request.user.display_name,
                'old_score': old_score,
                'new_score': score.total_score,
                'max_score': score.max_score,
            },
        )
    else:
        from core.models.audit import SCORE_SUBMITTED
        AuditLogService.log(
            action=SCORE_SUBMITTED,
            user=request.user,
            request=request,
            resource=score,
            new_value={'total_score': score.total_score, 'max_score': score.max_score},
            description=f'Submitted score {score.total_score}/{score.max_score}',
        )

    return JsonResponse({
        'success': True,
        'total_score': round(score.total_score, 2),
        'max_score': round(score.max_score, 2) if score.max_score else 0,
        'percentage': round(score.percentage, 2) if score.percentage else 0,
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

    from core.models.audit import SCORE_UPDATED
    AuditLogService.log(
        action=SCORE_UPDATED,
        user=request.user,
        request=request,
        resource=score,
        old_value={'status': 'submitted'},
        new_value={'status': 'in_progress'},
        description='Undo submit — score reopened for editing',
    )

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
        if session_student_id and station_id and not request.user.is_superuser:
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


# ── Dry exam verification endpoints ───────────────────────────────

@login_required
@require_POST
def verify_student_registration(request):
    """Verify student registration number before starting dry exam."""
    data, err = _parse_json_body(request)
    if err:
        return err

    student_number = (data.get('student_number') or '').strip().upper()
    student_id = data.get('student_id')
    session_id = data.get('session_id')
    assignment_id = data.get('assignment_id')

    if not student_number or not student_id or not session_id or not assignment_id:
        return JsonResponse({
            'valid': False,
            'error': 'missing_fields',
            'message': 'Student number, student ID, session ID, and assignment ID are required.',
        }, status=400)

    from core.models.audit import EXAM_START_VERIFICATION_ATTEMPT, EXAM_START_VERIFICATION_SUCCESS, STATUS_FAILED
    AuditLogService.log(
        action=EXAM_START_VERIFICATION_ATTEMPT,
        user=request.user,
        request=request,
        resource_type='SessionStudent',
        resource_id=str(student_id),
        description=f'Verification attempt for student {student_number}',
        extra={'session_id': str(session_id), 'assignment_id': str(assignment_id)},
    )

    student = SessionStudent.objects.filter(
        pk=student_id,
        session_id=session_id,
    ).first()

    if not student:
        return JsonResponse({
            'valid': False,
            'error': 'student_not_found',
            'message': 'Student not found in this session.',
        }, status=404)

    if student.student_number.upper() != student_number:
        return JsonResponse({
            'valid': False,
            'error': 'registration_not_found',
            'message': 'ID number does not match this student record.',
        })

    # Store authorization in server-side session — no token in URL
    session_key = f'dry_auth_{assignment_id}_{student_id}'
    expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=4)
    request.session[session_key] = {
        'user_id': request.user.id,
        'student_id': str(student_id),
        'assignment_id': str(assignment_id),
        'expires_at': expires_at.isoformat(),
    }
    request.session.modified = True

    redirect_url = reverse(
        'examiner:dry_marking',
        kwargs={'assignment_id': assignment_id, 'student_id': student_id},
    )

    AuditLogService.log(
        action=EXAM_START_VERIFICATION_SUCCESS,
        user=request.user,
        request=request,
        resource_type='SessionStudent',
        resource_id=str(student_id),
        description=f'Student {student_number} verified successfully',
        extra={'session_id': str(session_id), 'assignment_id': str(assignment_id)},
    )

    return JsonResponse({
        'valid': True,
        'redirect_url': redirect_url,
    })


@login_required
@require_POST
def verify_master_key(request):
    """Verify examiner password (master key) before starting dry exam."""
    data, err = _parse_json_body(request)
    if err:
        return err

    password = data.get('password', '')
    student_id = data.get('student_id')
    session_id = data.get('session_id')
    assignment_id = data.get('assignment_id')

    if not password or not student_id or not session_id or not assignment_id:
        return JsonResponse({
            'valid': False,
            'error': 'missing_fields',
            'message': 'Password, student ID, session ID, and assignment ID are required.',
        }, status=400)

    from core.models.audit import (
        MASTER_KEY_VERIFICATION_ATTEMPT, MASTER_KEY_VERIFICATION_SUCCESS,
        STATUS_FAILED,
    )
    AuditLogService.log(
        action=MASTER_KEY_VERIFICATION_ATTEMPT,
        user=request.user,
        request=request,
        resource_type='Examiner',
        resource_id=str(request.user.pk),
        description=f'Master key verification attempt by {request.user.username}',
        extra={'session_id': str(session_id), 'assignment_id': str(assignment_id)},
    )

    user = authenticate(
        request=request,
        username=request.user.username,
        password=password,
    )

    if user is None:
        AuditLogService.log(
            action=MASTER_KEY_VERIFICATION_ATTEMPT,
            user=request.user,
            request=request,
            resource_type='Examiner',
            resource_id=str(request.user.pk),
            description=f'Master key verification FAILED for {request.user.username}',
            status=STATUS_FAILED,
            extra={'session_id': str(session_id), 'assignment_id': str(assignment_id)},
        )
        return JsonResponse({
            'valid': False,
            'error': 'invalid_password',
            'message': 'Incorrect password. Please try again.',
        })

    # Store authorization in server-side session — no token in URL
    session_key = f'dry_auth_{assignment_id}_{student_id}'
    expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=4)
    request.session[session_key] = {
        'user_id': request.user.id,
        'student_id': str(student_id),
        'assignment_id': str(assignment_id),
        'expires_at': expires_at.isoformat(),
    }
    request.session.modified = True

    redirect_url = reverse(
        'examiner:dry_marking',
        kwargs={'assignment_id': assignment_id, 'student_id': student_id},
    )

    AuditLogService.log(
        action=MASTER_KEY_VERIFICATION_SUCCESS,
        user=request.user,
        request=request,
        resource_type='Examiner',
        resource_id=str(request.user.pk),
        description=f'Master key verified successfully for {request.user.username}',
        extra={'session_id': str(session_id), 'assignment_id': str(assignment_id)},
    )

    return JsonResponse({
        'valid': True,
        'redirect_url': redirect_url,
    })


# ── Dry Marking PDF Upload ─────────────────────────────────────────────────

@login_required
@require_POST
def save_dry_pdf(request, score_id):
    """
    Receive a screenshot PDF of the dry-marking page (captured client-side
    with html2canvas + jsPDF) and forward it to Telegram.
    """
    import re
    import logging
    log = logging.getLogger(__name__)

    score = get_object_or_404(
        StationScore.objects.select_related(
            'session_student__session__exam',
            'session_student__session',
            'station',
        ),
        pk=score_id,
        examiner=request.user,
    )

    pdf_file = request.FILES.get('pdf_file')
    if not pdf_file:
        return JsonResponse({'success': False, 'error': 'No PDF file received.'}, status=400)

    if pdf_file.size > 50 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'PDF too large (max 50 MB).'}, status=400)

    pdf_bytes = pdf_file.read()

    # Build filename: "Student Name - Exam Name - Session Name.pdf"
    def _safe(s):
        return re.sub(r'[\\/:*?"<>|]+', '_', str(s)).strip()

    student_name = _safe(score.session_student.full_name or 'Unknown')
    try:
        exam_name = _safe(score.session_student.session.exam.name)
    except AttributeError:
        exam_name = 'Exam'
    try:
        session_name = _safe(score.session_student.session.name)
    except AttributeError:
        session_name = 'Session'

    filename = f'{student_name} - {exam_name} - {session_name}.pdf'

    try:
        from examiner.google_drive import upload_pdf
        file_id = upload_pdf(pdf_bytes, filename)
    except Exception as exc:
        log.error('Telegram upload failed: %s', exc, exc_info=True)
        return JsonResponse({'success': False, 'error': f'Upload failed: {exc}'}, status=500)

    return JsonResponse({'success': True, 'file_id': file_id, 'filename': filename})
