"""
Path CRUD views – detail, create, batch create, edit, delete, restore.
"""
import string

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from core.models import Exam, ExamSession, Path, Station, ChecklistItem, ExaminerAssignment


@login_required
def path_detail(request, path_id):
    """View path details and its stations."""
    path = get_object_or_404(Path, pk=path_id)
    stations = Station.objects.filter(path=path, active=True) \
        .prefetch_related('checklist_items') \
        .order_by('station_number')
    exam = path.exam
    
    # Get examiner assignments for this path's session
    session = path.session
    assignments_by_station = {}
    if session:
        assignments = ExaminerAssignment.objects.filter(
            session=session,
            station__path=path
        ).select_related('examiner')
        
        # Group by station
        for assignment in assignments:
            station_id = assignment.station_id
            if station_id not in assignments_by_station:
                assignments_by_station[station_id] = []
            assignments_by_station[station_id].append(assignment)
    
    # Add assignments to each station
    for station in stations:
        station.assigned_examiners = assignments_by_station.get(station.id, [])

    return render(request, 'creator/paths/detail.html', {
        'path': path,
        'stations': stations,
        'exam': exam,
    })

@login_required
def create_path(request, session_id):
    """Create a new path, optionally copying stations from another."""
    session = get_object_or_404(ExamSession, pk=session_id)
    exam = session.exam
    other_paths = Path.objects.filter(session=session, is_deleted=False).order_by('name')

    if request.method == 'POST':
        path_name = request.POST.get('name', '').strip()

        if not path_name:
            messages.error(request, 'Path name is required')
            return redirect('creator:create_path', session_id=str(session_id))

        if Path.objects.filter(session=session, name=path_name).exists():
            messages.error(request, f"Path '{path_name}' already exists")
            return redirect('creator:create_path', session_id=str(session_id))

        path = Path(
            session=session,
            name=path_name,
            description=request.POST.get('description', ''),
            rotation_minutes=int(
                request.POST.get('rotation_minutes', exam.station_duration_minutes or 8)
            ),
            is_active=True,
        )
        path.save()

        copy_from = request.POST.get('copy_from_path')
        if copy_from:
            try:
                source = get_object_or_404(Path, pk=copy_from)
                _copy_stations(source, path)
                source_count = Station.objects.filter(path=source, active=True).count()
                messages.success(
                    request,
                    f"Path '{path_name}' created with {source_count} station(s) copied from Path {source.name}.",
                )
                return redirect('creator:path_detail', path_id=str(path.id))
            except Exception as e:
                messages.error(request, f'Error copying stations: {e}')
                return redirect('creator:create_path', session_id=str(session_id))

        messages.success(request, f"Path '{path_name}' created. Now add stations.")
        return redirect('creator:path_detail', path_id=str(path.id))

    return render(request, 'creator/paths/form.html', {
        'session': session,
        'path': None,
        'exam': exam,
        'other_paths': other_paths,
    })


@login_required
def edit_path(request, path_id):
    """Edit an existing path."""
    path = get_object_or_404(Path, pk=path_id)
    session = path.session
    exam = session.exam
    other_paths = Path.objects.filter(session=session, is_deleted=False).order_by('name')

    if request.method == 'POST':
        path.name = request.POST.get('name', path.name).strip()
        path.description = request.POST.get('description', '')
        new_rot = int(request.POST.get('rotation_minutes', path.rotation_minutes))
        path.rotation_minutes = new_rot
        path.save()

        # Sync station durations
        Station.objects.filter(path=path, active=True).update(duration_minutes=new_rot)

        messages.success(request, f"Path '{path.name}' updated and station durations synchronized")
        return redirect('creator:path_detail', path_id=str(path.id))

    return render(request, 'creator/paths/form.html', {
        'session': session,
        'path': path,
        'exam': exam,
        'other_paths': other_paths,
    })


