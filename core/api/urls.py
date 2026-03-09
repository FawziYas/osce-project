"""
DRF API URL configuration — mounted at /api/v2/

Uses manually composed URL patterns (not DRF router) to support
the nested resource structure required by the permission map.
"""
from django.urls import path

from core.api.views import (
    DepartmentViewSet,
    DepartmentCoordinatorsViewSet,
    CourseViewSet,
    ExamViewSet,
    ExamSessionViewSet,
    PathViewSet,
    StationViewSet,
    ChecklistItemViewSet,
    ExaminerAssignmentViewSet,
    StationScoreViewSet,
    DepartmentReportViewSet,
)

app_name = 'api_v2'

# ── Helper: wrap ViewSet actions into view functions ─────────────────
dept_list = DepartmentViewSet.as_view({'get': 'list'})
dept_detail = DepartmentViewSet.as_view({'get': 'retrieve'})
dept_coordinators = DepartmentCoordinatorsViewSet.as_view({'get': 'list'})
dept_courses = CourseViewSet.as_view({'get': 'list'})

exam_list = ExamViewSet.as_view({'get': 'list'})
exam_detail = ExamViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'})

session_list = ExamSessionViewSet.as_view({'get': 'list'})

path_list = PathViewSet.as_view({'get': 'list'})

station_list = StationViewSet.as_view({'get': 'list'})
station_detail = StationViewSet.as_view({'get': 'retrieve'})

checklist_list = ChecklistItemViewSet.as_view({'get': 'list'})

assignment_list_create = ExaminerAssignmentViewSet.as_view({'get': 'list', 'post': 'create'})

score_list_create = StationScoreViewSet.as_view({'get': 'list', 'post': 'create'})
score_detail = StationScoreViewSet.as_view({'put': 'update', 'patch': 'partial_update'})

report_dept = DepartmentReportViewSet.as_view({'get': 'retrieve'})


urlpatterns = [
    # ── Departments ──────────────────────────────────────────────
    path('departments/',
         dept_list, name='department-list'),
    path('departments/<int:pk>/',
         dept_detail, name='department-detail'),
    path('departments/<int:dept_pk>/coordinators/',
         dept_coordinators, name='department-coordinators'),
    path('departments/<int:dept_pk>/courses/',
         dept_courses, name='department-courses'),

    # ── Courses → Exams ──────────────────────────────────────────
    path('courses/<int:course_pk>/exams/',
         exam_list, name='course-exam-list'),

    # ── Exams ────────────────────────────────────────────────────
    path('exams/<uuid:pk>/',
         exam_detail, name='exam-detail'),

    # ── Exams → Sessions ─────────────────────────────────────────
    path('exams/<uuid:exam_pk>/sessions/',
         session_list, name='exam-session-list'),

    # ── Sessions → Paths ─────────────────────────────────────────
    path('sessions/<uuid:session_pk>/paths/',
         path_list, name='session-path-list'),

    # ── Paths → Stations ─────────────────────────────────────────
    path('paths/<uuid:path_pk>/stations/',
         station_list, name='path-station-list'),

    # ── Stations ─────────────────────────────────────────────────
    path('stations/<uuid:pk>/',
         station_detail, name='station-detail'),
    path('stations/<uuid:station_pk>/checklist/',
         checklist_list, name='station-checklist'),
    path('stations/<uuid:station_pk>/assignments/',
         assignment_list_create, name='station-assignments'),

    # ── Scores ───────────────────────────────────────────────────
    path('stations/<uuid:station_pk>/scores/',
         score_list_create, name='station-scores'),
    path('scores/<uuid:pk>/',
         score_detail, name='score-detail'),

    # ── Reports ──────────────────────────────────────────────────
    path('reports/department/<int:pk>/',
         report_dept, name='department-report'),
]
