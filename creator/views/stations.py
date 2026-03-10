"""
Station CRUD views – create, detail, edit, delete, restore.
"""
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.http import HttpResponseForbidden

from core.models import ILO, Station, ChecklistItem, Path, ExamSession
from core.utils.roles import check_path_department, check_station_department
from core.utils.image_validators import validate_question_image, sanitize_image_filename


@login_required
def station_create(request, path_id):
    """Create a new station within a path — dept-scoped."""
    path = get_object_or_404(Path, pk=path_id)
    if not check_path_department(request.user, path):
        return HttpResponseForbidden('You do not have access to this path.')
    exam = path.exam
    ilos = ILO.objects.filter(course_id=exam.course_id).order_by('number')
    max_num = Station.objects.filter(path=path).aggregate(m=Max('station_number'))['m'] or 0

    if request.method == 'POST':
        try:
            duration = int(request.POST.get('duration_minutes', path.rotation_minutes or 8))

            station = Station(
                path=path,
                exam_id=exam.id,
                station_number=max_num + 1,
                name=request.POST['name'],
                scenario=request.POST.get('scenario', ''),
                instructions=request.POST.get('instructions', ''),
                duration_minutes=duration,
                active=True,
            )

            # Sync path rotation
            path.rotation_minutes = duration
            path.save()
            Station.objects.filter(path=path, active=True).update(duration_minutes=duration)

            station.save()

            # Parse checklist JSON
            checklist_json_str = request.POST.get('checklist_data', '[]')
            try:
                checklist_items = json.loads(checklist_json_str)
            except json.JSONDecodeError as e:
                messages.error(request, f'Invalid checklist format: {str(e)}')
                station.delete()
                checklist_items = []

            # Validate ILO assignment
            missing = []
            for idx, item_data in enumerate(checklist_items):
                if not item_data.get('ilo_id') or not str(item_data['ilo_id']).strip():
                    desc = item_data.get('description', '')[:50]
                    missing.append(f'Item {idx + 1}: {desc}')

            if missing:
                station.delete()
                error_msg = (
                    f'Error: {len(missing)} checklist item(s) missing ILO assignment. '
                    'Please assign an ILO to each item before saving.'
                )
                messages.error(request, error_msg)
                return render(request, 'creator/stations/form_simple.html', {
                    'path': path,
                    'exam': exam,
                    'station': None,
                    'ilos': ilos,
                    'existing_items': [],
                    'existing_items_json': '[]',
                    'next_station_number': max_num + 1,
                    'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path_id)}),
                })

            item_count = 0
            for item_data in checklist_items:
                section = item_data.get('section')
                ChecklistItem.objects.create(
                    station=station,
                    item_number=item_data.get('item_number', item_count + 1),
                    description=item_data.get('description', ''),
                    points=float(item_data.get('points', 1)),
                    rubric_type=item_data.get('scoring_type', 'binary'),
                    category=section or '',
                    ilo_id=int(item_data['ilo_id']) if item_data.get('ilo_id') else None,
                )
                item_count += 1

            messages.success(request, f'Station "{station.name}" created with {item_count} checklist items.')
            return redirect('creator:path_detail', path_id=str(path_id))
        except Exception as e:
            messages.error(request, f'Error creating station: {str(e)}')
            # Fall through to re-render form

    return render(request, 'creator/stations/form_simple.html', {
        'path': path,
        'exam': exam,
        'station': None,
        'ilos': ilos,
        'existing_items': [],
        'existing_items_json': '[]',
        'next_station_number': max_num + 1,
        'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path_id)}),
    })


