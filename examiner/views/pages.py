"""
Examiner page views – HTML page responses for the tablet interface.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from axes.decorators import axes_dispatch
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from core.models import (
    ExaminerAssignment, ExamSession, SessionStudent, Station,
    StationScore, ItemScore, Path,
)
from core.models.mixins import TimestampMixin
from core.utils.audit import log_action


def index(request):
    """Redirect to login or home."""
    if request.user.is_authenticated:
        return redirect('examiner:home')
    return redirect('examiner:login')


def offline(request):
    """Offline fallback page for PWA."""
    return render(request, 'examiner/offline.html')


@axes_dispatch
def login_view(request):
    """Redirect to unified login."""
    return redirect('/login/')


@login_required
def logout_view(request):
    """Logout examiner."""
    log_action(request, 'LOGOUT', 'Examiner', request.user.id,
               f'{request.user.display_name} logged out')
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('/login/')


# ── helpers ────────────────────────────────────────────────────────

def _consolidate_assignments(assignments):
    """
    Group assignments by (session_id, station_number) since an examiner
    sits in ONE room and marks students from ALL paths.
    """
    grouped = defaultdict(list)
    for a in assignments:
        if a.station:
            key = (str(a.session_id), a.station.station_number)
            grouped[key].append(a)

    consolidated = []
    for (session_id, station_num), group in grouped.items():
        first = group[0]

        total_students = 0
        for a in group:
            if a.station and a.station.path_id:
                total_students += SessionStudent.objects.filter(
                    session_id=session_id,
                    path_id=a.station.path_id,
                ).count()

        consolidated.append({
            'assignment': first,
            'assignment_id': str(first.id),
            'station_number': station_num,
            'station_name': first.station.name if first.station else 'Unknown',
            'station_duration': first.station.duration_minutes if first.station else 8,
            'station_max_score': first.station.get_max_score() if first.station else 0,
            'session': first.session,
            'total_students': total_students,
            'paths_count': len(group),
            'all_assignments': group,
        })

    return consolidated


@login_required
def home(request):
    """Examiner home – today's stations, recent and upcoming sessions."""
    today = datetime.now().date()

    # Today's assignments
    today_raw = list(
        ExaminerAssignment.objects.filter(
            examiner=request.user,
            session__session_date=today,
            session__status__in=['scheduled', 'in_progress'],
        ).select_related('station', 'session', 'station__path')
    )
    today_assignments = _consolidate_assignments(today_raw)

    # Recent (last 7 days)
    week_ago = today - timedelta(days=7)
    recent_raw = list(
        ExaminerAssignment.objects.filter(
            examiner=request.user,
            session__session_date__gte=week_ago,
            session__session_date__lt=today,
            session__status='completed',
        ).select_related('station', 'session', 'station__path')
    )
    recent_assignments = _consolidate_assignments(recent_raw)

    # Upcoming
    upcoming_raw = list(
        ExaminerAssignment.objects.filter(
            examiner=request.user,
            session__session_date__gt=today,
            session__status__in=['scheduled'],
        ).select_related('station', 'session', 'station__path')
    )
    upcoming_assignments = _consolidate_assignments(upcoming_raw)

    return render(request, 'examiner/station_home.html', {
        'assignments': today_assignments,
        'recent_assignments': recent_assignments,
        'upcoming_assignments': upcoming_assignments,
        'today': today,
    })


@login_required
def all_sessions(request):
    """View all sessions the examiner has been assigned to."""
    assignments = ExaminerAssignment.objects.filter(
        examiner=request.user,
    ).select_related('station', 'session').order_by('-session__session_date')

    return render(request, 'examiner/all_sessions.html', {
        'assignments': list(assignments),
    })


@login_required
def station_dashboard(request, assignment_id):
    """Station dashboard – students to mark and progress."""
    assignment = get_object_or_404(
        ExaminerAssignment.objects.select_related(
            'station', 'session', 'session__exam', 'station__path'),
        pk=assignment_id
    )

    if assignment.examiner_id != request.user.id:
        messages.error(request, 'You are not assigned to this station.')
        return redirect('examiner:home')

    # Check session status
    session = assignment.session
    if session and session.status != 'in_progress':
        status_messages = {
            'scheduled': ('This session is not yet active. Please wait for the coordinator to activate it.', 'warning'),
            'completed': ('This session has been completed.', 'info'),
        }
        msg, level = status_messages.get(session.status, ('This session is currently paused.', 'warning'))
        getattr(messages, level)(request, msg)
        return redirect('examiner:home')

    station = assignment.station
    if not station or not station.path_id:
        messages.error(request, 'Station or path not configured.')
        return redirect('examiner:home')

    students = SessionStudent.objects.filter(
        session_id=assignment.session_id,
        path_id=station.path_id,
    ).order_by('sequence_number')

    # Scored students by this examiner
    scored_student_ids = set(
        StationScore.objects.filter(
            station_id=assignment.station_id,
            examiner=request.user,
            status='submitted',
        ).values_list('session_student_id', flat=True)
    )

    # All scores for dual-examiner view - only submitted scores
    all_scores = StationScore.objects.filter(
        station_id=assignment.station_id,
        status='submitted'
    ).select_related('examiner')

    student_scores = {}
    for score in all_scores:
        sid = str(score.session_student_id)
        if sid not in student_scores:
            student_scores[sid] = {
                'my_score': None,
                'other_examiner_score': None,
                'max_score': score.max_score or 0,
                'final_score': None,
                'both_submitted': False,
            }
        if score.examiner_id == request.user.id:
            student_scores[sid]['my_score'] = score.total_score
        else:
            student_scores[sid]['other_examiner_score'] = score.total_score

    for sid, data in student_scores.items():
        if data['my_score'] is not None and data['other_examiner_score'] is not None:
            data['both_submitted'] = True
            data['final_score'] = round(
                (data['my_score'] + data['other_examiner_score']) / 2, 2
            )

    # Build student list with score data for template
    student_list = []
    for s in students:
        sid = str(s.id)
        score_data = student_scores.get(sid, {})
        student_list.append({
            'student': s,
            'my_score': score_data.get('my_score'),
            'other_examiner_score': score_data.get('other_examiner_score'),
            'both_submitted': score_data.get('both_submitted', False),
            'final_score': score_data.get('final_score'),
            'is_scored': s.id in scored_student_ids,
        })

    scored_count = len(scored_student_ids)
    total_count = students.count()
    remaining_count = total_count - scored_count
    progress_pct = round((scored_count / total_count * 100), 1) if total_count else 0

    return render(request, 'examiner/station_dashboard.html', {
        'assignment': assignment,
        'student_list': student_list,
        'scored_count': scored_count,
        'remaining_count': remaining_count,
        'total_count': total_count,
        'progress_pct': progress_pct,
    })


