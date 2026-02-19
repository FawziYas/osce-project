"""
Examiner management views – list, CRUD, unassign, bulk upload/download template.
"""
from datetime import datetime
from io import BytesIO

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from core.models import Examiner, ExaminerAssignment, ExamSession


@login_required
def examiner_list(request):
    """List all examiners."""
    examiners = Examiner.objects.filter(role='examiner').order_by('full_name')
    today = datetime.now().date()

    stats = {
        'total': Examiner.objects.filter(role='examiner').count(),
        'active': Examiner.objects.filter(role='examiner', is_active=True).count(),
        'assigned_today': ExaminerAssignment.objects.filter(
            session__session_date=today,
            examiner__role='examiner',
        ).values('examiner_id').distinct().count(),
        'total_assignments': ExaminerAssignment.objects.filter(
            examiner__role='examiner',
        ).count(),
    }

    return render(request, 'creator/examiners/list.html', {
        'examiners': examiners,
        'stats': stats,
    })


@login_required
def examiner_create(request):
    """Create a new examiner."""
    if request.method == 'POST':
        username = request.POST['username'].strip().lower()
        email = request.POST['email'].strip().lower()

        if Examiner.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
            return render(request, 'creator/examiners/form.html', {'examiner': None})

        if Examiner.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists.')
            return render(request, 'creator/examiners/form.html', {'examiner': None})

        examiner = Examiner(
            username=username,
            email=email,
            full_name=request.POST['full_name'].strip(),
            title=request.POST.get('title', '').strip() or '',
            department=request.POST.get('department', '').strip() or '',
            is_active='is_active' in request.POST,
        )
        examiner.set_password(request.POST['password'])
        examiner.save()

        messages.success(request, f'Examiner "{examiner.display_name}" created successfully.')
        return redirect('creator:examiner_list')

    return render(request, 'creator/examiners/form.html', {'examiner': None})


@login_required
def examiner_detail(request, examiner_id):
    """View examiner details and assignments."""
    examiner = get_object_or_404(Examiner, pk=examiner_id)
    assignments = ExaminerAssignment.objects.filter(
        examiner=examiner
    ).select_related('session', 'station')

    return render(request, 'creator/examiners/detail.html', {
        'examiner': examiner,
        'assignments': assignments,
    })


@login_required
def examiner_edit(request, examiner_id):
    """Edit an examiner."""
    examiner = get_object_or_404(Examiner, pk=examiner_id)

    if request.method == 'POST':
        email = request.POST['email'].strip().lower()
        if Examiner.objects.filter(email=email).exclude(pk=examiner_id).exists():
            messages.error(request, f'Email "{email}" is already used by another examiner.')
            return render(request, 'creator/examiners/form.html', {'examiner': examiner})

        examiner.email = email
        examiner.full_name = request.POST['full_name'].strip()
        examiner.title = request.POST.get('title', '').strip() or ''
        examiner.department = request.POST.get('department', '').strip() or ''
        examiner.is_active = 'is_active' in request.POST

        password = request.POST.get('password', '').strip()
        if password:
            examiner.set_password(password)

        examiner.save()
        messages.success(request, f'Examiner "{examiner.display_name}" updated.')
        return redirect('creator:examiner_detail', examiner_id=examiner_id)

    return render(request, 'creator/examiners/form.html', {'examiner': examiner})


@login_required
def examiner_delete(request, examiner_id):
    """Delete an examiner (hard delete). Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        messages.error(request, 'Only admins and superusers can delete examiners.')
        return redirect('creator:examiner_list')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('creator:examiner_list')

    examiner = get_object_or_404(Examiner, pk=examiner_id)
    name = examiner.display_name

    ExaminerAssignment.objects.filter(examiner=examiner).delete()
    examiner.delete()

    messages.success(request, f'Examiner "{name}" deleted successfully.')
    return redirect('creator:examiner_list')


@login_required
def examiner_unassign(request, assignment_id):
    """Remove an examiner assignment."""
    assignment = get_object_or_404(ExaminerAssignment, pk=assignment_id)
    examiner_id = assignment.examiner_id

    session = ExamSession.objects.filter(pk=assignment.session_id).first()
    if session and session.actual_start:
        messages.error(request, 'Cannot remove examiner assignments after session has been activated.')
        return redirect('creator:session_detail', session_id=str(session.id))

    assignment.delete()
    messages.success(request, 'Assignment removed.')
    return redirect('creator:examiner_detail', examiner_id=examiner_id)


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------

@login_required
def examiner_download_template(request):
    """Download an XLSX template for bulk examiner upload."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Examiners Template'

    headers = ['title', 'full_name', 'username', 'email', 'password', 'department']
    arabic_hints = [
        'اللقب (مثلاً Dr.)', 'الاسم الكامل', 'اسم المستخدم',
        'البريد الإلكتروني', 'كلمة المرور', 'القسم',
    ]

    header_fill = PatternFill(start_color='CFE2F3', end_color='CFE2F3', fill_type='solid')
    header_font = Font(bold=True)

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

        hint = ws.cell(row=2, column=col, value=arabic_hints[col - 1])
        hint.font = Font(italic=True, color='666666')
        hint.alignment = Alignment(horizontal='right')

    sample = ['Dr.', 'Ahmed Mansour', 'ahmed_m', 'ahmed@example.com', 'ahmed123', 'Surgery']
    for col, val in enumerate(sample, 1):
        ws.cell(row=3, column=col, value=val)

    for i in range(1, 7):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = 20

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f'examiner_upload_template_{datetime.now():%Y%m%d}.xlsx'
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response


