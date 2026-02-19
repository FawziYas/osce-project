"""
Session CRUD views – list, create, edit, delete, detail, PDF, assign examiner.
"""
import os
from collections import defaultdict
from datetime import datetime, time
from io import BytesIO

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from core.models import (
    Exam, ExamSession, SessionStudent, Path, Station, ChecklistItem,
    Examiner, ExaminerAssignment,
)
from core.utils.naming import generate_path_name


@login_required
def session_list(request, exam_id):
    """List sessions for an exam."""
    exam = get_object_or_404(Exam, pk=exam_id)
    sessions = ExamSession.objects.filter(exam=exam).order_by('-session_date')
    return render(request, 'creator/sessions/list.html', {
        'exam': exam,
        'sessions': sessions,
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
            for path_num in range(1, number_of_paths + 1):
                path_name = generate_path_name(path_num)
                Path.objects.create(
                    session=session,
                    name=path_name,
                    description=f'Path {path_name}',
                    rotation_minutes=exam.station_duration_minutes,
                    is_active=True,
                )

        messages.success(request, f'Session "{session.name}" created with 3 paths (A, B, C). Now add stations.')
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
    session = get_object_or_404(ExamSession, pk=session_id)
    students = SessionStudent.objects.filter(session=session).order_by('student_number')
    paths = Path.objects.filter(session=session, is_deleted=False).order_by('name')
    examiner_assignments = ExaminerAssignment.objects.filter(session=session).select_related(
        'examiner', 'station'
    )
    all_examiners = Examiner.objects.filter(is_active=True).order_by('full_name')

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

    return render(request, 'creator/sessions/detail.html', {
        'session': session,
        'students': students,
        'paths': paths,
        'examiner_assignments': examiner_assignments,
        'all_examiners': all_examiners,
        'session_metrics': session_metrics,
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
    """Assign an examiner to a station for this session (POST only)."""
    session = get_object_or_404(ExamSession, pk=session_id)

    examiner_id = request.POST.get('examiner_id')
    station_id = request.POST.get('station_id')
    is_primary = 'is_primary' in request.POST

    if not examiner_id or not station_id:
        messages.error(request, 'Please select both examiner and station.')
        return redirect('creator:session_detail', session_id=str(session_id))

    if ExaminerAssignment.objects.filter(
        session=session, station_id=station_id, examiner_id=examiner_id
    ).exists():
        messages.warning(request, 'This examiner is already assigned to this station.')
        return redirect('creator:session_detail', session_id=str(session_id))

    ExaminerAssignment.objects.create(
        session=session,
        station_id=station_id,
        examiner_id=int(examiner_id),
        is_primary=is_primary,
    )

    examiner = get_object_or_404(Examiner, pk=int(examiner_id))
    messages.success(request, f'Assigned {examiner.display_name} to station.')
    return redirect('creator:session_detail', session_id=str(session_id))
