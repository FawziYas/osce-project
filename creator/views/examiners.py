"""
Examiner management views – list, CRUD, unassign, bulk upload/download template.
"""
from datetime import datetime
from io import BytesIO
from django.utils import timezone
from django.conf import settings

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from core.models import Examiner, ExaminerAssignment, ExamSession


@login_required
def examiner_list(request):
    """List all examiners (active only). Deleted shown separately for admin/superuser."""
    examiners = Examiner.objects.filter(role='examiner', is_deleted=False).order_by('full_name')
    today = datetime.now().date()

    can_see_deleted = request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'
    deleted_examiners = Examiner.objects.filter(role='examiner', is_deleted=True).order_by('full_name') if can_see_deleted else []

    stats = {
        'total': Examiner.objects.filter(role='examiner', is_deleted=False).count(),
        'active': Examiner.objects.filter(role='examiner', is_active=True, is_deleted=False).count(),
        'assigned_today': ExaminerAssignment.objects.filter(
            session__session_date=today,
            examiner__role='examiner',
            examiner__is_deleted=False,
        ).values('examiner_id').distinct().count(),
        'total_assignments': ExaminerAssignment.objects.filter(
            examiner__role='examiner',
            examiner__is_deleted=False,
        ).count(),
    }

    return render(request, 'creator/examiners/list.html', {
        'examiners': examiners,
        'stats': stats,
        'deleted_examiners': deleted_examiners,
        'can_see_deleted': can_see_deleted,
    })


@login_required
def examiner_create(request):
    """Create a new examiner."""
    if request.method == 'POST':
        username = request.POST['username'].strip().lower()
        email = request.POST.get('email', '').strip().lower()

        if Examiner.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
            default_password = getattr(settings, 'DEFAULT_USER_PASSWORD', '123456789')
            return render(request, 'creator/examiners/form.html', {
                'examiner': None,
                'default_password': default_password,
            })

        if email and Examiner.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists.')
            default_password = getattr(settings, 'DEFAULT_USER_PASSWORD', '123456789')
            return render(request, 'creator/examiners/form.html', {
                'examiner': None,
                'default_password': default_password,
            })

        examiner = Examiner(
            username=username,
            email=email,
            full_name=request.POST['full_name'].strip(),
            title=request.POST.get('title', '').strip() or '',
            department=request.POST.get('department', '').strip() or '',
            is_active='is_active' in request.POST,
        )
        # Password is set automatically to DEFAULT_USER_PASSWORD by the
        # post_save signal.  User will be forced to change it on first login.
        examiner.save()

        messages.success(request, f'Examiner "{examiner.display_name}" created successfully.')
        return redirect('creator:examiner_list')

    default_password = getattr(settings, 'DEFAULT_USER_PASSWORD', '123456789')
    return render(request, 'creator/examiners/form.html', {
        'examiner': None,
        'default_password': default_password,
    })


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
        email = request.POST.get('email', '').strip().lower()
        if email and Examiner.objects.filter(email=email).exclude(pk=examiner_id).exists():
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
    """Soft-delete an examiner. Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        messages.error(request, 'Only admins and superusers can delete examiners.')
        return redirect('creator:examiner_list')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('creator:examiner_list')

    examiner = get_object_or_404(Examiner, pk=examiner_id, is_deleted=False)
    name = examiner.display_name
    examiner.is_deleted = True
    examiner.is_active = False
    examiner.deleted_at = timezone.now()
    examiner.save()

    messages.success(request, f'Examiner "{name}" has been deleted. You can restore them from the deleted list.')
    return redirect('creator:examiner_list')


@login_required
def examiner_restore(request, examiner_id):
    """Restore a soft-deleted examiner. Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        messages.error(request, 'Only admins and superusers can restore examiners.')
        return redirect('creator:examiner_list')

    if request.method != 'POST':
        return redirect('creator:examiner_list')

    examiner = get_object_or_404(Examiner, pk=examiner_id, is_deleted=True)
    examiner.is_deleted = False
    examiner.is_active = True
    examiner.deleted_at = None
    examiner.save()

    messages.success(request, f'Examiner "{examiner.display_name}" has been restored.')
    return redirect('creator:examiner_list')


@login_required
def examiner_permanent_delete(request, examiner_id):
    """Permanently delete an examiner. Superuser only.
    
    Station assignments are removed, but all scoring records are preserved
    with examiner shown as 'Deleted Examiner' in reports.
    """
    if not request.user.is_superuser:
        messages.error(request, 'Only superusers can permanently delete examiners.')
        return redirect('creator:examiner_list')

    if request.method != 'POST':
        return redirect('creator:examiner_list')

    examiner = get_object_or_404(Examiner, pk=examiner_id, is_deleted=True)
    name = examiner.display_name
    # StationScore records are preserved (SET_NULL on examiner FK)
    # ExaminerAssignment records are removed via CASCADE
    examiner.delete()

    messages.success(request, f'Examiner "{name}" permanently deleted. Their scoring records have been preserved.')
    return redirect('creator:examiner_list')


