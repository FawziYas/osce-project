"""
Station Template Library views – CRUD for TemplateLibrary and StationTemplate,
plus apply-templates-to-session.
"""
import json
import os
import re

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.storage import default_storage
from django.db.models import Max

from core.models import (
    Exam, ExamSession, Path, ILO, StationTemplate, TemplateLibrary,
)
from core.utils.image_validators import validate_question_image, sanitize_image_filename

def _get_dept_folder(exam):
    """Return a filesystem-safe department folder name for image uploads."""
    dept = (exam.department or '').strip() if exam else ''
    if not dept:
        dept = 'general'
    return re.sub(r'[^\w\-]', '_', dept).strip('_') or 'general'


# Preset library colors
LIBRARY_COLORS = [
    ('#0d6efd', 'Blue'),
    ('#198754', 'Green'),
    ('#dc3545', 'Red'),
    ('#fd7e14', 'Orange'),
    ('#0dcaf0', 'Cyan'),
    ('#6f42c1', 'Purple'),
    ('#e83e8c', 'Pink'),
    ('#343a40', 'Dark Gray'),
]


def _is_dry_template_items(items):
    """Heuristic: dry templates contain MCQ/Essay scoring types."""
    for item in items or []:
        scoring_type = str(item.get('scoring_type', '')).lower()
        if scoring_type in {'mcq', 'essay'}:
            return True
    return False


def _process_template_item_images(request, items, exam=None):
    """Save any newly-uploaded item images into question_images/<dept>/ storage.
    Mutates items in-place, adding/updating 'image_path' for each item that
    has a file upload. Items that already carry an 'image_path' and have no
    new upload keep their existing path. Returns the (mutated) items list."""
    dept_folder = _get_dept_folder(exam)
    for item in items:
        item_id = item.get('item_id', '')
        img_file = request.FILES.get(f'item_image_{item_id}')
        if img_file:
            try:
                validate_question_image(img_file)
                img_file.seek(0)
                filename = sanitize_image_filename(img_file.name)
                path = default_storage.save(f'question_images/{dept_folder}/{filename}', img_file)
                item['image_path'] = path
            except DjangoValidationError as ve:
                messages.warning(request, f'Image for item skipped: {ve.message}')
    return items


def _existing_items_with_urls(request, items):
    """Return items list with 'image_url' resolved from 'image_path' for display."""
    result = []
    for item in items:
        item = dict(item)
        image_path = item.get('image_path')
        if image_path:
            try:
                url = default_storage.url(image_path)
                # Azure Storage returns an absolute URL already; local storage returns a relative path
                if url.startswith(('http://', 'https://')):
                    item['image_url'] = url
                else:
                    item['image_url'] = request.build_absolute_uri(url)
            except Exception:
                pass
        result.append(item)
    return result


def _get_checklist_json_from_request(request):
    """Support both legacy and dry form payload field names."""
    return request.POST.get('checklist_json') or request.POST.get('checklist_data', '[]')


# =============================================================================
# Station Library overview
# =============================================================================

@login_required
def station_library(request, exam_id):
    """View and manage station template libraries for an exam."""
    exam = get_object_or_404(Exam, pk=exam_id)
    libraries = TemplateLibrary.objects.filter(
        exam=exam, is_active=True
    ).order_by('display_order', 'id')
    unassigned_templates = StationTemplate.objects.filter(
        exam=exam, library__isnull=True, is_active=True
    ).order_by('display_order', 'id')

    for library in libraries:
        templates_for_view = list(library.active_templates)
        for template in templates_for_view:
            # Use stored is_dry flag; fall back to heuristic for legacy templates
            template.is_dry_template = template.is_dry or _is_dry_template_items(template.get_checklist_items())
        library.templates_for_view = templates_for_view

    unassigned_templates = list(unassigned_templates)
    for template in unassigned_templates:
        template.is_dry_template = template.is_dry or _is_dry_template_items(template.get_checklist_items())

    return render(request, 'creator/exams/station_library.html', {
        'exam': exam,
        'libraries': libraries,
        'unassigned_templates': unassigned_templates,
    })


