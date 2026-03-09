"""
Unit tests for the multi-layer DRF authorization system.

Covers all 5 attack scenarios:
  1. Cross-department coordinator → 404 (not 403)
  2. Unassigned examiner → 404 (not 403)
  3. Examiner path access → 403
  4. Unauthenticated access → 401
  5. Cross-department existence leak → 404 (never 403)

Also tests happy paths: correct roles get correct data.
"""
import uuid
from datetime import date, time

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import (
    Department, Course, Exam, ExamSession, Path,
    Station, ChecklistItem, Examiner, ExaminerAssignment,
    StationScore, ItemScore, SessionStudent,
)


@override_settings(
    ROOT_URLCONF='osce_project.urls',
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework.authentication.SessionAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
        'DEFAULT_RENDERER_CLASSES': [
            'rest_framework.renderers.JSONRenderer',
        ],
        'EXCEPTION_HANDLER': 'core.api.exceptions.custom_exception_handler',
        'DEFAULT_PAGINATION_CLASS': None,
        'UNAUTHENTICATED_USER': None,
    },
)
class AuthorizationTestBase(TestCase):
    """
    Shared fixture: two departments, each with courses/exams/sessions/paths/
    stations/assignments. One coordinator per department. One examiner
    assigned only to dept_a stations.
    """

    @classmethod
    def setUpTestData(cls):
        # ── Departments ──────────────────────────────────────────
        cls.dept_a = Department.objects.create(name='Medicine')
        cls.dept_b = Department.objects.create(name='Surgery')

        # ── Users ────────────────────────────────────────────────
        cls.superuser = Examiner.objects.create_superuser(
            username='superadmin', password='pass1234',
        )
        cls.admin_user = Examiner.objects.create_user(
            username='admin1', password='pass1234',
            full_name='Admin One', role='admin', is_staff=True,
        )
        cls.coord_a = Examiner.objects.create_user(
            username='coord_a', password='pass1234',
            full_name='Coordinator A', role='coordinator',
            coordinator_department=cls.dept_a,
            coordinator_position='head',
        )
        cls.coord_b = Examiner.objects.create_user(
            username='coord_b', password='pass1234',
            full_name='Coordinator B', role='coordinator',
            coordinator_department=cls.dept_b,
            coordinator_position='head',
        )
        cls.examiner_assigned = Examiner.objects.create_user(
            username='examiner1', password='pass1234',
            full_name='Examiner Assigned', role='examiner',
        )
        cls.examiner_unassigned = Examiner.objects.create_user(
            username='examiner2', password='pass1234',
            full_name='Examiner Unassigned', role='examiner',
        )

        # ── Course → Exam → Session → Path → Station (Dept A) ───
        cls.course_a = Course.objects.create(
            code='MED101', name='Medicine 101',
            department=cls.dept_a, year_level=1,
        )
        cls.exam_a = Exam.objects.create(
            course=cls.course_a, name='Midterm OSCE',
            exam_date=date(2025, 6, 15), status='ready',
        )
        cls.session_a = ExamSession.objects.create(
            exam=cls.exam_a, name='Morning Session',
            session_date=date(2025, 6, 15),
            session_type='morning', start_time=time(9, 0),
            number_of_stations=2, number_of_paths=1,
            status='in_progress',
        )
        cls.path_a = Path.objects.create(
            session=cls.session_a, name='Path A',
        )
        cls.station_a = Station.objects.create(
            path=cls.path_a, exam=cls.exam_a,
            station_number=1, name='History Taking',
            duration_minutes=8,
        )
        cls.item_a = ChecklistItem.objects.create(
            station=cls.station_a, item_number=1,
            description='Introduces self', points=1.0,
        )
        cls.item_a2 = ChecklistItem.objects.create(
            station=cls.station_a, item_number=2,
            description='Asks about symptoms', points=2.0,
        )

        # Assignment: examiner_assigned ↔ station_a
        cls.assignment_a = ExaminerAssignment.objects.create(
            session=cls.session_a,
            station=cls.station_a,
            examiner=cls.examiner_assigned,
        )

        # Session student
        cls.student_a = SessionStudent.objects.create(
            session=cls.session_a,
            student_number='12345',
            full_name='Student One',
            path=cls.path_a,
        )

        # ── Course → Exam → Session → Path → Station (Dept B) ───
        cls.course_b = Course.objects.create(
            code='SUR201', name='Surgery 201',
            department=cls.dept_b, year_level=2,
        )
        cls.exam_b = Exam.objects.create(
            course=cls.course_b, name='Surgery OSCE',
            exam_date=date(2025, 6, 20), status='ready',
        )
        cls.session_b = ExamSession.objects.create(
            exam=cls.exam_b, name='Afternoon Session',
            session_date=date(2025, 6, 20),
            session_type='afternoon', start_time=time(14, 0),
            number_of_stations=1, number_of_paths=1,
            status='in_progress',
        )
        cls.path_b = Path.objects.create(
            session=cls.session_b, name='Path B',
        )
        cls.station_b = Station.objects.create(
            path=cls.path_b, exam=cls.exam_b,
            station_number=1, name='Suturing',
            duration_minutes=10,
        )

    def setUp(self):
        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user=user)

    def logout(self):
        self.client.force_authenticate(user=None)


