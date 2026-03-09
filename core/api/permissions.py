"""
Layer 2 — DRF Permission Classes.

Role-based gates that run BEFORE any queryset filtering.
These check the user's role stored on the Examiner model.

Usage in ViewSets:
    permission_classes = [IsAuthenticated, IsSuperuserOrAdmin]
    # or per-action via get_permissions()
"""
from rest_framework.permissions import BasePermission


# ── Single-role permissions ──────────────────────────────────────────

class IsSuperuser(BasePermission):
    """Allow only Django superusers."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


class IsAdmin(BasePermission):
    """Allow only role='admin' (NOT superuser — use IsSuperuserOrAdmin for both)."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and not request.user.is_superuser
            and getattr(request.user, 'role', '') == 'admin'
        )


class IsCoordinator(BasePermission):
    """Allow any coordinator role (head, rta, organizer)."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', '') == 'coordinator'
        )


class IsCoordinatorHead(BasePermission):
    """Allow only coordinator with position='head'."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', '') == 'coordinator'
            and getattr(request.user, 'coordinator_position', '') == 'head'
        )


class IsExaminer(BasePermission):
    """Allow only role='examiner'."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and not request.user.is_superuser
            and getattr(request.user, 'role', '') == 'examiner'
        )


# ── Composite permissions (OR combinations) ─────────────────────────

class IsSuperuserOrAdmin(BasePermission):
    """Superuser OR Admin — global access roles."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return getattr(request.user, 'role', '') == 'admin'


class IsGlobalOrCoordinator(BasePermission):
    """Superuser OR Admin OR any Coordinator."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        role = getattr(request.user, 'role', '')
        return role in ('admin', 'coordinator')


class IsGlobalOrCoordinatorHead(BasePermission):
    """Superuser OR Admin OR Coordinator-Head only."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        role = getattr(request.user, 'role', '')
        if role == 'admin':
            return True
        if role == 'coordinator':
            return getattr(request.user, 'coordinator_position', '') == 'head'
        return False


class IsGlobalOrCoordinatorOrAssignedExaminer(BasePermission):
    """
    Superuser / Admin / Coordinator (any) → always pass here;
    Examiner → pass here, but object-level check deferred to
    ExaminerAssignmentMixin.

    This is a *gate* permission — the actual assignment verification
    happens in the mixin's get_object().
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        role = getattr(request.user, 'role', '')
        return role in ('admin', 'coordinator', 'examiner')


class IsAssignedExaminer(BasePermission):
    """
    Gate for examiner-only endpoints (e.g. score write).
    Actual station assignment verified in ExaminerAssignmentMixin.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        role = getattr(request.user, 'role', '')
        return role == 'examiner'
