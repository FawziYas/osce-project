"""
Exam CRUD views – list, wizard, detail, edit, delete/archive/restore.
"""
import json
import logging
import traceback
from datetime import datetime, time

from django.core.cache import cache
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Exists, OuterRef

from core.models import (
    Course, Exam, ExamSession, Path, Station, ChecklistItem,
    SessionStudent, Department,
)
from core.utils.naming import generate_path_name
from core.utils.roles import (
    scope_queryset, check_exam_department, is_global, is_coordinator,
    get_user_department,
)
from core.utils.sanitize import strip_html


def _can_delete_exam(user):
    """Return True if the user may soft-delete or archive an exam.
    Allowed: Superuser, Admin, Coordinator-Head.
    """
    if user.is_superuser:
        return True
    role = getattr(user, 'role', None)
    if role == 'admin':
        return True
    if role == 'coordinator' and getattr(user, 'coordinator_position', None) == 'head':
        return True
    return False


@login_required
def exam_list(request):
    """List exams — scoped to user's department for coordinators."""
    search_query = request.GET.get('search', '').strip()
    exams_qs = Exam.objects.filter(is_deleted=False).select_related('course', 'course__department').order_by('-created_at')
    # Department scoping
    exams_qs = scope_queryset(request.user, exams_qs, dept_field='course__department')

    if search_query:
        exams_qs = exams_qs.filter(
            name__icontains=search_query
        ) | exams_qs.filter(
            course__name__icontains=search_query
        ) | exams_qs.filter(
            department__icontains=search_query
        )
        exams_qs = exams_qs.order_by('-created_at').distinct()

    page_num = request.GET.get('page', 1)
    paginator = Paginator(exams_qs, per_page=20)
    try:
        page_obj = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    # Deleted exams visible to superuser and admin only
    can_see_deleted = request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'
    deleted_exams = (
        Exam.objects.filter(is_deleted=True).select_related('course', 'course__department').order_by('-deleted_at')
        if can_see_deleted else []
    )
    return render(request, 'creator/exams/list.html', {
        'exams': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'search_query': search_query,
        'deleted_exams': deleted_exams,
        'can_delete_exam': _can_delete_exam(request.user),
    })


@login_required
def exam_wizard(request):
    """Multi-step exam creation wizard — dept-scoped."""
    user = request.user
    user_dept = get_user_department(user)

    # Scope courses and departments to user's department
    courses = scope_queryset(user, Course.objects.all(), dept_field='department').order_by('code')
    if user_dept:
        departments = Department.objects.filter(pk=user_dept.pk)
    else:
        departments = Department.objects.order_by('name')

    if request.method == 'POST':
      try:
       with transaction.atomic():
        # ---------- Exam ----------
        exam = Exam(
            course_id=int(request.POST['course_id']),
            name=strip_html(request.POST['exam_name']),
            description=strip_html(request.POST.get('description', '')),
            department=strip_html(request.POST.get('department', '')),
            status='draft',
        )

        if request.POST.get('exam_date'):
            exam.exam_date = datetime.strptime(request.POST['exam_date'], '%Y-%m-%d').date()
        else:
            messages.error(request, 'Exam date is required')
            return render(request, 'creator/exams/wizard.html', {'courses': courses, 'departments': departments})

        exam.number_of_stations = 8

        if request.POST.get('station_duration_minutes'):
            exam.station_duration_minutes = int(request.POST['station_duration_minutes'])
        else:
            messages.error(request, 'Station duration is required')
            return render(request, 'creator/exams/wizard.html', {'courses': courses, 'departments': departments})

        if request.POST.get('exam_weight'):
            exam.exam_weight = request.POST['exam_weight']
        else:
            messages.error(request, 'Exam weight is required.')
            return render(request, 'creator/exams/wizard.html', {'courses': courses, 'departments': departments})

        exam.save()

        # ---------- Sessions ----------
        session_count = 1
        while True:
            session_type = request.POST.get(f'session_type_{session_count}')
            if not session_type:
                break

            start_time_str = request.POST.get(f'session_start_time_{session_count}')
            number_of_paths = 3

            start_time_val = None
            if start_time_str:
                try:
                    start_time_val = datetime.strptime(start_time_str, '%H:%M').time()
                except ValueError:
                    start_time_val = None

            if not start_time_val:
                if session_type == 'morning':
                    start_time_val = time(8, 0)
                elif session_type == 'afternoon':
                    start_time_val = time(12, 30)
                else:
                    start_time_val = time(8, 0)

            session_type_name = {
                'morning': 'Morning Session',
                'afternoon': 'Afternoon Session',
                'all_day': 'All Day Session',
            }.get(session_type, 'Custom Session')

            course_code = exam.course.short_code or exam.course.code if exam.course else 'EXAM'
            session_name = f'{session_type_name} - {course_code} - {exam.exam_date.strftime("%b %d, %Y")}'

            if ExamSession.objects.filter(exam=exam, name=session_name).exists():
                session_count += 1
                continue

            session = ExamSession(
                exam=exam,
                name=session_name,
                session_date=exam.exam_date,
                session_type=session_type,
                start_time=start_time_val,
                number_of_stations=exam.number_of_stations,
                number_of_paths=number_of_paths,
                status='scheduled',
            )
            session.save()

            if not Path.objects.filter(session=session, is_deleted=False).exists():
                for path_num in range(number_of_paths):
                    path_name = generate_path_name(path_num)
                    Path.objects.create(
                        session=session,
                        name=path_name,
                        rotation_minutes=exam.station_duration_minutes,
                        is_active=True,
                    )

            session_count += 1

        total_sessions = session_count - 1
        messages.success(
            request,
            f'Exam "{exam.name}" created with {total_sessions} session(s). Now add stations to each path.',
        )
        return redirect('creator:exam_detail', exam_id=str(exam.id))
      except Exception as e:
        logger = logging.getLogger('django.request')
        tb = traceback.format_exc()
        logger.error(
            'exam_wizard POST error for user=%s: %s\n%s',
            request.user, e, tb,
        )
        # Temporary: return error details for remote debugging
        from django.http import HttpResponse
        return HttpResponse(
            f"ERROR: {type(e).__name__}: {e}\n\nTRACEBACK:\n{tb}",
            content_type='text/plain', status=500,
        )

    return render(request, 'creator/exams/wizard.html', {'courses': courses, 'departments': departments})


