"""Creator page URLs – all web-interface routes for the Creator interface."""
from django.urls import path

from .views import (
    dashboard,
    courses,
    exams,
    sessions,
    paths,
    stations,
    library,
    templates_views,
    examiners,
    students,
    reports,
)

app_name = 'creator'

urlpatterns = [
    # ── Dashboard ──────────────────────────────────────────────────────────
    path('', dashboard.dashboard, name='dashboard'),
    path('logout/', dashboard.logout_view, name='logout'),

    # ── Courses ────────────────────────────────────────────────────────────
    path('courses/', courses.course_list, name='course_list'),
    path('courses/new/', courses.course_create, name='course_create'),
    path('courses/<int:course_id>/', courses.course_detail, name='course_detail'),
    path('courses/<int:course_id>/edit/', courses.course_edit, name='course_edit'),

    # ── ILOs ───────────────────────────────────────────────────────────────
    path('courses/<int:course_id>/ilos/new/', courses.ilo_create, name='ilo_create'),
    path('ilos/<int:ilo_id>/edit/', courses.ilo_edit, name='ilo_edit'),

    # ── Exams ──────────────────────────────────────────────────────────────
    path('exams/', exams.exam_list, name='exam_list'),
    path('exams/wizard/', exams.exam_wizard, name='exam_wizard'),
    path('exams/new/', exams.exam_create, name='exam_create'),
    path('exams/<uuid:exam_id>/', exams.exam_detail, name='exam_detail'),
    path('exams/<uuid:exam_id>/edit/', exams.exam_edit, name='exam_edit'),
    path('exams/<uuid:exam_id>/delete/', exams.exam_delete, name='exam_delete'),
    path('exams/<uuid:exam_id>/archive/', exams.exam_archive, name='exam_archive'),
    path('exams/<uuid:exam_id>/restore/', exams.exam_restore, name='exam_restore'),
    path('exams/<uuid:exam_id>/permanent-delete/', exams.exam_permanent_delete, name='exam_permanent_delete'),

    # ── Sessions ───────────────────────────────────────────────────────────
    path('exams/<uuid:exam_id>/sessions/', sessions.session_list, name='session_list'),
    path('exams/<uuid:exam_id>/sessions/new/', sessions.session_create, name='session_create'),
    path('sessions/<uuid:session_id>/', sessions.session_detail, name='session_detail'),
    path('sessions/<uuid:session_id>/edit/', sessions.session_edit, name='session_edit'),
    path('sessions/<uuid:session_id>/delete/', sessions.session_delete, name='session_delete'),
    path('sessions/<uuid:session_id>/download-student-paths-pdf/', sessions.download_student_paths_pdf, name='download_student_paths_pdf'),
    path('sessions/<uuid:session_id>/assign-examiner/', sessions.assign_examiner, name='assign_examiner'),
    path('scores/<uuid:score_id>/unlock/', sessions.unlock_score_for_correction, name='unlock_score'),

    # ── Paths ──────────────────────────────────────────────────────────────
    path('paths/<uuid:path_id>/', paths.path_detail, name='path_detail'),
    path('sessions/<uuid:session_id>/paths/', paths.session_paths, name='session_paths'),
    path('sessions/<uuid:session_id>/paths/new/', paths.create_path, name='create_path'),
    path('sessions/<uuid:session_id>/paths/batch-create/', paths.batch_create_paths, name='batch_create_paths'),
    path('paths/<uuid:path_id>/edit/', paths.edit_path, name='edit_path'),
    path('paths/<uuid:path_id>/delete/', paths.delete_path, name='delete_path'),
    path('paths/<uuid:path_id>/restore/', paths.restore_path, name='restore_path'),

    # ── Stations ───────────────────────────────────────────────────────────
    path('paths/<uuid:path_id>/stations/new/', stations.station_create, name='station_create'),
    path('stations/<uuid:station_id>/', stations.station_detail, name='station_detail'),
    path('stations/<uuid:station_id>/edit/', stations.station_edit, name='station_edit'),
    path('stations/<uuid:station_id>/delete/', stations.station_delete, name='station_delete'),
    path('stations/<uuid:station_id>/restore/', stations.station_restore, name='station_restore'),

    # ── Checklist Library ──────────────────────────────────────────────────
    path('library/', library.library_list, name='library_list'),
    path('library/new/', library.library_item_create, name='library_item_create'),
    path('library/<int:item_id>/edit/', library.library_item_edit, name='library_item_edit'),

    # ── Station Template Library ───────────────────────────────────────────
    path('exams/<uuid:exam_id>/station-library/', templates_views.station_library, name='station_library'),
    path('exams/<uuid:exam_id>/station-library/new-library/', templates_views.template_library_create, name='template_library_create'),
    path('template-libraries/<int:library_id>/edit/', templates_views.template_library_edit, name='template_library_edit'),
    path('template-libraries/<int:library_id>/delete/', templates_views.template_library_delete, name='template_library_delete'),
    path('exams/<uuid:exam_id>/station-library/new/', templates_views.station_template_create, name='station_template_create'),
    path('station-templates/<int:template_id>/edit/', templates_views.station_template_edit, name='station_template_edit'),
    path('station-templates/<int:template_id>/delete/', templates_views.station_template_delete, name='station_template_delete'),
    path('sessions/<uuid:session_id>/apply-templates/', templates_views.apply_station_templates, name='apply_station_templates'),

    # ── Examiners ──────────────────────────────────────────────────────────
    path('examiners/', examiners.examiner_list, name='examiner_list'),
    path('examiners/template/', examiners.examiner_download_template, name='examiner_download_template'),
    path('examiners/bulk-upload/', examiners.examiner_bulk_upload, name='examiner_bulk_upload'),
    path('examiners/new/', examiners.examiner_create, name='examiner_create'),
    path('examiners/<int:examiner_id>/', examiners.examiner_detail, name='examiner_detail'),
    path('examiners/<int:examiner_id>/edit/', examiners.examiner_edit, name='examiner_edit'),
    path('examiners/<int:examiner_id>/delete/', examiners.examiner_delete, name='examiner_delete'),
    path('examiners/<int:examiner_id>/restore/', examiners.examiner_restore, name='examiner_restore'),
    path('examiners/<int:examiner_id>/permanent-delete/', examiners.examiner_permanent_delete, name='examiner_permanent_delete'),
    path('assignments/<uuid:assignment_id>/delete/', examiners.examiner_unassign, name='examiner_unassign'),
    # ── Coordinators ───────────────────────────────────────────
    path('coordinators/', examiners.coordinator_list, name='coordinator_list'),
    path('coordinators/new/', examiners.coordinator_create, name='coordinator_create'),
    path('coordinators/<int:coordinator_id>/delete/', examiners.coordinator_delete, name='coordinator_delete'),
    # ── Students ───────────────────────────────────────────────────────────
    path('sessions/<uuid:session_id>/students/add/', students.add_students, name='add_students'),
    path('sessions/<uuid:session_id>/students/upload-xlsx/', students.upload_students_xlsx, name='upload_students_xlsx'),

    # ── Reports ────────────────────────────────────────────────────────────
    path('reports/', reports.reports_index, name='reports_index'),
    path('reports/session/<uuid:session_id>/scoresheets/', reports.reports_scoresheets, name='reports_scoresheets'),
    path('reports/student/<uuid:student_id>/scoresheet/', reports.reports_student_scoresheet, name='reports_student_scoresheet'),
]
