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
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from creator.api.sessions import _sync_exam_status

from core.models import (
    Exam, ExamSession, SessionStudent, Path, Station, ChecklistItem,
    Examiner, ExaminerAssignment, StationScore, ItemScore,
)
from core.utils.naming import generate_path_name
from core.utils.cache_utils import (
    EXAMINER_LIST_KEY, EXAMINER_LIST_TTL,
    invalidate_session_detail, get_session_detail_cache_key,
    SESSION_DETAIL_KEY, SESSION_DETAIL_TTL,
    invalidate_exam_detail,
)
from core.utils.roles import check_exam_department, check_session_department
from core.utils.sanitize import strip_html


def _can_open_dry_grading(user):
    """Allow superuser, admin, coordinator-head/organizer, or users with the can_open_dry_grading permission."""
    if user.is_superuser:
        return True

    if user.has_perm('core.can_open_dry_grading'):
        return True

    role = getattr(user, 'role', None)
    if role == 'admin':
        return True

    if role == 'coordinator':
        return getattr(user, 'coordinator_position', None) in ('head', 'organizer')

    return False


@login_required
def live_student_search(request, session_id):
    """AJAX endpoint: real-time student search scoped to a session."""
    session = get_object_or_404(ExamSession, pk=session_id)
    if not check_session_department(request.user, session):
        return JsonResponse({'results': [], 'error': 'Access denied'}, status=403)
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

    # Precompute submitted station IDs per student for accurate completion check
    student_ids = [s.id for s in qs]
    submitted_map: dict = {}
    for row in (
        StationScore.objects
        .filter(session_student_id__in=student_ids, status='submitted',
                station__active=True, station__is_deleted=False)
        .values('session_student_id', 'station_id', 'station__path_id')
    ):
        submitted_map.setdefault(row['session_student_id'], set()).add(row['station_id'])

    results = []
    for s in qs:
        # Determine accurate display status
        if s.path_id:
            required = frozenset(
                s.path.stations.filter(active=True, is_deleted=False).values_list('id', flat=True)
            ) if s.path else frozenset()
            submitted = submitted_map.get(s.id, set())
            if required and required.issubset(submitted):
                display_status = 'completed'
            elif submitted:
                display_status = 'in_progress'
            else:
                display_status = s.status
        else:
            display_status = s.status

        results.append({
            'id': str(s.id),
            'student_number': s.student_number,
            'full_name': s.full_name,
            'status': display_status,
            'path_id': str(s.path_id) if s.path_id else '',
            'path_name': s.path.name if s.path else None,
        })
    return JsonResponse({'results': results})


@login_required
def session_list(request, exam_id):
    """List sessions for an exam with search — dept-scoped."""
    exam = get_object_or_404(Exam, pk=exam_id)
    if not check_exam_department(request.user, exam):
        return HttpResponseForbidden('You do not have access to this exam.')
    search_query = request.GET.get('search', '').strip()
    sessions_qs = ExamSession.objects.filter(exam=exam).order_by('session_date', 'start_time')
    
    if search_query:
        sessions_qs = sessions_qs.filter(
            name__icontains=search_query
        ) | ExamSession.objects.filter(
            exam=exam, session_date__icontains=search_query
        ).order_by('session_date', 'start_time')
        sessions_qs = sessions_qs.order_by('session_date', 'start_time').distinct()
    
    return render(request, 'creator/sessions/list.html', {
        'exam': exam,
        'sessions': sessions_qs,
        'search_query': search_query,
    })


@login_required
def session_create(request, exam_id):
    """Create a new exam session — dept-scoped."""
    exam = get_object_or_404(Exam, pk=exam_id)
    if not check_exam_department(request.user, exam):
        return HttpResponseForbidden('You do not have access to this exam.')

    if not exam.exam_date:
        messages.warning(request, 'Please set an exam date before creating sessions.')
        return redirect('creator:exam_edit', exam_id=str(exam_id))

    if request.method == 'POST':
        session_name = strip_html(request.POST.get('name', '').strip())
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

        _sync_exam_status(exam, session.id)  # exam becomes 'ready' once it has a scheduled session

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
        invalidate_exam_detail(exam_id)
        return redirect('creator:session_detail', session_id=str(session.id))

    return render(request, 'creator/sessions/form.html', {'exam': exam, 'session': None})


