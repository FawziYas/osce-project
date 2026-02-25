"""
Session CRUD views – list, create, edit, delete, detail, PDF, assign examiner.
"""
import os
from collections import defaultdict
from datetime import datetime, time
from io import BytesIO

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from core.models.mixins import TimestampMixin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from core.models import (
    Exam, ExamSession, SessionStudent, Path, Station, ChecklistItem,
    Examiner, ExaminerAssignment, StationScore,
)
from core.utils.naming import generate_path_name


@login_required
def live_student_search(request, session_id):
    """AJAX endpoint: real-time student search scoped to a session."""
    session = get_object_or_404(ExamSession, pk=session_id)
    q = request.GET.get('q', '').strip()

    if len(q) < 2:
        return JsonResponse({'results': []})

    qs = (
        SessionStudent.objects.filter(session=session)
        .filter(
            full_name__icontains=q
        ) | SessionStudent.objects.filter(
            session=session, student_number__icontains=q
        )
    ).select_related('path').order_by('student_number').distinct()[:20]

    results = [
        {
            'id': str(s.id),
            'student_number': s.student_number,
            'full_name': s.full_name,
            'status': s.status,
            'path_id': str(s.path_id) if s.path_id else '',
            'path_name': s.path.name if s.path else None,
        }
        for s in qs
    ]
    return JsonResponse({'results': results})


@login_required
def session_list(request, exam_id):
    """List sessions for an exam with search."""
    exam = get_object_or_404(Exam, pk=exam_id)
    search_query = request.GET.get('search', '').strip()
    sessions_qs = ExamSession.objects.filter(exam=exam).order_by('-session_date')
    
    if search_query:
        sessions_qs = sessions_qs.filter(
            name__icontains=search_query
        ) | ExamSession.objects.filter(
            exam=exam, session_date__icontains=search_query
        ).order_by('-session_date')
        sessions_qs = sessions_qs.order_by('-session_date').distinct()
    
    return render(request, 'creator/sessions/list.html', {
        'exam': exam,
        'sessions': sessions_qs,
        'search_query': search_query,
    })


@login_required
def session_create(request, exam_id):
    """Create a new exam session."""
    exam = get_object_or_404(Exam, pk=exam_id)

    if not exam.exam_date:
        messages.warning(request, 'Please set an exam date before creating sessions.')
        return redirect('creator:exam_edit', exam_id=str(exam_id))

    if request.method == 'POST':
        session_name = request.POST.get('name', '').strip()
        if not session_name:
            messages.error(request, 'Session name is required')
            return render(request, 'creator/sessions/form.html', {'exam': exam, 'session': None})

        if ExamSession.objects.filter(exam=exam, name=session_name).exists():
            messages.warning(request, f'A session with the name "{session_name}" already exists.')
            return render(request, 'creator/sessions/form.html', {'exam': exam, 'session': None})

        session_type = request.POST.get('session_type', 'all_day')

        start_time_val = None
        if request.POST.get('start_time'):
            try:
                start_time_val = datetime.strptime(request.POST['start_time'], '%H:%M').time()
            except ValueError:
                start_time_val = time(8, 0)
        else:
            start_time_val = time(8, 0)

        number_of_paths = 3  # Always 3

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

        path_labels = ', '.join(str(i + 1) for i in range(number_of_paths))
        messages.success(request, f'Session "{session.name}" created with {number_of_paths} paths ({path_labels}). Now add stations.')
        return redirect('creator:session_detail', session_id=str(session.id))

    return render(request, 'creator/sessions/form.html', {'exam': exam, 'session': None})


@login_required
def session_edit(request, session_id):
    """Edit a session."""
    session = get_object_or_404(ExamSession, pk=session_id)
    exam = session.exam

    if not exam.exam_date:
        messages.warning(request, 'Please set an exam date first.')
        return redirect('creator:exam_edit', exam_id=str(exam.id))

    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()
        if not new_name:
            messages.error(request, 'Session name is required')
            return render(request, 'creator/sessions/form.html', {'exam': exam, 'session': session})

        if ExamSession.objects.filter(exam=exam, name=new_name).exclude(pk=session.pk).exists():
            messages.warning(request, f'A session with the name "{new_name}" already exists.')
            return render(request, 'creator/sessions/form.html', {'exam': exam, 'session': session})

        session.name = new_name
        session.session_type = request.POST.get('session_type', session.session_type)
        session.session_date = exam.exam_date

        if request.POST.get('start_time'):
            try:
                session.start_time = datetime.strptime(request.POST['start_time'], '%H:%M').time()
            except ValueError:
                pass

        session.notes = request.POST.get('notes', '')
        session.save()
        messages.success(request, f'Session "{session.name}" updated.')
        return redirect('creator:session_detail', session_id=str(session.id))

    return render(request, 'creator/sessions/form.html', {'exam': exam, 'session': session})


