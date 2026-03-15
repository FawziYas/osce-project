"""
Tests for dry exam verification modal – API endpoints and token validation.
"""
import json
from datetime import date, time
from unittest.mock import patch

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from core.models import (
    Course, Exam, ExamSession, Path, Station, ChecklistItem,
    Examiner, ExaminerAssignment, SessionStudent, ILO,
)
from core.models.user_profile import UserProfile
from core.signals import log_successful_login, log_failed_login


@override_settings(
    AXES_ENABLED=False,
    AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend'],
)
class DryVerifyTestBase(TestCase):
    """Shared fixtures for dry verification tests."""

    @classmethod
    def setUpTestData(cls):
        # Disconnect login signals to avoid audit log issues in tests
        user_logged_in.disconnect(log_successful_login)
        user_login_failed.disconnect(log_failed_login)

        cls.course = Course.objects.create(
            code='MED201', name='Medicine 2', year_level=2,
        )
        cls.ilo = ILO.objects.create(
            course=cls.course, number=1, description='Test ILO',
        )
        cls.exam = Exam.objects.create(
            name='Dry Exam', course=cls.course,
            exam_date=date(2025, 6, 1),
        )
        cls.session = ExamSession.objects.create(
            exam=cls.exam, name='Dry Session A', status='in_progress',
            session_date=date(2025, 6, 1),
            start_time=time(8, 0),
            number_of_stations=2,
            number_of_paths=1,
        )
        cls.path = Path.objects.create(
            session=cls.session, name='Path 1',
        )
        cls.station = Station.objects.create(
            exam=cls.exam, path=cls.path,
            station_number=1, name='Dry Station 1',
            duration_minutes=8, is_dry=True,
        )
        cls.item = ChecklistItem.objects.create(
            station=cls.station, ilo=cls.ilo,
            item_number=1, description='Check BP', points=5,
        )
        cls.examiner = Examiner.objects.create_user(
            username='dry_examiner', password='ExamPass123!',
            full_name='Dry Examiner', email='dry@osce.local',
        )
        # Re-set password after creation because provision_new_user signal
        # overwrites it with DEFAULT_USER_PASSWORD
        cls.examiner.set_password('ExamPass123!')
        cls.examiner.save(update_fields=['password'])
        cls.other_examiner = Examiner.objects.create_user(
            username='other_examiner', password='OtherPass123!',
            full_name='Other Examiner', email='other@osce.local',
        )
        # Disable forced password change for test users
        UserProfile.objects.filter(
            user__in=[cls.examiner, cls.other_examiner]
        ).update(must_change_password=False)
        cls.assignment = ExaminerAssignment.objects.create(
            session=cls.session, station=cls.station,
            examiner=cls.examiner,
        )
        cls.student = SessionStudent.objects.create(
            session=cls.session, student_number='11844785',
            full_name='John Doe', path=cls.path,
        )

    @classmethod
    def tearDownClass(cls):
        # Reconnect signals
        user_logged_in.connect(log_successful_login)
        user_login_failed.connect(log_failed_login)
        super().tearDownClass()


class VerifyStudentRegistrationTest(DryVerifyTestBase):
    """Test POST /api/dry/verify-student-registration/."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('examiner_api:verify_student_reg')

    def _login(self):
        self.client.force_login(self.examiner)

    def test_unauthenticated_returns_302(self):
        """Unauthenticated request redirects to login."""
        r = self.client.post(self.url, json.dumps({
            'student_number': '11844785',
            'student_id': str(self.student.id),
            'session_id': str(self.session.id),
            'assignment_id': str(self.assignment.id),
        }), content_type='application/json')
        self.assertEqual(r.status_code, 302)

    def test_valid_registration_passes(self):
        """Correct student number returns valid=True with redirect_url."""
        self._login()
        r = self.client.post(self.url, json.dumps({
            'student_number': '11844785',
            'student_id': str(self.student.id),
            'session_id': str(self.session.id),
            'assignment_id': str(self.assignment.id),
        }), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['valid'])
        self.assertIn('redirect_url', data)
        # redirect_url is now a plain path (session-based auth, no token in URL)
        self.assertTrue(data['redirect_url'].startswith('/'))

    def test_case_insensitive_match(self):
        """Registration number matching is case-insensitive."""
        self._login()
        r = self.client.post(self.url, json.dumps({
            'student_number': '11844785',
            'student_id': str(self.student.id),
            'session_id': str(self.session.id),
            'assignment_id': str(self.assignment.id),
        }), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['valid'])

    def test_invalid_registration_blocked(self):
        """Wrong student number returns valid=False."""
        self._login()
        r = self.client.post(self.url, json.dumps({
            'student_number': '99999999',
            'student_id': str(self.student.id),
            'session_id': str(self.session.id),
            'assignment_id': str(self.assignment.id),
        }), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data['valid'])
        self.assertEqual(data['error'], 'registration_not_found')

    def test_missing_fields_returns_400(self):
        """Missing required fields returns 400."""
        self._login()
        r = self.client.post(self.url, json.dumps({
            'student_number': '11844785',
        }), content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_student_not_in_session_returns_404(self):
        """Student not found in session returns 404."""
        self._login()
        other_session = ExamSession.objects.create(
            exam=self.exam, name='Other Session', status='in_progress',
            session_date=date(2025, 6, 2), start_time=time(9, 0),
            number_of_stations=2, number_of_paths=1,
        )
        r = self.client.post(self.url, json.dumps({
            'student_number': '11844785',
            'student_id': str(self.student.id),
            'session_id': str(other_session.id),
            'assignment_id': str(self.assignment.id),
        }), content_type='application/json')
        self.assertEqual(r.status_code, 404)


class VerifyMasterKeyTest(DryVerifyTestBase):
    """Test POST /api/dry/verify-master-key/."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('examiner_api:verify_master_key')

    def _login(self):
        self.client.force_login(self.examiner)

    def test_unauthenticated_returns_302(self):
        """Unauthenticated request redirects to login."""
        r = self.client.post(self.url, json.dumps({
            'password': 'ExamPass123!',
            'student_id': str(self.student.id),
            'session_id': str(self.session.id),
            'assignment_id': str(self.assignment.id),
        }), content_type='application/json')
        self.assertEqual(r.status_code, 302)

    def test_valid_password_passes(self):
        """Correct password returns valid=True with redirect_url."""
        self._login()
        r = self.client.post(self.url, json.dumps({
            'password': 'ExamPass123!',
            'student_id': str(self.student.id),
            'session_id': str(self.session.id),
            'assignment_id': str(self.assignment.id),
        }), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['valid'])
        self.assertIn('redirect_url', data)
        # redirect_url is now a plain path (session-based auth, no token in URL)
        self.assertTrue(data['redirect_url'].startswith('/'))

    def test_invalid_password_blocked(self):
        """Wrong password returns valid=False."""
        self._login()
        r = self.client.post(self.url, json.dumps({
            'password': 'WrongPassword!',
            'student_id': str(self.student.id),
            'session_id': str(self.session.id),
            'assignment_id': str(self.assignment.id),
        }), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data['valid'])
        self.assertEqual(data['error'], 'invalid_password')

    def test_missing_fields_returns_400(self):
        """Missing required fields returns 400."""
        self._login()
        r = self.client.post(self.url, json.dumps({
            'password': 'ExamPass123!',
        }), content_type='application/json')
        self.assertEqual(r.status_code, 400)