@login_required
def station_create_dry(request, path_id):
    """Create a new dry OSCE station within a path — dept-scoped, ILO assignment required."""
    path = get_object_or_404(Path, pk=path_id)
    if not check_path_department(request.user, path):
        return HttpResponseForbidden('You do not have access to this path.')
    exam = path.exam
    ilos = ILO.objects.filter(course_id=exam.course_id).order_by('number')
    max_num = Station.objects.filter(path=path).aggregate(m=Max('station_number'))['m'] or 0

    if request.method == 'POST':
        try:
            duration = int(request.POST.get('duration_minutes', path.rotation_minutes or 8))

            station = Station(
                path=path,
                exam_id=exam.id,
                station_number=max_num + 1,
                name=request.POST['name'],
                scenario=request.POST.get('scenario', ''),
                instructions=request.POST.get('instructions', ''),
                duration_minutes=duration,
                active=True,
                is_dry=True,
            )

            path.rotation_minutes = duration
            path.save()
            Station.objects.filter(path=path, active=True).update(duration_minutes=duration)

            station.save()

            checklist_json_str = request.POST.get('checklist_data', '[]')
            try:
                checklist_items = json.loads(checklist_json_str)
            except json.JSONDecodeError as e:
                messages.error(request, f'Invalid checklist format: {str(e)}')
                station.delete()
                checklist_items = []

            # Validate ILO assignment
            missing = []
            for idx, item_data in enumerate(checklist_items):
                if not item_data.get('ilo_id') or not str(item_data['ilo_id']).strip():
                    desc = item_data.get('description', '')[:50]
                    missing.append(f'Item {idx + 1}: {desc}')

            if missing:
                station.delete()
                error_msg = (
                    f'Error: {len(missing)} checklist item(s) missing ILO assignment. '
                    'Please assign an ILO to each item before saving.'
                )
                messages.error(request, error_msg)
                return render(request, 'creator/stations/Dry_form_simple.html', {
                    'path': path,
                    'exam': exam,
                    'station': None,
                    'ilos': ilos,
                    'existing_items': [],
                    'existing_items_json': '[]',
                    'next_station_number': max_num + 1,
                    'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path_id)}),
                })

            item_count = 0
            for item_data in checklist_items:
                section = item_data.get('section')
                scoring_type = item_data.get('scoring_type', 'mcq')
                rubric_levels = None
                expected_response = ''
                if scoring_type == 'mcq':
                    rubric_levels = {
                        'options': item_data.get('mcq_options', []),
                        'correct_index': int(item_data.get('correct_index', -1)),
                    }
                elif scoring_type == 'essay':
                    expected_response = item_data.get('key_answer', '')
                new_item = ChecklistItem.objects.create(
                    station=station,
                    item_number=item_data.get('item_number', item_count + 1),
                    description=item_data.get('description', ''),
                    points=float(item_data.get('points', 1)),
                    rubric_type=scoring_type,
                    rubric_levels=rubric_levels,
                    expected_response=expected_response,
                    category=section or '',
                    ilo_id=int(item_data['ilo_id']) if item_data.get('ilo_id') else None,
                )
                # Handle optional image upload for this item
                img_key = f'item_image_{item_data.get("item_id", "")}'
                img_file = request.FILES.get(img_key)
                if img_file:
                    try:
                        validate_question_image(img_file)
                        img_file.name = sanitize_image_filename(img_file.name)
                        new_item.image = img_file
                        new_item.save()
                    except ValidationError as ve:
                        messages.warning(
                            request,
                            f'Image for item {item_count + 1} was skipped: {ve.message}'
                        )
                item_count += 1

            messages.success(request, f'Dry OSCE station "{station.name}" created with {item_count} checklist items.')
            return redirect('creator:path_detail', path_id=str(path_id))
        except Exception as e:
            messages.error(request, f'Error creating station: {str(e)}')

    return render(request, 'creator/stations/Dry_form_simple.html', {
        'path': path,
        'exam': exam,
        'station': None,
        'ilos': ilos,
        'existing_items': [],
        'existing_items_json': '[]',
        'next_station_number': max_num + 1,
        'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path_id)}),
    })


@login_required
def station_detail(request, station_id):
    """View station details and checklist — dept-scoped."""
    station = get_object_or_404(Station, pk=station_id)
    if not check_station_department(request.user, station):
        return HttpResponseForbidden('You do not have access to this station.')
    items = ChecklistItem.objects.filter(station=station).order_by('item_number')
    parent_path = station.path
    parent_session = parent_path.session if parent_path else None
    parent_exam = parent_path.exam if parent_path else None
    return render(request, 'creator/stations/detail.html', {
        'station': station,
        'items': items,
        'parent_path': parent_path,
        'parent_session': parent_session,
        'parent_exam': parent_exam,
    })