@login_required
def exam_create(request):
    """Simple form – redirects to wizard."""
    return redirect('creator:exam_wizard')


@login_required
def exam_detail(request, exam_id):
    """View exam, sessions, and overview stats — dept-scoped."""
    exam = get_object_or_404(Exam, pk=exam_id)
    if not check_exam_department(request.user, exam):
        return HttpResponseForbidden('You do not have access to this exam.')

    cache_key = f'exam_detail_{exam_id}'
    cached = cache.get(cache_key)
    if cached:
        sessions, stations, total_students = cached['sessions'], cached['stations'], cached['total_students']
    else:
        dry_station_exists_subquery = Station.objects.filter(
            path__session_id=OuterRef('pk'),
            active=True,
            is_dry=True,
        )
        sessions = list(ExamSession.objects.filter(exam=exam).annotate(
            has_dry_stations=Exists(dry_station_exists_subquery)
        ).order_by('session_date', 'start_time'))
        stations = list(Station.objects.filter(exam=exam, active=True))
        total_students = SessionStudent.objects.filter(
            session__exam=exam
        ).count()
        cache.set(cache_key, {'sessions': sessions, 'stations': stations, 'total_students': total_students}, timeout=600)

    can_delete_sessions = request.user.is_superuser or request.user.has_perm('core.can_delete_session')
    has_dry_stations = any(s.is_dry for s in stations)

    u = request.user
    _role = getattr(u, 'role', None)
    _coord_pos = getattr(u, 'coordinator_position', None)
    can_dry_grade = (
        u.is_superuser
        or _role == 'admin'
        or (_role == 'coordinator' and _coord_pos in ('head', 'organizer'))
        or u.has_perm('core.can_open_dry_grading')
    )

    can_complete_exam = (
        u.is_superuser
        or _role == 'admin'
        or (_role == 'coordinator' and _coord_pos in ('head', 'organizer'))
    )

    active_sessions = [s for s in sessions if s.status not in ('archived', 'cancelled')]
    all_sessions_finished = bool(active_sessions) and all(
        s.status == 'finished' for s in active_sessions
    )

    return render(request, 'creator/exams/detail.html', {
        'exam': exam,
        'stations': stations,
        'sessions': sessions,
        'total_students': total_students,
        'can_delete_sessions': can_delete_sessions,
        'can_delete_exam': _can_delete_exam(request.user),
        'can_complete_exam': can_complete_exam,
        'all_sessions_finished': all_sessions_finished,
        'has_dry_stations': has_dry_stations,
        'can_dry_grade': can_dry_grade,
    })


