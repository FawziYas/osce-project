"""
Creator API – Student management endpoints.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from core.models import ExamSession, SessionStudent, Path, StationScore


@login_required
@require_POST
def update_student_path_assignment(request, student_id):
    """POST /api/creator/students/<id>/path"""
    student = get_object_or_404(SessionStudent, pk=student_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)
    path_id = data.get('path_id')
    student.path_id = path_id if path_id else None
    student.save()
    return JsonResponse({'success': True, 'path_id': str(student.path_id) if student.path_id else None})


@login_required
def delete_student(request, student_id):
    """DELETE /api/creator/students/<id>"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE required'}, status=405)

    student = get_object_or_404(SessionStudent, pk=student_id)
    session = ExamSession.objects.filter(pk=student.session_id).first()

    if session and session.actual_start:
        return JsonResponse(
            {'error': 'Cannot delete students after session has been activated'},
            status=403,
        )

    # Delete scores first
    StationScore.objects.filter(session_student=student).delete()
    student.delete()
    return JsonResponse({'success': True, 'message': 'Student deleted'})


@login_required
def delete_all_students(request, session_id):
    """DELETE /api/creator/sessions/<id>/students"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'DELETE required'}, status=405)

    session = get_object_or_404(ExamSession, pk=session_id)

    if session.actual_start:
        return JsonResponse(
            {'error': 'Cannot delete students after session has been activated'},
            status=403,
        )

    student_ids = list(
        SessionStudent.objects.filter(session=session).values_list('id', flat=True)
    )
    if student_ids:
        StationScore.objects.filter(session_student_id__in=student_ids).delete()
        SessionStudent.objects.filter(session=session).delete()

    return JsonResponse({'success': True, 'message': f'Deleted {len(student_ids)} students'})


@login_required
@require_POST
def redistribute_students(request, session_id):
    """POST /api/creator/sessions/<id>/redistribute-students"""
    session = get_object_or_404(ExamSession, pk=session_id)

    if session.actual_start:
        return JsonResponse(
            {'error': 'Cannot redistribute students after session has been activated'},
            status=403,
        )

    paths = list(Path.objects.filter(session=session, is_deleted=False).order_by('name'))
    if not paths:
        return JsonResponse({'error': 'No paths defined for this session'}, status=400)

    students = list(
        SessionStudent.objects.filter(session=session).order_by('student_number')
    )

    for i, student in enumerate(students):
        student.path_id = paths[i % len(paths)].id

    # P7: Bulk update instead of save() per student
    SessionStudent.objects.bulk_update(students, ['path_id'])

    return JsonResponse({
        'success': True,
        'message': f'Distributed {len(students)} students across {len(paths)} paths',
    })


@login_required
@require_POST
def assign_student_to_path(request, session_id, student_id):
    """POST /api/creator/sessions/<id>/students/<id>/assign-path"""
    student = get_object_or_404(
        SessionStudent, pk=student_id, session_id=session_id
    )
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)
    if not data.get('path_id'):
        return JsonResponse({'error': 'path_id is required'}, status=400)

    path = get_object_or_404(Path, pk=data['path_id'])
    if str(path.session_id) != str(session_id):
        return JsonResponse({'error': 'Path does not belong to this session'}, status=400)

    student.path_id = path.id
    student.save()

    return JsonResponse({
        'message': f'Student assigned to Path {path.name}',
        'path_name': path.name,
    })


@login_required
@require_POST
def auto_assign_paths(request, session_id):
    """POST /api/creator/sessions/<id>/auto-assign-paths"""
    session = get_object_or_404(ExamSession, pk=session_id)
    paths = list(Path.objects.filter(session=session, is_deleted=False).order_by('name'))

    if not paths:
        return JsonResponse({'error': 'No paths defined for this session'}, status=400)

    unassigned = list(
        SessionStudent.objects.filter(session=session, path__isnull=True)
    )
    if not unassigned:
        return JsonResponse({'message': 'All students already assigned'})

    assignments = {p.id: 0 for p in paths}
    for i, student in enumerate(unassigned):
        p = paths[i % len(paths)]
        student.path_id = p.id
        student.save()
        assignments[p.id] += 1

    summary = [{'path_name': p.name, 'assigned': assignments[p.id]} for p in paths]
    return JsonResponse({
        'message': f'Assigned {len(unassigned)} students to {len(paths)} paths',
        'distribution': summary,
    })
