# Copilot Session Context — OSCE Project

> Paste this entire file at the start of any new Copilot Chat to restore full context instantly.
> Update this file at the end of each session before pushing.

---

## Project Identity

- **Repo:** https://github.com/FawziYas/osce-project.git
- **Local path:** `C:\Users\M7md\Desktop\dev\osce_project`
- **Venv:** `.\venv\Scripts\Activate.ps1` (the correct one — NOT `C:\Users\M7md\Desktop\dev\.venv`)
- **Run:** `python manage.py runserver` after activating venv
- **Settings:** split into `osce_project/settings/base.py`, `development.py`, `production.py`
- **Auth model:** `core.Examiner` (custom user, not Django's default)
- **DB (dev):** SQLite — `db.sqlite3`
- **DB (prod):** PostgreSQL on Azure
- **Last pushed commit:** `48148db` on branch `main`

---

## Tech Stack

- Django 5.2.11 (all deps pinned in requirements.txt)
- Whitenoise (static files)
- Gunicorn (production WSGI server)
- Azure App Service (planned deployment — university $100/mo credit, target 1000 concurrent users)
- openpyxl, reportlab, arabic-reshaper, python-bidi (Excel/PDF/Arabic)
- pillow (image handling)

---

## Roles & Architecture

| Role | Description |
|---|---|
| **Creator** (coordinator) | Creates exams, sessions, stations; uploads students; activates sessions |
| **Examiner** | Evaluates students at stations during live sessions |

### Core Models (`core/models/`)

| Model | DB Table | Purpose |
|---|---|---|
| `Exam` | `exams` | Top-level exam container |
| `ExamSession` | `exam_sessions` | Session under exam (date, status) |
| `SessionStudent` | `session_students` | Student in a session — unique per `(session, student_number)` |
| `Station` | `stations` | Exam station |
| `Path` | `paths` | Grouping of stations (e.g. IM Junior, IM Senior) |
| `ExaminerAssignment` | `examiner_assignments` | Examiner assigned to station+session |
| `ChecklistItem` | `checklist_items` | Criterion on a station's checklist |
| `StationScore` | `station_scores` | One examiner's total score for one student at one station |
| `ItemScore` | `item_scores` | Individual checklist item score (child of StationScore) |

### Status Values

- **Session:** `scheduled` → `in_progress` → `completed` → `archived` / `cancelled`
- **Exam:** `draft` → `ready` → `in_progress` → `completed` → `archived`

---

## Session 1 — Azure Deployment Guide

**What was done:**
- Decided to switch hosting from Railway → Azure App Service
- Created `AZURE_DEPLOYMENT_GUIDE.md` (~1000 lines) with full step-by-step Azure setup
- Confirmed: development settings are unchanged — Azure config only affects production env
- Localhost (`python manage.py runserver`) always uses `development.py` regardless

---

## Session 2 — Exam Status Label Fix

**Problem:** Status values like `in_progress` were displayed raw in templates.

**What was done:**
- Added `status_label` filter to `core/templatetags/osce_filters.py`
- Mapping: `draft`→"Draft", `ready`→"Ready", `in_progress`→"In Progress", `completed`→"Completed", `archived`→"Archived", `cancelled`→"Cancelled"
- Updated 9 templates to use `{% load osce_filters %}` and `|status_label`
- Fixed CSS badges in `static/css/creator.css`:
  - `badge-completed` → green `#198754`
  - Added `badge-archived` → gray `#6c757d`
  - Added `badge-cancelled` → red `#dc3545`

---

## Session 3 — Exam Status Auto-Sync

**Problem:** Exam status had to be set manually and could be wrong.

**What was done:**
- Added `_sync_exam_status(exam)` to `creator/api/sessions.py`
- Logic:
  ```python
  if any session is 'in_progress'   → exam = 'in_progress'
  elif all sessions are 'completed'  → exam = 'completed'
  elif any session is 'scheduled'    → exam = 'ready'
  else                               → exam = 'draft'
  # 'archived'/'cancelled' sessions excluded from logic
  # exam status 'archived' is never overwritten
  ```
- Called after all 6 session API endpoints + 2 HTML views (`session_create`, `session_delete`)
- Exam status is now **read-only** in the UI — removed dropdown from `templates/creator/exams/form.html`, replaced with badge: `<span class="badge badge-{{ exam.status }}">{{ exam.status|status_label }}</span>`
- Removed manual override in `exam_edit` view

---

## Session 4 — Backfill Existing Exam Statuses

**What was done:**
- Created and ran a one-time script `_fix_exam_status.py`
- Result: 5 exams corrected (e.g. `osce im 30/1`: draft → in_progress)
- Script deleted after use

---

## Session 5 — GitHub Push

- `git commit -m "feat: auto-sync exam status..."` → commit `dd9fdd4`
- Pushed 16 files, 1169 insertions, 91 deletions

---

## Session 6 — Localhost / Azure Questions

**Questions answered:**
- Q: "Does Azure production setup affect localhost?"
- A: No. `python manage.py runserver` always uses `development.py`. Azure env vars only read in production. Completely independent.

---

## Session 7 — Examiner Home Page Rework

**User request:** "make upcoming events include today's unactivated exams, rename Today's Stations to Running Stations showing only activated ones, hide completed"

**Files changed:**

`examiner/views/pages.py` — `home()` function:
```python
# Running Stations — only truly active right now
today_raw = ExaminerAssignment.objects.filter(
    examiner=request.user,
    session__status='in_progress',
)

# Upcoming — includes TODAY (not yet activated) + future dates
upcoming_raw = ExaminerAssignment.objects.filter(
    examiner=request.user,
    session__session_date__gte=today,
    session__status='scheduled',
).order_by('session__session_date')
```
Removed `recent_assignments` (last 7 days completed) — no longer in context or template.

`templates/examiner/station_home.html`:
- "Today's Stations" → "Running Stations" with `bi-play-circle-fill` icon
- Empty state: "No Active Stations Right Now — Stations appear here once activated by coordinator"
- Upcoming: today's scheduled → teal "TODAY" box + "Not yet activated" warning; future → blue date box + path name

---

## Session 8 — Color Fix for Date Box

**Problem:** `.date-box-today` was amber, didn't match teal page theme.

**Fix in `static/css/examiner-home.css`:**
```css
.date-box-today {
    background: linear-gradient(135deg, #0c4a3e 0%, #0f766e 60%, #14b8a6 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
```
Matches the page header gradient exactly.

---

## Session 9 — Student Score Isolation Question

**Question:** "If the same registration number is in different exams or sessions, does that affect scores?"

**Answer:** No — completely isolated.
- Chain: `StationScore` → FK → `SessionStudent` → FK → `ExamSession`
- `SessionStudent` has `UniqueConstraint(['session', 'student_number'])` — same reg number in two sessions = two separate `SessionStudent` rows = two completely separate score sets
- No cross-contamination possible

---

## Session 10 — Score Storage & DB Viewing

**Where scores are stored:**
- `station_scores` — overall station performance per examiner per student
- `item_scores` — individual checklist item scores (child of station_scores)

**How final score is calculated (`core/models/scoring.py` → `get_final_score()`):**
```python
# Averages all submitted examiner scores for one student at one station
final_score = round(sum(StationScore.total_score for all submitted) / count, 2)
# Only status='submitted' scores are included — in_progress are excluded
```

**Multi-examiner scenarios:**
- 3 examiners all score same student → final = average of all 3
- Examiner 1 scores everyone, E2 scores half, E3 scores other half → each student averages only their own examiners' submitted scores

**How to view DB in VS Code:**
- Installed extension: `alexcvzz.vscode-sqlite`
- `Ctrl+Shift+P` → "SQLite: Open Database" → select `db.sqlite3`
- Browse tables visually or run SQL queries directly

---

## Session 11 — Requirements Pinned

All packages pinned to exact versions in `requirements.txt`:
```
Django==5.2.11, asgiref==3.11.1, sqlparse==0.5.5
django-environ==0.13.0, django-axes==8.3.1, packaging==26.0
whitenoise==6.11.0, gunicorn==25.1.0
psycopg2-binary==2.9.11
openpyxl==3.1.5, et_xmlfile==2.0.0, reportlab==4.4.10
arabic-reshaper==3.0.0, python-bidi==0.6.7, charset-normalizer==3.4.4
pillow==12.1.1, tzdata==2025.3
```

---

## Session 12 — Cross-PC Context File (This File)

- Created `COPILOT_CONTEXT.md` covering all sessions and pushed to repo
- On any new PC: `git pull` → open this file → paste into new Copilot Chat → full context restored

---

## Pending Tasks (Not Yet Implemented)

### ⏳ Department Auto-select from Course
**User request:** "make the department droplist disabled and it selects according to the course — if it's IM junior or senior it selects Internal Medicine, and so on"

**Context:**
- Exam `form.html` has a department `<select>` with 4 options: Internal Medicine, Pediatrics, General Surgery, Obstetrics and Gynecology
- `Course` model fields: `code`, `short_code`, `name`, `year_level` — **no department field**
- Interrupted by a GitHub push request before implementation

**Implementation plan:**
1. In `creator/views/exams.py`: pass `courses_json = json.dumps({str(c.id): c.name for c in Course.objects.all()})` to template context
2. In `templates/creator/exams/form.html`: add JS that:
   - Listens to `course_id` change
   - Maps course name keywords → department value:
     - `"internal"` → `"Internal Medicine"`
     - `"pediatric"` → `"Pediatrics"`
     - `"surgery"` → `"General Surgery"`
     - `"obstetric"` or `"gynecolog"` → `"Obstetrics and Gynecology"`
   - Auto-sets the department dropdown and disables it
3. Same JS likely needed in `templates/creator/exams/wizard.html`

---

## Key File Map

```
osce_project/
├── core/
│   ├── models/
│   │   ├── scoring.py          ← StationScore, ItemScore, get_final_score()
│   │   ├── session.py          ← ExamSession, SessionStudent
│   │   └── exam.py             ← Exam model
│   └── templatetags/
│       └── osce_filters.py     ← status_label, strftime, to_letter, get_item, average_score
├── creator/
│   ├── api/
│   │   └── sessions.py         ← _sync_exam_status(), all 6 session API endpoints
│   └── views/
│       ├── exams.py            ← exam_create, exam_edit (status is read-only now)
│       └── sessions.py         ← session_create, session_delete (call _sync_exam_status)
├── examiner/
│   └── views/
│       └── pages.py            ← home(): Running Stations (in_progress) + Upcoming (scheduled)
├── templates/
│   ├── creator/exams/
│   │   ├── form.html           ← Exam form — status badge, no dropdown
│   │   └── wizard.html         ← Exam creation wizard
│   └── examiner/
│       └── station_home.html   ← Running Stations + Upcoming sections
├── static/css/
│   ├── creator.css             ← badge-completed (green), badge-archived, badge-cancelled
│   └── examiner-home.css       ← .date-box-today teal gradient
├── requirements.txt            ← ALL versions pinned exactly
├── requirements-dev.txt        ← includes debug-toolbar, django-extensions
├── AZURE_DEPLOYMENT_GUIDE.md   ← Full Azure deployment steps
└── COPILOT_CONTEXT.md          ← This file
```

---

## Setup on New PC

```powershell
git clone https://github.com/FawziYas/osce-project.git
cd osce-project
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
