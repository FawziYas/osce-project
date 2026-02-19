"""
Student management views – add from textarea and XLSX upload.
"""
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from core.models import ExamSession, SessionStudent, Path


@login_required
def add_students(request, session_id):
    """Add students to a session from textarea (number,name per line)."""
    session = get_object_or_404(ExamSession, pk=session_id)
    paths = list(Path.objects.filter(session=session, is_deleted=False).order_by('name'))

    student_data = request.POST.get('student_list', '')
    path_id = request.POST.get('path_id', '')

    students_to_add = []
    for line in student_data.strip().split('\n'):
        if ',' in line:
            parts = line.strip().split(',', 1)
            if len(parts) == 2:
                students_to_add.append((parts[0].strip(), parts[1].strip()))

    if not students_to_add:
        return JsonResponse({
            'success': False,
            'message': 'No valid student data found. Format: student_number,full_name',
        })

    added = 0
    skipped = 0
    for i, (number, name) in enumerate(students_to_add):
        if SessionStudent.objects.filter(session=session, student_number=number).exists():
            skipped += 1
            continue

        assigned_path_id = None
        if path_id:
            assigned_path_id = path_id
        elif paths:
            assigned_path_id = str(paths[i % len(paths)].id)

        SessionStudent.objects.create(
            session=session,
            student_number=number,
            full_name=name,
            path_id=assigned_path_id,
            status='registered',
        )
        added += 1

    if added > 0 and skipped > 0:
        return JsonResponse({
            'success': True,
            'message': f'Added {added} students to session.',
            'warning': f'{skipped} duplicate(s) were skipped.',
        })
    elif added > 0:
        return JsonResponse({'success': True, 'message': f'Added {added} students to session.'})
    elif skipped > 0:
        return JsonResponse({
            'success': False,
            'message': f'All {skipped} students were already in this session.',
        })
    return JsonResponse({'success': False, 'message': 'No students to add.'})


@login_required
def upload_students_xlsx(request, session_id):
    """Upload students from XLSX file."""
    import openpyxl

    session = get_object_or_404(ExamSession, pk=session_id)
    paths = list(Path.objects.filter(session=session, is_deleted=False).order_by('name'))

    if 'file' not in request.FILES:
        return JsonResponse({'success': False, 'message': 'No file uploaded.'})

    f = request.FILES['file']
    if not f.name.endswith('.xlsx'):
        return JsonResponse({'success': False, 'message': 'Please upload an .xlsx file.'})

    # File size validation (5 MB max)
    max_size = 5 * 1024 * 1024
    if f.size > max_size:
        return JsonResponse({'success': False, 'message': 'File too large. Maximum size is 5 MB.'})

    path_id = request.POST.get('path_id', '')

    try:
        wb = openpyxl.load_workbook(f)
        ws = wb.active

        students_to_add = []
        first_row = True
        for row in ws.iter_rows(values_only=True):
            if not any(row):
                continue
            number = str(row[0]).strip() if row[0] is not None else ''
            name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''

            if first_row:
                if number.lower() in ('student_number', 'id', 'number', 'student_id'):
                    first_row = False
                    continue
                first_row = False

            if number and name:
                students_to_add.append((number, name))

        if not students_to_add:
            return JsonResponse({'success': False, 'message': 'No valid student data found in XLSX.'})

        added = 0
        skipped = 0
        for i, (number, name) in enumerate(students_to_add):
            if SessionStudent.objects.filter(session=session, student_number=number).exists():
                skipped += 1
                continue

            assigned_path_id = None
            if path_id:
                assigned_path_id = path_id
            elif paths:
                assigned_path_id = str(paths[i % len(paths)].id)

            SessionStudent.objects.create(
                session=session,
                student_number=number,
                full_name=name,
                path_id=assigned_path_id,
                status='registered',
            )
            added += 1

        if added > 0 and skipped > 0:
            return JsonResponse({
                'success': True,
                'message': f'Uploaded {added} students from XLSX.',
                'warning': f'{skipped} duplicate(s) were skipped.',
            })
        elif added > 0:
            return JsonResponse({'success': True, 'message': f'Uploaded {added} students from XLSX.'})
        elif skipped > 0:
            return JsonResponse({
                'success': False,
                'message': f'All {skipped} students were already in this session.',
            })
        return JsonResponse({'success': False, 'message': 'No students found in XLSX.'})

    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error reading XLSX: {e}'})
