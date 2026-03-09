You are a senior Django REST Framework engineer.

Build a complete multi-layer authorization system for a clinical exam
platform. No unauthorized access must be possible — even when a direct
URL is shared with an unauthorized user or role.

## ATTACK SCENARIOS TO PREVENT

1. Coordinator from Dept A opens:
   GET /api/exams/abc-123/
   → BLOCK if exam belongs to Dept B → return 404

2. Examiner opens:
   GET /api/stations/xyz-789/
   → BLOCK if not assigned to this station → return 404

3. Examiner opens:
   GET /api/paths/def-456/
   → BLOCK always → Examiners have no Path access → 403

4. Unauthenticated user opens any URL → 401

5. Coordinator opens:
   GET /api/departments/   (another dept)
   → 404, never confirm existence

## FULL ROUTE PERMISSION MAP

GET  /api/departments/                          → Admin, Superuser
GET  /api/departments/:deptId/                  → Admin, Superuser,
                                                   Coordinator (own dept only)
GET  /api/departments/:deptId/coordinators/     → Admin, Superuser,
                                                   Coordinator (own dept only)
GET  /api/departments/:deptId/courses/          → Admin, Superuser,
                                                   Coordinator (own dept only)
GET  /api/courses/:courseId/exams/              → Admin, Superuser,
                                                   Coordinator (own dept only)
GET  /api/exams/:examId/                        → Admin, Superuser,
                                                   Coordinator (own dept only)
GET  /api/exams/:examId/sessions/               → Admin, Superuser,
                                                   Coordinator (own dept only)
GET  /api/sessions/:sessionId/paths/            → Admin, Superuser,
                                                   Coordinator (own dept only)
GET  /api/paths/:pathId/stations/               → Admin, Superuser,
                                                   Coordinator (own dept only)
GET  /api/stations/:stationId/                  → Admin, Superuser,
                                                   Coordinator (own dept only),
                                                   Examiner (assigned only)
GET  /api/stations/:stationId/checklist/        → Admin, Superuser,
                                                   Coordinator (own dept only),
                                                   Examiner (assigned only)
POST /api/stations/:stationId/checklist/:itemId/score/ 
                                                → Examiner (assigned only,
                                                   active session only)
PUT  /api/stations/:stationId/checklist/:itemId/score/
                                                → Examiner (assigned, not finalized)
GET  /api/stations/:stationId/assignments/      → Admin, Superuser,
                                                   Coordinator (own dept only)
POST /api/stations/:stationId/assignments/      → Admin, Superuser,
                                                   Coordinator (own dept only)
GET  /api/reports/department/:deptId/           → Admin, Superuser,
                                                   Coordinator (own dept only)

## PERMISSION LAYER STACK

### Layer 1 — Authentication
- Validate token on every request
- Attach: user_id, role, department_id, assigned_station_ids
- Missing/expired token → 401

### Layer 2 — Role Permission Class
- Build IsSuperuser, IsAdmin, IsCoordinator, IsExaminer
  DRF permission classes
- Compose them per ViewSet action

### Layer 3 — Department Scope Mixin
- For every resource below Department, trace FK chain up to department_id
- Compare against request.user.department_id
- Mismatch → 404 (never 403 — do not confirm existence)
- Apply as a reusable mixin: DepartmentScopedMixin

### Layer 4 — Examiner Assignment Scope Mixin
- For Station and ChecklistItem views accessed by Examiner:
  verify ExaminerAssignment.objects.filter(
      examiner=request.user,
      station=obj,
      is_active=True
  ).exists()
- Not found → 404

### Layer 5 — Session State Guard
- Examiner can only POST/PUT scores during an active Session window
- Session.status must be ACTIVE
- Finalized scores → block UPDATE for all roles

## OUTPUT
1. Custom DRF Permission classes for each role
2. DepartmentScopedMixin (get_queryset + get_object)
3. ExaminerAssignmentScopedMixin
4. SessionStateGuard mixin
5. All ViewSets with correct permission_classes per action
6. Error responses: {"error": "...", "code": "...", "detail": "..."}
7. Unit tests for all 5 attack scenarios