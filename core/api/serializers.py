"""
DRF Serializers for the OSCE API.

Read-mostly serializers — the API is primarily for querying;
score creation/update is the main write path.
"""
from rest_framework import serializers

from core.models import (
    Department, Course, Exam, ExamSession, Path,
    Station, ChecklistItem, Examiner, ExaminerAssignment,
    StationScore, ItemScore, SessionStudent,
)


# ── Lightweight nested / summary serializers ─────────────────────────

class CoordinatorSummarySerializer(serializers.ModelSerializer):
    """Slim representation used when nesting coordinators inside a dept."""
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Examiner
        fields = ['id', 'username', 'full_name', 'display_name',
                  'coordinator_position', 'email']
        read_only_fields = fields


class ExaminerSummarySerializer(serializers.ModelSerializer):
    """Slim examiner representation for assignments and scores."""
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Examiner
        fields = ['id', 'username', 'full_name', 'display_name']
        read_only_fields = fields


# ── Department ───────────────────────────────────────────────────────

class DepartmentListSerializer(serializers.ModelSerializer):
    """Department list — lightweight."""
    coordinator_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'coordinator_count']
        read_only_fields = fields

    def get_coordinator_count(self, obj):
        return obj.coordinators.filter(is_deleted=False).count()


class DepartmentDetailSerializer(serializers.ModelSerializer):
    """Department detail — includes coordinators list."""
    coordinators = serializers.SerializerMethodField()
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'coordinators', 'course_count']
        read_only_fields = fields

    def get_coordinators(self, obj):
        qs = obj.coordinators.filter(is_deleted=False).order_by('coordinator_position', 'full_name')
        return CoordinatorSummarySerializer(qs, many=True).data

    def get_course_count(self, obj):
        return obj.courses.count()


# ── Course ───────────────────────────────────────────────────────────

class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    exam_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'code', 'short_code', 'name', 'description',
                  'year_level', 'department_id', 'department_name',
                  'osce_mark', 'exam_count']
        read_only_fields = fields

    def get_exam_count(self, obj):
        return obj.exams.filter(is_deleted=False).count()


# ── Exam ─────────────────────────────────────────────────────────────

class ExamListSerializer(serializers.ModelSerializer):
    """Exam in a list context — no nested stations."""
    course_code = serializers.CharField(source='course.code', read_only=True)
    station_count = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = ['id', 'name', 'description', 'exam_date', 'status',
                  'course_id', 'course_code', 'number_of_stations',
                  'station_duration_minutes', 'exam_weight',
                  'station_count']
        read_only_fields = fields

    def get_station_count(self, obj):
        return obj.stations.filter(is_deleted=False).count()


class ExamDetailSerializer(ExamListSerializer):
    """Exam detail — includes session count and total marks."""
    session_count = serializers.SerializerMethodField()
    total_marks = serializers.SerializerMethodField()

    class Meta(ExamListSerializer.Meta):
        fields = ExamListSerializer.Meta.fields + [
            'session_count', 'total_marks',
        ]

    def get_session_count(self, obj):
        return obj.sessions.count()

    def get_total_marks(self, obj):
        return obj.get_total_marks()


# ── Exam Session ─────────────────────────────────────────────────────

class ExamSessionSerializer(serializers.ModelSerializer):
    student_count = serializers.IntegerField(read_only=True, source='student_count_annotation', default=None)
    path_count = serializers.IntegerField(read_only=True, source='path_count_annotation', default=None)

    class Meta:
        model = ExamSession
        fields = ['id', 'name', 'session_date', 'session_type',
                  'start_time', 'number_of_stations', 'number_of_paths',
                  'status', 'notes', 'student_count', 'path_count']
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Fallback to property if annotation not present
        if data.get('student_count') is None:
            data['student_count'] = instance.student_count
        if data.get('path_count') is None:
            data['path_count'] = instance.path_count
        return data


# ── Path ─────────────────────────────────────────────────────────────

class PathSerializer(serializers.ModelSerializer):
    class Meta:
        model = Path
        fields = ['id', 'name', 'session_id', 'rotation_minutes',
                  'is_active']
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Properties return int from queryset counts
        data['station_count'] = instance.station_count
        data['student_count'] = instance.student_count
        return data


# ── Station ──────────────────────────────────────────────────────────