# =============================================================================
# Template Library CRUD
# =============================================================================

@login_required
def template_library_create(request, exam_id):
    """Create a new template library."""
    exam = get_object_or_404(Exam, pk=exam_id)
    max_order = TemplateLibrary.objects.filter(exam=exam).aggregate(
        m=Max('display_order')
    )['m'] or 0

    if request.method == 'POST':
        TemplateLibrary.objects.create(
            exam=exam,
            name=request.POST['name'],
            description=request.POST.get('description', ''),
            color=request.POST.get('color', '#0d6efd'),
            display_order=max_order + 1,
            is_active=True,
        )
        messages.success(request, f'Template library "{request.POST["name"]}" created.')
        return redirect('creator:station_library', exam_id=str(exam_id))

    return render(request, 'creator/exams/library_form.html', {
        'exam': exam,
        'library': None,
        'next_order': max_order + 1,
        'colors': LIBRARY_COLORS,
    })


@login_required
def template_library_edit(request, library_id):
    """Edit a template library."""
    library = get_object_or_404(TemplateLibrary, pk=library_id)
    exam = library.exam

    if request.method == 'POST':
        library.name = request.POST['name']
        library.description = request.POST.get('description', '')
        library.color = request.POST.get('color', '#0d6efd')
        library.save()
        messages.success(request, f'Template library "{library.name}" updated.')
        return redirect('creator:station_library', exam_id=str(exam.id))

    return render(request, 'creator/exams/library_form.html', {
        'exam': exam,
        'library': library,
        'next_order': library.display_order,
        'colors': LIBRARY_COLORS,
    })


@login_required
def template_library_delete(request, library_id):
    """Hard-delete a template library."""
    library = get_object_or_404(TemplateLibrary, pk=library_id)
    exam_id = str(library.exam_id)
    name = library.name
    library.delete()
    messages.success(request, f'Template library "{name}" deleted.')
    return redirect('creator:station_library', exam_id=exam_id)


# =============================================================================
# Station Template CRUD
# =============================================================================

@login_required
def station_template_create(request, exam_id):
    """Create a new station template."""
    exam = get_object_or_404(Exam, pk=exam_id)
    library_id = request.GET.get('library_id') or request.POST.get('library_id')
    ilos = ILO.objects.filter(course_id=exam.course_id).order_by('number')
    libraries = TemplateLibrary.objects.filter(exam=exam, is_active=True).order_by('name')

    if not libraries.exists():
        messages.warning(
            request,
            'You must create a template library before adding templates. Please create a library first.',
        )
        return redirect('creator:template_library_create', exam_id=str(exam_id))

    max_order = StationTemplate.objects.filter(exam=exam).aggregate(
        m=Max('display_order')
    )['m'] or 0

    if request.method == 'POST':
        try:
            template = StationTemplate(
                exam=exam,
                library_id=int(request.POST['library_id']) if request.POST.get('library_id') else None,
                name=request.POST['name'],
                description=request.POST.get('description', ''),
                scenario=request.POST.get('scenario', ''),
                instructions=request.POST.get('instructions', ''),
                display_order=max_order + 1,
                is_active=True,
            )

            checklist_json_str = _get_checklist_json_from_request(request)
            try:
                items = json.loads(checklist_json_str)
                template.set_checklist_items(items)
            except json.JSONDecodeError as e:
                messages.error(request, f'Invalid checklist format: {str(e)}')
                items = []
                template.set_checklist_items(items)

            template.save()
            messages.success(
                request,
                f'Station template "{template.name}" created with {template.get_item_count()} items.',
            )
            return redirect('creator:station_library', exam_id=str(exam_id))
        except Exception as e:
            messages.error(request, f'Error creating template: {str(e)}')
            # Fall through to re-render form

    return render(request, 'creator/stations/template_form.html', {
        'exam': exam,
        'template': None,
        'ilos': ilos,
        'libraries': libraries,
        'selected_library_id': int(library_id) if library_id else None,
        'existing_items_json': '[]',
        'next_order': max_order + 1,
        'cancel_url': reverse('creator:station_library', kwargs={'exam_id': str(exam_id)}),
    })