@login_required
def session_edit(request, session_id):
    """Edit a session — dept-scoped."""
    session = get_object_or_404(ExamSession, pk=session_id)
    if not check_session_department(request.user, session):
        return HttpResponseForbidden('You do not have access to this session.')
    exam = session.exam

    if not exam.exam_date:
        messages.warning(request, 'Please set an exam date first.')
        return redirect('creator:exam_edit', exam_id=str(exam.id))

    if request.method == 'POST':
        new_name = strip_html(request.POST.get('name', '').strip())
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

        session.notes = strip_html(request.POST.get('notes', ''))
        session.save()
        invalidate_session_detail(session_id)
        invalidate_exam_detail(str(exam.id))
        messages.success(request, f'Session "{session.name}" updated.')
        return redirect('creator:exam_detail', exam_id=str(exam.id))

    return render(request, 'creator/sessions/form.html', {'exam': exam, 'session': session})


@login_required
def session_delete(request, session_id):
    """Cancel a session — dept-scoped, head coordinator or above only."""
    session = get_object_or_404(ExamSession, pk=session_id)
    if not check_session_department(request.user, session):
        return HttpResponseForbidden('You do not have access to this session.')
    # Only head coordinator, admin, or superuser can cancel sessions
    user = request.user
    if not (user.is_superuser or getattr(user, 'role', None) == 'admin'
            or (getattr(user, 'role', None) == 'coordinator'
                and getattr(user, 'coordinator_position', None) == 'head')):
        messages.error(request, 'Only head coordinators or admins can cancel sessions.')
        return redirect('creator:exam_detail', exam_id=str(session.exam_id))
    exam_id = str(session.exam_id)
    session_name = session.name

    session.status = 'cancelled'
    session.save()
    invalidate_session_detail(session_id)
    invalidate_exam_detail(exam_id)
    _sync_exam_status(session.exam, session.id)  # recalculate exam status after session cancelled

    messages.success(request, f"Session '{session_name}' has been cancelled.")
    return redirect('creator:exam_detail', exam_id=exam_id)


@login_required
def session_detail(request, session_id):
    """View session details, paths, students — dept-scoped."""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    session = get_object_or_404(ExamSession, pk=session_id)
    if not check_session_department(request.user, session):
        return HttpResponseForbidden('You do not have access to this session.')
    
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

    all_examiners_cached = None
    from django.core.cache import cache as _cache
    all_examiners_cached = _cache.get(EXAMINER_LIST_KEY)
    if all_examiners_cached is None:
        all_examiners_cached = list(Examiner.objects.filter(is_active=True, role='examiner').order_by('full_name'))
        _cache.set(EXAMINER_LIST_KEY, all_examiners_cached, EXAMINER_LIST_TTL)
    all_examiners = all_examiners_cached

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

    # ── Compute truly-completed student IDs ─────────────────────────────
    # A student is "completed" only when every active, non-deleted station
    # in their path has at least one submitted score.
    path_station_ids = {
        p.id: frozenset(
            p.stations.filter(active=True, is_deleted=False).values_list('id', flat=True)
        )
        for p in paths
    }
    # Submitted station IDs per student (scoped to their path's active stations)
    student_submitted_station_ids: dict = {}
    for row in (
        StationScore.objects
        .filter(session_student__session=session, status='submitted',
                station__active=True, station__is_deleted=False)
        .values('session_student_id', 'station_id', 'station__path_id')
    ):
        sid = row['session_student_id']
        student_submitted_station_ids.setdefault(sid, set()).add(row['station_id'])

    truly_completed_student_ids = set()
    for student_obj in students_qs:
        if not student_obj.path_id:
            continue
        required = path_station_ids.get(student_obj.path_id, frozenset())
        if not required:
            continue
        submitted = student_submitted_station_ids.get(student_obj.id, set())
        if required.issubset(submitted):
            truly_completed_student_ids.add(str(student_obj.id))

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
        'truly_completed_student_ids': truly_completed_student_ids,
        'can_delete_sessions': request.user.is_superuser or request.user.has_perm('core.can_delete_session'),
    })


