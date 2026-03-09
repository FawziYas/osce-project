"""
core.api — DRF-based REST API with multi-layer authorization.

Layer stack (evaluated top → bottom):
  1. Authentication  – SessionAuthentication (DRF default)
  2. Role Permission – IsSuperuser / IsAdmin / IsCoordinator / IsExaminer
  3. Department Scope – DepartmentScopedMixin (traces FK chain → dept)
  4. Assignment Scope – ExaminerAssignmentMixin (station assignment check)
  5. Session Guard   – SessionStateGuard (active session + not finalized)
"""
