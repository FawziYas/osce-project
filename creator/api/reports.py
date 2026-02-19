"""
Creator API – Reports & export endpoints.
"""
import csv
import re
from datetime import datetime
from io import BytesIO, StringIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from core.models import (
    ChecklistItem,
    ExamSession,
    Examiner,
    ItemScore,
    Path,
    SessionStudent,
    Station,
    StationScore,
)


def _safe_filename(name: str) -> str:
    """Sanitize a string for safe use in Content-Disposition headers."""
    return re.sub(r'[^\w\-.]', '_', name)


@login_required
def get_session_summary(request, session_id):
    """GET /api/creator/reports/session/<id>/summary"""
    session = get_object_or_404(ExamSession, pk=session_id)
    students = list(SessionStudent.objects.filter(session=session))

    # Unique station numbers across all paths
    paths = list(Path.objects.filter(session=session))
    station_headers = []
    seen_nums = set()
    for p in paths:
        for s in p.stations.filter(active=True, is_deleted=False):
            if s.station_number not in seen_nums:
                station_headers.append({'number': s.station_number, 'name': s.name})
                seen_nums.add(s.station_number)
    station_headers.sort(key=lambda x: x['number'])

    # Pre-calculate station info
    station_info_map = {}
    for p in paths:
        for s in p.stations.filter(active=True, is_deleted=False):
            station_info_map[(p.id, s.station_number)] = {
                'id': s.id,
                'max_score': s.get_max_score(),
            }

    total_students = len(students)
    completed_students = 0
    total_percentage = 0
    passed_count = 0
    pass_threshold = 60

    student_data = []
    for student in students:
        student_scores = {}
        total_score = 0
        max_score = 0

        for header in station_headers:
            s_info = station_info_map.get((student.path_id, header['number']))
            if s_info:
                st_max = s_info['max_score']
                max_score += st_max
                final = StationScore.get_final_score(student.id, s_info['id'])
                if final:
                    student_scores[header['number']] = final['final_score']
                    total_score += final['final_score']
                else:
                    student_scores[header['number']] = None
            else:
                student_scores[header['number']] = None

        percentage = (total_score / max_score * 100) if max_score > 0 else 0

        if total_score > 0 or max_score > 0:
            completed_students += 1
            total_percentage += percentage
            if percentage >= pass_threshold:
                passed_count += 1

        path = Path.objects.filter(pk=student.path_id).first() if student.path_id else None

        student_data.append({
            'id': str(student.id),
            'student_number': student.student_number,
            'full_name': student.full_name,
            'path_name': path.name if path else None,
            'station_scores': student_scores,
            'total_score': round(total_score, 1),
            'max_score': round(max_score, 1),
            'percentage': round(percentage, 1),
            'passed': percentage >= pass_threshold,
        })

    avg_percentage = (total_percentage / completed_students) if completed_students > 0 else 0
    pass_rate = (passed_count / completed_students * 100) if completed_students > 0 else 0

    return JsonResponse({
        'success': True,
        'data': {
            'session_id': str(session_id),
            'session_name': session.name,
            'total_students': total_students,
            'completed_students': completed_students,
            'average_percentage': round(avg_percentage, 1),
            'pass_rate': round(pass_rate, 1),
            'station_headers': station_headers,
            'students': sorted(student_data, key=lambda x: x['full_name']),
        },
    })


# ── helpers ─────────────────────────────────────────────────────────────────
def _build_station_info(session_id):
    """Return (paths, station_headers, station_info_map) for a session."""
    paths = list(Path.objects.filter(session_id=session_id))
    station_headers = []
    seen = set()
    station_info_map = {}

    for p in paths:
        for s in p.stations.filter(active=True, is_deleted=False):
            station_info_map[(p.id, s.station_number)] = {
                'id': s.id,
                'max_score': s.get_max_score(),
            }
            if s.station_number not in seen:
                station_headers.append({'number': s.station_number, 'name': s.name})
                seen.add(s.station_number)

    station_headers.sort(key=lambda x: x['number'])
    return paths, station_headers, station_info_map


