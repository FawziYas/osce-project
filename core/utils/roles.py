"""
Role-based access control utilities for Django views.

Provides decorators and helpers to enforce:
  1. Role gating (admin-only, coordinator-only, etc.)
  2. Department scoping (coordinators see only their own department's data)
  3. Position restrictions (e.g. only head coordinator can delete exams)

Usage:
    from core.utils.roles import role_required, get_user_department, scope_queryset

    @login_required
    @role_required('admin', 'coordinator')
    def my_view(request):
        courses = scope_queryset(request.user, Course.objects.all())
        ...
"""
from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect


# ── Role constants ───────────────────────────────────────────────────

ROLE_EXAMINER = 'examiner'
ROLE_COORDINATOR = 'coordinator'
ROLE_ADMIN = 'admin'

POSITION_HEAD = 'head'
POSITION_RTA = 'rta'
POSITION_ORGANIZER = 'organizer'


# ── Quick role checks ────────────────────────────────────────────────

def is_superuser(user):
    return user.is_authenticated and user.is_superuser


def is_admin(user):
    return user.is_authenticated and getattr(user, 'role', None) == ROLE_ADMIN


def is_coordinator(user):
    return user.is_authenticated and getattr(user, 'role', None) == ROLE_COORDINATOR


def is_examiner_role(user):
    return user.is_authenticated and getattr(user, 'role', None) == ROLE_EXAMINER


def is_global(user):
    """Superuser or Admin — cross-department access."""
    return is_superuser(user) or is_admin(user)


def is_global_or_coordinator(user):
    return is_global(user) or is_coordinator(user)


def is_head_coordinator(user):
    return (is_coordinator(user) and
            getattr(user, 'coordinator_position', '') == POSITION_HEAD)


# ── Department helpers ───────────────────────────────────────────────

def get_user_department(user):
    """
    Return the Department instance the user is scoped to, or None.
    - Superuser / Admin → None (global access)
    - Coordinator → their department
    """
    if is_global(user):
        return None  # sentinel for "show all"
    if is_coordinator(user):
        return getattr(user, 'department', None)
    return None


def get_user_department_id(user):
    """Return the department PK or None."""
    dept = get_user_department(user)
    return dept.pk if dept else None


def user_can_access_department(user, dept_id):
    """
    Check if the user may access resources belonging to dept_id.
    Globals always pass.  Coordinators pass only for their own department.
    """
    if is_global(user):
        return True
    if is_coordinator(user):
        user_dept = getattr(user, 'department', None)
        if user_dept and str(user_dept.pk) == str(dept_id):
            return True
    return False


# ── Queryset scoping ────────────────────────────────────────────────

def scope_queryset(user, qs, dept_field='department'):
    """
    Filter a queryset by the user's department scope.

    For global users (superuser/admin): returns qs unfiltered.
    For coordinators: filters to their own department.

    `dept_field` is the field name on the model that references the
    Department FK.  Examples:
        - Course: dept_field='department'
        - Exam:   dept_field='course__department'
        - Session: dept_field='exam__course__department'
    """
    if is_global(user):
        return qs
    if is_coordinator(user):
        dept = getattr(user, 'department', None)
        if dept:
            return qs.filter(**{dept_field: dept})
        # Coordinator without department — should not happen (DB constraint)
        # but fallback to empty
        return qs.none()
    # Examiner or unknown — no creator access at all
    return qs.none()


def scope_queryset_by_dept_id(user, qs, dept_id_field='department_id'):
    """
    Same as scope_queryset but uses the ID field directly.
    Useful for CharField department fields like Exam.department.
    """
    if is_global(user):
        return qs
    if is_coordinator(user):
        dept = getattr(user, 'department', None)
        if dept:
            return qs.filter(**{dept_id_field: dept.pk})
        return qs.none()
    return qs.none()


# ── Object-level department check ────────────────────────────────────

def check_object_department(user, obj, dept_attr='department'):
    """
    Verify the user can access a specific object based on its department.
    Returns True if allowed, False if not.

    For Exam objects where department is a CharField:
      check_exam_department(user, exam) should be used instead.
    """
    if is_global(user):
        return True
    if is_coordinator(user):
        obj_dept = getattr(obj, dept_attr, None)
        user_dept = getattr(user, 'department', None)
        if obj_dept and user_dept:
            obj_dept_id = obj_dept.pk if hasattr(obj_dept, 'pk') else obj_dept
            return str(obj_dept_id) == str(user_dept.pk)
    return False


def check_course_department(user, course):
    """Check if user can access a Course (FK to Department)."""
    return check_object_department(user, course, 'department')


def check_exam_department(user, exam):
    """Check if user can access an Exam (via course.department FK)."""
    if is_global(user):
        return True
    if is_coordinator(user):
        course_dept = getattr(exam.course, 'department', None) if exam.course else None
        user_dept = getattr(user, 'department', None)
        if course_dept and user_dept:
            return str(course_dept.pk) == str(user_dept.pk)
    return False


def check_session_department(user, session):
    """Check if user can access an ExamSession (via exam.course.department)."""
    return check_exam_department(user, session.exam)


def check_path_department(user, path):
    """Check if user can access a Path (via path.session.exam.course.department or path.exam.course.department)."""
    if is_global(user):
        return True
    exam = getattr(path, 'exam', None) or (path.session.exam if hasattr(path, 'session') and path.session else None)
    if exam:
        return check_exam_department(user, exam)
    return False


def check_station_department(user, station):
    """Check if user can access a Station (via station.path.exam.course.department)."""
    if is_global(user):
        return True
    path = getattr(station, 'path', None)
    if path:
        return check_path_department(user, path)
    return False


# ── Decorators ───────────────────────────────────────────────────────

def role_required(*allowed_roles, position=None):
    """
    Decorator: restrict view to specific roles.
    Superuser always passes.

    Usage:
        @login_required
        @role_required('admin', 'coordinator')
        def some_view(request): ...

        @login_required
        @role_required('coordinator', position='head')
        def head_only_view(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect('login')

            # Superuser bypass
            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_role = getattr(user, 'role', None)
            if user_role not in allowed_roles:
                return HttpResponseForbidden(
                    '<h1>403 Forbidden</h1>'
                    '<p>You do not have permission to access this page.</p>'
                )

            # Optional position check (for coordinator sub-roles)
            if position:
                user_position = getattr(user, 'coordinator_position', '')
                if user_position != position:
                    return HttpResponseForbidden(
                        '<h1>403 Forbidden</h1>'
                        '<p>This action requires a higher permission level.</p>'
                    )

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def admin_or_superuser_required(view_func):
    """Shorthand: only superuser or admin role."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser or getattr(request.user, 'role', None) == ROLE_ADMIN:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden(
            '<h1>403 Forbidden</h1><p>Admin access required.</p>'
        )
    return _wrapped


def head_or_admin_required(view_func):
    """Shorthand: superuser, admin, or head coordinator only."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        user = request.user
        if user.is_superuser:
            return view_func(request, *args, **kwargs)
        role = getattr(user, 'role', None)
        if role == ROLE_ADMIN:
            return view_func(request, *args, **kwargs)
        if role == ROLE_COORDINATOR and getattr(user, 'coordinator_position', '') == POSITION_HEAD:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden(
            '<h1>403 Forbidden</h1><p>Head coordinator or admin access required.</p>'
        )
    return _wrapped