@login_required
def select_student(request, assignment_id):
    """Student selection page."""
    assignment = get_object_or_404(ExaminerAssignment, pk=assignment_id)

    if assignment.examiner_id != request.user.id:
        messages.error(request, 'You are not assigned to this station.')
        return redirect('examiner:home')

    students = SessionStudent.objects.filter(
        session_id=assignment.session_id,
    ).order_by('rotation_group', 'sequence_number')

    return render(request, 'examiner/select_student.html', {
        'assignment': assignment,
        'students': students,
    })


@login_required
def marking_interface(request, assignment_id, student_id):
    """Main marking interface where examiners mark students."""
    assignment = get_object_or_404(
        ExaminerAssignment.objects.select_related(
            'station', 'session', 'session__exam'),
        pk=assignment_id
    )
    student = get_object_or_404(SessionStudent, pk=student_id)

    if assignment.examiner_id != request.user.id:
        messages.error(request, 'You are not assigned to this station.')
        return redirect('examiner:home')

    # Check session status — only block if NOT already submitted (review is allowed)
    session = assignment.session
    if session and session.status != 'in_progress':
        # Allow if already submitted (review mode) even after session ends
        existing_score = StationScore.objects.filter(
            session_student=student,
            station_id=assignment.station_id,
            examiner=request.user,
            status='submitted',
        ).first()
        if not existing_score:
            status_messages = {
                'scheduled': ('This session is not yet active. Marking is disabled.', 'warning'),
                'completed': ('This session has been completed. No further marking allowed.', 'info'),
            }
            msg, level = status_messages.get(session.status, ('This session is currently paused. Marking is disabled.', 'warning'))
            getattr(messages, level)(request, msg)
            return redirect('examiner:home')

    if str(student.session_id) != str(assignment.session_id):
        messages.error(request, 'Student is not in this exam session.')
        return redirect('examiner:station_dashboard', assignment_id=assignment_id)

    # Get or create station score
    score = StationScore.objects.filter(
        session_student=student,
        station_id=assignment.station_id,
        examiner=request.user,
    ).first()

    if not score:
        score = StationScore.objects.create(
            session_student=student,
            station_id=assignment.station_id,
            examiner=request.user,
            max_score=assignment.station_max_score,
            started_at=TimestampMixin.utc_timestamp(),
            status='in_progress',
        )

    # Review mode: score is submitted, NOT unlocked, and past the 5-min grace window
    _now = TimestampMixin.utc_timestamp()
    within_undo_window = (
        score.status == 'submitted'
        and score.completed_at is not None
        and (_now - score.completed_at) <= 300
    )
    review_mode = (
        score.status == 'submitted'
        and not score.unlocked_for_correction
        and not within_undo_window
    )


    # Check for co-examiner submission (dual-examiner finalize info)
    co_score = StationScore.objects.filter(
        session_student=student,
        station_id=assignment.station_id,
        status='submitted',
    ).exclude(examiner=request.user).select_related('examiner').first()
    co_examiner_name = None
    co_examiner_score = None
    both_finalized = False
    final_avg = None
    if co_score:
        co_examiner_name = co_score.examiner.display_name if co_score.examiner else 'Co-Examiner'
        co_examiner_score = co_score.total_score
        if score.status == 'submitted':
            both_finalized = True
            final_avg = round((score.total_score + co_score.total_score) / 2, 2)

    # Get saved item scores
    saved_item_scores = {}
    for is_obj in ItemScore.objects.filter(station_score=score):
        saved_item_scores[is_obj.checklist_item_id] = {
            'score': is_obj.score,
            'max_points': is_obj.max_points,
        }

    max_score = assignment.station.get_max_score() if assignment.station else 0
    duration = assignment.station.duration_minutes if assignment.station else 8

    return render(request, 'examiner/marking.html', {
        'assignment': assignment,
        'student': student,
        'score': score,
        'saved_item_scores_json': json.dumps(saved_item_scores),
        'max_score': max_score,
        'duration': duration,
        'review_mode': review_mode,
        'within_undo_window': within_undo_window,
        'score_status': score.status,
        'saved_comments': score.comments or '',
        'co_examiner_name': co_examiner_name,
        'co_examiner_score': co_examiner_score,
        'both_finalized': both_finalized,
        'final_avg': final_avg,
    })
