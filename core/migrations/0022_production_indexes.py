"""
Add production performance indexes for high-concurrency scoring.

These indexes target the hottest queries during exam day:
- Examiner looking up their scores by session
- Student scores by session and station
- Session student lookup by path
- Item scores by station_score + checklist_item (already has UniqueConstraint)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_add_status_indexes'),
    ]

    operations = [
        # StationScore: examiner scoring views — lookup by examiner + session_student
        migrations.AddIndex(
            model_name='stationscore',
            index=models.Index(
                fields=['examiner', 'status'],
                name='idx_score_examiner_status',
            ),
        ),
        migrations.AddIndex(
            model_name='stationscore',
            index=models.Index(
                fields=['session_student', 'station'],
                name='idx_score_student_station',
            ),
        ),
        # SessionStudent: student lookup per session + path
        migrations.AddIndex(
            model_name='sessionstudent',
            index=models.Index(
                fields=['session', 'path'],
                name='idx_student_session_path',
            ),
        ),
        migrations.AddIndex(
            model_name='sessionstudent',
            index=models.Index(
                fields=['session', 'status'],
                name='idx_student_session_status',
            ),
        ),
    ]
