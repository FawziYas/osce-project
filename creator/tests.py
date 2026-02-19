"""
Creator app tests – route smoke tests, API endpoint tests, and security tests.
"""
import json
from datetime import date, time

from django.test import TestCase, Client
from django.urls import reverse

from core.models import (
    Course, ILO, Exam, ExamSession, Path, Station, ChecklistItem,
    ChecklistLibrary, Examiner, ExaminerAssignment, SessionStudent,
)


class CreatorTestBase(TestCase):
    """Shared test fixtures for creator tests."""

    @classmethod
    def setUpTestData(cls):
        # Create admin user
        cls.user = Examiner.objects.create_user(
            username='admin', password='AdminPass123!',
            full_name='Admin User', email='admin@osce.local',
            is_staff=True,
        )
        # Course & ILO
        cls.course = Course.objects.create(
            code='MED101', name='Medicine 1', year_level=1,
        )
        cls.ilo = ILO.objects.create(
            course=cls.course, number=1,
            description='Test ILO', osce_marks=10,
        )
        # Library item
        cls.lib_item = ChecklistLibrary.objects.create(
            ilo=cls.ilo, description='Check vitals',
            is_critical=False, suggested_points=2,
        )
        # Exam
        cls.exam = Exam.objects.create(
            name='Test Exam', course=cls.course, status='draft',
            exam_date=date(2025, 6, 1),
        )
        # Session
        cls.session = ExamSession.objects.create(
            exam=cls.exam, name='Session A',
            session_date=date(2025, 6, 1),
            start_time=time(8, 0),
            number_of_stations=4,
            number_of_paths=2,
        )
        # Path
        cls.path = Path.objects.create(
            session=cls.session, name='Path 1',
        )
        # Station
        cls.station = Station.objects.create(
            exam=cls.exam, path=cls.path,
            station_number=1, name='Station 1',
            duration_minutes=8,
        )
        # Checklist item
        cls.checklist_item = ChecklistItem.objects.create(
            station=cls.station, ilo=cls.ilo,
            item_number=1, description='Check BP',
            points=5,
        )
        # Student
        cls.student = SessionStudent.objects.create(
            session=cls.session, student_number='12345',
            full_name='Test Student', path=cls.path,
        )
        # Another examiner (non-admin)
        cls.examiner = Examiner.objects.create_user(
            username='examiner1', password='ExPass123!',
            full_name='Test Examiner', email='ex1@osce.local',
        )
        # Assignment
        cls.assignment = ExaminerAssignment.objects.create(
            session=cls.session, station=cls.station,
            examiner=cls.examiner, is_primary=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='AdminPass123!')


# ── Page view smoke tests ─────────────────────────────────────────────────