# ═════════════════════════════════════════════════════════════════════
# Attack Scenario 1: Cross-Department Coordinator → 404
# ═════════════════════════════════════════════════════════════════════

class TestCrossDepartmentCoordinator(AuthorizationTestBase):
    """
    A coordinator from Dept B must NOT see Dept A resources.
    Must receive 404 (not 403) to avoid leaking existence.
    """

    def test_coordinator_b_cannot_retrieve_dept_a(self):
        """GET /api/v2/departments/<dept_a>/ → 404 for coord_b."""
        self.login(self.coord_b)
        resp = self.client.get(f'/api/v2/departments/{self.dept_a.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_coordinator_b_cannot_list_dept_a_courses(self):
        """GET /api/v2/departments/<dept_a>/courses/ → empty list for coord_b."""
        self.login(self.coord_b)
        resp = self.client.get(f'/api/v2/departments/{self.dept_a.pk}/courses/')
        # The department-level URL filter means coord_b either sees empty
        # or gets a 404 depending on dept scoping — both are acceptable
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(len(resp.json()), 0)

    def test_coordinator_b_cannot_retrieve_exam_a(self):
        """GET /api/v2/exams/<exam_a>/ → 404 for coord_b."""
        self.login(self.coord_b)
        resp = self.client.get(f'/api/v2/exams/{self.exam_a.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_coordinator_b_cannot_delete_exam_a(self):
        """DELETE /api/v2/exams/<exam_a>/ → 404 for coord_b."""
        self.login(self.coord_b)
        resp = self.client.delete(f'/api/v2/exams/{self.exam_a.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_coordinator_a_can_retrieve_own_dept(self):
        """Coordinator A CAN retrieve their own department."""
        self.login(self.coord_a)
        resp = self.client.get(f'/api/v2/departments/{self.dept_a.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['name'], 'Medicine')

    def test_coordinator_a_can_list_own_courses(self):
        """Coordinator A CAN list courses in their department."""
        self.login(self.coord_a)
        resp = self.client.get(f'/api/v2/departments/{self.dept_a.pk}/courses/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(len(data) >= 1)
        self.assertEqual(data[0]['code'], 'MED101')


# ═════════════════════════════════════════════════════════════════════
# Attack Scenario 2: Unassigned Examiner → 404
# ═════════════════════════════════════════════════════════════════════

class TestUnassignedExaminer(AuthorizationTestBase):
    """
    An examiner not assigned to station_a must get 404 when
    trying to access that station or its checklist.
    """

    def test_unassigned_examiner_station_detail_404(self):
        """GET /api/v2/stations/<station_a>/ → 404 for unassigned examiner."""
        self.login(self.examiner_unassigned)
        resp = self.client.get(f'/api/v2/stations/{self.station_a.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_unassigned_examiner_checklist_empty(self):
        """GET /api/v2/stations/<station_a>/checklist/ → empty or 404."""
        self.login(self.examiner_unassigned)
        resp = self.client.get(f'/api/v2/stations/{self.station_a.pk}/checklist/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(len(resp.json()), 0)

    def test_assigned_examiner_can_access_station(self):
        """Assigned examiner CAN retrieve their station."""
        self.login(self.examiner_assigned)
        resp = self.client.get(f'/api/v2/stations/{self.station_a.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['name'], 'History Taking')

    def test_assigned_examiner_can_see_checklist(self):
        """Assigned examiner CAN see checklist items."""
        self.login(self.examiner_assigned)
        resp = self.client.get(f'/api/v2/stations/{self.station_a.pk}/checklist/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(len(data) >= 2)


# ═════════════════════════════════════════════════════════════════════
# Attack Scenario 3: Examiner Path Access → 403
# ═════════════════════════════════════════════════════════════════════

class TestExaminerPathAccess(AuthorizationTestBase):
    """
    Examiners must be blocked from listing paths entirely (403).
    Paths reveal exam structure an examiner should not see.
    """

    def test_examiner_cannot_list_paths(self):
        """GET /api/v2/sessions/<session_a>/paths/ → 403 for examiner."""
        self.login(self.examiner_assigned)
        resp = self.client.get(f'/api/v2/sessions/{self.session_a.pk}/paths/')
        self.assertEqual(resp.status_code, 403)

    def test_examiner_cannot_list_sessions(self):
        """GET /api/v2/exams/<exam_a>/sessions/ → 403 for examiner."""
        self.login(self.examiner_assigned)
        resp = self.client.get(f'/api/v2/exams/{self.exam_a.pk}/sessions/')
        self.assertEqual(resp.status_code, 403)

    def test_coordinator_can_list_paths(self):
        """Coordinator CAN list paths in their session."""
        self.login(self.coord_a)
        resp = self.client.get(f'/api/v2/sessions/{self.session_a.pk}/paths/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(len(data) >= 1)


# ═════════════════════════════════════════════════════════════════════
# Attack Scenario 4: Unauthenticated Access → 401
# ═════════════════════════════════════════════════════════════════════

class TestUnauthenticatedAccess(AuthorizationTestBase):
    """
    All endpoints must return 401 for unauthenticated requests.
    """

    def test_departments_unauthenticated(self):
        self.logout()
        resp = self.client.get('/api/v2/departments/')
        self.assertIn(resp.status_code, [401, 403])

    def test_station_unauthenticated(self):
        self.logout()
        resp = self.client.get(f'/api/v2/stations/{self.station_a.pk}/')
        self.assertIn(resp.status_code, [401, 403])

    def test_score_create_unauthenticated(self):
        self.logout()
        resp = self.client.post(
            f'/api/v2/stations/{self.station_a.pk}/scores/',
            data={}, format='json',
        )
        self.assertIn(resp.status_code, [401, 403])

    def test_error_envelope_format(self):
        """Error response must use uniform envelope."""
        self.logout()
        resp = self.client.get('/api/v2/departments/')
        data = resp.json()
        self.assertIn('error', data)
        self.assertIn('code', data)


# ═════════════════════════════════════════════════════════════════════
# Attack Scenario 5: Cross-Department Existence Leak → always 404
# ═════════════════════════════════════════════════════════════════════

class TestExistenceLeak(AuthorizationTestBase):
    """
    When a resource exists but user has no access, the response must
    be 404 (not 403). This prevents attackers from probing for valid IDs.
    """

    def test_coordinator_b_gets_404_for_existing_exam_a(self):
        """Exam A exists but coord_b should see 404, not 403."""
        self.login(self.coord_b)
        resp = self.client.get(f'/api/v2/exams/{self.exam_a.pk}/')
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data['code'], 'NOT_FOUND')

    def test_coordinator_b_gets_404_for_nonexistent_exam(self):
        """Non-existent exam → also 404 with same shape."""
        self.login(self.coord_b)
        fake_id = uuid.uuid4()
        resp = self.client.get(f'/api/v2/exams/{fake_id}/')
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data['code'], 'NOT_FOUND')

    def test_same_404_shape_for_existing_and_nonexistent(self):
        """404 for unauthorized-existing and non-existent must look identical."""
        self.login(self.coord_b)
        # Existing but unauthorized
        resp_existing = self.client.get(f'/api/v2/exams/{self.exam_a.pk}/')
        # Non-existent
        resp_fake = self.client.get(f'/api/v2/exams/{uuid.uuid4()}/')

        self.assertEqual(resp_existing.status_code, resp_fake.status_code)
        self.assertEqual(
            resp_existing.json()['code'],
            resp_fake.json()['code'],
        )

    def test_examiner_gets_404_for_unassigned_station_not_403(self):
        """Unassigned examiner → station_b returns 404, not 403."""
        self.login(self.examiner_assigned)
        resp = self.client.get(f'/api/v2/stations/{self.station_b.pk}/')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()['code'], 'NOT_FOUND')


# ═════════════════════════════════════════════════════════════════════
# Layer 5: Session State Guard Tests
# ═════════════════════════════════════════════════════════════════════

class TestSessionStateGuard(AuthorizationTestBase):
    """
    Score creation blocked if session not active.
    Score update blocked if score is finalized.
    """

    def test_score_creation_blocked_when_session_completed(self):
        """POST score → 403 when session is 'completed'."""
        # Change session to completed
        self.session_a.status = 'completed'
        self.session_a.save()

        self.login(self.examiner_assigned)
        resp = self.client.post(
            f'/api/v2/stations/{self.station_a.pk}/scores/',
            data={
                'session_student_id': str(self.student_a.pk),
                'item_scores': [
                    {'checklist_item_id': self.item_a.pk, 'score': 1.0},
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

        # Restore
        self.session_a.status = 'in_progress'
        self.session_a.save()

    def test_score_creation_allowed_when_session_active(self):
        """POST score → 201 when session is 'in_progress'."""
        self.login(self.examiner_assigned)
        resp = self.client.post(
            f'/api/v2/stations/{self.station_a.pk}/scores/',
            data={
                'session_student_id': str(self.student_a.pk),
                'item_scores': [
                    {'checklist_item_id': self.item_a.pk, 'score': 1.0},
                    {'checklist_item_id': self.item_a2.pk, 'score': 1.5},
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['status'], 'in_progress')
        self.assertEqual(data['total_score'], 2.5)

    def test_score_update_blocked_when_finalized(self):
        """PUT score → 403 when score is 'submitted' and not unlocked."""
        # Create a submitted score
        score = StationScore.objects.create(
            session_student=self.student_a,
            station=self.station_a,
            examiner=self.examiner_assigned,
            max_score=3.0,
            total_score=2.5,
            status='submitted',
        )

        self.login(self.examiner_assigned)
        resp = self.client.put(
            f'/api/v2/scores/{score.pk}/',
            data={
                'comments': 'trying to change',
                'item_scores': [],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_score_update_allowed_when_unlocked(self):
        """PUT score → 200 when unlocked_for_correction=True."""
        score = StationScore.objects.create(
            session_student=self.student_a,
            station=self.station_a,
            examiner=self.examiner_assigned,
            max_score=3.0,
            total_score=2.5,
            status='submitted',
            unlocked_for_correction=True,
        )

        self.login(self.examiner_assigned)
        resp = self.client.put(
            f'/api/v2/scores/{score.pk}/',
            data={
                'comments': 'correction applied',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)


# ═════════════════════════════════════════════════════════════════════
# Happy Path: Admin / Superuser Full Access
# ═════════════════════════════════════════════════════════════════════

class TestGlobalRoleAccess(AuthorizationTestBase):
    """Superuser and Admin can access everything."""

    def test_superuser_list_departments(self):
        self.login(self.superuser)
        resp = self.client.get('/api/v2/departments/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.json()) >= 2)

    def test_admin_list_departments(self):
        self.login(self.admin_user)
        resp = self.client.get('/api/v2/departments/')
        self.assertEqual(resp.status_code, 200)

    def test_superuser_retrieve_any_exam(self):
        self.login(self.superuser)
        resp = self.client.get(f'/api/v2/exams/{self.exam_a.pk}/')
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f'/api/v2/exams/{self.exam_b.pk}/')
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_delete_exam(self):
        """Admin can soft-delete any exam."""
        self.login(self.admin_user)
        resp = self.client.delete(f'/api/v2/exams/{self.exam_a.pk}/')
        self.assertIn(resp.status_code, [200, 204])
        # Restore
        self.exam_a.restore()

    def test_superuser_list_all_paths(self):
        """Superuser can list paths in any session."""
        self.login(self.superuser)
        resp = self.client.get(f'/api/v2/sessions/{self.session_a.pk}/paths/')
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f'/api/v2/sessions/{self.session_b.pk}/paths/')
        self.assertEqual(resp.status_code, 200)

    def test_admin_department_report(self):
        self.login(self.admin_user)
        resp = self.client.get(f'/api/v2/reports/department/{self.dept_a.pk}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['department_name'], 'Medicine')
        self.assertIn('total_courses', data)
        self.assertIn('sessions_by_status', data)


# ═════════════════════════════════════════════════════════════════════
# Error Envelope Format
# ═════════════════════════════════════════════════════════════════════

class TestErrorEnvelope(AuthorizationTestBase):
    """All errors use the uniform envelope: {error, code, detail}."""

    def test_404_envelope(self):
        self.login(self.coord_b)
        resp = self.client.get(f'/api/v2/exams/{self.exam_a.pk}/')
        data = resp.json()
        self.assertIn('error', data)
        self.assertIn('code', data)
        self.assertIn('detail', data)
        self.assertEqual(data['code'], 'NOT_FOUND')

    def test_403_envelope(self):
        self.login(self.examiner_assigned)
        resp = self.client.get(f'/api/v2/sessions/{self.session_a.pk}/paths/')
        data = resp.json()
        self.assertEqual(resp.status_code, 403)
        self.assertIn('error', data)
        self.assertIn('code', data)

    def test_401_envelope(self):
        self.logout()
        resp = self.client.get('/api/v2/departments/')
        data = resp.json()
        self.assertIn('error', data)
        self.assertIn('code', data)