@login_required
def exam_edit(request, exam_id):
    """Edit an exam — dept-scoped."""
    exam = get_object_or_404(Exam, pk=exam_id)
    if not check_exam_department(request.user, exam):
        return HttpResponseForbidden('You do not have access to this exam.')

    user_dept = get_user_department(request.user)
    courses = scope_queryset(request.user, Course.objects.all(), dept_field='department').order_by('code')
    if user_dept:
        departments = Department.objects.filter(pk=user_dept.pk)
    else:
        departments = Department.objects.order_by('name')

    # Check if any sessions are active or completed (date lock)
    active_or_completed_sessions = ExamSession.objects.filter(
        exam=exam, status__in=['in_progress', 'completed']
    ).exists()

    if request.method == 'POST':
        exam.course_id = int(request.POST['course_id'])
        exam.name = strip_html(request.POST['name'])
        exam.description = strip_html(request.POST.get('description', exam.description))
        exam.department = strip_html(request.POST.get('department', exam.department))
        # Status is auto-derived from sessions — do NOT accept manual override from the form

        if request.POST.get('exam_date'):
            new_date = datetime.strptime(request.POST['exam_date'], '%Y-%m-%d').date()
            if exam.exam_date != new_date:
                # Prevent date change if sessions are in progress or completed
                if active_or_completed_sessions:
                    messages.error(
                        request,
                        'Cannot change the exam date while sessions are in progress or completed. '
                        'Complete or revert all active sessions first.'
                    )
                else:
                    exam.exam_date = new_date
                    updated = ExamSession.objects.filter(exam=exam).update(session_date=new_date)
                    messages.info(
                        request,
                        f'Exam date updated to {new_date:%Y-%m-%d}. All {updated} session(s) updated automatically.',
                    )

        if request.POST.get('number_of_stations'):
            exam.number_of_stations = int(request.POST['number_of_stations'])

        if request.POST.get('exam_weight'):
            exam.exam_weight = request.POST['exam_weight']
        else:
            messages.error(request, 'Exam weight is required.')
            return render(request, 'creator/exams/form.html', {
                'exam': exam,
                'courses': courses,
                'departments': departments,
                'date_field_disabled': active_or_completed_sessions,
            })

        exam.save()
        messages.success(request, f'Exam "{exam.name}" updated.')
        return redirect('creator:exam_detail', exam_id=str(exam.id))

    return render(request, 'creator/exams/form.html', {
        'exam': exam,
        'courses': courses,
        'departments': departments,
        'date_field_disabled': active_or_completed_sessions,
    })


# ---------------------------------------------------------------------------
# Delete / Archive / Restore (return JSON for AJAX)
# ---------------------------------------------------------------------------

@login_required
def exam_delete(request, exam_id):
    """Soft-delete a draft/ready exam. Superuser, Admin, and Coordinator-Head only.
    Also enforces department scope."""
    if not _can_delete_exam(request.user):
        return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)
    try:
        exam = get_object_or_404(Exam, pk=exam_id)
        if not check_exam_department(request.user, exam):
            return JsonResponse({'success': False, 'message': 'You do not have access to this exam.'}, status=403)
        if exam.status not in ('draft', 'ready'):
            return JsonResponse({
                'success': False,
                'message': f"Cannot delete exam in '{exam.status}' status. Only draft or ready exams can be deleted.",
            }, status=400)

        exam.soft_delete(request.user.id)
        return JsonResponse({'success': True, 'message': f"Exam '{exam.name}' has been deleted successfully."})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {e}'}, status=500)


@login_required
def exam_archive(request, exam_id):
    """Archive an in-progress or completed exam. Superuser, Admin, and Coordinator-Head only.
    Also enforces department scope."""
    if not _can_delete_exam(request.user):
        return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)
    try:
        exam = get_object_or_404(Exam, pk=exam_id)
        if not check_exam_department(request.user, exam):
            return JsonResponse({'success': False, 'message': 'You do not have access to this exam.'}, status=403)
        if exam.status not in ('in_progress', 'completed'):
            return JsonResponse({
                'success': False,
                'message': f"Cannot archive exam in '{exam.status}' status.",
            }, status=400)

        exam.soft_delete(request.user.id)
        return JsonResponse({'success': True, 'message': f"Exam '{exam.name}' has been archived successfully."})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {e}'}, status=500)


@login_required
def exam_restore(request, exam_id):
    """Restore a soft-deleted exam. Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)
    try:
        exam = get_object_or_404(Exam, pk=exam_id)
        exam.restore()
        msg = f"Exam '{exam.name}' has been restored."

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'success': True, 'message': msg})

        messages.success(request, msg)
        return redirect('creator:exam_detail', exam_id=str(exam.id))
    except Exception as e:
        err = f'Error: {e}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': err}, status=500)
        messages.error(request, err)
        return redirect('creator:exam_list')


@login_required
def exam_permanent_delete(request, exam_id):
    """Permanently delete a soft-deleted exam. Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        return JsonResponse({'success': False, 'message': 'Permission denied.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)
    try:
        exam = get_object_or_404(Exam, pk=exam_id)
        if not exam.is_deleted:
            return JsonResponse({
                'success': False,
                'message': 'Only deleted exams can be permanently removed.',
            }, status=400)

        exam_name = exam.name
        # Django CASCADE delete handles related objects automatically
        exam.delete()

        return JsonResponse({'success': True, 'message': f"Exam '{exam_name}' has been permanently deleted."})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {e}'}, status=500)
