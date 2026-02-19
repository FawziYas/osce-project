"""
Examiner (Custom User) and ExaminerAssignment models.
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from .mixins import TimestampMixin


class ExaminerManager(BaseUserManager):
    """Custom manager for Examiner user model."""

    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("Username is required")
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('full_name', username)
        return self.create_user(username, email, password, **extra_fields)


class Examiner(AbstractBaseUser, PermissionsMixin, TimestampMixin):
    """
    Custom user model for examiners.

    Replaces Flask-Login's UserMixin + Examiner model.
    AUTH_USER_MODEL = 'core.Examiner'
    """

    ROLE_EXAMINER    = 'examiner'
    ROLE_COORDINATOR = 'coordinator'
    ROLE_ADMIN       = 'admin'
    ROLE_CHOICES = [
        (ROLE_EXAMINER,    'Examiner'),
        (ROLE_COORDINATOR, 'Coordinator'),
        (ROLE_ADMIN,       'Admin'),
    ]

    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=80, unique=True)
    email = models.EmailField(max_length=120, unique=True)
    full_name = models.CharField(max_length=150)

    # Display on marking screen
    title = models.CharField(max_length=20, blank=True, default='')  # Dr., Prof.
    department = models.CharField(max_length=100, blank=True, default='')

    # Role-based access control
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_EXAMINER)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ExaminerManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'full_name']

    class Meta:
        db_table = 'examiners'
        verbose_name = 'Examiner'
        verbose_name_plural = 'Examiners'

    def __str__(self):
        return f'{self.username}'

    @property
    def display_name(self):
        if self.title:
            return f"{self.title} {self.full_name}"
        return self.full_name

    @property
    def is_admin(self):
        """True for role=admin only. Superusers are a higher tier."""
        return not self.is_superuser and self.role == self.ROLE_ADMIN

    @property
    def is_coordinator(self):
        """True only for coordinator role."""
        return not self.is_superuser and self.role == self.ROLE_COORDINATOR

    @property
    def is_examiner_only(self):
        return not self.is_superuser and self.role == self.ROLE_EXAMINER

    @property
    def has_creator_access(self):
        """True for superuser, admin and coordinator."""
        return self.is_superuser or self.role in (self.ROLE_ADMIN, self.ROLE_COORDINATOR)

    @property
    def role_display(self):
        """Human-readable role label for the UI."""
        if self.is_superuser:
            return 'Superuser'
        mapping = {
            self.ROLE_ADMIN:       'Admin',
            self.ROLE_COORDINATOR: 'Coordinator',
            self.ROLE_EXAMINER:    'Examiner',
        }
        return mapping.get(self.role, self.role.capitalize())


class ExaminerAssignment(TimestampMixin):
    """
    Assigns an examiner to a station for a specific exam session.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        'core.ExamSession', on_delete=models.CASCADE,
        related_name='examiner_assignments', db_index=True
    )
    station = models.ForeignKey(
        'core.Station', on_delete=models.CASCADE,
        related_name='examiner_assignments', db_index=True
    )
    examiner = models.ForeignKey(
        'core.Examiner', on_delete=models.CASCADE,
        related_name='assignments', db_index=True
    )

    is_primary = models.BooleanField(default=True)

    class Meta:
        db_table = 'examiner_assignments'
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'station', 'examiner'],
                name='unique_session_station_examiner'
            ),
        ]

    def __str__(self):
        return f'Assignment: {self.examiner_id} @ Station {self.station_id}'

    # Convenience properties for templates
    @property
    def station_name(self):
        return self.station.name if self.station else 'Unknown Station'

    @property
    def station_duration(self):
        return self.station.duration_minutes if self.station else 8

    @property
    def station_max_score(self):
        return self.station.get_max_score() if self.station else 0

    @property
    def station_scenario(self):
        return self.station.scenario if self.station else ''

    @property
    def station_instructions(self):
        return self.station.instructions if self.station else ''

    @property
    def exam_name(self):
        return self.station.exam.name if self.station and self.station.exam else 'Unknown Exam'

    @property
    def session_date(self):
        return self.session.session_date if self.session else None