class StationSerializer(serializers.ModelSerializer):
    max_score = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Station
        fields = ['id', 'station_number', 'name', 'scenario',
                  'instructions', 'duration_minutes', 'active',
                  'path_id', 'exam_id', 'max_score', 'item_count']
        read_only_fields = fields

    def get_max_score(self, obj):
        return obj.get_max_score()

    def get_item_count(self, obj):
        return obj.checklist_items.count()


# ── Checklist Item ───────────────────────────────────────────────────

class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ['id', 'item_number', 'description', 'points',
                  'category', 'rubric_type', 'rubric_levels',
                  'expected_response', 'station_id', 'ilo_id']
        read_only_fields = fields


# ── Examiner Assignment ──────────────────────────────────────────────

class ExaminerAssignmentReadSerializer(serializers.ModelSerializer):
    """Read representation — includes nested examiner summary."""
    examiner = ExaminerSummarySerializer(read_only=True)

    class Meta:
        model = ExaminerAssignment
        fields = ['id', 'session_id', 'station_id', 'examiner']
        read_only_fields = fields


class ExaminerAssignmentWriteSerializer(serializers.ModelSerializer):
    """Write representation — accepts IDs only."""

    class Meta:
        model = ExaminerAssignment
        fields = ['session_id', 'station_id', 'examiner_id']

    def validate(self, attrs):
        # Ensure the station belongs to the session (via path)
        station = attrs.get('station')
        session = attrs.get('session')
        if station and session:
            if station.path and station.path.session_id != session.id:
                raise serializers.ValidationError(
                    'Station does not belong to this session.'
                )
        return attrs


# ── Scoring ──────────────────────────────────────────────────────────

class ItemScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemScore
        fields = ['id', 'checklist_item_id', 'score', 'max_points',
                  'marked_at', 'notes']
        read_only_fields = ['id']


class StationScoreReadSerializer(serializers.ModelSerializer):
    """Read-only detailed station score."""
    examiner = ExaminerSummarySerializer(read_only=True)
    item_scores = ItemScoreSerializer(many=True, read_only=True)

    class Meta:
        model = StationScore
        fields = ['id', 'session_student_id', 'station_id',
                  'examiner', 'total_score', 'max_score', 'percentage',
                  'global_rating', 'comments', 'status',
                  'unlocked_for_correction', 'started_at', 'completed_at',
                  'item_scores']
        read_only_fields = fields


class ItemScoreWriteSerializer(serializers.Serializer):
    """Nested item for score creation/update."""
    checklist_item_id = serializers.IntegerField()
    score = serializers.FloatField(min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class StationScoreCreateSerializer(serializers.Serializer):
    """
    Create a new StationScore with item scores.

    Used by examiners during active sessions.
    The station and session_student come from the URL context.
    """
    session_student_id = serializers.UUIDField()
    global_rating = serializers.IntegerField(required=False, allow_null=True)
    comments = serializers.CharField(required=False, allow_blank=True, default='')
    item_scores = ItemScoreWriteSerializer(many=True)

    def validate_item_scores(self, value):
        if not value:
            raise serializers.ValidationError('At least one item score is required.')
        return value


class StationScoreUpdateSerializer(serializers.Serializer):
    """
    Update an existing StationScore.

    Only allowed when score is not finalized (or unlocked_for_correction).
    """
    global_rating = serializers.IntegerField(required=False, allow_null=True)
    comments = serializers.CharField(required=False, allow_blank=True, default='')
    item_scores = ItemScoreWriteSerializer(many=True, required=False)
    status = serializers.ChoiceField(
        choices=['in_progress', 'submitted'],
        required=False,
    )


# ── Session Student (for reports) ────────────────────────────────────

class SessionStudentSerializer(serializers.ModelSerializer):
    stations_completed = serializers.IntegerField(read_only=True)
    total_score = serializers.FloatField(read_only=True)
    max_possible_score = serializers.FloatField(read_only=True)

    class Meta:
        model = SessionStudent
        fields = ['id', 'student_number', 'full_name', 'status',
                  'path_id', 'stations_completed', 'total_score',
                  'max_possible_score']
        read_only_fields = fields


# ── Department Report ────────────────────────────────────────────────

class DepartmentReportSerializer(serializers.Serializer):
    """Aggregated report data for a department."""
    department_id = serializers.IntegerField()
    department_name = serializers.CharField()
    total_courses = serializers.IntegerField()
    total_exams = serializers.IntegerField()
    total_sessions = serializers.IntegerField()
    total_students_scored = serializers.IntegerField()
    sessions_by_status = serializers.DictField(child=serializers.IntegerField())
