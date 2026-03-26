"""
Student management views – add from textarea and XLSX upload.
"""
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from core.models import Exam, ExamSession, SessionStudent, Path
from core.utils.audit import AuditLogService
from core.utils.roles import scope_queryset


def validate_registration_number(number):
    """Validate that registration number contains only digits."""
    if not number.isdigit():
        return False, 'Registration number must contain numbers only.'
    return True, None


@login_required
@require_POST
def add_students(request, session_id):
    """Add students to a session from textarea (number,name per line)."""
    session = get_object_or_404(ExamSession, pk=session_id)
    paths = list(Path.objects.filter(session=session, is_deleted=False).order_by('name'))

    student_data = request.POST.get('student_list', '')
    path_id = request.POST.get('path_id', '')
    # 'auto' means auto-distribute across paths (explicit user choice)
    if path_id == 'auto':
        path_id = ''

    students_to_add = []
    validation_errors = []
    for line_num, line in enumerate(student_data.strip().split('\n'), 1):
        if ',' in line:
            parts = line.strip().split(',', 1)
            if len(parts) == 2:
                number = parts[0].strip()
                name = parts[1].strip()
                
                # Validate registration number
                if number:
                    is_valid, error_msg = validate_registration_number(number)
                    if not is_valid:
                        validation_errors.append(f'Line {line_num}: {error_msg}')
                        continue
                
                students_to_add.append((number, name))
    
    # Return validation errors if any
    if validation_errors:
        return JsonResponse({
            'success': False,
            'message': 'Validation errors found:',
            'errors': validation_errors,
        })

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
        AuditLogService.log(
            action='STUDENT_BULK_IMPORT',
            resource=session,
            request=request,
            description=f'Added {added} students to session {session.name} (textarea), {skipped} skipped',
            extra={'added': added, 'skipped': skipped},
        )
        return JsonResponse({
            'success': True,
            'message': f'Added {added} students to session.',
            'warning': f'{skipped} duplicate(s) were skipped.',
        })
    elif added > 0:
        AuditLogService.log(
            action='STUDENT_BULK_IMPORT',
            resource=session,
            request=request,
            description=f'Added {added} students to session {session.name} (textarea)',
            extra={'added': added},
        )
        return JsonResponse({'success': True, 'message': f'Added {added} students to session.'})
    elif skipped > 0:
        return JsonResponse({
            'success': False,
            'message': f'All {skipped} students were already in this session.',
        })
    return JsonResponse({'success': False, 'message': 'No students to add.'})


@login_required
@require_POST
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
    # 'auto' means auto-distribute across paths (explicit user choice)
    if path_id == 'auto':
        path_id = ''

    try:
        wb = openpyxl.load_workbook(f)
        ws = wb.active

        def _sanitize_cell(val):
            """Strip formula-triggering prefixes from imported cell values."""
            if not isinstance(val, str):
                return val
            if val and val[0] in ('=', '+', '@', '\t', '\r'):
                return val.lstrip('=+@\t\r')
            return val

        students_to_add = []
        first_row = True
        validation_errors = []
        row_num = 0
        for row in ws.iter_rows(values_only=True):
            row_num += 1
            if not any(row):
                continue
            number = str(row[0]).strip() if row[0] is not None else ''
            name = _sanitize_cell(str(row[1]).strip()) if len(row) > 1 and row[1] is not None else ''

            if first_row:
                if number.lower() in ('student_number', 'id', 'number', 'student_id'):
                    first_row = False
                    continue
                first_row = False

            if number and name:
                # Validate registration number
                is_valid, error_msg = validate_registration_number(number)
                if not is_valid:
                    validation_errors.append(f'Row {row_num}: {error_msg}')
                    continue
                students_to_add.append((number, name))
        
        # Return validation errors if any
        if validation_errors:
            return JsonResponse({
                'success': False,
                'message': 'Validation errors found in XLSX:',
                'errors': validation_errors,
            })

        if not students_to_add:
            error_msg = 'No valid student data found in XLSX.'
            if validation_errors:
                error_msg += ' Check registration numbers - they must contain only digits.'
            return JsonResponse({'success': False, 'message': error_msg})

        added = 0
        skipped = 0
        invalid_count = 0
        for i, (number, name) in enumerate(students_to_add):
            if SessionStudent.objects.filter(session=session, student_number=number).exists():
                skipped += 1
                continue
            
            assigned_path_id = None
            if path_id:
                assigned_path_id = path_id
            elif paths:
                assigned_path_id = str(paths[i % len(paths)].id)
            
            try:
                SessionStudent.objects.create(
                    session=session,
                    student_number=number,
                    full_name=name,
                    path_id=assigned_path_id,
                    status='registered',
                )
                added += 1
            except ValidationError as ve:
                invalid_count += 1
                continue

        if added > 0 and skipped > 0:
            AuditLogService.log(
                action='STUDENT_BULK_IMPORT',
                resource=session,
                request=request,
                description=f'Uploaded {added} students from XLSX to session {session.name}, {skipped} skipped',
                extra={'added': added, 'skipped': skipped, 'source': 'xlsx'},
            )
            return JsonResponse({
                'success': True,
                'message': f'Uploaded {added} students from XLSX.',
                'warning': f'{skipped} duplicate(s) were skipped.',
            })
        elif added > 0:
            AuditLogService.log(
                action='STUDENT_BULK_IMPORT',
                resource=session,
                request=request,
                description=f'Uploaded {added} students from XLSX to session {session.name}',
                extra={'added': added, 'source': 'xlsx'},
            )
            return JsonResponse({'success': True, 'message': f'Uploaded {added} students from XLSX.'})
        elif skipped > 0:
            return JsonResponse({
                'success': False,
                'message': f'All {skipped} students were already in this session.',
            })
        return JsonResponse({'success': False, 'message': 'No students found in XLSX.'})

    except Exception as e:
        error_msg = str(e)
        if 'Registration number must contain' in error_msg:
            return JsonResponse({'success': False, 'message': error_msg})
        return JsonResponse({'success': False, 'message': f'Error reading XLSX: {e}'})