@login_required
def examiner_unassign(request, assignment_id):
    """Remove an examiner assignment."""
    assignment = get_object_or_404(ExaminerAssignment, pk=assignment_id)
    examiner_id = assignment.examiner_id

    session = ExamSession.objects.filter(pk=assignment.session_id).first()
    if session and session.actual_start and not request.user.is_superuser:
        messages.error(request, 'Cannot remove examiner assignments after session has been activated.')
        return redirect('creator:session_detail', session_id=str(session.id))

    session_id = assignment.session_id
    assignment.delete()
    messages.success(request, 'Assignment removed.')

    # Redirect back to where the user came from
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if next_url:
        return redirect(next_url)
    # If coming from session detail, go back there
    referer = request.META.get('HTTP_REFERER', '')
    if session_id and 'session' in referer:
        return redirect('creator:session_detail', session_id=str(session_id))
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

    headers = ['title', 'full_name', 'username', 'email', 'department']
    arabic_hints = [
        'اللقب (مثلاً Dr.)', 'الاسم الكامل', 'اسم المستخدم',
        'البريد الإلكتروني', 'القسم',
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

    sample = ['Dr.', 'Ahmed Mansour', 'ahmed_m', 'ahmed@example.com', 'Surgery']
    for col, val in enumerate(sample, 1):
        ws.cell(row=3, column=col, value=val)

    for i in range(1, 6):
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
        required = ['full_name', 'username']
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
                email = str(row[idx['email']]).strip().lower() if 'email' in idx and row[idx['email']] else ''
                full_name = str(row[idx['full_name']]).strip()
                title = str(row[idx.get('title', -1)]).strip() if 'title' in idx and row[idx['title']] else ''
                department = str(row[idx.get('department', -1)]).strip() if 'department' in idx and row[idx['department']] else ''

                if not all([username, full_name]):
                    errors_list.append(f'Row {row_num}: Missing required data')
                    continue

                if Examiner.objects.filter(username=username).exists():
                    errors_list.append(f"Row {row_num}: Username '{username}' already exists")
                    continue
                if email and Examiner.objects.filter(email=email).exists():
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
                # Password is set automatically by the post_save signal
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
    """List all coordinators with search. Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        messages.error(request, 'You do not have permission to manage coordinators.')
        return redirect('creator:dashboard')

    search_query = request.GET.get('search', '').strip()
    coordinators_qs = Examiner.objects.filter(role='coordinator').order_by('full_name')
    
    if search_query:
        coordinators_qs = coordinators_qs.filter(
            full_name__icontains=search_query
        ) | Examiner.objects.filter(
            role='coordinator', username__icontains=search_query
        ) | Examiner.objects.filter(
            role='coordinator', email__icontains=search_query
        )
        coordinators_qs = coordinators_qs.order_by('full_name').distinct()
    
    return render(request, 'creator/coordinators/list.html', {
        'coordinators': coordinators_qs,
        'search_query': search_query,
    })


@login_required
def coordinator_create(request):
    """Create a new coordinator. Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        messages.error(request, 'You do not have permission to add coordinators.')
        return redirect('creator:dashboard')

    default_password = getattr(settings, 'DEFAULT_USER_PASSWORD', '123456789')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip().lower()
        email = request.POST.get('email', '').strip().lower()
        full_name = request.POST.get('full_name', '').strip()

        if Examiner.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
            return render(request, 'creator/coordinators/form.html', {
                'default_password': default_password,
            })

        if Examiner.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists.')
            return render(request, 'creator/coordinators/form.html', {
                'default_password': default_password,
            })

        coordinator = Examiner(
            username=username,
            email=email,
            full_name=full_name,
            role='coordinator',
            is_active=True,
        )
        # Password is set automatically to DEFAULT_USER_PASSWORD by the
        # post_save signal.  User will be forced to change it on first login.
        coordinator.save()

        messages.success(request, f'Coordinator "{full_name}" created successfully.')
        return redirect('creator:coordinator_list')

    return render(request, 'creator/coordinators/form.html', {
        'default_password': default_password,
    })


@login_required
def coordinator_edit(request, coordinator_id):
    """Edit coordinator details. Admin/superuser only."""
    if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
        messages.error(request, 'You do not have permission to edit coordinators.')
        return redirect('creator:coordinator_list')
    
    coordinator = get_object_or_404(Examiner, pk=coordinator_id, role='coordinator')
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        is_active = request.POST.get('is_active') == 'on'
        
        if not full_name:
            messages.error(request, 'Full name is required.')
            return render(request, 'creator/coordinators/edit.html', {'coordinator': coordinator})
        
        # Check if email is already used by another coordinator
        if email != coordinator.email and Examiner.objects.filter(email=email, role='coordinator').exclude(id=coordinator_id).exists():
            messages.error(request, f'Email "{email}" is already used by another coordinator.')
            return render(request, 'creator/coordinators/edit.html', {'coordinator': coordinator})
        
        coordinator.full_name = full_name
        coordinator.email = email
        coordinator.is_active = is_active
        coordinator.save()
        
        messages.success(request, f'Coordinator "{full_name}" updated successfully.')
        return redirect('creator:coordinator_list')
    
    return render(request, 'creator/coordinators/edit.html', {'coordinator': coordinator})


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
