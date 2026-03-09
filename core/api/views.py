"""
DRF ViewSets — multi-layer authorization for the OSCE REST API.

Each ViewSet composes:
  Layer 2: Role permission classes (via get_permissions)
  Layer 3: DepartmentScopedMixin (queryset filtering)
  Layer 4: ExaminerAssignmentMixin (station assignment check)
  Layer 5: SessionStateGuard (score write guards)

Route permission map implemented:
  GET  /departments/                        → Superuser, Admin
  GET  /departments/:id/                    → Superuser, Admin, Coordinator (own)
  GET  /departments/:id/coordinators/       → Superuser, Admin, Coordinator (own)
  GET  /departments/:id/courses/            → Superuser, Admin, Coordinator (own)
  GET  /courses/:id/exams/                  → Superuser, Admin, Coordinator (own)
  GET  /exams/:id/                          → Superuser, Admin, Coordinator (own)
  DELETE /exams/:id/                        → Superuser, Admin, Coordinator-Head (own)
  GET  /exams/:id/sessions/                 → Superuser, Admin, Coordinator (own)
  GET  /sessions/:id/paths/                 → Superuser, Admin, Coordinator (own)
  GET  /paths/:id/stations/                 → Superuser, Admin, Coordinator (own)
  GET  /stations/:id/                       → + Examiner (assigned)
  GET  /stations/:id/checklist/             → + Examiner (assigned)
  POST /stations/:id/scores/               → Examiner (assigned + active session)
  PUT  /scores/:id/                        → Examiner (assigned + not finalized)
  GET  /stations/:id/assignments/           → Superuser, Admin, Coordinator (own)
  POST /stations/:id/assignments/           → Superuser, Admin, Coordinator (own)
  GET  /reports/department/:id/             → Superuser, Admin, Coordinator (own)
"""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import (
    Department, Course, Exam, ExamSession, Path,
    Station, ChecklistItem, ExaminerAssignment,
    StationScore, ItemScore, SessionStudent,
)
from core.api.permissions import (
    IsSuperuserOrAdmin,
    IsGlobalOrCoordinator,
    IsGlobalOrCoordinatorHead,
    IsGlobalOrCoordinatorOrAssignedExaminer,
)
from core.api.mixins import DepartmentScopedMixin, ExaminerAssignmentMixin
from core.api.guards import SessionStateGuard
from core.api.serializers import (
    DepartmentListSerializer,
    DepartmentDetailSerializer,
    CoordinatorSummarySerializer,
    CourseSerializer,
    ExamListSerializer,
    ExamDetailSerializer,
    ExamSessionSerializer,
    PathSerializer,
    StationSerializer,
    ChecklistItemSerializer,
    ExaminerAssignmentReadSerializer,
    ExaminerAssignmentWriteSerializer,
    StationScoreReadSerializer,
    StationScoreCreateSerializer,
    StationScoreUpdateSerializer,
    ItemScoreSerializer,
    DepartmentReportSerializer,
)


# ── Department ───────────────────────────────────────────────────────

