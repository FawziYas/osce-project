"""
Creator API – Session endpoints (status, activate, deactivate, complete, delete, restore, revert).
"""
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from core.models import (
    ExamSession, SessionStudent, Path, Station, ExaminerAssignment, StationScore, ItemScore,
)
from core.models.mixins import TimestampMixin
from core.utils.roles import scope_queryset
from core.utils.cache_utils import invalidate_session_detail, invalidate_exam_detail

audit_logger = logging.getLogger('osce.audit')


def _scoped_session(user):
    """Return ExamSession queryset scoped to the user's department."""
    return scope_queryset(
        user,
        ExamSession.objects.select_related('exam', 'exam__course', 'exam__course__department'),
        dept_field='exam__course__department',
    )


def _sync_exam_status(exam, session_id):
    """
    Recalculate and save the exam status based on the current statuses of
    all its sessions.  Called after every session status change.

    Rules (in priority order):
      1. Any session is in_progress OR finished → exam = in_progress
         (finished sessions wait for the exam-level Complete action)
      2. All active sessions are completed (≥1 exists) → exam = completed
      3. Any session is scheduled    → exam = ready
      4. No active sessions          → exam = draft (or leave draft)

    Never changes an archived exam.
    """
    if exam.status == 'archived':
        return

    sessions = ExamSession.objects.filter(exam=exam)
    active = sessions.exclude(status__in=['archived', 'cancelled'])

    statuses = set(active.values_list('status', flat=True))

    if 'in_progress' in statuses:
        new_status = 'in_progress'
    elif statuses and statuses <= {'completed'}:
        # All active sessions are completed
        new_status = 'completed'
    elif 'scheduled' in statuses:
        new_status = 'ready'
    else:
        # No active sessions at all
        new_status = 'draft'

    if exam.status != new_status:
        exam.status = new_status
        exam.save(update_fields=['status'])

    invalidate_session_detail(session_id)
    invalidate_exam_detail(str(exam.id))


@login_required
@require_GET
def get_session_status(request, session_id):
    """GET /api/creator/sessions/<id>/status"""
    session = get_object_or_404(_scoped_session(request.user), pk=session_id)
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
    with transaction.atomic():
        session = get_object_or_404(
            _scoped_session(request.user).select_for_update(of=('self',)), pk=session_id
        )
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
        _sync_exam_status(session.exam, session_id)

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
    with transaction.atomic():
        session = get_object_or_404(
            _scoped_session(request.user).select_for_update(of=('self',)), pk=session_id
        )
        if session.status in ('completed', 'finished'):
            return JsonResponse(
                {'error': f'Cannot deactivate a {session.status} session'},
                status=400,
            )

        session.status = 'scheduled'
        session.save()
        _sync_exam_status(session.exam, session_id)
        return JsonResponse({'message': 'Session deactivated', 'status': 'scheduled'})


@login_required
@require_POST
def finish_session(request, session_id):
    """POST /api/creator/sessions/<id>/finish

    Mark an in-progress session as finished.  Finished sessions are waiting
    for the exam-level Complete action; they can be reverted to scheduled by
    users with can_revert_session permission (or superusers).
    """
    with transaction.atomic():
        session = get_object_or_404(
            _scoped_session(request.user).select_for_update(of=('self',)), pk=session_id
        )
        if session.status != 'in_progress':
            return JsonResponse(
                {'error': f'Cannot finish: session status is "{session.status}", not "in_progress".'},
                status=400,
            )
        session.status = 'finished'
        session.actual_end = TimestampMixin.utc_timestamp()
        session.save()
        # Finishing a session is a local action – exam status is unchanged.
        # Use the exam-level "Complete Exam" action to finalize the whole exam.
        invalidate_session_detail(session_id)
        invalidate_exam_detail(str(session.exam_id))
        return JsonResponse({'message': 'Session finished', 'status': 'finished'})


@login_required
@require_POST
def complete_session(request, session_id):
    """POST /api/creator/sessions/<id>/complete

    Internal endpoint – normally called via the exam-level complete action.
    Marks the session as officially completed.
    """
    with transaction.atomic():
        session = get_object_or_404(
            _scoped_session(request.user).select_for_update(of=('self',)), pk=session_id
        )

        # Block if this session has dry stations with ungraded essay items
        total = ItemScore.objects.filter(
            checklist_item__rubric_type='essay',
            station_score__session_student__session=session,
            station_score__station__is_dry=True,
        ).count()
        graded = ItemScore.objects.filter(
            checklist_item__rubric_type='essay',
            station_score__session_student__session=session,
            station_score__station__is_dry=True,
            marked_at__isnull=False,
        ).count()

        if total > 0 and graded < total:
            pending = total - graded
            return JsonResponse(
                {
                    'error': (
                        f'Cannot complete session: {pending} of {total} dry essay '
                        f'answer(s) have not been graded yet. '
                        f'Please finish dry grading before completing this session.'
                    ),
                    'pending': pending,
                    'total': total,
                    'graded': graded,
                },
                status=400,
            )

        session.status = 'completed'
        session.save()
        _sync_exam_status(session.exam, session_id)
        return JsonResponse({'message': 'Session completed', 'status': 'completed'})