@login_required
def station_template_create_dry(request, exam_id):
    """Create a new dry station template (MCQ/Essay)."""
    exam = get_object_or_404(Exam, pk=exam_id)
    library_id = request.GET.get('library_id') or request.POST.get('library_id')
    ilos = ILO.objects.filter(course_id=exam.course_id).order_by('number')
    libraries = TemplateLibrary.objects.filter(exam=exam, is_active=True).order_by('name')

    if not libraries.exists():
        messages.warning(
            request,
            'You must create a template library before adding templates. Please create a library first.',
        )
        return redirect('creator:template_library_create', exam_id=str(exam_id))

    max_order = StationTemplate.objects.filter(exam=exam).aggregate(
        m=Max('display_order')
    )['m'] or 0

    if request.method == 'POST':
        try:
            template = StationTemplate(
                exam=exam,
                library_id=int(request.POST['library_id']) if request.POST.get('library_id') else None,
                name=request.POST['name'],
                description=request.POST.get('description', ''),
                scenario=request.POST.get('scenario', ''),
                instructions=request.POST.get('instructions', ''),
                display_order=max_order + 1,
                is_dry=True,
                is_active=True,
            )

            checklist_json_str = _get_checklist_json_from_request(request)
            try:
                items = json.loads(checklist_json_str)
            except json.JSONDecodeError as e:
                messages.error(request, f'Invalid checklist format: {str(e)}')
                items = []

            # Save uploaded images and embed paths in JSON before storing
            _process_template_item_images(request, items, exam)
            template.set_checklist_items(items)
            template.save()
            messages.success(
                request,
                f'Dry template "{template.name}" created with {template.get_item_count()} items.',
            )
            return redirect('creator:station_library', exam_id=str(exam_id))
        except Exception as e:
            messages.error(request, f'Error creating dry template: {str(e)}')

    return render(request, 'creator/stations/Dry_template_form.html', {
        'exam': exam,
        'template': None,
        'station': None,
        'ilos': ilos,
        'libraries': libraries,
        'selected_library_id': int(library_id) if library_id else None,
        'existing_items_json': '[]',
        'next_order': max_order + 1,
        'cancel_url': reverse('creator:station_library', kwargs={'exam_id': str(exam_id)}),
    })


@login_required
def station_template_edit(request, template_id):
    """Edit a station template."""
    template = get_object_or_404(StationTemplate, pk=template_id)
    exam = template.exam
    ilos = ILO.objects.filter(course_id=exam.course_id).order_by('number')
    libraries = TemplateLibrary.objects.filter(exam=exam, is_active=True).order_by('name')
    existing_items = template.get_checklist_items()

    if request.method == 'POST':
        try:
            template.name = request.POST['name']
            template.scenario = request.POST.get('scenario', '')
            template.instructions = request.POST.get('instructions', '')
            template.library_id = int(request.POST['library_id']) if request.POST.get('library_id') else None

            checklist_json_str = _get_checklist_json_from_request(request)
            try:
                items = json.loads(checklist_json_str)
                template.set_checklist_items(items)
            except json.JSONDecodeError as e:
                messages.error(request, f'Invalid checklist format: {str(e)}')
                template.set_checklist_items([])

            template.save()
            messages.success(request, f'Station template "{template.name}" updated.')
            return redirect('creator:station_library', exam_id=str(exam.id))
        except Exception as e:
            messages.error(request, f'Error updating template: {str(e)}')
            # Fall through to re-render form

    return render(request, 'creator/stations/template_form.html', {
        'exam': exam,
        'template': template,
        'ilos': ilos,
        'libraries': libraries,
        'selected_library_id': template.library_id,
        'existing_items': existing_items,
        'existing_items_json': json.dumps(existing_items),
        'next_order': template.display_order,
        'cancel_url': reverse('creator:station_library', kwargs={'exam_id': str(exam.id)}),
    })