@login_required
def session_delete(request, session_id):
    """Cancel a session."""
    session = get_object_or_404(ExamSession, pk=session_id)
    exam_id = str(session.exam_id)
    session_name = session.name

    session.status = 'cancelled'
    session.save()

    messages.success(request, f"Session '{session_name}' has been cancelled.")
    return redirect('creator:exam_detail', exam_id=exam_id)


@login_required
def session_detail(request, session_id):
    """View session details, paths, students."""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    session = get_object_or_404(ExamSession, pk=session_id)
    
    # Search and pagination for students
    search_query = request.GET.get('search', '').strip()
    students_qs = SessionStudent.objects.filter(session=session).order_by('student_number')
    
    if search_query:
        students_qs = students_qs.filter(
            full_name__icontains=search_query
        ) | SessionStudent.objects.filter(
            session=session, student_number__icontains=search_query
        )
        students_qs = students_qs.order_by('student_number').distinct()
    
    # Pagination: 50 students per page
    page_num = request.GET.get('page', 1)
    paginator = Paginator(students_qs, per_page=50)
    try:
        page_obj = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    students = page_obj.object_list
    
    paths = Path.objects.filter(session=session, is_deleted=False).order_by('name')
    examiner_assignments = ExaminerAssignment.objects.filter(session=session).select_related(
        'examiner', 'station'
    )
    all_examiners = Examiner.objects.filter(is_active=True, role='examiner').order_by('full_name')

    # Session metrics
    rotation_display = 'Not set'
    rotation_detail = None

    path_rotations = [(p.name, p.rotation_minutes) for p in paths if p.rotation_minutes]
    if path_rotations:
        rotation_values = {m for _, m in path_rotations if m}
        if rotation_values:
            if len(rotation_values) == 1:
                rotation_display = f'{rotation_values.pop()} minutes'
            else:
                rotation_display = 'Varies by path'
                rotation_detail = ', '.join(
                    f'Path {n}: {m} min' for n, m in path_rotations if m
                )
    elif session.exam and session.exam.station_duration_minutes:
        rotation_display = f'{session.exam.station_duration_minutes} minutes (exam default)'

    total_station_count = sum(p.station_count for p in paths)
    station_detail = None
    if paths.exists():
        station_detail = ', '.join(f'Path {p.name}: {p.station_count}' for p in paths)
    station_display = str(total_station_count)
    if total_station_count == 0 and session.exam and session.exam.number_of_stations:
        station_display = f'{session.exam.number_of_stations} (exam default)'

    session_metrics = {
        'rotation_display': rotation_display,
        'rotation_detail': rotation_detail,
        'station_display': station_display,
        'station_detail': station_detail,
    }

    # Calculate grace period status for each submitted score
    submitted_scores_list = list(StationScore.objects.filter(
        session_student__session=session,
        status='submitted',
    ).select_related('examiner', 'session_student', 'station').order_by(
        'session_student__student_number', 'station__station_number'
    ))
    
    _now = TimestampMixin.utc_timestamp()
    for score in submitted_scores_list:
        score.within_undo_window = (
            score.completed_at is not None
            and (_now - score.completed_at) <= 300
        )

    # Build per-path unassigned station counts in a single query pass
    # Collect station IDs that DO have an assignment for this session
    assigned_station_ids = set(
        ExaminerAssignment.objects.filter(session=session)
        .values_list('station_id', flat=True)
    )

    total_unassigned = 0
    paths = list(paths)   # materialise so we can annotate
    for path in paths:
        unassigned = [
            s for s in path.stations.filter(active=True, is_deleted=False)
            if s.id not in assigned_station_ids
        ]
        path.unassigned_stations = unassigned      # attach to object
        path.unassigned_count = len(unassigned)    # convenience count
        total_unassigned += len(unassigned)

    return render(request, 'creator/sessions/detail.html', {
        'session': session,
        'students': students,
        'page_obj': page_obj,
        'paginator': paginator,
        'search_query': search_query,
        'total_students': students_qs.count(),
        'paths': paths,
        'examiner_assignments': examiner_assignments,
        'all_examiners': all_examiners,
        'session_metrics': session_metrics,
        'submitted_scores': submitted_scores_list,
        'total_unassigned': total_unassigned,
        'can_delete_sessions': request.user.is_superuser or request.user.has_perm('core.can_delete_session'),
    })