def _build_student_paths_pdf(session):
    """
    Build and return the raw PDF bytes for the student-path distribution report.
    Shared by the sync view and the async Celery task.
    """
    from datetime import datetime
    from io import BytesIO
    from collections import defaultdict

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, PageBreak,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import arabic_reshaper
    from bidi.algorithm import get_display

    # ── Arabic reshape helper ────────────────────────────────────────────
    def ra(text):
        if not text:
            return text
        try:
            return get_display(arabic_reshaper.reshape(str(text)))
        except Exception:
            return str(text) if text else ''

    # ── Font setup ───────────────────────────────────────────────────────
    fnt = 'Helvetica'
    fnt_bold = 'Helvetica-Bold'
    try:
        win_fonts = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
        times_path = os.path.join(win_fonts, 'times.ttf')
        times_bold_path = os.path.join(win_fonts, 'timesbd.ttf')
        tnr_path = os.path.join(win_fonts, 'times new roman.ttf')
        tnr_bold_path = os.path.join(win_fonts, 'times new roman bold.ttf')

        registered = False
        if os.path.exists(times_path) or os.path.exists(tnr_path):
            p = times_path if os.path.exists(times_path) else tnr_path
            pdfmetrics.registerFont(TTFont('TimesNew', p))
            fnt = 'TimesNew'
            registered = True
        if os.path.exists(times_bold_path) or os.path.exists(tnr_bold_path):
            pb = times_bold_path if os.path.exists(times_bold_path) else tnr_bold_path
            pdfmetrics.registerFont(TTFont('TimesNew-Bold', pb))
            fnt_bold = 'TimesNew-Bold'
            registered = True

        if not registered:
            arial_path = os.path.join(win_fonts, 'arial.ttf')
            arial_bold_path = os.path.join(win_fonts, 'arialbd.ttf')
            if os.path.exists(arial_path):
                pdfmetrics.registerFont(TTFont('Arial', arial_path))
                fnt = 'Arial'
            if os.path.exists(arial_bold_path):
                pdfmetrics.registerFont(TTFont('Arial-Bold', arial_bold_path))
                fnt_bold = 'Arial-Bold'
    except Exception:
        pass

    # ── Colour palette ───────────────────────────────────────────────────
    C_NAVY    = colors.HexColor('#1A1A2E')   # page header / footer band
    C_COL_HDR = colors.HexColor('#0F3460')   # path column header bg
    C_STRIPE  = colors.HexColor('#E8EEF7')   # alternating row stripe
    C_BORDER  = colors.HexColor('#CBD5E1')   # table border
    C_INFO    = colors.HexColor('#F0F4FF')   # summary block bg

    # ── Data ─────────────────────────────────────────────────────────────
    students       = list(SessionStudent.objects.filter(session=session).order_by('student_number'))
    paths          = list(Path.objects.filter(session=session, is_deleted=False).order_by('name'))
    total_students = len(students)
    total_paths    = len(paths)

    students_by_path = defaultdict(list)
    for s in students:
        key = str(s.path_id) if s.path_id else 'unassigned'
        students_by_path[key].append(s)

    exam_name    = ra(session.exam.name) if session.exam else ''
    session_name = ra(session.name or 'Session')
    date_str     = str(session.session_date) if session.session_date else '—'
    generated_at = datetime.now().strftime('%d %b %Y  %H:%M')

    page_w, page_h = A4
    usable_w = page_w - 0.9 * inch

    # ── Canvas header / footer ───────────────────────────────────────────
    def _draw_page(canvas, doc):
        canvas.saveState()

        # Header band
        band_h = 0.65 * inch
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, page_h - band_h, page_w, band_h, fill=True, stroke=False)

        canvas.setFillColor(colors.white)
        canvas.setFont(fnt_bold, 11.5)
        canvas.drawString(0.45 * inch, page_h - 0.27 * inch, 'Student Path Distribution')
        canvas.setFont(fnt, 8.5)
        canvas.drawString(0.45 * inch, page_h - 0.48 * inch, exam_name)

        canvas.setFont(fnt, 8.5)
        canvas.drawRightString(page_w - 0.45 * inch, page_h - 0.27 * inch, session_name)
        canvas.drawRightString(page_w - 0.45 * inch, page_h - 0.48 * inch, date_str)

        # Accent underline
        canvas.setStrokeColor(colors.HexColor('#0F3460'))
        canvas.setLineWidth(2)
        canvas.line(0, page_h - band_h, page_w, page_h - band_h)

        # Footer
        fy = 0.28 * inch
        canvas.setStrokeColor(C_BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(0.45 * inch, fy + 0.15 * inch,
                    page_w - 0.45 * inch, fy + 0.15 * inch)

        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.setFont(fnt, 7.5)
        canvas.drawString(0.45 * inch, fy, f'Generated: {generated_at}')
        canvas.drawCentredString(page_w / 2, fy, f'Page {doc.page}')
        canvas.drawRightString(page_w - 0.45 * inch, fy,
                               f'Students: {total_students}  |  Paths: {total_paths}')

        canvas.restoreState()

    # ── Summary info block ───────────────────────────────────────────────
    def _info_table():
        style_p = ParagraphStyle('inf', fontName=fnt, fontSize=8.5, leading=13)
        cells = [
            Paragraph(f'<b>Exam:</b>  {exam_name}', style_p),
            Paragraph(f'<b>Session:</b>  {session_name}', style_p),
            Paragraph(f'<b>Date:</b>  {date_str}', style_p),
            Paragraph(f'<b>Total Students:</b>  {total_students}', style_p),
            Paragraph(f'<b>Total Paths:</b>  {total_paths}', style_p),
        ]
        widths = [usable_w * f for f in [0.3, 0.23, 0.17, 0.17, 0.13]]
        t = Table([cells], colWidths=widths)
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), C_INFO),
            ('BOX',           (0, 0), (-1, 0), 0.5, C_BORDER),
            ('INNERGRID',     (0, 0), (-1, 0), 0.5, C_BORDER),
            ('TOPPADDING',    (0, 0), (-1, 0), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('LEFTPADDING',   (0, 0), (-1, 0), 9),
            ('VALIGN',        (0, 0), (-1, 0), 'MIDDLE'),
        ]))
        return t

    # ── Document ─────────────────────────────────────────────────────────
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.45 * inch,
        rightMargin=0.45 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.65 * inch,
    )
    elements = []

    # 3 paths per page — each path is a column, student names only (no # or ID)
    PATHS_PER_PAGE = 3
    path_groups = [paths[i:i + PATHS_PER_PAGE] for i in range(0, len(paths), PATHS_PER_PAGE)]
    if not path_groups:
        path_groups = [[]]

    col_w = usable_w / PATHS_PER_PAGE

    hdr_name_style = ParagraphStyle(
        'hn', fontName=fnt_bold, fontSize=13,
        alignment=TA_CENTER, textColor=colors.white, leading=18,
    )
    hdr_count_style = ParagraphStyle(
        'hc', fontName=fnt, fontSize=9,
        alignment=TA_CENTER, textColor=colors.HexColor('#B0C4DE'), leading=13,
    )

    for grp_idx, group in enumerate(path_groups):
        if grp_idx > 0:
            elements.append(PageBreak())

        elements.append(_info_table())
        elements.append(Spacer(1, 0.10 * inch))

        # Pad group to always PATHS_PER_PAGE entries
        padded = list(group) + [None] * (PATHS_PER_PAGE - len(group))
        col_students = [
            students_by_path.get(str(p.id), []) if p else []
            for p in padded
        ]
        max_rows = max(len(s) for s in col_students) if any(col_students) else 0

        # Header row: [path name + count, path name + count, path name + count]
        header_row = []
        for i, path in enumerate(padded):
            if path is None:
                header_row.append('')
            else:
                cnt = len(col_students[i])
                header_row.append([
                    Paragraph(f'<font size=10>Path</font> {ra(path.name)}', hdr_name_style),
                    Paragraph(f'{cnt} student{"s" if cnt != 1 else ""}', hdr_count_style),
                ])

        data = [header_row]
        for row_idx in range(max_rows):
            row = []
            for col_idx in range(PATHS_PER_PAGE):
                stud_list = col_students[col_idx]
                if row_idx < len(stud_list):
                    s = stud_list[row_idx]
                    row.append(ra(s.full_name or '—'))
                else:
                    row.append('')
            data.append(row)

        table = Table(data, colWidths=[col_w] * PATHS_PER_PAGE, repeatRows=1)

        style_cmds = [
            # Header row
            ('BACKGROUND',    (0, 0), (-1, 0), C_COL_HDR),
            ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
            ('FONTNAME',      (0, 0), (-1, 0), fnt_bold),
            ('ALIGN',         (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            # Data rows
            ('FONTNAME',      (0, 1), (-1, -1), fnt_bold),
            ('FONTSIZE',      (0, 1), (-1, -1), 11),
            ('ALIGN',         (0, 1), (-1, -1), 'CENTER'),
            ('TOPPADDING',    (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 7),
            # Borders
            ('BOX',           (0, 0), (-1, -1), 0.75, C_COL_HDR),
            ('INNERGRID',     (0, 0), (-1, -1), 0.4, C_BORDER),
            ('LINEBELOW',     (0, 0), (-1, 0), 1.5, C_COL_HDR),
            # Strong vertical lines between columns
            ('LINEBEFORE',    (1, 0), (1, -1), 1.5, C_COL_HDR),
            ('LINEBEFORE',    (2, 0), (2, -1), 1.5, C_COL_HDR),
        ]

        # Alternating row shading
        for i in range(1, len(data)):
            bg = C_STRIPE if i % 2 == 1 else colors.white
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))

        table.setStyle(TableStyle(style_cmds))
        elements.append(table)

    if not paths:
        elements.append(_info_table())
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph(
            'No paths defined for this session.',
            ParagraphStyle('np', fontName=fnt, fontSize=11, alignment=TA_CENTER),
        ))

    doc.build(elements, onFirstPage=_draw_page, onLaterPages=_draw_page)
    buffer.seek(0)
    return buffer.getvalue()