@login_required
def station_edit(request, station_id):
    """Edit a station and its checklist — dept-scoped."""
    station = get_object_or_404(Station, pk=station_id)
    if not check_station_department(request.user, station):
        return HttpResponseForbidden('You do not have access to this station.')
    # Dry stations use their own edit form
    if station.is_dry:
        return redirect('creator:station_edit_dry', station_id=station_id)
    path = station.path
    exam = path.exam if path else None
    ilos = ILO.objects.filter(
        course_id=exam.course_id
    ).order_by('number') if exam else ILO.objects.none()
    existing_items = list(ChecklistItem.objects.filter(station=station).order_by('item_number'))
    existing_items_dicts = [
        {
            'item_number': item.item_number,
            'description': item.description,
            'points': item.points,
            'rubric_type': item.rubric_type,
            'ilo_id': item.ilo_id,
            'category': item.category,
        }
        for item in existing_items
    ]

    if request.method == 'POST':
        try:
            station.name = request.POST['name']
            station.scenario = request.POST.get('scenario', '')
            station.instructions = request.POST.get('instructions', '')

            checklist_json_str = request.POST.get('checklist_data', '[]')
            try:
                checklist_items = json.loads(checklist_json_str)
            except json.JSONDecodeError as e:
                messages.error(request, f'Invalid checklist format: {str(e)}')
                checklist_items = []

            # Validate ILO
            missing = []
            for idx, item_data in enumerate(checklist_items):
                if not item_data.get('ilo_id') or not str(item_data['ilo_id']).strip():
                    desc = item_data.get('description', '')[:50]
                    missing.append(f'Item {idx + 1}: {desc}')

            if missing:
                messages.error(
                    request,
                    f'Error: {len(missing)} checklist item(s) missing ILO assignment.',
                )
                return render(request, 'creator/stations/form_simple.html', {
                    'path': path,
                    'exam': exam,
                    'station': station,
                    'ilos': ilos,
                    'existing_items': existing_items,
                    'existing_items_json': json.dumps(existing_items_dicts),
                    'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
                })

            # Clear & recreate
            ChecklistItem.objects.filter(station=station).delete()

            item_count = 0
            for item_data in checklist_items:
                section = item_data.get('section')
                ChecklistItem.objects.create(
                    station=station,
                    item_number=item_data.get('item_number', item_count + 1),
                    description=item_data.get('description', ''),
                    points=float(item_data.get('points', 1)),
                    rubric_type=item_data.get('scoring_type', 'binary'),
                    category=section or '',
                    ilo_id=int(item_data['ilo_id']) if item_data.get('ilo_id') else None,
                )
                item_count += 1

            station.save()
            messages.success(request, f'Station "{station.name}" updated with {item_count} checklist items.')
            if path:
                return redirect('creator:path_detail', path_id=str(path.id))
            return redirect('creator:exam_detail', exam_id=str(exam.id) if exam else '')
        except Exception as e:
            messages.error(request, f'Error updating station: {str(e)}')
            # Fall through to re-render form

    return render(request, 'creator/stations/form_simple.html', {
        'path': path,
        'exam': exam,
        'station': station,
        'ilos': ilos,
        'existing_items': existing_items,
        'existing_items_json': json.dumps(existing_items_dicts),
        'next_station_number': station.station_number,
        'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
    })


