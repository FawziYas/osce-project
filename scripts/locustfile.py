"""
Locust load test script — simulates 50-100 concurrent OSCE examiners.

Usage:
    pip install locust
    locust -f scripts/locustfile.py --host=https://osce-app.azurewebsites.net

    Then open http://localhost:8089 and start the test.

    ⚠️  Run against STAGING only — never against production during exams.
"""
import json
import random

from locust import HttpUser, between, task, SequentialTaskSet


class ExaminerWorkflow(SequentialTaskSet):
    """Simulates a single examiner's workflow during an exam session."""

    station_score_id = None
    station_id = None
    session_id = None
    checklist_items = []

    def on_start(self):
        """Login as examiner."""
        # Get CSRF token
        resp = self.client.get('/login/', name='/login/ [GET]')
        csrf = resp.cookies.get('csrftoken', '')

        self.client.post('/login/', data={
            'username': self.user.username,
            'password': self.user.password,
            'csrfmiddlewaretoken': csrf,
        }, name='/login/ [POST]', headers={
            'Referer': f'{self.client.base_url}/login/',
        })

    @task
    def fetch_session_students(self):
        """Fetch student list for the assigned session."""
        if not self.session_id:
            # In a real test, set this from known test data
            return
        self.client.get(
            f'/examiner/api/session/{self.session_id}/students/',
            name='/api/session/:id/students/',
        )

    @task
    def fetch_station_checklist(self):
        """Fetch checklist items for the current station."""
        if not self.station_id:
            return
        resp = self.client.get(
            f'/examiner/api/station/{self.station_id}/checklist/',
            name='/api/station/:id/checklist/',
        )
        if resp.status_code == 200:
            data = resp.json()
            self.checklist_items = data.get('items', [])

    @task
    def start_marking(self):
        """Start a marking session for a random student."""
        if not self.session_id or not self.station_id:
            return

        resp = self.client.post(
            '/examiner/api/score/start/',
            json={
                'session_student_id': self.user.session_student_id,
                'station_id': self.station_id,
            },
            name='/api/score/start/',
        )
        if resp.status_code == 200:
            data = resp.json()
            self.station_score_id = data.get('id')

    @task
    def mark_all_items_batch(self):
        """Submit all checklist items in a single batch request."""
        if not self.station_score_id or not self.checklist_items:
            return

        items = []
        for ci in self.checklist_items:
            max_pts = ci.get('points', 1)
            rubric = ci.get('rubric_type', 'binary')
            if rubric == 'binary':
                score = random.choice([0, max_pts])
            elif rubric == 'partial':
                score = random.choice([0, max_pts * 0.5, max_pts])
            else:
                score = random.randint(0, int(max_pts))

            items.append({
                'checklist_item_id': ci['id'],
                'score': score,
                'max_points': max_pts,
                'notes': '',
            })

        self.client.post(
            f'/examiner/api/score/{self.station_score_id}/items/',
            json={'items': items},
            name='/api/score/:id/items/ [batch]',
        )

    @task
    def submit_score(self):
        """Submit the final score for this station."""
        if not self.station_score_id:
            return

        self.client.post(
            f'/examiner/api/score/{self.station_score_id}/submit/',
            json={
                'global_rating': random.choice([None, 'borderline', 'pass', 'fail']),
                'comments': 'Load test submission',
            },
            name='/api/score/:id/submit/',
        )
        # Reset for next cycle
        self.station_score_id = None


class OSCEExaminer(HttpUser):
    """
    Simulates 50-100 concurrent examiners marking students.

    Configure test users via environment or modify the defaults below.
    Each user logs in, fetches their station checklist, marks all items
    in batch, and submits — then repeats for the next student.
    """
    tasks = [ExaminerWorkflow]

    # Wait 2-5 seconds between each task (simulates examiner reading/tapping)
    wait_time = between(2, 5)

    # ── Test Configuration ────────────────────────────────────────
    # Override these with values from your staging environment
    username = 'test_examiner'
    password = 'test_password'
    session_student_id = None  # UUID of a test SessionStudent

    def on_start(self):
        """Assign unique test credentials per user instance.

        For proper load testing, create N test examiner accounts in staging
        and assign them here. Example:
            self.username = f'examiner_{self.environment.runner.user_count}'
        """
        pass
