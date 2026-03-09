You are a senior React / Next.js frontend engineer.

Implement a complete client-side access control layer for a clinical exam
platform. The frontend enforces roles for UX only — API + DB + RLS handle
true security. No sensitive data must ever enter the DOM for unauthorized 
roles.

## ROLE CONTEXT ON LOGIN
On successful login, store in context:
- user_id, role (SUPERUSER / ADMIN / COORDINATOR_HEAD / 
  COORDINATOR_ORGANIZER / COORDINATOR_RTA / EXAMINER)
- department_id  (Coordinators only)
- assigned_station_ids[]  (Examiners only)

## ROUTE PROTECTION MAP

/dashboard                                  → All authenticated
/admin/*                                    → Superuser only
/departments/                               → Admin, Superuser
/departments/:deptId/*                      → Admin, Superuser,
                                              Coordinator (own dept)
/departments/:deptId/courses/               → Admin, Superuser,
                                              Coordinator (own dept)
/courses/:courseId/exams/                   → Admin, Superuser,
                                              Coordinator (own dept)
/exams/:examId/                             → Admin, Superuser,
                                              Coordinator (own dept)
/exams/:examId/sessions/                    → Admin, Superuser,
                                              Coordinator (own dept)
/sessions/:sessionId/paths/                 → Admin, Superuser,
                                              Coordinator (own dept)
/paths/:pathId/stations/                    → Admin, Superuser,
                                              Coordinator (own dept)
/stations/:stationId/                       → Admin, Superuser,
                                              Coordinator (own dept),
                                              Examiner (assigned only)
/stations/:stationId/checklist/             → Admin, Superuser,
                                              Coordinator (own dept),
                                              Examiner (assigned only)
/stations/:stationId/score/                 → Examiner (assigned only,
                                              active session only)
/reports/department/:deptId/                → Admin, Superuser,
                                              Coordinator (own dept)

## COMPONENT-LEVEL RENDERING RULES

DepartmentList      → render only for Admin / Superuser
DepartmentCard      → show Edit/Delete only to Admin / Superuser
CoordinatorPanel    → render for Coordinator (own dept) + Admin + Superuser
CourseCard          → show Edit/Delete to Coordinator (own dept) + Admin
ExamCard            → show Edit/Delete to Coordinator-Head (own dept) + Admin + Superuser
SessionPanel        → show "Assign Path / Examiner" to Coordinator + Admin
PathView            → render for Coordinator (own dept) + Admin + Superuser
                      NEVER render for Examiner
StationList         → Examiner sees ONLY their assigned stations
                      Coordinator sees all stations in their dept
StationCard         → show "Edit Station" to Coordinator + Admin only
                      show "Score" button to Examiner (assigned, active session)
ChecklistForm       → render ONLY for Examiner on assigned station,
                      during active session window,
                      disable all inputs once finalized
ExaminerAssignment  → render for Coordinator (own dept) + Admin + Superuser
                      NEVER render for Examiner
ReportsDashboard    → Coordinator sees own dept only
                      Admin / Superuser sees all departments
                      Examiner has ZERO access — never render

## ZERO TRUST UI RULES
- NEVER use CSS display:none to hide sensitive data
  Use conditional rendering — sensitive content must not enter the DOM
- All page components verify session server-side before rendering
- usePermission(action, resource, scopeId) hook on every component
  that renders sensitive data
- Examiner accessing any non-assigned URL:
  → Do not flash content
  → Redirect to /403 immediately
  → Log attempt

## OUTPUT
1. withAuth(requiredRoles[], scopeCheck?) HOC / layout wrapper
2. usePermission(action, resource, scopeId) hook
3. DepartmentScopeContext provider
4. ExaminerAssignmentContext provider (loads assigned_station_ids on login)
5. Role-aware rendering for EVERY component listed above
6. /401 and /403 page components
7. Next.js middleware.ts for edge-level route protection