@login_required
def examiner_bulk_upload(request):
    """Handle XLSX upload for bulk examiner creation."""
    import openpyxl

    if request.method != 'POST' or 'file' not in request.FILES:
        messages.error(request, 'No file uploaded')
        return redirect('creator:examiner_list')

    f = request.FILES['file']
    if not f.name.endswith('.xlsx'):
        messages.error(request, 'Please upload an .xlsx file')
        return redirect('creator:examiner_list')

    # File size validation (5 MB max)
    max_size = 5 * 1024 * 1024
    if f.size > max_size:
        messages.error(request, 'File too large. Maximum size is 5 MB.')
        return redirect('creator:examiner_list')

    try:
        wb = openpyxl.load_workbook(f)
        ws = wb.active

        headers = [str(c.value).strip().lower() for c in ws[1] if c.value]
        required = ['full_name', 'username', 'email', 'password']
        for field in required:
            if field not in headers:
                messages.error(request, f'Missing required column: {field}')
                return redirect('creator:examiner_list')

        idx = {h: i for i, h in enumerate(headers)}
        success_count = 0
        errors_list = []

        for row_num, row in enumerate(ws.iter_rows(min_row=3, values_only=True), 3):
            if not any(row):
                continue
            try:
                username = str(row[idx['username']]).strip().lower()
                email = str(row[idx['email']]).strip().lower()
                full_name = str(row[idx['full_name']]).strip()
                password = str(row[idx['password']])
                title = str(row[idx.get('title', -1)]).strip() if 'title' in idx and row[idx['title']] else ''
                department = str(row[idx.get('department', -1)]).strip() if 'department' in idx and row[idx['department']] else ''

                if not all([username, email, full_name, password]):
                    errors_list.append(f'Row {row_num}: Missing required data')
                    continue

                if Examiner.objects.filter(username=username).exists():
                    errors_list.append(f"Row {row_num}: Username '{username}' already exists")
                    continue
                if Examiner.objects.filter(email=email).exists():
                    errors_list.append(f"Row {row_num}: Email '{email}' already exists")
                    continue

                new_examiner = Examiner(
                    username=username,
                    email=email,
                    full_name=full_name,
                    title=title,
                    department=department,
                    is_active=True,
                )
                new_examiner.set_password(password)
                new_examiner.save()
                success_count += 1
            except Exception as e:
                errors_list.append(f'Row {row_num}: {e}')

        if success_count:
            messages.success(request, f'Successfully imported {success_count} examiners.')
        if errors_list:
            messages.warning(request, f'Failed to import {len(errors_list)} rows.')
            for err in errors_list[:5]:
                messages.error(request, err)
            if len(errors_list) > 5:
                messages.error(request, f'...and {len(errors_list) - 5} more errors.')

    except Exception as e:
        messages.error(request, f'Error processing file: {e}')

    return redirect('creator:examiner_list')


# ── Coordinator management (staff/superuser only) ──────────────────

@login_required
def coordinator_list(request):
    """List all coordinators. Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        messages.error(request, 'You do not have permission to manage coordinators.')
        return redirect('creator:dashboard')

    coordinators = Examiner.objects.filter(role='coordinator').order_by('full_name')
    return render(request, 'creator/coordinators/list.html', {
        'coordinators': coordinators,
    })


@login_required
def coordinator_create(request):
    """Create a new coordinator. Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        messages.error(request, 'You do not have permission to add coordinators.')
        return redirect('creator:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip().lower()
        email = request.POST.get('email', '').strip().lower()
        full_name = request.POST.get('full_name', '').strip()
        password = request.POST.get('password', '')

        if Examiner.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
            return render(request, 'creator/coordinators/form.html')

        if Examiner.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists.')
            return render(request, 'creator/coordinators/form.html')

        coordinator = Examiner(
            username=username,
            email=email,
            full_name=full_name,
            role='coordinator',
            is_active=True,
        )
        coordinator.set_password(password)
        coordinator.save()

        messages.success(request, f'Coordinator "{full_name}" created successfully.')
        return redirect('creator:coordinator_list')

    return render(request, 'creator/coordinators/form.html')


@login_required
def coordinator_delete(request, coordinator_id):
    """Delete a coordinator. Superuser only."""
    if not request.user.is_superuser:
        messages.error(request, 'Only superusers can delete coordinators.')
        return redirect('creator:coordinator_list')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('creator:coordinator_list')

    coordinator = get_object_or_404(Examiner, pk=coordinator_id, role='coordinator')
    full_name = coordinator.full_name
    coordinator.delete()
    messages.success(request, f'Coordinator "{full_name}" deleted successfully.')
    return redirect('creator:coordinator_list')
