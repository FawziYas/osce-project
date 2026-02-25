"""
Reports views – scoresheets and report index.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum

from core.models import (
    Course, Exam, ExamSession, SessionStudent, Station, ChecklistItem,
    StationScore,
)


@login_required
def reports_index(request):
    """Reports dashboard – select session and generate reports."""
    # Base filter
    sessions_qs = ExamSession.objects.filter(
        exam__is_deleted=False,
    ).select_related('exam', 'exam__course')
    
    # Permission-based filtering
    # Only superusers can see all sessions (scheduled, in_progress, completed)
    # Coordinator and Admin can see only completed sessions
    # Regular examiners can see only completed sessions
    if not request.user.is_superuser:
        sessions_qs = sessions_qs.filter(status='completed')
    
    sessions = sessions_qs.order_by('-session_date')

    selected_session = None
    session_id = request.GET.get('session_id')
    if session_id:
        selected_session = ExamSession.objects.filter(pk=session_id).first()

    return render(request, 'creator/reports/index.html', {
        'sessions': sessions,
        'selected_session': selected_session,
    })


@login_required
def reports_scoresheets(request, session_id):
    """Print-ready score sheets for a session with pagination, search, and print_all mode."""
    session = get_object_or_404(ExamSession, pk=session_id)
    
    # Access control: non-superusers can only view completed sessions
    if not request.user.is_superuser and session.status != 'completed':
        return HttpResponseForbidden(
            "You do not have permission to view this session. "
            "Only superusers can view non-completed sessions."
        )
    
    # Search filter
    search_query = request.GET.get('search', '').strip()
    print_all = request.GET.get('print_all') == '1'

    students_qs = SessionStudent.objects.filter(session=session)
    if search_query:
        students_qs = students_qs.filter(full_name__icontains=search_query) | SessionStudent.objects.filter(
            session=session, student_number__icontains=search_query
        )
    students_qs = students_qs.order_by('full_name').distinct()

    # Paginate: 10 per page normally; all students in print_all mode
    per_page = students_qs.count() if print_all else 10
    page_num = 1 if print_all else request.GET.get('page', 1)
    paginator = Paginator(students_qs, per_page=max(per_page, 1))

    try:
        students_page = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        students_page = paginator.page(1)

    students = students_page.object_list

    student_data = []
    for student in students:
        if student.path_id:
            student_stations = Station.objects.filter(
                path_id=student.path_id, active=True,
            ).order_by('station_number')
        else:
            student_stations = Station.objects.none()

        # Only count submitted scores, ignore abandoned/in-progress evaluations
        scores_qs = StationScore.objects.filter(
            session_student=student,
            status='submitted'
        ).exclude(
            total_score__isnull=True
        ).select_related('examiner')
        # Map all scores by station (not just one per station)
        score_map_all = {}
        for score in scores_qs:
            if score.station_id not in score_map_all:
                score_map_all[score.station_id] = []
            score_map_all[score.station_id].append(score)

        max_possible = 0
        for st in student_stations:
            st_max = ChecklistItem.objects.filter(station=st).aggregate(
                total=Sum('points')
            )['total'] or 0
            max_possible += st_max

        # Calculate total using average for multiple examiners per station
        total_score = 0
        for station_id, scores_list in score_map_all.items():
            if scores_list:
                # Use average if multiple scores, otherwise use single score
                avg_score = sum(s.total_score or 0 for s in scores_list) / len(scores_list)
                total_score += avg_score
        
        percentage = (total_score / max_possible * 100) if max_possible > 0 else 0
        
        # Build comments with examiner names
        comments_with_examiner = []
        for score in scores_qs:
            if score.comments and score.comments.strip():
                examiner_name = score.examiner.full_name if score.examiner else "Unknown Examiner"
                comments_with_examiner.append({
                    'station': Station.objects.filter(pk=score.station_id).first(),
                    'examiner_name': examiner_name,
                    'comment_text': score.comments,
                    'formatted': f"{examiner_name}:\n{score.comments}"
                })
        
        student_data.append({
            'student': student,
            'stations': student_stations,
            'scores': score_map_all,
            'total_score': round(total_score, 1),
            'max_score': max_possible,
            'percentage_display': round(percentage, 1),
            'passed': percentage >= 60,
            'comments_with_examiner': comments_with_examiner,
        })

    return render(request, 'creator/reports/scoresheets.html', {
        'session': session,
        'students': student_data,
        'page_obj': students_page,
        'paginator': paginator,
        'search_query': search_query,
        'print_all': print_all,
    })


@login_required
def reports_student_scoresheet(request, student_id):
    """Print-ready score sheet for a single student."""
    student = get_object_or_404(SessionStudent, pk=student_id)
    session = get_object_or_404(ExamSession, pk=student.session_id)
    
    # Access control: non-superusers can only view completed sessions
    if not request.user.is_superuser and session.status != 'completed':
        return HttpResponseForbidden(
            "You do not have permission to view this session. "
            "Only superusers can view non-completed sessions."
        )

    if student.path_id:
        student_stations = Station.objects.filter(
            path_id=student.path_id, active=True,
        ).order_by('station_number')
    else:
        student_stations = Station.objects.none()

    # Only count submitted scores, ignore abandoned/in-progress evaluations
    scores_qs = StationScore.objects.filter(
        session_student=student,
        status='submitted'
    ).exclude(
        total_score__isnull=True
    ).select_related('examiner')
    # Map all scores by station (not just one per station)
    score_map_all = {}
    for score in scores_qs:
        if score.station_id not in score_map_all:
            score_map_all[score.station_id] = []
        score_map_all[score.station_id].append(score)

    max_possible = 0
    for st in student_stations:
        st_max = ChecklistItem.objects.filter(station=st).aggregate(
            total=Sum('points')
        )['total'] or 0
        max_possible += st_max

    # Calculate total using average for multiple examiners per station
    _total = 0
    for station_id, scores_list in score_map_all.items():
        if scores_list:
            # Use average if multiple scores, otherwise use single score
            avg_score = sum(s.total_score or 0 for s in scores_list) / len(scores_list)
            _total += avg_score
    
    _pct = (_total / max_possible * 100) if max_possible > 0 else 0
    
    # Build comments with examiner names
    comments_with_examiner = []
    for score in scores_qs:
        if score.comments and score.comments.strip():
            examiner_name = score.examiner.full_name if score.examiner else "Unknown Examiner"
            comments_with_examiner.append({
                'station': Station.objects.filter(pk=score.station_id).first(),
                'examiner_name': examiner_name,
                'comment_text': score.comments,
                'formatted': f"{examiner_name}:\n{score.comments}"
            })
    
    student_data = [{
        'student': student,
        'stations': student_stations,
        'scores': score_map_all,
        'total_score': round(_total, 1),
        'max_score': max_possible,
        'percentage_display': round(_pct, 1),
        'passed': _pct >= 60,
        'comments_with_examiner': comments_with_examiner,
    }]

    return render(request, 'creator/reports/scoresheets.html', {
        'session': session,
        'students': student_data,
        'single_student': True,
    })
