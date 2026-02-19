"""
Exam CRUD views – list, wizard, detail, edit, delete/archive/restore.
"""
import json
from datetime import datetime, time

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse

from core.models import (
    Course, Exam, ExamSession, Path, Station, ChecklistItem,
)
from core.utils.naming import generate_path_name


@login_required
def exam_list(request):
    """List all exams with search and pagination."""
    search_query = request.GET.get('search', '').strip()
    exams_qs = Exam.objects.filter(is_deleted=False).select_related('course').order_by('-created_at')
    if search_query:
        exams_qs = exams_qs.filter(
            name__icontains=search_query
        ) | Exam.objects.filter(
            is_deleted=False, course__name__icontains=search_query
        ).select_related('course') | Exam.objects.filter(
            is_deleted=False, department__icontains=search_query
        ).select_related('course')
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
        Exam.objects.filter(is_deleted=True).select_related('course').order_by('-deleted_at')
        if can_see_deleted else []
    )
    return render(request, 'creator/exams/list.html', {
        'exams': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'search_query': search_query,
        'deleted_exams': deleted_exams,
    })


@login_required
def exam_wizard(request):
    """Multi-step exam creation wizard – Exam → Sessions → Paths."""
    courses = Course.objects.filter(active=True).order_by('code')

    if request.method == 'POST':
        # ---------- Exam ----------
        exam = Exam(
            course_id=int(request.POST['course_id']),
            name=request.POST['exam_name'],
            description=request.POST.get('description', ''),
            department=request.POST.get('department', ''),
            status='draft',
        )

        if request.POST.get('exam_date'):
            exam.exam_date = datetime.strptime(request.POST['exam_date'], '%Y-%m-%d').date()
        else:
            messages.error(request, 'Exam date is required')
            return render(request, 'creator/exams/wizard.html', {'courses': courses})

        exam.number_of_stations = 8

        if request.POST.get('station_duration_minutes'):
            exam.station_duration_minutes = int(request.POST['station_duration_minutes'])
        else:
            messages.error(request, 'Station duration is required')
            return render(request, 'creator/exams/wizard.html', {'courses': courses})

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
                for path_num in range(1, number_of_paths + 1):
                    path_name = generate_path_name(path_num)
                    Path.objects.create(
                        session=session,
                        name=path_name,
                        description=f'Path {path_name}',
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

    return render(request, 'creator/exams/wizard.html', {'courses': courses})


@login_required
def exam_create(request):
    """Simple form – redirects to wizard."""
    return redirect('creator:exam_wizard')


@login_required
def exam_detail(request, exam_id):
    """View exam, sessions, and overview stats."""
    exam = get_object_or_404(Exam, pk=exam_id)
    sessions = ExamSession.objects.filter(exam=exam).order_by('session_date')
    stations = Station.objects.filter(exam=exam, active=True)
    total_marks = sum(s.get_max_score() for s in stations) if stations.exists() else 0

    return render(request, 'creator/exams/detail.html', {
        'exam': exam,
        'stations': stations,
        'sessions': sessions,
        'total_marks': total_marks,
    })


@login_required
def exam_edit(request, exam_id):
    """Edit an exam."""
    exam = get_object_or_404(Exam, pk=exam_id)
    courses = Course.objects.filter(active=True).order_by('code')

    if request.method == 'POST':
        exam.course_id = int(request.POST['course_id'])
        exam.name = request.POST['name']
        exam.description = request.POST.get('description', exam.description)
        exam.department = request.POST.get('department', exam.department)
        exam.status = request.POST.get('status', exam.status)

        if request.POST.get('exam_date'):
            new_date = datetime.strptime(request.POST['exam_date'], '%Y-%m-%d').date()
            if exam.exam_date != new_date:
                exam.exam_date = new_date
                updated = ExamSession.objects.filter(exam=exam).update(session_date=new_date)
                messages.info(
                    request,
                    f'Exam date updated to {new_date:%Y-%m-%d}. All {updated} session(s) updated automatically.',
                )

        if request.POST.get('number_of_stations'):
            exam.number_of_stations = int(request.POST['number_of_stations'])

        exam.save()
        messages.success(request, f'Exam "{exam.name}" updated.')
        return redirect('creator:exam_detail', exam_id=str(exam.id))

    return render(request, 'creator/exams/form.html', {'exam': exam, 'courses': courses})


# ---------------------------------------------------------------------------
# Delete / Archive / Restore (return JSON for AJAX)
# ---------------------------------------------------------------------------

@login_required
def exam_delete(request, exam_id):
    """Soft-delete a draft/ready exam."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)
    try:
        exam = get_object_or_404(Exam, pk=exam_id)
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
    """Archive an in-progress or completed exam."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)
    try:
        exam = get_object_or_404(Exam, pk=exam_id)
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