class DepartmentViewSet(DepartmentScopedMixin,
                        mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    """
    list:   Admin, Superuser only
    retrieve: Admin, Superuser, Coordinator (own department)
    """
    queryset = Department.objects.all()
    department_field = 'pk'  # Department IS the department

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DepartmentDetailSerializer
        return DepartmentListSerializer

    def get_permissions(self):
        if self.action == 'list':
            return [IsAuthenticated(), IsSuperuserOrAdmin()]
        # retrieve: coordinators can see their own dept (scoped by mixin)
        return [IsAuthenticated(), IsGlobalOrCoordinator()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # For coordinators on list action: filter to own dept only
        # (DepartmentScopedMixin handles this via department_field='pk')
        # For retrieve: the scoped queryset + get_object will return 404 if not own
        return qs


class DepartmentCoordinatorsViewSet(mixins.ListModelMixin,
                                    viewsets.GenericViewSet):
    """
    GET /departments/:dept_id/coordinators/
    Superuser, Admin, Coordinator (own department)
    """
    serializer_class = CoordinatorSummarySerializer
    permission_classes = [IsAuthenticated, IsGlobalOrCoordinator]

    def get_queryset(self):
        from core.models import Examiner
        dept_id = self.kwargs.get('dept_pk')
        user = self.request.user

        # For coordinators: verify they own this department
        if (not user.is_superuser
                and getattr(user, 'role', '') == 'coordinator'):
            coord_dept = getattr(user, 'coordinator_department', None)
            if coord_dept is None or str(coord_dept.pk) != str(dept_id):
                return Examiner.objects.none()

        return Examiner.objects.filter(
            role='coordinator',
            coordinator_department_id=dept_id,
            is_deleted=False,
        ).order_by('coordinator_position', 'full_name')


# ── Course (nested under department) ─────────────────────────────────

class CourseViewSet(DepartmentScopedMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    """
    GET /departments/:dept_id/courses/
    Superuser, Admin, Coordinator (own department)
    """
    serializer_class = CourseSerializer
    queryset = Course.objects.select_related('department').all()
    department_field = 'department'
    permission_classes = [IsAuthenticated, IsGlobalOrCoordinator]

    def get_queryset(self):
        qs = super().get_queryset()
        dept_id = self.kwargs.get('dept_pk')
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        return qs


# ── Exam ─────────────────────────────────────────────────────────────

class ExamViewSet(DepartmentScopedMixin,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    """
    list:     GET /courses/:course_id/exams/ — Superuser, Admin, Coordinator (own)
    retrieve: GET /exams/:id/                — Superuser, Admin, Coordinator (own)
    destroy:  DELETE /exams/:id/             — Superuser, Admin, Coordinator-Head (own)
    """
    queryset = Exam.objects.select_related('course', 'course__department').filter(is_deleted=False)
    department_field = 'course__department'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExamDetailSerializer
        return ExamListSerializer

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsGlobalOrCoordinatorHead()]
        return [IsAuthenticated(), IsGlobalOrCoordinator()]

    def get_queryset(self):
        qs = super().get_queryset()
        course_id = self.kwargs.get('course_pk')
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs

    def perform_destroy(self, instance):
        """Soft-delete the exam."""
        instance.soft_delete(user_id=self.request.user.pk)


# ── Exam Session ─────────────────────────────────────────────────────

class ExamSessionViewSet(DepartmentScopedMixin,
                         mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    """
    GET /exams/:exam_id/sessions/
    Superuser, Admin, Coordinator (own department)
    """
    serializer_class = ExamSessionSerializer
    queryset = ExamSession.objects.select_related('exam', 'exam__course', 'exam__course__department')
    department_field = 'exam__course__department'
    permission_classes = [IsAuthenticated, IsGlobalOrCoordinator]

    def get_queryset(self):
        qs = super().get_queryset()
        exam_id = self.kwargs.get('exam_pk')
        if exam_id:
            qs = qs.filter(exam_id=exam_id)
        return qs.order_by('-session_date')


# ── Path ─────────────────────────────────────────────────────────────

class PathViewSet(DepartmentScopedMixin,
                  mixins.ListModelMixin,
                  viewsets.GenericViewSet):
    """
    GET /sessions/:session_id/paths/
    Superuser, Admin, Coordinator (own department)

    Examiners are BLOCKED from path listing (attack scenario #3).
    """
    serializer_class = PathSerializer
    queryset = Path.objects.select_related(
        'session', 'session__exam', 'session__exam__course',
        'session__exam__course__department',
    ).filter(is_deleted=False)
    department_field = 'session__exam__course__department'
    permission_classes = [IsAuthenticated, IsGlobalOrCoordinator]

    def get_queryset(self):
        qs = super().get_queryset()
        session_id = self.kwargs.get('session_pk')
        if session_id:
            qs = qs.filter(session_id=session_id)
        return qs.order_by('name')


# ── Station ──────────────────────────────────────────────────────────

class StationViewSet(ExaminerAssignmentMixin,
                     DepartmentScopedMixin,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    list:     GET /paths/:path_id/stations/  — Superuser, Admin, Coordinator (own)
    retrieve: GET /stations/:id/             — + Examiner (assigned)
    """
    serializer_class = StationSerializer
    queryset = Station.objects.select_related(
        'path', 'path__session', 'path__session__exam',
        'path__session__exam__course', 'path__session__exam__course__department',
    ).filter(is_deleted=False, active=True)
    department_field = 'path__session__exam__course__department'

    def get_permissions(self):
        if self.action == 'list':
            return [IsAuthenticated(), IsGlobalOrCoordinator()]
        # retrieve: examiners (assigned) can access
        return [IsAuthenticated(), IsGlobalOrCoordinatorOrAssignedExaminer()]

    def get_queryset(self):
        qs = super().get_queryset()
        path_id = self.kwargs.get('path_pk')
        if path_id:
            qs = qs.filter(path_id=path_id)
        return qs.order_by('station_number')


# ── Checklist Items ──────────────────────────────────────────────────

class ChecklistItemViewSet(mixins.ListModelMixin,
                           viewsets.GenericViewSet):
    """
    GET /stations/:station_id/checklist/
    Superuser, Admin, Coordinator (own) + Examiner (assigned to station)

    Does not use ExaminerAssignmentMixin because ChecklistItem PKs
    are not Station IDs. Scoping done inline.
    """
    serializer_class = ChecklistItemSerializer
    permission_classes = [IsAuthenticated, IsGlobalOrCoordinatorOrAssignedExaminer]

    def get_queryset(self):
        """
        For examiners: filter to stations they're assigned to.
        For coordinators: filter to own department.
        For global roles: no filtering.
        """
        user = self.request.user
        station_id = self.kwargs.get('station_pk')

        base_qs = ChecklistItem.objects.select_related(
            'station', 'station__path', 'station__path__session',
        )
        if station_id:
            base_qs = base_qs.filter(station_id=station_id)

        if not user or not user.is_authenticated:
            return base_qs.none()

        # Global roles — no department scoping
        if user.is_superuser or getattr(user, 'role', '') == 'admin':
            return base_qs.order_by('item_number')

        if getattr(user, 'role', '') == 'coordinator':
            dept = getattr(user, 'coordinator_department', None)
            if dept is None:
                return base_qs.none()
            return base_qs.filter(
                station__path__session__exam__course__department=dept
            ).order_by('item_number')

        if getattr(user, 'role', '') == 'examiner':
            # Only see items for stations they're assigned to
            assigned_station_ids = ExaminerAssignment.objects.filter(
                examiner=user,
            ).values_list('station_id', flat=True)
            return base_qs.filter(
                station_id__in=assigned_station_ids
            ).order_by('item_number')

        return base_qs.none()


# ── Examiner Assignment ──────────────────────────────────────────────

class ExaminerAssignmentViewSet(DepartmentScopedMixin,
                                mixins.ListModelMixin,
                                mixins.CreateModelMixin,
                                viewsets.GenericViewSet):
    """
    GET  /stations/:station_id/assignments/ — Superuser, Admin, Coordinator (own)
    POST /stations/:station_id/assignments/ — Superuser, Admin, Coordinator (own)
    """
    queryset = ExaminerAssignment.objects.select_related('examiner', 'station', 'session')
    department_field = 'station__path__session__exam__course__department'
    permission_classes = [IsAuthenticated, IsGlobalOrCoordinator]

    def get_serializer_class(self):
        if self.action == 'create':
            return ExaminerAssignmentWriteSerializer
        return ExaminerAssignmentReadSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        station_id = self.kwargs.get('station_pk')
        if station_id:
            qs = qs.filter(station_id=station_id)
        return qs

    def perform_create(self, serializer):
        station_id = self.kwargs.get('station_pk')
        if station_id:
            station = get_object_or_404(Station, pk=station_id, is_deleted=False)
            serializer.save(station=station)
        else:
            serializer.save()


# ── Score ────────────────────────────────────────────────────────────

class StationScoreViewSet(SessionStateGuard,
                          DepartmentScopedMixin,
                          mixins.ListModelMixin,
                          mixins.CreateModelMixin,
                          mixins.UpdateModelMixin,
                          viewsets.GenericViewSet):
    """
    GET  /stations/:station_id/scores/  — Superuser, Admin, Coordinator (own), Examiner (assigned)
    POST /stations/:station_id/scores/  — Examiner (assigned + active session)
    PUT  /scores/:id/                   — Examiner (assigned + not finalized)

    Note: does NOT use ExaminerAssignmentMixin because StationScore PKs
    are NOT Station IDs. Examiner filtering is done inline.
    """
    queryset = StationScore.objects.select_related(
        'examiner', 'station', 'station__path',
        'station__path__session',
        'station__path__session__exam',
        'station__path__session__exam__course',
        'station__path__session__exam__course__department',
    )
    department_field = 'station__path__session__exam__course__department'

    def get_serializer_class(self):
        if self.action == 'create':
            return StationScoreCreateSerializer
        if self.action in ('update', 'partial_update'):
            return StationScoreUpdateSerializer
        return StationScoreReadSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [IsAuthenticated(), IsGlobalOrCoordinatorOrAssignedExaminer()]
        return [IsAuthenticated(), IsGlobalOrCoordinatorOrAssignedExaminer()]

    def get_queryset(self):
        qs = super().get_queryset()
        station_id = self.kwargs.get('station_pk')
        if station_id:
            qs = qs.filter(station_id=station_id)

        user = self.request.user
        # Examiners see only their own scores for stations they're assigned to
        if (not user.is_superuser
                and getattr(user, 'role', '') == 'examiner'):
            assigned_station_ids = ExaminerAssignment.objects.filter(
                examiner=user,
            ).values_list('station_id', flat=True)
            qs = qs.filter(examiner=user, station_id__in=assigned_station_ids)
        return qs

    def perform_create(self, serializer):
        """Create StationScore + nested ItemScores."""
        station_id = self.kwargs.get('station_pk')
        station = get_object_or_404(Station, pk=station_id, is_deleted=False)

        # Stash station for SessionStateGuard
        self._station = station

        # Let the guard check session state
        data = serializer.validated_data
        session_student_id = data['session_student_id']
        session_student = get_object_or_404(SessionStudent, pk=session_student_id)

        # Check session is active (via guard)
        session = station.path.session if station.path else None
        if session and session.status != 'in_progress':
            from core.api.guards import SessionNotActiveError
            raise SessionNotActiveError()

        # Create the station score
        score = StationScore.objects.create(
            session_student=session_student,
            station=station,
            examiner=self.request.user,
            max_score=station.get_max_score(),
            global_rating=data.get('global_rating'),
            comments=data.get('comments', ''),
            status='in_progress',
        )

        # Create item scores
        for item_data in data.get('item_scores', []):
            checklist_item = get_object_or_404(
                ChecklistItem, pk=item_data['checklist_item_id'], station=station
            )
            ItemScore.objects.create(
                station_score=score,
                checklist_item=checklist_item,
                score=item_data['score'],
                max_points=checklist_item.points,
                notes=item_data.get('notes', ''),
            )

        # Recalculate total
        score.calculate_total()
        score.save()

        # Return the read serializer data
        self._created_score = score

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.validate(serializer.initial_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read_serializer = StationScoreReadSerializer(self._created_score)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        """Update StationScore and optionally its ItemScores."""
        score = self.get_object()

        # SessionStateGuard check
        if (score.status == 'submitted'
                and not score.unlocked_for_correction):
            from core.api.guards import ScoreFinalizedError
            raise ScoreFinalizedError()

        if score.station and score.station.path:
            session = score.station.path.session
            if session and session.status not in ('in_progress',):
                from core.api.guards import SessionNotActiveError
                raise SessionNotActiveError()

        data = serializer.validated_data

        # Update scalar fields
        if 'global_rating' in data:
            score.global_rating = data['global_rating']
        if 'comments' in data:
            score.comments = data['comments']
        if 'status' in data:
            score.status = data['status']
            if data['status'] == 'submitted':
                from core.models.mixins import TimestampMixin
                score.completed_at = TimestampMixin.utc_timestamp()

        # Update item scores if provided
        if 'item_scores' in data:
            for item_data in data['item_scores']:
                checklist_item = get_object_or_404(
                    ChecklistItem,
                    pk=item_data['checklist_item_id'],
                    station=score.station,
                )
                ItemScore.objects.update_or_create(
                    station_score=score,
                    checklist_item=checklist_item,
                    defaults={
                        'score': item_data['score'],
                        'max_points': checklist_item.points,
                        'notes': item_data.get('notes', ''),
                    },
                )

        score.calculate_total()
        score.save()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        # Re-fetch with nested data
        instance.refresh_from_db()
        read_serializer = StationScoreReadSerializer(instance)
        return Response(read_serializer.data)


# ── Department Report ────────────────────────────────────────────────

class DepartmentReportViewSet(DepartmentScopedMixin,
                              mixins.RetrieveModelMixin,
                              viewsets.GenericViewSet):
    """
    GET /reports/department/:id/
    Superuser, Admin, Coordinator (own department)
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentReportSerializer
    department_field = 'pk'
    permission_classes = [IsAuthenticated, IsGlobalOrCoordinator]

    def retrieve(self, request, *args, **kwargs):
        dept = self.get_object()

        courses = Course.objects.filter(department=dept)
        exams = Exam.objects.filter(course__department=dept, is_deleted=False)
        sessions = ExamSession.objects.filter(exam__course__department=dept)

        # Sessions by status
        status_counts = {}
        for s in sessions.values('status').annotate(count=Count('id')):
            status_counts[s['status']] = s['count']

        # Total students scored
        total_scored = StationScore.objects.filter(
            station__path__session__exam__course__department=dept,
            status='submitted',
        ).values('session_student').distinct().count()

        data = {
            'department_id': dept.pk,
            'department_name': dept.name,
            'total_courses': courses.count(),
            'total_exams': exams.count(),
            'total_sessions': sessions.count(),
            'total_students_scored': total_scored,
            'sessions_by_status': status_counts,
        }
        serializer = self.get_serializer(data)
        return Response(serializer.data)