class CreatorPageViewTests(CreatorTestBase):
    """Smoke test all creator page views return 200."""

    def test_dashboard(self):
        r = self.client.get(reverse('creator:dashboard'))
        self.assertEqual(r.status_code, 200)

    def test_course_list(self):
        r = self.client.get(reverse('creator:course_list'))
        self.assertEqual(r.status_code, 200)

    def test_course_detail(self):
        r = self.client.get(reverse('creator:course_detail', args=[self.course.id]))
        self.assertEqual(r.status_code, 200)

    def test_exam_list(self):
        r = self.client.get(reverse('creator:exam_list'))
        self.assertEqual(r.status_code, 200)

    def test_exam_detail(self):
        r = self.client.get(reverse('creator:exam_detail', args=[self.exam.id]))
        self.assertEqual(r.status_code, 200)

    def test_session_list(self):
        r = self.client.get(reverse('creator:session_list', args=[self.exam.id]))
        self.assertEqual(r.status_code, 200)

    def test_session_detail(self):
        r = self.client.get(reverse('creator:session_detail', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)

    def test_session_paths(self):
        r = self.client.get(reverse('creator:session_paths', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)

    def test_library_list(self):
        r = self.client.get(reverse('creator:library_list'))
        self.assertEqual(r.status_code, 200)

    def test_examiner_list(self):
        r = self.client.get(reverse('creator:examiner_list'))
        self.assertEqual(r.status_code, 200)

    def test_reports_index(self):
        r = self.client.get(reverse('creator:reports_index'))
        self.assertEqual(r.status_code, 200)


# ── Authentication tests ──────────────────────────────────────────────────

class CreatorAuthTests(TestCase):
    """Test that unauthenticated users are redirected."""

    def test_dashboard_requires_login(self):
        c = Client()
        r = c.get(reverse('creator:dashboard'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login', r.url)

    def test_api_requires_login(self):
        c = Client()
        r = c.get(reverse('creator_api:get_courses'))
        self.assertEqual(r.status_code, 302)


# ── API endpoint tests ───────────────────────────────────────────────────

class CreatorAPITests(CreatorTestBase):
    """Test creator API endpoints return JSON."""

    def test_get_courses(self):
        r = self.client.get(reverse('creator_api:get_courses'))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertIsInstance(data, list)
        self.assertTrue(any(c['code'] == 'MED101' for c in data))

    def test_get_course_ilos(self):
        r = self.client.get(reverse('creator_api:get_course_ilos', args=[self.course.id]))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertIsInstance(data, list)

    def test_get_exams(self):
        r = self.client.get(reverse('creator_api:get_exams'))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertIsInstance(data, list)

    def test_get_exam_stations(self):
        r = self.client.get(reverse('creator_api:get_exam_stations', args=[self.exam.id]))
        self.assertEqual(r.status_code, 200)

    def test_get_station_items(self):
        r = self.client.get(reverse('creator_api:get_station_items', args=[self.station.id]))
        self.assertEqual(r.status_code, 200)

    def test_get_exam_summary(self):
        r = self.client.get(reverse('creator_api:get_exam_summary', args=[self.exam.id]))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data['exam_name'], 'Test Exam')

    def test_session_status(self):
        r = self.client.get(reverse('creator_api:session_status', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)

    def test_get_session_paths(self):
        r = self.client.get(reverse('creator_api:get_session_paths', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)

    def test_get_path(self):
        r = self.client.get(reverse('creator_api:get_path', args=[self.path.id]))
        self.assertEqual(r.status_code, 200)

    def test_get_path_stations(self):
        r = self.client.get(reverse('creator_api:get_path_stations', args=[self.path.id]))
        self.assertEqual(r.status_code, 200)

    def test_get_library(self):
        r = self.client.get(reverse('creator_api:get_library'))
        self.assertEqual(r.status_code, 200)

    def test_get_examiners(self):
        r = self.client.get(reverse('creator_api:get_examiners'))
        self.assertEqual(r.status_code, 200)

    def test_get_session_assignments(self):
        r = self.client.get(reverse('creator_api:get_assignments', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)

    def test_stats_overview(self):
        r = self.client.get(reverse('creator_api:stats_overview'))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertIn('courses', data)
        self.assertIn('exams', data)

    def test_session_summary(self):
        r = self.client.get(reverse('creator_api:session_summary', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)


# ── API mutation tests ───────────────────────────────────────────────────

class CreatorAPIMutationTests(CreatorTestBase):
    """Test POST/PUT/DELETE API endpoints."""

    def test_activate_deactivate_session(self):
        # Activate
        r = self.client.post(reverse('creator_api:activate_session', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data['status'], 'in_progress')

        # Deactivate
        r = self.client.post(reverse('creator_api:deactivate_session', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)

    def test_complete_session(self):
        r = self.client.post(reverse('creator_api:complete_session', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data['status'], 'completed')

    def test_create_path(self):
        r = self.client.post(
            reverse('creator_api:create_session_path', args=[self.session.id]),
            data=json.dumps({'path_name': 'Path 2'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 201)

    def test_create_library_item(self):
        r = self.client.post(
            reverse('creator_api:create_library_item'),
            data=json.dumps({
                'ilo_id': self.ilo.id,
                'description': 'New library item',
            }),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 201)

    def test_create_examiner_api(self):
        r = self.client.post(
            reverse('creator_api:create_examiner'),
            data=json.dumps({
                'username': 'newexam',
                'full_name': 'New Examiner',
                'password': 'SecurePass99!',
            }),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 201)

    def test_create_assignment(self):
        # Create a new station for testing
        station2 = Station.objects.create(
            exam=self.exam, path=self.path,
            station_number=2, name='Station 2',
            duration_minutes=8,
        )
        r = self.client.post(
            reverse('creator_api:create_assignment', args=[self.session.id]),
            data=json.dumps({
                'station_id': str(station2.id),
                'examiner_id': self.examiner.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 201)

    def test_redistribute_students(self):
        r = self.client.post(
            reverse('creator_api:redistribute_students', args=[self.session.id]),
        )
        self.assertEqual(r.status_code, 200)

    def test_reorder_stations(self):
        r = self.client.post(
            reverse('creator_api:reorder_stations', args=[self.path.id]),
            data=json.dumps({'station_order': [str(self.station.id)]}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)


# ── Export tests ──────────────────────────────────────────────────────────

class CreatorExportTests(CreatorTestBase):
    """Test CSV/XLSX export endpoints."""

    def test_export_students_csv(self):
        r = self.client.get(reverse('creator_api:export_students_csv', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv')

    def test_export_stations_csv(self):
        r = self.client.get(reverse('creator_api:export_stations_csv', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv')

    def test_export_raw_csv(self):
        r = self.client.get(reverse('creator_api:export_raw_csv', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv')

    def test_export_students_xlsx(self):
        r = self.client.get(reverse('creator_api:export_students_xlsx', args=[self.session.id]))
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])


# ── Security header tests ────────────────────────────────────────────────

class SecurityHeaderTests(CreatorTestBase):
    """Test that security headers are present."""

    def test_csp_header(self):
        r = self.client.get(reverse('creator:dashboard'))
        self.assertIn('Content-Security-Policy', r)

    def test_referrer_policy(self):
        r = self.client.get(reverse('creator:dashboard'))
        self.assertEqual(r['Referrer-Policy'], 'strict-origin-when-cross-origin')

    def test_permissions_policy(self):
        r = self.client.get(reverse('creator:dashboard'))
        self.assertIn('Permissions-Policy', r)

    def test_x_frame_options(self):
        r = self.client.get(reverse('creator:dashboard'))
        self.assertIn('X-Frame-Options', r)
