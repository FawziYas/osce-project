"""
Dry Station models – MCQ and Essay questions.
"""
from django.db import models
from .mixins import TimestampMixin


class DryQuestion(TimestampMixin):
    """Individual question within a dry station (MCQ or Essay)."""

    id = models.AutoField(primary_key=True)
    station = models.ForeignKey(
        'core.Station', on_delete=models.CASCADE,
        related_name='dry_questions', db_index=True
    )

    question_number = models.IntegerField()
    question_type = models.CharField(max_length=20)  # 'mcq' or 'essay'

    question_text = models.TextField()
    stem_image = models.CharField(max_length=255, blank=True, default='')

    points = models.FloatField(default=1)

    # Essay specific
    instructions = models.TextField(blank=True, default='')
    rubric = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'dry_questions'
        ordering = ['question_number']
        constraints = [
            models.UniqueConstraint(
                fields=['station', 'question_number'],
                name='unique_station_question_number'
            ),
        ]
        indexes = [
            models.Index(fields=['question_type'], name='idx_question_type'),
        ]

    def __str__(self):
        return f'DryQuestion #{self.question_number}: {self.question_type}'

    def to_dict(self, include_options=False):
        data = {
            'id': self.id,
            'station_id': str(self.station_id),
            'question_number': self.question_number,
            'question_type': self.question_type,
            'question_text': self.question_text,
            'stem_image': self.stem_image,
            'points': self.points,
        }
        if include_options and self.question_type == 'mcq':
            data['options'] = [
                o.to_dict() for o in self.mcq_options.order_by('option_number')
            ]
        return data


class MCQOption(TimestampMixin):
    """Answer option for a multiple-choice question."""

    id = models.AutoField(primary_key=True)
    question = models.ForeignKey(
        DryQuestion, on_delete=models.CASCADE,
        related_name='mcq_options', db_index=True
    )

    option_number = models.IntegerField()
    option_text = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        db_table = 'mcq_options'
        ordering = ['option_number']
        constraints = [
            models.UniqueConstraint(
                fields=['question', 'option_number'],
                name='unique_question_option_number'
            ),
        ]

    def __str__(self):
        letter = chr(64 + self.option_number)
        return f'Option {letter}: {self.option_text[:30]}'

    def to_dict(self):
        return {
            'id': self.id,
            'option_number': self.option_number,
            'option_text': self.option_text,
            'is_correct': self.is_correct,
        }


class DryStationResponse(TimestampMixin):
    """Student's answer to a dry station question."""

    id = models.AutoField(primary_key=True)
    question = models.ForeignKey(
        DryQuestion, on_delete=models.CASCADE,
        related_name='responses', db_index=True
    )
    student = models.ForeignKey(
        'core.Examiner', on_delete=models.CASCADE,
        related_name='dry_responses_as_student', db_index=True
    )
    exam = models.ForeignKey(
        'core.Exam', on_delete=models.CASCADE,
        related_name='dry_responses', db_index=True
    )
    osce_path_student = models.ForeignKey(
        'core.OSCEPathStudent', on_delete=models.SET_NULL,
        null=True, blank=True, db_index=True
    )

    answer_text = models.TextField(blank=True, default='')
    selected_option = models.ForeignKey(
        MCQOption, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Scoring
    auto_score = models.FloatField(null=True, blank=True)
    manual_score = models.FloatField(null=True, blank=True)
    final_score = models.FloatField(null=True, blank=True)

    graded_by = models.ForeignKey(
        'core.Examiner', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='graded_responses'
    )
    grading_feedback = models.TextField(blank=True, default='')
    graded_at = models.IntegerField(null=True, blank=True)

    submitted_at = models.IntegerField()

    class Meta:
        db_table = 'dry_station_responses'
        constraints = [
            models.UniqueConstraint(
                fields=['question', 'student', 'exam'],
                name='unique_student_question_exam'
            ),
        ]
        indexes = [
            models.Index(fields=['exam', 'student'], name='idx_response_exam_student'),
            models.Index(fields=['graded_at', 'graded_by'], name='idx_response_graded'),
        ]

    def __str__(self):
        return f'Response Q{self.question_id} Student{self.student_id}'

    @property
    def is_mcq(self):
        return self.question.question_type == 'mcq'

    @property
    def is_essay(self):
        return self.question.question_type == 'essay'

    def auto_grade_mcq(self):
        if not self.is_mcq or not self.selected_option:
            return None
        self.auto_score = float(self.question.points) if self.selected_option.is_correct else 0.0
        return self.auto_score

    def set_essay_grade(self, score, feedback='', graded_by_user=None):
        import time
        self.manual_score = float(score)
        self.grading_feedback = feedback
        self.graded_at = int(time.time())
        if graded_by_user:
            self.graded_by = graded_by_user
        self.final_score = self.manual_score

    def to_dict(self, include_feedback=False):
        data = {
            'id': self.id,
            'question_id': self.question_id,
            'student_id': self.student_id,
            'exam_id': str(self.exam_id),
            'answer_text': self.answer_text if self.is_essay else None,
            'selected_option_id': self.selected_option_id if self.is_mcq else None,
            'auto_score': self.auto_score,
            'final_score': self.final_score,
            'submitted_at': self.submitted_at,
        }
        if include_feedback and self.is_essay:
            data['grading_feedback'] = self.grading_feedback
            data['graded_by_id'] = self.graded_by_id
            data['graded_at'] = self.graded_at
        return data
