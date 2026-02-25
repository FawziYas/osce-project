"""
Station Template Library views – CRUD for TemplateLibrary and StationTemplate,
plus apply-templates-to-session.
"""
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max

from core.models import (
    Exam, ExamSession, Path, ILO, StationTemplate, TemplateLibrary,
)


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
    })


@login_required
def template_library_delete(request, library_id):
    """Soft-delete a template library."""
    library = get_object_or_404(TemplateLibrary, pk=library_id)
    exam_id = str(library.exam_id)
    library.is_active = False
    library.save()
    messages.success(request, f'Template library "{library.name}" deleted.')
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

            checklist_json_str = request.POST.get('checklist_json', '[]')
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

            checklist_json_str = request.POST.get('checklist_json', '[]')
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
def station_template_delete(request, template_id):
    """Soft-delete a station template."""
    template = get_object_or_404(StationTemplate, pk=template_id)
    exam_id = str(template.exam_id)
    template.is_active = False
    template.save()
    messages.success(request, f'Station template "{template.name}" deleted.')
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