@login_required
def station_edit_dry(request, station_id):
    """Edit a dry OSCE station — handles MCQ/Essay rubric types."""
    station = get_object_or_404(Station, pk=station_id)
    if not check_station_department(request.user, station):
        return HttpResponseForbidden('You do not have access to this station.')
    path = station.path
    exam = path.exam if path else None
    ilos = ILO.objects.filter(
        course_id=exam.course_id
    ).order_by('number') if exam else ILO.objects.none()
    existing_items = list(ChecklistItem.objects.filter(station=station).order_by('item_number'))
    existing_items_dicts = [
        {
            'item_number': item.item_number,
            'description': item.description,
            'points': item.points,
            'rubric_type': item.rubric_type,
            'rubric_levels': item.rubric_levels,
            'expected_response': item.expected_response or '',
            'ilo_id': item.ilo_id,
            'category': item.category,
            'db_id': item.pk,
            'image_url': request.build_absolute_uri(item.image.url) if item.image else None,
        }
        for item in existing_items
    ]

    if request.method == 'POST':
        try:
            station.name = request.POST['name']
            station.scenario = request.POST.get('scenario', '')
            station.instructions = request.POST.get('instructions', '')

            duration = int(request.POST.get('duration_minutes', station.duration_minutes or 8))
            station.duration_minutes = duration

            checklist_json_str = request.POST.get('checklist_data', '[]')
            try:
                checklist_items = json.loads(checklist_json_str)
            except json.JSONDecodeError as e:
                messages.error(request, f'Invalid checklist format: {str(e)}')
                checklist_items = []

            # Validate ILO
            missing = []
            for idx, item_data in enumerate(checklist_items):
                if not item_data.get('ilo_id') or not str(item_data['ilo_id']).strip():
                    desc = item_data.get('description', '')[:50]
                    missing.append(f'Item {idx + 1}: {desc}')

            if missing:
                messages.error(request, f'Error: {len(missing)} checklist item(s) missing ILO assignment.')
                return render(request, 'creator/stations/Dry_form_simple.html', {
                    'path': path,
                    'exam': exam,
                    'station': station,
                    'ilos': ilos,
                    'existing_items': existing_items,
                    'existing_items_json': json.dumps(existing_items_dicts),
                    'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
                })

            # Save old image file paths before deletion so we can restore them
            old_images = {item.pk: item.image.name for item in existing_items if item.image}

            # Clear & recreate checklist items
            ChecklistItem.objects.filter(station=station).delete()

            item_count = 0
            for item_data in checklist_items:
                section = item_data.get('section')
                scoring_type = item_data.get('scoring_type', 'mcq')
                rubric_levels = None
                expected_response = ''
                if scoring_type == 'mcq':
                    rubric_levels = {
                        'options': item_data.get('mcq_options', []),
                        'correct_index': int(item_data.get('correct_index', -1)),
                    }
                elif scoring_type == 'essay':
                    expected_response = item_data.get('key_answer', '')
                new_item = ChecklistItem.objects.create(
                    station=station,
                    item_number=item_data.get('item_number', item_count + 1),
                    description=item_data.get('description', ''),
                    points=float(item_data.get('points', 1)),
                    rubric_type=scoring_type,
                    rubric_levels=rubric_levels,
                    expected_response=expected_response,
                    category=section or '',
                    ilo_id=int(item_data['ilo_id']) if item_data.get('ilo_id') else None,
                )
                # Handle image: new upload → validate & save; no upload + old db_id → restore
                img_key = f'item_image_{item_data.get("item_id", "")}'
                img_file = request.FILES.get(img_key)
                if img_file:
                    try:
                        validate_question_image(img_file)
                        img_file.name = sanitize_image_filename(img_file.name)
                        new_item.image = img_file
                        new_item.save()
                    except ValidationError as ve:
                        messages.warning(
                            request,
                            f'Image for item {item_count + 1} was skipped: {ve.message}'
                        )
                elif item_data.get('db_id') and not item_data.get('image_removed'):
                    db_id = int(item_data['db_id'])
                    if db_id in old_images:
                        new_item.image = old_images[db_id]
                        new_item.save()
                item_count += 1

            station.save()
            messages.success(request, f'Dry OSCE station "{station.name}" updated with {item_count} checklist items.')
            if path:
                return redirect('creator:path_detail', path_id=str(path.id))
            return redirect('creator:exam_detail', exam_id=str(exam.id) if exam else '')
        except Exception as e:
            messages.error(request, f'Error updating station: {str(e)}')

    return render(request, 'creator/stations/Dry_form_simple.html', {
        'path': path,
        'exam': exam,
        'station': station,
        'ilos': ilos,
        'existing_items': existing_items,
        'existing_items_json': json.dumps(existing_items_dicts),
        'next_station_number': station.station_number,
        'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
    })


@login_required
def station_delete(request, station_id):
    """Hard delete a station — dept-scoped, head coordinator or above."""
    station = get_object_or_404(Station, pk=station_id)
    if not check_station_department(request.user, station):
        return HttpResponseForbidden('You do not have access to this station.')
    # Only head coordinator, admin, or superuser can delete stations
    user = request.user
    if not (user.is_superuser or getattr(user, 'role', None) == 'admin'
            or (getattr(user, 'role', None) == 'coordinator'
                and getattr(user, 'coordinator_position', None) == 'head')):
        path_id = str(station.path_id) if station.path_id else None
        messages.error(request, 'Only head coordinators or admins can delete stations.')
        if path_id:
            return redirect('creator:path_detail', path_id=path_id)
        return redirect('creator:exam_list')
    path_id = str(station.path_id) if station.path_id else None
    name = station.name

    # Block deletion when a session for this exam has already started
    if not request.user.is_superuser:
        exam = station.path.exam if station.path else None
        if exam and ExamSession.objects.filter(exam=exam, actual_start__isnull=False).exists():
            messages.error(
                request,
                f"Cannot delete station \u2018{name}\u2019 \u2014 a session for this exam has already started."
            )
            if path_id:
                return redirect('creator:path_detail', path_id=path_id)
            return redirect('creator:exam_list')

    station.delete()
    messages.success(request, f"Station '{name}' has been deleted.")
    if path_id:
        return redirect('creator:path_detail', path_id=path_id)
    return redirect('creator:exam_list')
