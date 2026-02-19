"""
Core model tests – verify model creation, relationships, and methods.
"""
from datetime import date, time

from django.test import TestCase

from core.models import (
    Course, ILO, Theme, Exam, Station, ChecklistItem, ChecklistLibrary,
    ExamSession, SessionStudent, Path, StationScore, ItemScore,
    Examiner, ExaminerAssignment,
)


class ExaminerModelTest(TestCase):
    """Test the custom Examiner (user) model."""

    def test_create_examiner(self):
        e = Examiner.objects.create_user(
            username='testexam', password='TestPass123!',
            full_name='Test Examiner', email='test@osce.local',
        )
        self.assertEqual(e.username, 'testexam')
        self.assertTrue(e.check_password('TestPass123!'))
        self.assertTrue(e.is_active)
        self.assertFalse(e.is_staff)

    def test_display_name(self):
        e = Examiner(username='jane', full_name='Jane Smith', title='Dr.')
        self.assertIn('Jane', e.display_name)


class CourseILOTest(TestCase):
    """Test Course and ILO creation."""

    def setUp(self):
        self.course = Course.objects.create(
            code='MED101', name='Medicine 1', year_level=1,
        )

    def test_course_str(self):
        self.assertIn('MED101', str(self.course))

    def test_ilo_creation(self):
        ilo = ILO.objects.create(
            course=self.course, number=1,
            description='Test ILO', osce_marks=10,
        )
        self.assertEqual(ilo.course, self.course)
        self.assertEqual(self.course.ilos.count(), 1)


class ExamStationTest(TestCase):
    """Test Exam and Station models."""

    def setUp(self):
        self.course = Course.objects.create(
            code='MED101', name='Medicine 1', year_level=1,
        )
        self.exam = Exam.objects.create(
            name='Test Exam', course=self.course, status='draft',
            exam_date=date(2025, 6, 1),
        )

    def test_exam_uuid_pk(self):
        self.assertIsNotNone(self.exam.pk)
        self.assertEqual(len(str(self.exam.pk)), 36)  # UUID format

    def test_soft_delete(self):
        self.exam.soft_delete()
        self.assertTrue(self.exam.is_deleted)
        self.exam.restore()
        self.assertFalse(self.exam.is_deleted)


class SessionPathTest(TestCase):
    """Test ExamSession, Path, and student assignment."""

    def setUp(self):
        self.course = Course.objects.create(
            code='MED101', name='Medicine 1', year_level=1,
        )
        self.exam = Exam.objects.create(
            name='Test Exam', course=self.course,
            exam_date=date(2025, 6, 1),
        )
        self.session = ExamSession.objects.create(
            exam=self.exam, name='Session A',
            session_date=date(2025, 6, 1),
            start_time=time(8, 0),
            number_of_stations=4,
            number_of_paths=2,
        )

    def test_session_creation(self):
        self.assertEqual(self.session.status, 'scheduled')

    def test_path_and_student(self):
        path = Path.objects.create(
            session=self.session, name='Path 1',
        )
        student = SessionStudent.objects.create(
            session=self.session,
            student_number='12345',
            full_name='Test Student',
            path=path,
        )
        self.assertEqual(student.path, path)
        self.assertEqual(path.students.count(), 1)


class ChecklistLibraryTest(TestCase):
    """Test ChecklistLibrary model."""

    def setUp(self):
        self.course = Course.objects.create(
            code='MED101', name='Medicine 1', year_level=1,
        )
        self.ilo = ILO.objects.create(
            course=self.course, number=1,
            description='Test ILO',
        )

    def test_library_item(self):
        item = ChecklistLibrary.objects.create(
            ilo=self.ilo,
            description='Check vital signs',
            is_critical=True,
            suggested_points=5,
        )
        self.assertTrue(item.is_critical)
        self.assertEqual(item.suggested_points, 5)
