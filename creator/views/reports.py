"""
Reports views – scoresheets, report index, and XLSX exports.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, F
from collections import defaultdict

from core.models import (
    Course, Exam, ExamSession, SessionStudent, Station, ChecklistItem,
    StationScore, ItemScore, ILO,
)


@login_required
def reports_index(request):
    """Reports dashboard – select session and generate reports."""
    # Base filter
    sessions_qs = ExamSession.objects.filter(
        exam__is_deleted=False,
    ).select_related('exam', 'exam__course')
    
    # Permission-based filtering
    # Only superusers can see all sessions (scheduled, in_progress, completed)
    # Coordinator and Admin can see only completed sessions
    # Regular examiners can see only completed sessions
    if not request.user.is_superuser:
        sessions_qs = sessions_qs.filter(status='completed')
    
    sessions = sessions_qs.order_by('-session_date')

    selected_session = None
    session_id = request.GET.get('session_id')
    if session_id:
        selected_session = ExamSession.objects.filter(pk=session_id).first()

    return render(request, 'creator/reports/index.html', {
        'sessions': sessions,
        'selected_session': selected_session,
    })


@login_required
def reports_scoresheets(request, session_id):
    """Print-ready score sheets for a session with pagination, search, and print_all mode."""
    session = get_object_or_404(ExamSession, pk=session_id)
    
    # Access control: non-superusers can only view completed sessions
    if not request.user.is_superuser and session.status != 'completed':
        return HttpResponseForbidden(
            "You do not have permission to view this session. "
            "Only superusers can view non-completed sessions."
        )
    
    # Search filter
    search_query = request.GET.get('search', '').strip()
    print_all = request.GET.get('print_all') == '1'

    students_qs = SessionStudent.objects.filter(session=session)
    if search_query:
        students_qs = students_qs.filter(full_name__icontains=search_query) | SessionStudent.objects.filter(
            session=session, student_number__icontains=search_query
        )
    students_qs = students_qs.order_by('full_name').distinct()

    # Paginate: 10 per page normally; all students in print_all mode
    per_page = students_qs.count() if print_all else 10
    page_num = 1 if print_all else request.GET.get('page', 1)
    paginator = Paginator(students_qs, per_page=max(per_page, 1))

    try:
        students_page = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        students_page = paginator.page(1)

    students = students_page.object_list

    student_data = []
    for student in students:
        if student.path_id:
            student_stations = Station.objects.filter(
                path_id=student.path_id, active=True,
            ).order_by('station_number')
        else:
            student_stations = Station.objects.none()

        # Only count submitted scores, ignore abandoned/in-progress evaluations
        scores_qs = StationScore.objects.filter(
            session_student=student,
            status='submitted'
        ).exclude(
            total_score__isnull=True
        ).select_related('examiner')
        # Map all scores by station (not just one per station)
        score_map_all = {}
        for score in scores_qs:
            if score.station_id not in score_map_all:
                score_map_all[score.station_id] = []
            score_map_all[score.station_id].append(score)

        max_possible = 0
        for st in student_stations:
            st_max = ChecklistItem.objects.filter(station=st).aggregate(
                total=Sum('points')
            )['total'] or 0
            max_possible += st_max

        # Calculate total using average for multiple examiners per station
        total_score = 0
        for station_id, scores_list in score_map_all.items():
            if scores_list:
                # Use average if multiple scores, otherwise use single score
                avg_score = sum(s.total_score or 0 for s in scores_list) / len(scores_list)
                total_score += avg_score
        
        percentage = (total_score / max_possible * 100) if max_possible > 0 else 0
        
        # Build comments with examiner names
        comments_with_examiner = []
        for score in scores_qs:
            if score.comments and score.comments.strip():
                examiner_name = score.examiner.full_name if score.examiner else "Unknown Examiner"
                comments_with_examiner.append({
                    'station': Station.objects.filter(pk=score.station_id).first(),
                    'examiner_name': examiner_name,
                    'comment_text': score.comments,
                    'formatted': f"{examiner_name}:\n{score.comments}"
                })
        
        student_data.append({
            'student': student,
            'stations': student_stations,
            'scores': score_map_all,
            'total_score': round(total_score, 2),
            'max_score': max_possible,
            'percentage_display': round(percentage, 2),
            'passed': percentage >= 60,
            'comments_with_examiner': comments_with_examiner,
        })

    return render(request, 'creator/reports/scoresheets.html', {
        'session': session,
        'students': student_data,
        'page_obj': students_page,
        'paginator': paginator,
        'search_query': search_query,
        'print_all': print_all,
    })


@login_required
def reports_student_scoresheet(request, student_id):
    """Print-ready score sheet for a single student."""
    student = get_object_or_404(SessionStudent, pk=student_id)
    session = get_object_or_404(ExamSession, pk=student.session_id)
    
    # Access control: non-superusers can only view completed sessions
    if not request.user.is_superuser and session.status != 'completed':
        return HttpResponseForbidden(
            "You do not have permission to view this session. "
            "Only superusers can view non-completed sessions."
        )

    if student.path_id:
        student_stations = Station.objects.filter(
            path_id=student.path_id, active=True,
        ).order_by('station_number')
    else:
        student_stations = Station.objects.none()

    # Only count submitted scores, ignore abandoned/in-progress evaluations
    scores_qs = StationScore.objects.filter(
        session_student=student,
        status='submitted'
    ).exclude(
        total_score__isnull=True
    ).select_related('examiner')
    # Map all scores by station (not just one per station)
    score_map_all = {}
    for score in scores_qs:
        if score.station_id not in score_map_all:
            score_map_all[score.station_id] = []
        score_map_all[score.station_id].append(score)

    max_possible = 0
    for st in student_stations:
        st_max = ChecklistItem.objects.filter(station=st).aggregate(
            total=Sum('points')
        )['total'] or 0
        max_possible += st_max

    # Calculate total using average for multiple examiners per station
    _total = 0
    for station_id, scores_list in score_map_all.items():
        if scores_list:
            # Use average if multiple scores, otherwise use single score
            avg_score = sum(s.total_score or 0 for s in scores_list) / len(scores_list)
            _total += avg_score
    
    _pct = (_total / max_possible * 100) if max_possible > 0 else 0
    
    # Build comments with examiner names
    comments_with_examiner = []
    for score in scores_qs:
        if score.comments and score.comments.strip():
            examiner_name = score.examiner.full_name if score.examiner else "Unknown Examiner"
            comments_with_examiner.append({
                'station': Station.objects.filter(pk=score.station_id).first(),
                'examiner_name': examiner_name,
                'comment_text': score.comments,
                'formatted': f"{examiner_name}:\n{score.comments}"
            })
    
    student_data = [{
        'student': student,
        'stations': student_stations,
        'scores': score_map_all,
        'total_score': round(_total, 2),
        'max_score': max_possible,
        'percentage_display': round(_pct, 2),
        'passed': _pct >= 60,
        'comments_with_examiner': comments_with_examiner,
    }]

    return render(request, 'creator/reports/scoresheets.html', {
        'session': session,
        'students': student_data,
        'single_student': True,
    })


# ── XLSX Export: ILO Scores per Student ─────────────────────────────────

@login_required
def export_ilo_scores_xlsx(request, session_id):
    """
    Generate an XLSX workbook for a session.
    Sheet layout — rows = students, columns = ILOs.
    Each cell = average of examiner scores for that student / ILO.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    session = get_object_or_404(
        ExamSession.objects.select_related('exam', 'exam__course'),
        pk=session_id,
    )

    # Access control
    if not request.user.is_superuser and session.status != 'completed':
        return HttpResponseForbidden("Only superusers can export non-completed sessions.")

    exam = session.exam
    course = exam.course

    # ── Gather ILOs for this course ─────────────────────────────────────
    ilos = list(ILO.objects.filter(course=course).order_by('number'))
    if not ilos:
        return HttpResponse("No ILOs defined for this course.", status=400)

    ilo_ids = [ilo.id for ilo in ilos]

    # ── Gather students ─────────────────────────────────────────────────
    students = list(
        SessionStudent.objects.filter(session=session)
        .order_by('full_name')
    )
    student_ids = [s.id for s in students]

    # ── Fetch all submitted item-level scores in one query ──────────────
    # Join: ItemScore → StationScore → SessionStudent
    #        ItemScore → ChecklistItem (for ilo_id, points)
    rows = (
        ItemScore.objects
        .filter(
            station_score__session_student_id__in=student_ids,
            station_score__status='submitted',
            checklist_item__ilo_id__in=ilo_ids,
        )
        .values(
            'station_score__session_student_id',
            'station_score__station_id',
            'station_score__examiner_id',
            'checklist_item__ilo_id',
        )
        .annotate(
            earned=Sum('score'),
            possible=Sum('max_points'),
        )
    )

    # Structure:  student_id → ilo_id → list of (earned, possible) per examiner-station combo
    # When multiple examiners score the same station we average their totals.
    # raw_data[student_id][ilo_id][(station_id, examiner_id)] = (earned, possible)
    raw_data = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        sid = r['station_score__session_student_id']
        ilo_id = r['checklist_item__ilo_id']
        key = (r['station_score__station_id'], r['station_score__examiner_id'])
        raw_data[sid][ilo_id][key] = (r['earned'] or 0, r['possible'] or 0)

    # Collapse to averages per station, then sum across stations.
    # Result: scores[student_id][ilo_id] = {'earned': float, 'possible': float}
    scores = {}
    for sid in student_ids:
        scores[sid] = {}
        for ilo in ilos:
            examiner_station_data = raw_data[sid].get(ilo.id, {})
            if not examiner_station_data:
                scores[sid][ilo.id] = {'earned': 0, 'possible': 0}
                continue

            # Group by station, average examiners within each station
            station_groups = defaultdict(list)
            station_possible = {}
            for (station_id, _examiner_id), (earned, possible) in examiner_station_data.items():
                station_groups[station_id].append(earned)
                station_possible[station_id] = possible  # same max for same station

            total_earned = 0
            total_possible = 0
            for station_id, earned_list in station_groups.items():
                total_earned += sum(earned_list) / len(earned_list)  # average across examiners
                total_possible += station_possible[station_id]

            scores[sid][ilo.id] = {
                'earned': round(total_earned, 2),
                'possible': round(total_possible, 2),
            }

    # ── Build workbook ──────────────────────────────────────────────────
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'ILO Scores'

    # Styles
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='1A1A2E', end_color='1A1A2E', fill_type='solid')
    sub_header_fill = PatternFill(start_color='4A6FA5', end_color='4A6FA5', fill_type='solid')
    sub_header_font = Font(bold=True, color='FFFFFF', size=10)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left_align = Alignment(horizontal='left', vertical='center')

    # ── Row 1: Title ────────────────────────────────────────────────────
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=3 + len(ilos) * 2 + 1)
    title_cell = ws.cell(row=1, column=1,
                         value=f'{exam.name} — {session.name} — ILO Score Report')
    title_cell.font = Font(bold=True, size=14, color='1A1A2E')
    title_cell.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[1].height = 30

    # ── Row 2: Course info ──────────────────────────────────────────────
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=3 + len(ilos) * 2 + 1)
    info_cell = ws.cell(row=2, column=1,
                        value=f'Course: {course.code} — {course.name}  |  Students: {len(students)}')
    info_cell.font = Font(size=10, color='666666')
    ws.row_dimensions[2].height = 20

    # ── Row 3: Empty spacer ─────────────────────────────────────────────
    start_row = 4

    # ── Row 4: Header — fixed columns ──────────────────────────────────
    fixed_headers = ['#', 'Student Number', 'Student Name']
    for ci, hdr in enumerate(fixed_headers, 1):
        cell = ws.cell(row=start_row, column=ci, value=hdr)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border

    # ILO columns: pairs of (Score, Max) for each ILO
    col = len(fixed_headers) + 1
    for ilo in ilos:
        # Merge header for the ILO pair
        ws.merge_cells(start_row=start_row, start_column=col,
                       end_row=start_row, end_column=col + 1)
        cell = ws.cell(row=start_row, column=col,
                       value=f'ILO #{ilo.number}')
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
        # Also style the merged cell's right side
        ws.cell(row=start_row, column=col + 1).fill = header_fill
        ws.cell(row=start_row, column=col + 1).border = border
        col += 2

    # Total column pair
    ws.merge_cells(start_row=start_row, start_column=col,
                   end_row=start_row, end_column=col + 1)
    total_hdr = ws.cell(row=start_row, column=col, value='TOTAL')
    total_hdr.font = header_font
    total_hdr.fill = PatternFill(start_color='198754', end_color='198754', fill_type='solid')
    total_hdr.alignment = center
    total_hdr.border = border
    ws.cell(row=start_row, column=col + 1).fill = PatternFill(
        start_color='198754', end_color='198754', fill_type='solid')
    ws.cell(row=start_row, column=col + 1).border = border

    # Percentage column
    pct_col = col + 2
    pct_cell = ws.cell(row=start_row, column=pct_col, value='%')
    pct_cell.font = header_font
    pct_cell.fill = PatternFill(start_color='0D6EFD', end_color='0D6EFD', fill_type='solid')
    pct_cell.alignment = center
    pct_cell.border = border

    # ── Row 5: Sub-header (Score / Max under each ILO) ──────────────────
    sub_row = start_row + 1
    for ci in range(1, len(fixed_headers) + 1):
        cell = ws.cell(row=sub_row, column=ci, value='')
        cell.fill = sub_header_fill
        cell.border = border

    col = len(fixed_headers) + 1
    for _ilo in ilos:
        ws.cell(row=sub_row, column=col, value='Score').font = sub_header_font
        ws.cell(row=sub_row, column=col).fill = sub_header_fill
        ws.cell(row=sub_row, column=col).alignment = center
        ws.cell(row=sub_row, column=col).border = border
        ws.cell(row=sub_row, column=col + 1, value='Max').font = sub_header_font
        ws.cell(row=sub_row, column=col + 1).fill = sub_header_fill
        ws.cell(row=sub_row, column=col + 1).alignment = center
        ws.cell(row=sub_row, column=col + 1).border = border
        col += 2

    # Total sub-header
    ws.cell(row=sub_row, column=col, value='Score').font = sub_header_font
    ws.cell(row=sub_row, column=col).fill = sub_header_fill
    ws.cell(row=sub_row, column=col).alignment = center
    ws.cell(row=sub_row, column=col).border = border
    ws.cell(row=sub_row, column=col + 1, value='Max').font = sub_header_font
    ws.cell(row=sub_row, column=col + 1).fill = sub_header_fill
    ws.cell(row=sub_row, column=col + 1).alignment = center
    ws.cell(row=sub_row, column=col + 1).border = border

    # % sub-header
    ws.cell(row=sub_row, column=pct_col, value='').fill = sub_header_fill
    ws.cell(row=sub_row, column=pct_col).border = border

    # ── Data rows ───────────────────────────────────────────────────────
    data_start = sub_row + 1
    even_fill = PatternFill(start_color='F8F9FA', end_color='F8F9FA', fill_type='solid')
    pass_fill = PatternFill(start_color='D1E7DD', end_color='D1E7DD', fill_type='solid')
    fail_fill = PatternFill(start_color='F8D7DA', end_color='F8D7DA', fill_type='solid')

    for idx, student in enumerate(students):
        row_num = data_start + idx
        row_fill = even_fill if idx % 2 == 0 else None

        # Fixed columns
        ws.cell(row=row_num, column=1, value=idx + 1).alignment = center
        ws.cell(row=row_num, column=2, value=student.student_number).alignment = left_align
        ws.cell(row=row_num, column=3, value=student.full_name).alignment = left_align

        for ci in range(1, 4):
            ws.cell(row=row_num, column=ci).border = border
            if row_fill:
                ws.cell(row=row_num, column=ci).fill = row_fill

        # ILO columns
        col = len(fixed_headers) + 1
        grand_earned = 0
        grand_possible = 0

        for ilo in ilos:
            s = scores.get(student.id, {}).get(ilo.id, {'earned': 0, 'possible': 0})
            earned = s['earned']
            possible = s['possible']
            grand_earned += earned
            grand_possible += possible

            earned_cell = ws.cell(row=row_num, column=col, value=earned if earned else '')
            earned_cell.alignment = center
            earned_cell.border = border
            if row_fill:
                earned_cell.fill = row_fill

            max_cell = ws.cell(row=row_num, column=col + 1, value=possible if possible else '')
            max_cell.alignment = center
            max_cell.border = border
            max_cell.font = Font(color='999999', size=10)
            if row_fill:
                max_cell.fill = row_fill

            col += 2

        # Total
        total_earned_cell = ws.cell(row=row_num, column=col, value=round(grand_earned, 2))
        total_earned_cell.font = Font(bold=True)
        total_earned_cell.alignment = center
        total_earned_cell.border = border

        total_possible_cell = ws.cell(row=row_num, column=col + 1, value=round(grand_possible, 2))
        total_possible_cell.alignment = center
        total_possible_cell.border = border
        total_possible_cell.font = Font(color='999999')

        # Percentage
        pct_val = round((grand_earned / grand_possible * 100), 1) if grand_possible > 0 else 0
        pct_data_cell = ws.cell(row=row_num, column=pct_col, value=f'{pct_val}%')
        pct_data_cell.alignment = center
        pct_data_cell.border = border
        pct_data_cell.font = Font(bold=True)
        pct_data_cell.fill = pass_fill if pct_val >= 60 else fail_fill

    # ── ILO description row at the bottom ───────────────────────────────
    desc_row = data_start + len(students) + 1
    ws.cell(row=desc_row, column=1, value='ILO Descriptions:').font = Font(bold=True, size=10)
    for i, ilo in enumerate(ilos):
        ws.cell(row=desc_row + 1 + i, column=1,
                value=f'ILO #{ilo.number}: {ilo.description} (Max: {ilo.osce_marks})')
        ws.cell(row=desc_row + 1 + i, column=1).font = Font(size=9, color='555555')

    # ── Column widths ───────────────────────────────────────────────────
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 28
    for ci in range(len(fixed_headers) + 1, pct_col + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 9

    # ── Freeze panes ────────────────────────────────────────────────────
    ws.freeze_panes = f'D{data_start}'

    # ── Response ────────────────────────────────────────────────────────
    filename = f'ILO_Scores_{exam.name}_{session.name}.xlsx'.replace(' ', '_')
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response
