"""
Core models package – all OSCE domain models.
"""
from .mixins import TimestampMixin
from .theme import Theme, DEFAULT_THEMES
from .course import Course, ILO
from .exam import Exam, Station, ChecklistItem
from .session import ExamSession, SessionStudent
from .scoring import StationScore, ItemScore
from .department import Department
from .examiner import Examiner, ExaminerAssignment
from .path import Path, StudentPath, PathStation
from .library import ChecklistLibrary
from .osce_paths import OSCEExamPath, OSCERoomAssignment, OSCEPathStudent
from .station_variant import StationVariant
from .template_library import TemplateLibrary
from .station_template import StationTemplate
from .audit import AuditLog, AuditLogArchive
from .login_audit import LoginAuditLog
from .user_session import UserSession
from .user_profile import UserProfile

__all__ = [
    # Base
    'TimestampMixin',
    # Themes
    'Theme', 'DEFAULT_THEMES',
    # Course & ILO
    'Course', 'ILO',
    # Exam structure
    'Exam', 'Station', 'ChecklistItem',
    'ChecklistLibrary', 'TemplateLibrary', 'StationTemplate',
    # Sessions & Variants
    'ExamSession', 'SessionStudent', 'StationVariant',
    # Paths
    'Path', 'StudentPath', 'PathStation',
    # Scoring
    'StationScore', 'ItemScore',
    # Examiners
    'Examiner', 'ExaminerAssignment',
    # Departments
    'Department',
    # OSCE rotation
    'OSCEExamPath', 'OSCERoomAssignment', 'OSCEPathStudent',
    # Audit
    'AuditLog',
    'AuditLogArchive',
    'LoginAuditLog',
    # Session tracking
    'UserSession',
    # User profile
    'UserProfile',
]
