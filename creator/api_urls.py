"""Creator API URLs – all JSON endpoints under /api/creator/."""
from django.urls import path

from .api import courses, examiners, exams, library, paths, reports, sessions, stations, stats, students

app_name = 'creator_api'

urlpatterns = [
    # ── Courses & ILOs ──────────────────────────────────────────────────────
    path('courses', courses.get_courses, name='get_courses'),
    path('courses/<int:course_id>/ilos', courses.get_course_ilos, name='get_course_ilos'),
    path('ilos/<int:ilo_id>/library', courses.get_ilo_library, name='get_ilo_library'),

    # ── Exams ────────────────────────────────────────────────────────────────
    path('exams', exams.get_exams, name='get_exams'),
    path('exams/<uuid:exam_id>/stations', exams.get_exam_stations, name='get_exam_stations'),
    path('exams/<uuid:exam_id>/summary', exams.get_exam_summary, name='get_exam_summary'),
    path('exams/<uuid:exam_id>', exams.delete_exam_api, name='delete_exam'),
    path('exams/<uuid:exam_id>/restore', exams.restore_exam_api, name='restore_exam'),
    path('stations/<uuid:station_id>/items', exams.get_station_items, name='get_station_items'),

    # ── Stations (delete/restore) ────────────────────────────────────────────
    path('stations/<uuid:station_id>', stations.delete_station_api, name='delete_station'),
    path('stations/<uuid:station_id>/restore', stations.restore_station_api, name='restore_station'),

    # ── Sessions ─────────────────────────────────────────────────────────────
    path('sessions/<uuid:session_id>/status', sessions.get_session_status, name='session_status'),
    path('sessions/<uuid:session_id>/activate', sessions.activate_session, name='activate_session'),
    path('sessions/<uuid:session_id>/deactivate', sessions.deactivate_session, name='deactivate_session'),
    path('sessions/<uuid:session_id>/complete', sessions.complete_session, name='complete_session'),
    path('sessions/<uuid:session_id>', sessions.delete_session_api, name='delete_session'),
    path('sessions/<uuid:session_id>/restore', sessions.restore_session_api, name='restore_session'),
    path('sessions/<uuid:session_id>/hard-delete', sessions.hard_delete_session_api, name='hard_delete_session'),
    path('sessions/<uuid:session_id>/revert-to-scheduled', sessions.revert_session_to_scheduled, name='revert_session'),

    # ── Paths ────────────────────────────────────────────────────────────────
    path('sessions/<uuid:session_id>/paths', paths.get_session_paths, name='get_session_paths'),
    path('sessions/<uuid:session_id>/paths/create', paths.create_session_path, name='create_session_path'),
    path('paths/<uuid:path_id>', paths.get_path, name='get_path'),
    path('paths/<uuid:path_id>/update', paths.update_path, name='update_path'),
    path('paths/<uuid:path_id>/delete', paths.delete_path_api, name='delete_path'),
    path('paths/<uuid:path_id>/stations', paths.get_path_stations, name='get_path_stations'),
    path('paths/<uuid:path_id>/stations/add', paths.add_station_to_path, name='add_station_to_path'),
    path('paths/<uuid:path_id>/stations/<uuid:station_id>/remove', paths.remove_station_from_path, name='remove_station_from_path'),
    path('paths/<uuid:path_id>/stations/reorder', paths.reorder_path_stations, name='reorder_stations'),

    # ── Library ──────────────────────────────────────────────────────────────
    path('library', library.get_library, name='get_library'),
    path('library/create', library.create_library_item, name='create_library_item'),
    path('library/<int:item_id>/delete', library.delete_library_item, name='delete_library_item'),

    # ── Examiners ────────────────────────────────────────────────────────────
    path('examiners', examiners.get_examiners, name='get_examiners'),
    path('examiners/create', examiners.create_examiner_api, name='create_examiner'),
    path('sessions/<uuid:session_id>/assignments', examiners.get_session_assignments, name='get_assignments'),
    path('sessions/<uuid:session_id>/assignments/create', examiners.create_assignment, name='create_assignment'),

    # ── Students ─────────────────────────────────────────────────────────────
    path('students/<uuid:student_id>/path', students.update_student_path_assignment, name='update_student_path'),
    path('students/<uuid:student_id>', students.delete_student, name='delete_student'),
    path('sessions/<uuid:session_id>/students', students.delete_all_students, name='delete_all_students'),
    path('sessions/<uuid:session_id>/redistribute-students', students.redistribute_students, name='redistribute_students'),
    path('sessions/<uuid:session_id>/students/<uuid:student_id>/assign-path', students.assign_student_to_path, name='assign_student_path'),
    path('sessions/<uuid:session_id>/auto-assign-paths', students.auto_assign_paths, name='auto_assign_paths'),

    # ── Stats ────────────────────────────────────────────────────────────────
    path('stats/overview', stats.get_stats_overview, name='stats_overview'),

    # ── Reports / Exports ────────────────────────────────────────────────────
    path('reports/session/<uuid:session_id>/summary', reports.get_session_summary, name='session_summary'),
    path('reports/session/<uuid:session_id>/students/csv', reports.export_students_csv, name='export_students_csv'),
    path('reports/session/<uuid:session_id>/students/xlsx', reports.export_students_xlsx, name='export_students_xlsx'),
    path('reports/session/<uuid:session_id>/stations/csv', reports.export_stations_csv, name='export_stations_csv'),
    path('reports/session/<uuid:session_id>/raw/csv', reports.export_raw_csv, name='export_raw_csv'),
]
