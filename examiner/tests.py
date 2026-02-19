"""
Examiner app tests – login, page views, and authentication requirements.
"""
from datetime import date, time

from django.test import TestCase, Client
from django.urls import reverse

from core.models import (
    Course, Exam, ExamSession, Path, Station, ChecklistItem,
    Examiner, ExaminerAssignment, SessionStudent, ILO,
)


class ExaminerTestBase(TestCase):
    """Shared fixtures for examiner tests."""

    @classmethod
    def setUpTestData(cls):
        cls.course = Course.objects.create(
            code='MED101', name='Medicine 1', year_level=1,
        )
        cls.ilo = ILO.objects.create(
            course=cls.course, number=1, description='Test ILO',
        )
        cls.exam = Exam.objects.create(
            name='Test Exam', course=cls.course,
            exam_date=date(2025, 6, 1),
        )
        cls.session = ExamSession.objects.create(
            exam=cls.exam, name='Session A', status='in_progress',
            session_date=date(2025, 6, 1),
            start_time=time(8, 0),
            number_of_stations=4,
            number_of_paths=2,
        )
        cls.path = Path.objects.create(
            session=cls.session, name='Path 1',
        )
        cls.station = Station.objects.create(
            exam=cls.exam, path=cls.path,
            station_number=1, name='Station 1',
            duration_minutes=8,
        )
        cls.item = ChecklistItem.objects.create(
            station=cls.station, ilo=cls.ilo,
            item_number=1, description='Check BP', points=5,
        )
        cls.examiner = Examiner.objects.create_user(
            username='examiner1', password='ExamPass123!',
            full_name='Test Examiner', email='ex@osce.local',
        )
        cls.assignment = ExaminerAssignment.objects.create(
            session=cls.session, station=cls.station,
            examiner=cls.examiner, is_primary=True,
        )
        cls.student = SessionStudent.objects.create(
            session=cls.session, student_number='12345',
            full_name='Test Student', path=cls.path,
        )


class ExaminerLoginTest(ExaminerTestBase):
    """Test the examiner login flow."""

    def test_login_page(self):
        r = self.client.get(reverse('examiner:login'))
        self.assertEqual(r.status_code, 200)

    def test_login_success(self):
        r = self.client.post(reverse('examiner:login'), {
            'username': 'examiner1', 'password': 'ExamPass123!',
        })
        self.assertIn(r.status_code, [200, 302])

    def test_login_failure(self):
        r = self.client.post(reverse('examiner:login'), {
            'username': 'examiner1', 'password': 'wrong',
        })
        self.assertEqual(r.status_code, 200)  # Re-renders form

    def test_index_no_login(self):
        r = self.client.get(reverse('examiner:index'))
        self.assertEqual(r.status_code, 302)  # index redirects to login

    def test_offline_page(self):
        r = self.client.get(reverse('examiner:offline'))
        self.assertEqual(r.status_code, 200)  # offline is public


class ExaminerAuthenticatedTest(ExaminerTestBase):
    """Test examiner pages behind login."""

    def setUp(self):
        self.client = Client()
        self.client.login(username='examiner1', password='ExamPass123!')

    def test_home_page(self):
        r = self.client.get(reverse('examiner:home'))
        self.assertEqual(r.status_code, 200)

    def test_all_sessions(self):
        r = self.client.get(reverse('examiner:all_sessions'))
        self.assertEqual(r.status_code, 200)

    def test_station_dashboard(self):
        r = self.client.get(
            reverse('examiner:station_dashboard', args=[self.assignment.id])
        )
        self.assertEqual(r.status_code, 200)

    def test_select_student(self):
        r = self.client.get(
            reverse('examiner:select_student', args=[self.assignment.id])
        )
        self.assertEqual(r.status_code, 200)

    def test_marking_interface(self):
        r = self.client.get(reverse(
            'examiner:marking_interface',
            args=[self.assignment.id, self.student.id],
        ))
        self.assertEqual(r.status_code, 200)

    def test_home_requires_login(self):
        c = Client()
        r = c.get(reverse('examiner:home'))
        self.assertEqual(r.status_code, 302)
