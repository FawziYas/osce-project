"""
Department-based access control helpers.

Usage:
    from creator.dept_access import has_full_access, get_coordinator_dept, filter_exams_by_dept

Rules:
    - Superuser / Admin   → full access to everything
    - Coordinator          → scoped to their department only
"""


def has_full_access(user):
    """Return True if the user has unrestricted access (superuser or admin)."""
    return user.is_superuser or getattr(user, 'role', None) == 'admin'


def get_coordinator_dept(user):
    """Return the Department instance for a coordinator, or None."""
    if has_full_access(user):
        return None
    return getattr(user, 'coordinator_department', None)


def filter_exams_by_dept(qs, user):
    """Filter an Exam queryset to the user's department if the user is a coordinator."""
    dept = get_coordinator_dept(user)
    if dept is None:
        return qs  # admin/superuser sees all
    return qs.filter(department=dept.name)


def filter_sessions_by_dept(qs, user):
    """Filter an ExamSession queryset to the user's department."""
    dept = get_coordinator_dept(user)
    if dept is None:
        return qs
    return qs.filter(exam__department=dept.name)


def filter_courses_by_dept(qs, user):
    """Filter a Course queryset to the user's department."""
    dept = get_coordinator_dept(user)
    if dept is None:
        return qs
    return qs.filter(department=dept)


def can_access_exam(user, exam):
    """Return True if the user may access this exam."""
    if has_full_access(user):
        return True
    dept = get_coordinator_dept(user)
    if dept is None:
        return False
    return exam.department == dept.name


def can_access_session(user, session):
    """Return True if the user may access this session (via exam department)."""
    return can_access_exam(user, session.exam)