class DryMarkingTokenTest(DryVerifyTestBase):
    """Test dry_marking page token validation."""

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.examiner)

    def _set_session_auth(self, assignment_id=None, student_id=None):
        """Set up session-based dry exam authorization."""
        from datetime import datetime, timedelta, timezone as tz
        a_id = str(assignment_id or self.assignment.id)
        s_id = str(student_id or self.student.id)
        session_key = f'dry_auth_{a_id}_{s_id}'
        session = self.client.session
        session[session_key] = {
            'user_id': self.examiner.id,
            'student_id': s_id,
            'assignment_id': a_id,
            'expires_at': (datetime.now(tz=tz.utc) + timedelta(hours=4)).isoformat(),
        }
        session.save()

    def test_valid_session_auth_renders_page(self):
        """Valid session authorization allows access to dry_marking page."""
        self._set_session_auth()
        r = self.client.get(
            reverse('examiner:dry_marking',
                    kwargs={'assignment_id': self.assignment.id,
                            'student_id': self.student.id})
        )
        self.assertEqual(r.status_code, 200)

    def test_missing_session_auth_redirects(self):
        """No session authorization redirects to station dashboard."""
        r = self.client.get(
            reverse('examiner:dry_marking',
                    kwargs={'assignment_id': self.assignment.id,
                            'student_id': self.student.id})
        )
        self.assertEqual(r.status_code, 302)

    def test_no_session_auth_with_garbage_param_redirects(self):
        """No session auth with garbage query params still redirects."""
        r = self.client.get(
            reverse('examiner:dry_marking',
                    kwargs={'assignment_id': self.assignment.id,
                            'student_id': self.student.id})
            + '?token=invalid-garbage-token'
        )
        self.assertEqual(r.status_code, 302)

    def test_wrong_user_session_redirects(self):
        """Session auth for different user redirects."""
        from datetime import datetime, timedelta, timezone as tz
        a_id = str(self.assignment.id)
        s_id = str(self.student.id)
        session_key = f'dry_auth_{a_id}_{s_id}'
        session = self.client.session
        session[session_key] = {
            'user_id': 99999,
            'student_id': s_id,
            'assignment_id': a_id,
            'expires_at': (datetime.now(tz=tz.utc) + timedelta(hours=4)).isoformat(),
        }
        session.save()
        r = self.client.get(
            reverse('examiner:dry_marking',
                    kwargs={'assignment_id': self.assignment.id,
                            'student_id': self.student.id})
        )
        self.assertEqual(r.status_code, 302)

    def test_wrong_student_session_redirects(self):
        """Session auth for different student redirects."""
        from datetime import datetime, timedelta, timezone as tz
        other_student = SessionStudent.objects.create(
            session=self.session, student_number='99999',
            full_name='Other Student', path=self.path,
        )
        a_id = str(self.assignment.id)
        s_id = str(self.student.id)
        session_key = f'dry_auth_{a_id}_{s_id}'
        session = self.client.session
        session[session_key] = {
            'user_id': self.examiner.id,
            'student_id': str(other_student.id),
            'assignment_id': a_id,
            'expires_at': (datetime.now(tz=tz.utc) + timedelta(hours=4)).isoformat(),
        }
        session.save()
        r = self.client.get(
            reverse('examiner:dry_marking',
                    kwargs={'assignment_id': self.assignment.id,
                            'student_id': self.student.id})
        )
        self.assertEqual(r.status_code, 302)

    def test_marking_interface_redirect_for_dry_station(self):
        """marking_interface redirects dry stations to dry_marking."""
        self._set_session_auth()
        r = self.client.get(
            reverse('examiner:marking_interface',
                    kwargs={'assignment_id': self.assignment.id,
                            'student_id': self.student.id}),
            follow=False,
        )
        self.assertEqual(r.status_code, 302)