@login_required
def download_student_paths_pdf(request, session_id):
    """Download PDF with students grouped by path — dept-scoped."""
    session_obj = get_object_or_404(ExamSession, pk=session_id)
    if not check_session_department(request.user, session_obj):
        return HttpResponseForbidden('You do not have access to this session.')

    pdf_bytes = _build_student_paths_pdf(session_obj)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=student_paths_{session_id}.pdf'
    return response


@login_required
def request_pdf_async(request, session_id):
    """
    Dispatch async PDF generation via Celery.
    Returns JSON with either 'task_id' for async polling or 'fallback_url' for sync download.
    """
    from django.conf import settings
    from django.urls import reverse
    session = get_object_or_404(ExamSession, pk=session_id)

    broker = getattr(settings, 'CELERY_BROKER_URL', '')
    if not broker:
        # Celery not configured – return fallback URL for direct download
        fallback_url = reverse('creator:download_student_paths_pdf', args=[session_id])
        return JsonResponse({'fallback_url': fallback_url})

    from core.tasks import generate_pdf_report
    result = generate_pdf_report.delay(str(session_id))
    return JsonResponse({'task_id': result.id})


@login_required
def pdf_report_status(request, session_id):
    """
    Poll the status of a PDF generation task.
    GET /sessions/<id>/pdf-status/?task_id=<uuid>
    Returns: {status: 'running'|'done'|'error', pdf_b64?: str, filename?: str, message?: str}
    """
    from django.core.cache import cache
    task_id = request.GET.get('task_id', '')
    if not task_id:
        return JsonResponse({'status': 'error', 'message': 'Missing task_id'}, status=400)

    status_key = f'osce:pdf_status:{session_id}:{task_id}'
    result = cache.get(status_key)
    if result is None:
        return JsonResponse({'status': 'pending'})
    return JsonResponse(result)