@login_required
def download_student_paths_pdf(request, session_id):
    """Download PDF with students grouped by path."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import arabic_reshaper
    from bidi.algorithm import get_display

    def reshape_arabic(text):
        if not text:
            return text
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text

    session = get_object_or_404(ExamSession, pk=session_id)
    students = SessionStudent.objects.filter(session=session).order_by('student_number')
    paths = Path.objects.filter(session=session, is_deleted=False).order_by('name')

    students_by_path = defaultdict(list)
    for s in students:
        key = str(s.path_id) if s.path_id else 'unassigned'
        students_by_path[key].append(s)

    buffer = BytesIO()
    pagesize = landscape(A4)
    doc = SimpleDocTemplate(buffer, pagesize=pagesize,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    elements = []

    # Font setup
    try:
        arial_path = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'arial.ttf')
        if os.path.exists(arial_path):
            pdfmetrics.registerFont(TTFont('Arial', arial_path))
            default_font = 'Arial'
        else:
            default_font = 'Helvetica'
    except Exception:
        default_font = 'Helvetica'

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=14, alignment=TA_CENTER, spaceAfter=15, fontName=default_font,
    )

    elements.append(
        Paragraph(f"Student Path Assignments - {session.name or 'Session'}", title_style)
    )
    elements.append(Spacer(1, 0.15 * inch))

    paths_list = list(paths)
    per_page = 5

    for page_start in range(0, len(paths_list), per_page):
        if page_start > 0:
            elements.append(PageBreak())

        page_paths = paths_list[page_start:page_start + per_page]
        header_row = [f'Path {p.name}' for p in page_paths]
        data = [header_row]

        max_students = max(
            (len(students_by_path.get(str(p.id), [])) for p in page_paths), default=0
        )

        for i in range(max_students):
            row = []
            for p in page_paths:
                ps = students_by_path.get(str(p.id), [])
                if i < len(ps):
                    row.append(reshape_arabic(ps[i].full_name))
                else:
                    row.append('')
            data.append(row)

        num_cols = len(header_row)
        col_width = (10 * inch) / num_cols
        table = Table(data, colWidths=[col_width] * num_cols)

        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), default_font if default_font == 'Arial' else 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ECF0F1')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, -1), default_font),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_cmds.append(('BACKGROUND', (0, i), (-1, i), colors.white))

        table.setStyle(TableStyle(style_cmds))
        elements.append(table)
        elements.append(Spacer(1, 0.2 * inch))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=student_paths_{session_id}.pdf'
    return response


@login_required
def assign_examiner(request, session_id):
    """Bulk-assign examiners to all stations of a path (POST only)."""
    from django.db import transaction

    session = get_object_or_404(ExamSession, pk=session_id)

    if request.method != 'POST':
        return redirect('creator:session_detail', session_id=str(session_id))

    path_id = request.POST.get('path_id')
    if not path_id:
        messages.error(request, 'Please select a path.')
        return redirect('creator:session_detail', session_id=str(session_id))

    path = get_object_or_404(Path, pk=path_id, session=session, is_deleted=False)
    stations = path.get_stations_in_order()
    all_examiners = Examiner.objects.filter(is_active=True, role='examiner')

    created = 0
    skipped = 0
    errors = []

    # Validate: Examiner 1 is required for every station
    missing_e1 = []
    for station in stations:
        e1_val = request.POST.get(f'examiner_1_{station.id}', '').strip()
        if not e1_val:
            missing_e1.append(station.name)
    if missing_e1:
        messages.error(request, f'Examiner 1 is required for: {(", ").join(missing_e1)}')
        return redirect('creator:session_detail', session_id=str(session_id))

    try:
        with transaction.atomic():
            for station in stations:
                sid = str(station.id)
                e1_val = request.POST.get(f'examiner_1_{sid}', '').strip()
                e2_val = request.POST.get(f'examiner_2_{sid}', '').strip()

                # Check same examiner in both slots
                if e1_val and e2_val and e1_val == e2_val:
                    errors.append(f'Station {station.name}: Examiner 1 and 2 cannot be the same.')
                    continue

                for examiner_id_str in [e1_val, e2_val]:
                    if not examiner_id_str:
                        continue
                    try:
                        examiner_id = int(examiner_id_str)
                    except (ValueError, TypeError):
                        errors.append(f'Invalid examiner ID for station {station.name}.')
                        continue

                    if not all_examiners.filter(pk=examiner_id).exists():
                        errors.append(f'Examiner ID {examiner_id} not found.')
                        continue

                    if ExaminerAssignment.objects.filter(
                        session=session, station=station, examiner_id=examiner_id
                    ).exists():
                        skipped += 1
                        continue

                    ExaminerAssignment.objects.create(
                        session=session,
                        station=station,
                        examiner_id=examiner_id,
                    )
                    created += 1

    except Exception as exc:
        messages.error(request, f'Error saving assignments: {exc}')
        return redirect('creator:session_detail', session_id=str(session_id))

    # Build success message
    parts = []
    if created:
        parts.append(f'{created} assignment(s) created')
    if skipped:
        parts.append(f'{skipped} duplicate(s) skipped')
    if errors:
        parts.append(f'{len(errors)} error(s)')
        for e in errors:
            messages.warning(request, e)
    if parts:
        messages.success(request, f'Path {path.name}: {", ".join(parts)}.')
    else:
        messages.info(request, 'No changes made.')

    return redirect('creator:session_detail', session_id=str(session_id))


@login_required
def get_path_stations_for_assignment(request, session_id, path_id):
    """AJAX endpoint: return HTML partial with station rows for the bulk assignment modal."""
    session = get_object_or_404(ExamSession, pk=session_id)
    path = get_object_or_404(Path, pk=path_id, session=session, is_deleted=False)
    stations = path.get_stations_in_order()
    all_examiners = Examiner.objects.filter(is_active=True, role='examiner').order_by('full_name')

    # Pre-load existing assignments for this path's stations
    existing = ExaminerAssignment.objects.filter(
        session=session, station__in=stations
    ).select_related('examiner', 'station')

    # Build lookup: station_id -> {primary: examiner_id, secondary: examiner_id}
    assignment_map = {}
    for a in existing:
        sid = str(a.station_id)
        if sid not in assignment_map:
            assignment_map[sid] = {'primary': None, 'secondary': None}
        if assignment_map[sid]['primary'] is None:
            assignment_map[sid]['primary'] = a.examiner_id
        else:
            assignment_map[sid]['secondary'] = a.examiner_id

    # Annotate stations with their existing assignments for easy template access
    stations_list = list(stations)
    for s in stations_list:
        mapping = assignment_map.get(str(s.id), {})
        s.assigned_primary = mapping.get('primary')
        s.assigned_secondary = mapping.get('secondary')

    return render(request, 'creator/sessions/_bulk_assign_stations.html', {
        'stations': stations_list,
        'all_examiners': all_examiners,
        'path': path,
    })


@login_required
@require_POST
def unlock_score_for_correction(request, score_id):
    """Allow coordinator/admin to unlock a submitted score so the examiner can correct it."""
    if request.user.role not in ('coordinator', 'admin') and not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    score = get_object_or_404(StationScore, pk=score_id)

    if score.status != 'submitted':
        return JsonResponse({'error': 'Score is not in submitted state'}, status=400)

    examiner_name = score.examiner.display_name if score.examiner else 'Deleted Examiner'
    student_name = score.session_student.full_name if score.session_student else 'Unknown Student'
    station_name = score.station.name if score.station else str(score.station_id)
    old_score = score.total_score
    max_score = score.max_score

    score.unlocked_for_correction = True
    score.save(update_fields=['unlocked_for_correction'])

    from core.utils.audit import log_action
    log_action(
        request,
        'UNLOCK',
        'StationScore',
        str(score.id),
        f'Coordinator {request.user.display_name} unlocked score for correction '
        f'| Student: {student_name} | Station: {station_name} '
        f'| Examiner: {examiner_name} | Current score: {old_score}/{max_score}',
        extra_data={
            'coordinator': request.user.username,
            'coordinator_display': request.user.display_name,
            'examiner': examiner_name,
            'student': student_name,
            'station': station_name,
            'score_before_unlock': old_score,
            'max_score': max_score,
        }
    )

    return JsonResponse({
        'success': True,
        'message': f'Score for {student_name} by {examiner_name} has been unlocked for correction.',
    })
