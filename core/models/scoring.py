"""
StationScore and ItemScore models.
"""
import uuid
from django.db import models
from .mixins import TimestampMixin


class StationScore(models.Model):
    """Score record for a student at a specific station."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session_student = models.ForeignKey(
        'core.SessionStudent', on_delete=models.CASCADE,
        related_name='station_scores', db_index=True
    )
    station = models.ForeignKey(
        'core.Station', on_delete=models.CASCADE,
        related_name='scores', db_index=True
    )
    examiner = models.ForeignKey(
        'core.Examiner', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='station_scores', db_index=True
    )

    # Timing
    started_at = models.IntegerField(null=True, blank=True)
    completed_at = models.IntegerField(null=True, blank=True)

    # Scores
    total_score = models.FloatField(default=0)
    max_score = models.FloatField(null=True, blank=True)
    percentage = models.FloatField(null=True, blank=True)

    # Critical items
    passed_critical = models.BooleanField(default=True)
    critical_items_failed = models.TextField(blank=True, default='')

    global_rating = models.IntegerField(null=True, blank=True)
    comments = models.TextField(blank=True, default='')

    # Status: in_progress, submitted, reviewed, flagged
    status = models.CharField(max_length=20, default='in_progress')

    # Offline sync fields
    local_uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    client_id = models.CharField(max_length=50, blank=True, default='')
    local_timestamp = models.IntegerField(null=True, blank=True)
    synced_at = models.IntegerField(null=True, blank=True)
    sync_status = models.CharField(max_length=20, default='local')

    created_at = models.IntegerField(null=True, blank=True)
    updated_at = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'station_scores'
        indexes = [
            models.Index(fields=['station', 'status'], name='idx_station_score_status'),
            models.Index(fields=['sync_status'], name='idx_sync_status'),
        ]

    def __str__(self):
        return f'Score: Student {self.session_student_id} @ Station {self.station_id}'

    def save(self, *args, **kwargs):
        now = TimestampMixin.utc_timestamp()
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now
        super().save(*args, **kwargs)

    @staticmethod
    def get_final_score(session_student_id, station_id):
        scores = StationScore.objects.filter(
            session_student_id=session_student_id,
            station_id=station_id,
            status='submitted'
        )
        if not scores.exists():
            return None

        scores_list = list(scores)
        result = {
            'examiner_scores': [],
            'final_score': 0,
            'max_score': scores_list[0].max_score if scores_list else 0,
            'percentage': 0,
            'both_submitted': len(scores_list) >= 2,
        }

        total = 0
        for score in scores_list:
            result['examiner_scores'].append({
                'examiner_id': score.examiner_id,
                'examiner_name': score.examiner.display_name if score.examiner else 'Deleted Examiner',
                'score': score.total_score,
                'submitted_at': score.completed_at,
            })
            total += score.total_score or 0

        if scores_list:
            result['final_score'] = round(total / len(scores_list), 2)
            if result['max_score']:
                result['percentage'] = round(
                    (result['final_score'] / result['max_score']) * 100, 1
                )
        return result

    def calculate_total(self):
        self.total_score = sum(item.score or 0 for item in self.item_scores.all())
        if self.max_score and self.max_score > 0:
            self.percentage = (self.total_score / self.max_score) * 100
        return self.total_score

    def check_critical_items(self, critical_item_ids):
        failed = []
        for item_score in self.item_scores.all():
            if item_score.checklist_item_id in critical_item_ids:
                if item_score.score < item_score.max_points:
                    failed.append(item_score.checklist_item_id)
        self.passed_critical = len(failed) == 0
        self.critical_items_failed = str(failed) if failed else ''
        return self.passed_critical


class ItemScore(models.Model):
    """Individual checklist item score within a station score."""

    id = models.AutoField(primary_key=True)
    station_score = models.ForeignKey(
        StationScore, on_delete=models.CASCADE,
        related_name='item_scores', db_index=True
    )
    checklist_item = models.ForeignKey(
        'core.ChecklistItem', on_delete=models.CASCADE,
        related_name='item_scores', db_index=True
    )

    score = models.FloatField(default=0)
    max_points = models.FloatField(default=1)
    marked_at = models.IntegerField(null=True, blank=True)
    notes = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'item_scores'
        constraints = [
            models.UniqueConstraint(
                fields=['station_score', 'checklist_item'],
                name='unique_score_item'
            ),
        ]

    def __str__(self):
        return f'ItemScore {self.checklist_item_id} = {self.score}'