@login_required
def assign_examiner(request, session_id):
    """Bulk-assign examiners to all stations of a path (POST only) — dept-scoped."""
    from django.db import transaction

    session = get_object_or_404(ExamSession, pk=session_id)
    if not check_session_department(request.user, session):
        return HttpResponseForbidden('You do not have access to this session.')

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

    invalidate_session_detail(session_id)
    return redirect('creator:session_detail', session_id=str(session_id))


@login_required
def get_path_stations_for_assignment(request, session_id, path_id):
    """AJAX endpoint: return HTML partial with station rows — dept-scoped."""
    session = get_object_or_404(
        ExamSession.objects.select_related('exam__course__department'),
        pk=session_id,
    )
    if not check_session_department(request.user, session):
        return HttpResponseForbidden('You do not have access to this session.')
    path = get_object_or_404(Path, pk=path_id, session=session, is_deleted=False)
    stations = path.get_stations_in_order()

    # Filter examiners to those matching the exam's department
    exam_dept = session.exam.course.department
    examiner_qs = Examiner.objects.filter(is_active=True, role='examiner')
    if exam_dept is not None:
        examiner_qs = examiner_qs.filter(department=exam_dept)
    all_examiners = examiner_qs.order_by('full_name')

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
def session_dry_grading(request, session_id):
    """
    Creator-side dry marking page.

    Access control:
      - Superuser, Admin, Coordinator-Head, Coordinator-Organizer only
      - Coordinator access remains department-scoped via check_session_department
    """
    session = get_object_or_404(
        ExamSession.objects.select_related('exam', 'exam__course', 'exam__course__department'),
        pk=session_id,
    )

    if not check_session_department(request.user, session):
        return HttpResponseForbidden('You do not have access to this session.')

    if not _can_open_dry_grading(request.user):
        return HttpResponseForbidden('Access denied.')

    if session.status not in ('finished', 'completed'):
        messages.warning(request, 'Dry marking is available only after the session is finished.')
        return redirect('creator:session_detail', session_id=str(session.id))

    dry_paths = list(
        Path.objects.filter(
            session=session,
            is_deleted=False,
            stations__is_dry=True,
            stations__active=True,
        )
        .distinct()
        .order_by('name')
    )

    if not dry_paths:
        messages.warning(request, 'No dry stations found in this session.')
        return redirect('creator:session_detail', session_id=str(session.id))

    selected_path_id = request.POST.get('path_id') or request.GET.get('path_id')
    selected_path = next((p for p in dry_paths if str(p.id) == str(selected_path_id)), None)
    if selected_path is None:
        selected_path = dry_paths[0]

    dry_stations = list(
        Station.objects.filter(
            path=selected_path,
            active=True,
            is_dry=True,
        )
        .select_related('path')
        .order_by('station_number')
    )

    selected_station_id = request.POST.get('station_id') or request.GET.get('station_id')
    selected_station = next((s for s in dry_stations if str(s.id) == str(selected_station_id)), None)
    if selected_station is None and dry_stations:
        selected_station = dry_stations[0]

    essay_items = []
    selected_item = None
    if selected_station:
        essay_items = list(
            ChecklistItem.objects.filter(
                station=selected_station,
                rubric_type='essay',
            ).order_by('item_number')
        )

        selected_item_id = request.POST.get('checklist_item_id') or request.GET.get('checklist_item_id')
        selected_item = next((i for i in essay_items if str(i.id) == str(selected_item_id)), None)
        if selected_item is None and essay_items:
            selected_item = essay_items[0]

    answer_rows = []
    if selected_item and selected_station:
        answer_rows = list(
            ItemScore.objects.filter(
                checklist_item=selected_item,
                station_score__session_student__session=session,
                station_score__station=selected_station,
            )
            .select_related('station_score', 'station_score__session_student', 'station_score__examiner', 'graded_by')
            .order_by('station_score__session_student__student_number')
        )

    if request.method == 'POST' and selected_item and answer_rows:
        updated = 0
        affected_station_scores = {}

        for row in answer_rows:
            field_name = f'mark_{row.id}'
            if field_name not in request.POST:
                continue

            raw_mark = (request.POST.get(field_name) or '').strip()
            if raw_mark == '':
                continue

            try:
                value = float(raw_mark)
            except ValueError:
                continue

            # Clamp to valid range for this checklist item
            if value < 0:
                value = 0
            if value > selected_item.points:
                value = float(selected_item.points)

            should_mark_graded = row.marked_at is None
            score_changed = float(row.score or 0) != float(value)

            if score_changed or should_mark_graded:
                row.score = value
                row.max_points = selected_item.points
                row.marked_at = TimestampMixin.utc_timestamp()
                row.graded_by = request.user
                row.save(update_fields=['score', 'max_points', 'marked_at', 'graded_by'])
                affected_station_scores[row.station_score.id] = row.station_score
                updated += 1

        for station_score in affected_station_scores.values():
            station_score.calculate_total()
            station_score.save(update_fields=['total_score', 'percentage', 'updated_at'])

        if updated:
            from core.utils.audit import log_action
            log_action(
                request,
                'UPDATE',
                'ChecklistItem',
                str(selected_item.id),
                f'Overwrote {updated} dry marks for item #{selected_item.item_number} in session {session.name}',
            )
            messages.success(request, f'{updated} mark(s) updated successfully.')
        else:
            messages.info(request, 'No marks changed.')

        path_id_for_redirect = str(selected_path.id) if selected_path else ''
        station_id_for_redirect = str(selected_station.id) if selected_station else ''
        item_id_for_redirect = str(selected_item.id)

        redirect_url = (
            f"{reverse('creator:session_dry_grading', kwargs={'session_id': str(session.id)})}"
            f"?path_id={path_id_for_redirect}&station_id={station_id_for_redirect}&checklist_item_id={item_id_for_redirect}"
        )
        return redirect(redirect_url)

    session_total = ItemScore.objects.filter(
        checklist_item__rubric_type='essay',
        station_score__session_student__session=session,
        station_score__station__is_dry=True,
    ).count()
    session_graded = ItemScore.objects.filter(
        checklist_item__rubric_type='essay',
        station_score__session_student__session=session,
        station_score__station__is_dry=True,
        marked_at__isnull=False,
    ).count()

    return render(request, 'creator/sessions/dry_grading.html', {
        'session': session,
        'exam': session.exam,
        'dry_paths': dry_paths,
        'dry_stations': dry_stations,
        'essay_items': essay_items,
        'selected_path': selected_path,
        'selected_station': selected_station,
        'selected_item': selected_item,
        'answer_rows': answer_rows,
        'session_total_items': session_total,
        'session_graded_items': session_graded,
        'session_pending_items': session_total - session_graded,
    })


@login_required
@require_POST
def unlock_score_for_correction(request, score_id):
    """Allow coordinator/admin to unlock a submitted score so the examiner can correct it."""
    if request.user.role not in ('coordinator', 'admin') and not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    score = get_object_or_404(StationScore, pk=score_id)

    # Enforce department scope on the score's session
    session_obj = score.session_student.session if score.session_student else None
    if session_obj and not check_session_department(request.user, session_obj):
        return JsonResponse({'error': 'You do not have access to this session.'}, status=403)

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