@login_required
def delete_path(request, path_id):
    """Soft delete a path."""
    path = get_object_or_404(Path, pk=path_id)
    session_id = str(path.session_id)

    if path.session and path.session.actual_start:
        messages.error(request, 'Cannot delete paths after session has been activated.')
        return redirect('creator:session_detail', session_id=session_id)

    path.soft_delete()
    messages.success(request, f"Path '{path.name}' has been deleted.")
    return redirect('creator:session_detail', session_id=session_id)


@login_required
def restore_path(request, path_id):
    """Restore a soft-deleted path."""
    path = get_object_or_404(Path, pk=path_id)
    path.restore()
    messages.success(request, f"Path '{path.name}' has been restored.")
    return redirect('creator:path_detail', path_id=str(path.id))


@login_required
def batch_create_paths(request, session_id):
    """Create multiple paths at once, optionally copying stations."""
    if request.method != 'POST':
        return redirect('creator:session_detail', session_id=str(session_id))

    try:
        session = get_object_or_404(ExamSession, pk=session_id)
        exam = session.exam

        path_count = int(request.POST.get('path_count', 1))
        naming_pattern = request.POST.get('naming_pattern', 'letters')
        rotation_minutes = int(request.POST.get('rotation_minutes', exam.station_duration_minutes or 8))
        copy_from_path_id = request.POST.get('copy_from_path_id')

        if path_count < 1 or path_count > 50:
            messages.error(request, 'Path count must be between 1 and 50')
            return redirect('creator:session_detail', session_id=str(session_id))

        source_stations = []
        if copy_from_path_id:
            try:
                source_path = Path.objects.get(pk=copy_from_path_id)
                source_stations = list(
                    Station.objects.filter(path=source_path, active=True).order_by('station_number')
                )
            except Path.DoesNotExist:
                pass

        created_paths = []

        if naming_pattern == 'letters':
            candidates = list(string.ascii_uppercase) + list(string.ascii_lowercase)
        else:
            candidates = [str(i) for i in range(1, 101)]

        for cand in candidates:
            if len(created_paths) >= path_count:
                break
            if Path.objects.filter(session=session, name=cand).exists():
                continue

            path = Path(
                session=session,
                name=cand,
                description=f'Path {cand}' if naming_pattern == 'letters' else str(cand),
                rotation_minutes=rotation_minutes,
                is_active=True,
            )
            path.save()

            if source_stations:
                _copy_stations_list(source_stations, path)

            created_paths.append(path)

        stations_msg = f' with {len(source_stations)} station(s) each' if source_stations else ''
        names = ', '.join(p.name for p in created_paths)
        messages.success(
            request,
            f'Successfully created {len(created_paths)} path(s): {names}{stations_msg}.',
        )
        return redirect('creator:session_detail', session_id=str(session_id))
    except Exception as e:
        messages.error(request, f'Error: {e}')
        return redirect('creator:session_detail', session_id=str(session_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _copy_stations(source_path, target_path):
    """Copy all active stations (with checklist items) from source to target path."""
    source_stations = Station.objects.filter(path=source_path, active=True).order_by('station_number')
    _copy_stations_list(list(source_stations), target_path)


def _copy_stations_list(source_stations, target_path):
    """Copy a list of stations into target_path."""
    for src in source_stations:
        new_station = Station.objects.create(
            path=target_path,
            exam_id=target_path.session.exam_id if target_path.session else None,
            station_number=src.station_number,
            name=src.name,
            scenario=src.scenario,
            instructions=src.instructions,
            duration_minutes=src.duration_minutes,
            active=True,
        )
        for item in ChecklistItem.objects.filter(station=src).order_by('item_number'):
            ChecklistItem.objects.create(
                station=new_station,
                item_number=item.item_number,
                description=item.description,
                points=item.points,
                rubric_type=item.rubric_type,
                category=item.category,
                ilo_id=item.ilo_id,
            )
