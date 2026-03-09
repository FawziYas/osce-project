"""
Layers 3 & 4 — Department Scope and Examiner Assignment Scope Mixins.

These are ViewSet mixins that filter querysets and objects so that:
  - Coordinators see only their own department's data (Layer 3)
  - Examiners see only their assigned stations (Layer 4)
  - Non-existent *and* unauthorized objects both return 404 (no existence leak)
"""
from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from core.models import ExaminerAssignment


# ── Layer 3: Department Scope ────────────────────────────────────────

class DepartmentScopedMixin:
    """
    Mixin for any ViewSet whose model can be traced to a Department.

    Subclasses MUST define:
        department_field: str
            The ORM lookup path from the model to department_id.
            Examples:
                'department'               (Course)
                'course__department'        (Exam → Course → Department)
                'exam__course__department'  (ExamSession → Exam → Course)
                'session__exam__course__department'  (Path)
                'path__session__exam__course__department'  (Station)

    Behaviour:
        - Superuser / Admin: no filtering (see all)
        - Coordinator: filter to own department only
        - Examiner: this mixin does NOT filter for examiners;
                    use ExaminerAssignmentMixin instead
        - Any other role / anonymous: empty queryset
    """

    department_field: str = None  # Must be set by subclass

    def get_queryset(self):
        """Filter the queryset to the user's department scope."""
        qs = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return qs.none()

        # Global roles see everything
        if user.is_superuser or getattr(user, 'role', '') == 'admin':
            return qs

        # Coordinators see only their department
        if getattr(user, 'role', '') == 'coordinator':
            dept = getattr(user, 'coordinator_department', None)
            if dept is None:
                return qs.none()
            if self.department_field is None:
                raise ValueError(
                    f'{self.__class__.__name__} must define department_field'
                )
            # Use the department's PK (not the object) for the ORM filter
            dept_id = dept.pk if hasattr(dept, 'pk') else dept
            return qs.filter(**{self.department_field: dept_id})

        # Examiners — DON'T filter here; let ExaminerAssignmentMixin handle it
        if getattr(user, 'role', '') == 'examiner':
            return qs

        return qs.none()

    def get_object(self):
        """
        Override to return 404 (not 403) when object exists but user
        has no access — never confirm existence to unauthorized users.
        """
        try:
            obj = super().get_object()
        except Http404:
            raise
        return obj


# ── Layer 4: Examiner Assignment Scope ───────────────────────────────

class ExaminerAssignmentMixin:
    """
    Mixin for Station-level ViewSets accessed by Examiners.

    For Examiners: filters stations to only those the examiner is
    assigned to via ExaminerAssignment.

    For Coordinators/Admin/Superuser: delegates to DepartmentScopedMixin.

    Use AFTER DepartmentScopedMixin in MRO:
        class StationViewSet(ExaminerAssignmentMixin, DepartmentScopedMixin, ...):
    """

    def get_queryset(self):
        """Further restrict queryset for examiners to assigned stations only."""
        qs = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return qs.none()

        # Examiners: only see stations they're assigned to
        if (not user.is_superuser
                and getattr(user, 'role', '') == 'examiner'):
            assigned_station_ids = ExaminerAssignment.objects.filter(
                examiner=user,
            ).values_list('station_id', flat=True)
            return qs.filter(pk__in=assigned_station_ids)

        # All other roles: DepartmentScopedMixin already handled it
        return qs
