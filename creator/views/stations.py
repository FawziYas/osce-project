"""
Station CRUD views – create, detail, edit, delete, restore.
"""
import json
import re

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F, Max
from django.http import HttpResponseForbidden, JsonResponse

from core.models import ILO, Station, ChecklistItem, Path, Exam
from core.utils.roles import check_path_department, check_station_department
from core.utils.image_validators import validate_question_image, sanitize_image_filename
from core.utils.sanitize import strip_html, html_safe_json


def _get_dept_folder(exam):
    """Return a filesystem-safe department folder name for image uploads."""
    dept = (exam.department or '').strip() if exam else ''
    if not dept:
        dept = 'general'
    return re.sub(r'[^\w\-]', '_', dept).strip('_') or 'general'


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
                name=strip_html(request.POST['name']),
                scenario=strip_html(request.POST.get('scenario', '')),
                instructions=strip_html(request.POST.get('instructions', '')),
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
                    description=strip_html(item_data.get('description', '')),
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
                name=strip_html(request.POST['name']),
                scenario=strip_html(request.POST.get('scenario', '')),
                instructions=strip_html(request.POST.get('instructions', '')),
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
                    description=strip_html(item_data.get('description', '')),
                    points=float(item_data.get('points', 1)),
                    rubric_type=scoring_type,
                    rubric_levels=rubric_levels,
                    expected_response=strip_html(expected_response),
                    category=section or '',
                    ilo_id=int(item_data['ilo_id']) if item_data.get('ilo_id') else None,
                )
                # Handle optional image upload for this item
                img_key = f'item_image_{item_data.get("item_id", "")}'
                img_file = request.FILES.get(img_key)
                if img_file:
                    try:
                        validate_question_image(img_file)
                        filename = sanitize_image_filename(img_file.name)
                        dept_folder = _get_dept_folder(exam)
                        img_file.seek(0)
                        saved_path = default_storage.save(
                            f'question_images/{dept_folder}/{filename}', img_file
                        )
                        new_item.image = saved_path
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
    session = path.session if path else None
    if session and session.actual_start and not request.user.is_superuser:
        messages.error(
            request,
            'Checklist editing is forbidden because this session has already been activated.'
        )
        if path:
            return redirect('creator:path_detail', path_id=str(path.id))
        return redirect('creator:exam_detail', exam_id=str(exam.id) if exam else '')

    ilos = ILO.objects.filter(
        course_id=exam.course_id
    ).order_by('number') if exam else ILO.objects.none()
    existing_items = list(ChecklistItem.objects.filter(station=station).order_by('item_number'))
    existing_items_dicts = [
        {
            'db_id': item.pk,
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
            station.name = strip_html(request.POST['name'])
            station.scenario = strip_html(request.POST.get('scenario', ''))
            station.instructions = strip_html(request.POST.get('instructions', ''))

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
                    'existing_items_json': html_safe_json(existing_items_dicts),
                    'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
                })

            # Build lookup of existing items by PK so we can update in-place
            existing_by_id = {item.pk: item for item in existing_items}
            submitted_db_ids = {
                int(d['db_id']) for d in checklist_items if d.get('db_id')
            }

            # Items the user removed — block if they have student submissions
            removed_ids = set(existing_by_id.keys()) - submitted_db_ids
            for pk in removed_ids:
                old_item = existing_by_id[pk]
                if old_item.item_scores.exists():
                    messages.error(
                        request,
                        f'Cannot remove item "{old_item.description[:40]}" — students have already '
                        'submitted answers for it.',
                    )
                    return render(request, 'creator/stations/form_simple.html', {
                        'path': path,
                        'exam': exam,
                        'station': station,
                        'ilos': ilos,
                        'existing_items': existing_items,
                        'existing_items_json': html_safe_json(existing_items_dicts),
                        'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
                    })

            with transaction.atomic():
                # Safe to delete: no student submissions on these removed items
                for pk in removed_ids:
                    existing_by_id[pk].delete()

                # Temporarily offset surviving item_numbers to avoid the unique
                # constraint when a duplicated (new) item is created with an
                # item_number that an existing item still holds in the DB.
                surviving_pks = set(existing_by_id.keys()) - removed_ids
                if surviving_pks:
                    ChecklistItem.objects.filter(pk__in=surviving_pks).update(
                        item_number=F('item_number') + 10000
                    )

                item_count = 0
                for item_data in checklist_items:
                    section = item_data.get('section')
                    raw_db_id = item_data.get('db_id')
                    db_id = int(raw_db_id) if raw_db_id else None

                    if db_id and db_id in existing_by_id:
                        # Update in-place so ItemScore FKs remain intact
                        item = existing_by_id[db_id]
                        item.item_number = item_data.get('item_number', item_count + 1)
                        item.description = strip_html(item_data.get('description', ''))
                        item.points = float(item_data.get('points', 1))
                        item.rubric_type = item_data.get('scoring_type', 'binary')
                        item.category = section or ''
                        item.ilo_id = int(item_data['ilo_id']) if item_data.get('ilo_id') else None
                        item.save()
                        # sync_station_max_score signal fires on item.save() above —
                        # it handles proportional rescaling of ItemScore and StationScore.
                    else:
                        ChecklistItem.objects.create(
                            station=station,
                            item_number=item_data.get('item_number', item_count + 1),
                            description=strip_html(item_data.get('description', '')),
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
        'existing_items_json': html_safe_json(existing_items_dicts),
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
    session = path.session if path else None
    session_started = bool(session and session.actual_start)
    ilos = ILO.objects.filter(
        course_id=exam.course_id
    ).order_by('number') if exam else ILO.objects.none()
    existing_items = list(ChecklistItem.objects.filter(station=station).order_by('item_number'))
    def _safe_image_url(item):
        try:
            if not item.image or not item.image.name:
                return None
            return request.build_absolute_uri(item.image.url)
        except Exception:
            return None

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
            'image_url': _safe_image_url(item),
        }
        for item in existing_items
    ]

    if request.method == 'POST':
        try:
            station.name = strip_html(request.POST['name'])
            station.scenario = strip_html(request.POST.get('scenario', ''))
            station.instructions = strip_html(request.POST.get('instructions', ''))

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
                    'existing_items_json': html_safe_json(existing_items_dicts),
                    'session_started': session_started,
                    'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
                })

            # Build lookup of existing items by PK so we can update in-place
            existing_by_id = {item.pk: item for item in existing_items}
            submitted_db_ids = {
                int(d['db_id']) for d in checklist_items if d.get('db_id')
            }

            # Items the user removed from the form
            removed_ids = set(existing_by_id.keys()) - submitted_db_ids

            # When a session has started, cannot remove any existing items
            if session_started and removed_ids:
                messages.error(request, 'Cannot remove checklist items after a session has started.')
                return render(request, 'creator/stations/Dry_form_simple.html', {
                    'path': path,
                    'exam': exam,
                    'station': station,
                    'ilos': ilos,
                    'existing_items': existing_items,
                    'existing_items_json': html_safe_json(existing_items_dicts),
                    'session_started': session_started,
                    'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
                })

            # Block removal if any removed item has student submissions
            for pk in removed_ids:
                old_item = existing_by_id[pk]
                if old_item.item_scores.exists():
                    messages.error(
                        request,
                        f'Cannot remove item "{old_item.description[:40]}" — students have already '
                        'submitted answers for it. You can edit its details but not delete it.',
                    )
                    return render(request, 'creator/stations/Dry_form_simple.html', {
                        'path': path,
                        'exam': exam,
                        'station': station,
                        'ilos': ilos,
                        'existing_items': existing_items,
                        'existing_items_json': html_safe_json(existing_items_dicts),
                        'session_started': session_started,
                        'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
                    })

            with transaction.atomic():
                # Safe to delete: no student submissions on these removed items
                for pk in removed_ids:
                    existing_by_id[pk].delete()

                # Temporarily offset surviving item_numbers to avoid the unique
                # constraint when a duplicated (new) item is created with an
                # item_number that an existing item still holds in the DB.
                surviving_pks = set(existing_by_id.keys()) - removed_ids
                if surviving_pks:
                    ChecklistItem.objects.filter(pk__in=surviving_pks).update(
                        item_number=F('item_number') + 10000
                    )

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

                    raw_db_id = item_data.get('db_id')
                    db_id = int(raw_db_id) if raw_db_id else None

                    img_key = f'item_image_{item_data.get("item_id", "")}'
                    img_file = request.FILES.get(img_key)

                    if db_id and db_id in existing_by_id:
                        # Update the existing ChecklistItem in-place so ItemScore FKs stay intact
                        item = existing_by_id[db_id]
                        item.item_number = item_data.get('item_number', item_count + 1)
                        item.description = strip_html(item_data.get('description', ''))
                        item.points = float(item_data.get('points', 1))
                        if session_started:
                            # Cannot change rubric type once session has started
                            if item.rubric_type == 'mcq':
                                existing_options = (item.rubric_levels or {}).get('options', [])
                                new_options = item_data.get('mcq_options', [])
                                if len(new_options) != len(existing_options):
                                    messages.error(
                                        request,
                                        f'Cannot add or remove MCQ options for item "{item.description[:40]}" after a session has started.'
                                    )
                                    return render(request, 'creator/stations/Dry_form_simple.html', {
                                        'path': path, 'exam': exam, 'station': station,
                                        'ilos': ilos, 'existing_items': existing_items,
                                        'existing_items_json': html_safe_json(existing_items_dicts),
                                        'session_started': session_started,
                                        'cancel_url': reverse('creator:path_detail', kwargs={'path_id': str(path.id)}),
                                    })
                                item.rubric_levels = {
                                    'options': new_options,
                                    'correct_index': int(item_data.get('correct_index', -1)),
                                }
                                item.expected_response = ''
                            else:
                                item.rubric_levels = None
                                item.expected_response = strip_html(item_data.get('key_answer', ''))
                        else:
                            item.rubric_type = scoring_type
                            item.rubric_levels = rubric_levels
                            item.expected_response = expected_response
                        item.category = section or ''
                        item.ilo_id = int(item_data['ilo_id']) if item_data.get('ilo_id') else None
                        if img_file:
                            try:
                                validate_question_image(img_file)
                                filename = sanitize_image_filename(img_file.name)
                                dept_folder = _get_dept_folder(exam)
                                img_file.seek(0)
                                saved_path = default_storage.save(
                                    f'question_images/{dept_folder}/{filename}', img_file
                                )
                                item.image = saved_path
                            except ValidationError as ve:
                                messages.warning(
                                    request,
                                    f'Image for item {item_count + 1} was skipped: {ve.message}',
                                )
                        elif item_data.get('image_removed'):
                            item.image = None
                        item.save()
                        # Sync max_points on ungraded ItemScore records
                        item.item_scores.filter(marked_at__isnull=True).update(
                            max_points=float(item_data.get('points', 1))
                        )
                    else:
                        # New item — create it
                        new_item = ChecklistItem.objects.create(
                            station=station,
                            item_number=item_data.get('item_number', item_count + 1),
                            description=strip_html(item_data.get('description', '')),
                            points=float(item_data.get('points', 1)),
                            rubric_type=scoring_type,
                            rubric_levels=rubric_levels,
                            expected_response=strip_html(expected_response),
                            category=section or '',
                            ilo_id=int(item_data['ilo_id']) if item_data.get('ilo_id') else None,
                        )
                        if img_file:
                            try:
                                validate_question_image(img_file)
                                filename = sanitize_image_filename(img_file.name)
                                dept_folder = _get_dept_folder(exam)
                                img_file.seek(0)
                                saved_path = default_storage.save(
                                    f'question_images/{dept_folder}/{filename}', img_file
                                )
                                new_item.image = saved_path
                                new_item.save()
                            except ValidationError as ve:
                                messages.warning(
                                    request,
                                    f'Image for item {item_count + 1} was skipped: {ve.message}',
                                )
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
        'existing_items_json': html_safe_json(existing_items_dicts),
        'session_started': session_started,
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


@login_required
def browse_department_images(request, exam_id):
    """Return JSON list of images already uploaded to question_images/<dept>/ for this exam."""
    exam = get_object_or_404(Exam, pk=exam_id)
    dept_folder = _get_dept_folder(exam)
    prefix = f'question_images/{dept_folder}'
    images = []
    try:
        _, files = default_storage.listdir(prefix)
        for fname in sorted(files):
            if not fname:
                continue
            path = f'{prefix}/{fname}'
            try:
                url = default_storage.url(path)
            except Exception:
                continue
            images.append({'name': fname, 'url': url, 'path': path})
    except Exception:
        pass
    return JsonResponse({'images': images})