@login_required
def station_template_edit_dry(request, template_id):
    """Edit a dry station template (MCQ/Essay)."""
    template = get_object_or_404(StationTemplate, pk=template_id)
    exam = template.exam
    ilos = ILO.objects.filter(course_id=exam.course_id).order_by('number')
    libraries = TemplateLibrary.objects.filter(exam=exam, is_active=True).order_by('name')
    existing_items = template.get_checklist_items()

    if request.method == 'POST':
        try:
            template.name = request.POST['name']
            template.scenario = request.POST.get('scenario', '')
            template.instructions = request.POST.get('instructions', '')
            template.library_id = int(request.POST['library_id']) if request.POST.get('library_id') else None

            checklist_json_str = _get_checklist_json_from_request(request)
            try:
                items = json.loads(checklist_json_str)
            except json.JSONDecodeError as e:
                messages.error(request, f'Invalid checklist format: {str(e)}')
                items = []

            # Save uploaded images and embed paths in JSON before storing
            _process_template_item_images(request, items, exam)
            template.set_checklist_items(items)

            template.save()
            messages.success(request, f'Dry template "{template.name}" updated.')
            return redirect('creator:station_library', exam_id=str(exam.id))
        except Exception as e:
            messages.error(request, f'Error updating dry template: {str(e)}')
            # Reload from DB so existing_items reflects current saved state
            existing_items = template.get_checklist_items()

    existing_items_for_display = _existing_items_with_urls(request, existing_items)
    return render(request, 'creator/stations/Dry_template_form.html', {
        'exam': exam,
        'template': template,
        'station': template,
        'ilos': ilos,
        'libraries': libraries,
        'selected_library_id': template.library_id,
        'existing_items': existing_items,
        'existing_items_json': json.dumps(existing_items_for_display),
        'next_order': template.display_order,
        'cancel_url': reverse('creator:station_library', kwargs={'exam_id': str(exam.id)}),
    })


@login_required
def station_template_delete(request, template_id):
    """Hard-delete a station template."""
    template = get_object_or_404(StationTemplate, pk=template_id)
    exam_id = str(template.exam_id)
    name = template.name
    template.delete()
    messages.success(request, f'Station template "{name}" deleted.')
    return redirect('creator:station_library', exam_id=exam_id)


# =============================================================================
# Apply templates to session
# =============================================================================

@login_required
def apply_station_templates(request, session_id):
    """Apply station templates to all paths in this session."""
    session = get_object_or_404(ExamSession, pk=session_id)
    exam = session.exam
    paths = list(Path.objects.filter(session=session, is_deleted=False).order_by('name'))

    library_id = request.GET.get('library_id')
    libraries = TemplateLibrary.objects.filter(exam=exam, is_active=True).order_by('name')

    if library_id:
        templates = StationTemplate.objects.filter(
            exam=exam, library_id=int(library_id), is_active=True
        ).order_by('display_order')
        selected_library = TemplateLibrary.objects.filter(pk=int(library_id)).first()
    else:
        templates = StationTemplate.objects.filter(
            exam=exam, is_active=True
        ).order_by('display_order')
        selected_library = None

    if request.method == 'POST':
        selected_ids = request.POST.getlist('template_ids')
        if not selected_ids:
            messages.warning(request, 'Please select at least one station template to apply.')
            return redirect(
                'creator:apply_station_templates',
                session_id=str(session_id),
            )

        station_count = 0
        for tid in selected_ids:
            tmpl = StationTemplate.objects.filter(pk=int(tid)).first()
            if not tmpl:
                continue
            for p in paths:
                station = tmpl.apply_to_path(str(p.id))
                if station:
                    station_count += 1

        messages.success(
            request,
            f'Applied {len(selected_ids)} template(s) to all {len(paths)} path(s), '
            f'creating {station_count} stations total.',
        )
        return redirect('creator:session_detail', session_id=str(session_id))

    return render(request, 'creator/sessions/apply_templates.html', {
        'session': session,
        'exam': exam,
        'paths': paths,
        'templates': templates,
        'libraries': libraries,
        'selected_library': selected_library,
    })