@login_required
@require_POST
def delete_session_api(request, session_id):
    """DELETE (POST) /api/creator/sessions/<id>/delete
    
    Only superusers or users with core.can_delete_session permission can delete/archive sessions.
    """
    # Permission check: only superuser or users with core.can_delete_session permission
    if not (request.user.is_superuser or request.user.has_perm('core.can_delete_session')):
        return JsonResponse(
            {'error': 'You do not have permission to delete sessions.'},
            status=403,
        )
    
    session = get_object_or_404(_scoped_session(request.user), pk=session_id)
    exam_id = session.exam_id

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
    _sync_exam_status(session.exam, session_id)
    return JsonResponse({'message': f"Session '{session.name}' archived"})


@login_required
@require_POST
def hard_delete_session_api(request, session_id):
    """POST /api/creator/sessions/<id>/hard-delete

    Permanently removes the session and all related data from the database.
    SUPERUSER ONLY – this action is irreversible.
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {'error': 'Only superusers can permanently delete sessions.'},
            status=403,
        )

    session = get_object_or_404(_scoped_session(request.user), pk=session_id)
    name = session.name
    exam_id = session.exam_id

    audit_logger.warning(
        'SESSION_HARD_DELETE | admin=%s | session_id=%s | session_name=%s',
        request.user.username,
        session.id,
        name,
    )

    session.delete()
    invalidate_session_detail(session_id)
    invalidate_exam_detail(str(exam_id))
    return JsonResponse({'message': f"Session '{name}' permanently deleted."})


@login_required
@require_POST
def restore_session_api(request, session_id):
    """POST /api/creator/sessions/<id>/restore
    
    Only superusers or users with core.can_delete_session permission can restore archived sessions.
    """
    # Permission check: same as delete - can restore if can delete
    if not (request.user.is_superuser or request.user.has_perm('core.can_delete_session')):
        return JsonResponse(
            {'error': 'You do not have permission to restore sessions.'},
            status=403,
        )
    
    session = get_object_or_404(_scoped_session(request.user), pk=session_id)
    if session.status != 'archived':
        return JsonResponse({'error': 'Session is not archived'}, status=400)

    session.status = 'completed'
    session.save()
    _sync_exam_status(session.exam, session_id)
    return JsonResponse({'message': f"Session '{session.name}' restored"})


@login_required
@require_POST
def revert_session_to_scheduled(request, session_id):
    """
    POST /api/creator/sessions/<id>/revert-to-scheduled

    Revert a finished or completed session back to scheduled.

    - "finished" → "scheduled": superuser or users with can_revert_session permission
    - "completed" → "scheduled": superuser or staff (admin) only
    """
    with transaction.atomic():
        session = get_object_or_404(
            _scoped_session(request.user).select_for_update(of=('self',)), pk=session_id
        )
        previous_status = session.status

        if previous_status == 'finished':
            if not (request.user.is_superuser or request.user.has_perm('core.can_revert_session')):
                return JsonResponse(
                    {'error': 'You do not have permission to revert finished sessions.'},
                    status=403,
                )
        elif previous_status == 'completed':
            # Completed sessions are locked – only superuser/admin can revert
            if not (request.user.is_superuser or request.user.is_staff):
                return JsonResponse(
                    {'error': 'Only admin users can revert a completed session.'},
                    status=403,
                )
        else:
            return JsonResponse(
                {'error': f'Cannot revert: session status is "{previous_status}", not "finished" or "completed".'},
                status=400,
            )

        session.status = 'scheduled'
        session.save(update_fields=['status', 'updated_at'])
        _sync_exam_status(session.exam, session_id)

    # Extract client IP
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        ip_address = x_forwarded.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')

    # Audit log
    audit_logger.info(
        'SESSION_REVERT | admin=%s | session_id=%s | '
        'previous_status=%s | new_status=scheduled | ip=%s',
        request.user.username,
        session.id,
        previous_status,
        ip_address,
    )

    return JsonResponse({
        'message': f'Session "{session.name}" reverted from {previous_status} to scheduled.',
        'status': 'scheduled',
    })