@login_required
@require_GET
def students_upload_status(request, session_id):
    """
    Poll the status of an async student import task.
    GET /sessions/<id>/students/upload-status/?task_id=<uuid>
    Returns: {status: 'pending'|'done'|'error', ...}
    """
    from django.core.cache import cache

    task_id = request.GET.get('task_id', '')
    if not task_id:
        return JsonResponse({'status': 'error', 'message': 'Missing task_id'}, status=400)

    result = cache.get(f'osce:students_import:{task_id}')
    if result is None:
        return JsonResponse({'status': 'pending'})
    return JsonResponse(result)


@permission_required('core.can_view_student_list', raise_exception=True)
def student_list(request):
    """Global student list — all students across all sessions, filterable by Exam/Session.
    
    Requires: core.can_view_student_list permission
    Dept-scoped: coordinators only see their department's exams and students.
    """
    from uuid import UUID
    
    # Scope exams to user's department
    all_exams = scope_queryset(
        request.user,
        Exam.objects.filter(is_deleted=False).select_related('course__department'),
        dept_field='course__department',
    ).order_by('name')

    # GET filters
    exam_id = request.GET.get('exam_id', '').strip()
    session_id = request.GET.get('session_id', '').strip()
    search_q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    # Validate exam_id is a valid UUID (ignore if empty or invalid)
    valid_exam_id = None
    if exam_id:
        try:
            UUID(exam_id)  # Validate UUID format
            valid_exam_id = exam_id
        except (ValueError, ValidationError):
            exam_id = ''  # Reset to empty if invalid

    # Validate session_id is a valid UUID (ignore if empty or invalid)
    valid_session_id = None
    if session_id:
        try:
            UUID(session_id)  # Validate UUID format
            valid_session_id = session_id
        except (ValueError, ValidationError):
            session_id = ''  # Reset to empty if invalid

    # Sessions for the selected exam (for the session dropdown) — scoped by dept
    sessions_for_exam = []
    if valid_exam_id:
        sessions_qs = ExamSession.objects.filter(exam_id=valid_exam_id).order_by('session_date')
        sessions_qs = scope_queryset(request.user, sessions_qs, dept_field='exam__course__department')
        sessions_for_exam = sessions_qs

    # Build queryset — scoped to user's department
    qs = SessionStudent.objects.select_related(
        'session', 'session__exam', 'path'
    ).filter(session__exam__is_deleted=False)
    qs = scope_queryset(request.user, qs, dept_field='session__exam__course__department')

    # If exam_id is not selected (empty or "Select Exam" placeholder), return empty queryset
    # This ensures "Select Exam" shows no results instead of all students
    if not valid_exam_id:
        qs = qs.none()  # Return empty queryset
    else:
        qs = qs.filter(session__exam_id=valid_exam_id)
        if valid_session_id:
            qs = qs.filter(session_id=valid_session_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search_q:
            qs = qs.filter(
                Q(full_name__icontains=search_q) | Q(student_number__icontains=search_q)
            )

    qs = qs.order_by('session__session_date', 'student_number')

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    status_choices = [
        ('registered', 'Registered'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    return render(request, 'creator/students/list.html', {
        'page_obj': page_obj,
        'all_exams': all_exams,
        'sessions_for_exam': sessions_for_exam,
        'selected_exam_id': exam_id,  # Pass original exam_id for form preservation
        'selected_session_id': session_id,  # Pass original session_id for form preservation
        'search_q': search_q,
        'status_filter': status_filter,
        'status_choices': status_choices,
        'total_count': qs.count(),
    })