def _student_rows(students, station_headers, station_info_map):
    """Yield (row_list, total_score, max_score, percentage, pass_fail) for each student."""
    for student in students:
        row = [student.student_number, student.full_name]
        path = Path.objects.filter(pk=student.path_id).first() if student.path_id else None
        row.append(path.name if path else '')

        total_score = 0
        max_score = 0

        for header in station_headers:
            s_info = station_info_map.get((student.path_id, header['number']))
            score_val = ''
            if s_info:
                st_max = s_info['max_score']
                max_score += st_max
                final = StationScore.get_final_score(student.id, s_info['id'])
                if final:
                    score_val = round(final['final_score'], 1)
                    total_score += final['final_score']
                else:
                    score_val = ''
            row.append(score_val)

        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        pass_fail = 'PASS' if percentage >= 60 else 'FAIL'
        row.extend([round(total_score, 1), round(max_score, 1), round(percentage, 1), pass_fail])
        yield row, total_score, max_score, percentage, pass_fail


# ── CSV exports ─────────────────────────────────────────────────────────────

@login_required
def export_students_csv(request, session_id):
    """GET /api/creator/reports/session/<id>/students/csv"""
    session = get_object_or_404(ExamSession, pk=session_id)
    students = SessionStudent.objects.filter(session=session).order_by('full_name')
    _, station_headers, station_info_map = _build_station_info(session_id)

    output = StringIO()
    writer = csv.writer(output)

    headers = ['Student Number', 'Full Name', 'Path']
    headers.extend([f"St.{h['number']}: {h['name']}" for h in station_headers])
    headers.extend(['Total Score', 'Max Score', 'Percentage', 'Pass/Fail'])
    writer.writerow(headers)

    for row, *_ in _student_rows(students, station_headers, station_info_map):
        writer.writerow(row)

    filename = _safe_filename(f"{session.name}_students_{session_id}.csv")
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_students_xlsx(request, session_id):
    """GET /api/creator/reports/session/<id>/students/xlsx"""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    session = get_object_or_404(ExamSession, pk=session_id)
    students = list(SessionStudent.objects.filter(session=session).order_by('full_name'))
    _, station_headers, station_info_map = _build_station_info(session_id)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Student Results'

    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_alignment = Alignment(horizontal='center', vertical='center')

    base_headers = ['Student Number', 'Full Name', 'Path']
    station_cols = [f"St.{h['number']}: {h['name']}" for h in station_headers]
    end_headers = ['Total Score', 'Max Score', 'Percentage', 'Pass/Fail', 'Comments']
    all_headers = base_headers + station_cols + end_headers

    # Title rows
    last_col_letter = chr(64 + min(len(all_headers), 26))
    ws.merge_cells(f'A1:{last_col_letter}1')
    ws['A1'] = f"{session.name} - Student Results"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')

    ws.merge_cells(f'A2:{last_col_letter}2')
    ws['A2'] = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws['A2'].alignment = Alignment(horizontal='center')

    for col_num, header in enumerate(all_headers, 1):
        cell = ws.cell(row=4, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment

    row_num = 5
    for student in students:
        # Get all scores for this student
        # Only count submitted scores with marks, ignore empty submissions
        scores_qs = StationScore.objects.filter(
            session_student=student,
            status='submitted'
        ).exclude(
            total_score__isnull=True
        ).exclude(
            total_score=0
        ).select_related('examiner')
        
        # Build row with station scores
        row = [student.student_number, student.full_name]
        path = Path.objects.filter(pk=student.path_id).first() if student.path_id else None
        row.append(path.name if path else '')

        total_score = 0
        max_score = 0

        for header in station_headers:
            s_info = station_info_map.get((student.path_id, header['number']))
            score_val = ''
            if s_info:
                st_max = s_info['max_score']
                max_score += st_max
                final = StationScore.get_final_score(student.id, s_info['id'])
                if final:
                    score_val = round(final['final_score'], 1)
                    total_score += final['final_score']
                else:
                    score_val = ''
            row.append(score_val)

        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        pass_fail = 'PASS' if percentage >= 60 else 'FAIL'
        
        # Build comments with examiner names
        comments_list = []
        for score in scores_qs:
            if score.comments and score.comments.strip():
                examiner_name = score.examiner.full_name if score.examiner else "Unknown Examiner"
                station_obj = Station.objects.filter(pk=score.station_id).first()
                station_name = station_obj.name if station_obj else "Unknown Station"
                comments_list.append(f"{examiner_name} ({station_name}):\n{score.comments}")
        
        comments_text = "\n---\n".join(comments_list) if comments_list else ""
        
        row.extend([round(total_score, 1), round(max_score, 1), round(percentage, 1), pass_fail, comments_text])
        
        # Write row to worksheet
        for col_idx, value in enumerate(row, 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.value = value
            cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        
        # Color-code pass/fail
        pf_cell = ws.cell(row=row_num, column=len(row) - 1)
        if pass_fail == 'PASS':
            pf_cell.font = Font(color='006100', bold=True)
            pf_cell.fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
        else:
            pf_cell.font = Font(color='9C0006', bold=True)
            pf_cell.fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
        
        row_num += 1

    # Auto-adjust column widths
    for col_idx, col in enumerate(ws.columns, 1):
        max_len = 0
        for cell in col:
            try:
                if hasattr(cell, 'value') and cell.value and len(str(cell.value)) > max_len:
                    max_len = len(str(cell.value))
            except Exception:
                pass
        col_letter = get_column_letter(col_idx)
        # Make comments column wider
        if col_letter == get_column_letter(len(all_headers)):
            ws.column_dimensions[col_letter].width = 50
        else:
            ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = _safe_filename(f"{session.name}_students_{session_id}.xlsx")
    response = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_stations_csv(request, session_id):
    """GET /api/creator/reports/session/<id>/stations/csv"""
    session = get_object_or_404(ExamSession, pk=session_id)
    paths = Path.objects.filter(session_id=session_id)
    stations = []
    for p in paths:
        stations.extend(Station.objects.filter(path=p, active=True))

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Station Name', 'Path', 'Max Score', 'Avg Score', 'Avg %',
        'Min Score', 'Max Achieved', 'Students Marked',
    ])

    for station in stations:
        scores = StationScore.objects.filter(station=station)
        if scores.exists():
            total_scores = [s.total_score or 0 for s in scores]
            max_scores = [s.max_score or 0 for s in scores]
            avg_score = sum(total_scores) / len(total_scores)
            avg_max = sum(max_scores) / len(max_scores) if max_scores else 0
            avg_pct = (avg_score / avg_max * 100) if avg_max > 0 else 0
            path = Path.objects.filter(pk=station.path_id).first()
            writer.writerow([
                station.name,
                path.name if path else '',
                round(avg_max, 1),
                round(avg_score, 1),
                round(avg_pct, 1),
                round(min(total_scores), 1),
                round(max(total_scores), 1),
                len(total_scores),
            ])

    filename = _safe_filename(f"{session.name}_stations_{session_id}.csv")
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_raw_csv(request, session_id):
    """GET /api/creator/reports/session/<id>/raw/csv"""
    session = get_object_or_404(ExamSession, pk=session_id)
    students = SessionStudent.objects.filter(session=session)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Student Number', 'Student Name', 'Path', 'Station',
        'Item', 'Score', 'Max Score', 'Examiner', 'Timestamp',
    ])

    for student in students:
        station_scores = StationScore.objects.filter(session_student=student)
        for ss in station_scores:
            station = Station.objects.filter(pk=ss.station_id).first()
            examiner = Examiner.objects.filter(pk=ss.examiner_id).first()
            path = Path.objects.filter(pk=student.path_id).first() if student.path_id else None
            item_scores = ItemScore.objects.filter(station_score=ss)

            for iscore in item_scores:
                item = ChecklistItem.objects.filter(pk=iscore.checklist_item_id).first()
                writer.writerow([
                    student.student_number,
                    student.full_name,
                    path.name if path else '',
                    station.name if station else '',
                    item.description if item else '',
                    iscore.score or 0,
                    iscore.max_score or 0,
                    examiner.full_name if examiner else '',
                    iscore.scored_at or '',
                ])

    filename = _safe_filename(f"{session.name}_raw_{session_id}.csv")
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
