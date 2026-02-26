"""
Station CRUD views – create, detail, edit, delete, restore.
"""
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max

from core.models import ILO, Station, ChecklistItem, Path


@login_required
def station_create(request, path_id):
    """Create a new station within a path – simple form builder."""
    path = get_object_or_404(Path, pk=path_id)
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
def station_detail(request, station_id):
    """View station details and checklist."""
    station = get_object_or_404(Station, pk=station_id)
    items = ChecklistItem.objects.filter(station=station).order_by('item_number')
    return render(request, 'creator/stations/detail.html', {
        'station': station,
        'items': items,
    })


@login_required
def station_edit(request, station_id):
    """Edit a station and its checklist – simple form builder."""
    station = get_object_or_404(Station, pk=station_id)
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
def station_delete(request, station_id):
    """Hard delete a station."""
    station = get_object_or_404(Station, pk=station_id)
    path_id = str(station.path_id) if station.path_id else None
    name = station.name

    station.delete()
    messages.success(request, f"Station '{name}' has been deleted.")
    if path_id:
        return redirect('creator:path_detail', path_id=path_id)
    return redirect('creator:exam_list')
