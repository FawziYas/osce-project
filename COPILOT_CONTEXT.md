# Copilot Session Context — OSCE Project

Paste this file contents at the start of any new Copilot chat to restore full context.

---

## Project

- **Repo:** https://github.com/FawziYas/osce-project.git
- **Path (local):** `C:\Users\M7md\Desktop\dev\osce_project`
- **Venv:** `.\venv\Scripts\Activate.ps1` (NOT `.venv`)
- **Run:** `python manage.py runserver` after activating venv
- **Settings:** split into `base.py` / `development.py` / `production.py`
- **Auth model:** `core.Examiner` (custom user)
- **DB:** SQLite (`db.sqlite3`) for dev; PostgreSQL for production (Azure)
- **Last pushed commit:** `7d99fdf` on branch `main`

---

## Tech Stack

- Django 5.2.11
- SQLite (dev) / PostgreSQL (prod)
- Whitenoise (static files)
- Gunicorn (production server)
- Azure (planned deployment target — $100/mo university credit, 1000 users)
- openpyxl, reportlab, arabic-reshaper, python-bidi (Excel, PDF, Arabic support)
- pillow (images)

---

## Architecture Overview

### Roles
- **Creator** — coordinator who creates exams, sessions, stations, uploads students
- **Examiner** — evaluates students at stations during live sessions

### Key Models (`core/models/`)
| Model | Table | Purpose |
|---|---|---|
| `Exam` | `exams` | Top-level exam container |
| `ExamSession` | `exam_sessions` | A session under an exam (date, status) |
| `SessionStudent` | `session_students` | Student in a session (unique per session+student_number) |
| `Station` | `stations` | Exam station |
| `ExaminerAssignment` | `examiner_assignments` | Examiner assigned to a station in a session |
| `StationScore` | `station_scores` | Examiner's total score for a student at a station |
| `ItemScore` | `item_scores` | Individual checklist item scores (child of StationScore) |

### Status Values
- **Session:** `scheduled` → `in_progress` → `completed` → `archived` / `cancelled`
- **Exam:** `draft` → `ready` → `in_progress` → `completed` → `archived`

---

## Completed Features (This Session)

### 1. Status Label Filter
- Added `status_label` filter to `core/templatetags/osce_filters.py`
- Maps slugs → human labels: `in_progress` → "In Progress", etc.
- Updated all templates that show statuses

### 2. CSS Badge Colors
- `badge-completed` → green `#198754`
- `badge-archived` → gray `#6c757d`
- `badge-cancelled` → red `#dc3545`
- File: `static/css/creator.css`

### 3. Exam Status Auto-Sync
- Function `_sync_exam_status(exam)` in `creator/api/sessions.py`
- Logic: if any session `in_progress` → exam `in_progress`; all `completed` → exam `completed`; any `scheduled` → exam `ready`; else → `draft`
- Called from all 6 API endpoints + 2 HTML view endpoints (session_create, session_delete)
- Exam status is now **read-only** in the UI (badge only, no dropdown in form)
- Existing 5 exams were backfilled via a one-time script

### 4. Examiner Home Page (`examiner/views/pages.py`)
- **Running Stations** section: only `status='in_progress'` sessions (no date filter)
- **Upcoming** section: `session_date__gte=today` + `status='scheduled'` (includes today's unactivated)
- Removed `recent_assignments` (last 7 days) entirely

### 5. Examiner Home Template (`templates/examiner/station_home.html`)
- "Today's Stations" renamed to "Running Stations" with `bi-play-circle-fill` icon
- Empty state: "No Active Stations Right Now — Stations appear here once activated"
- Upcoming: today's sessions get teal "TODAY" box + "Not yet activated" label; future sessions get blue date box

### 6. CSS for Upcoming (`static/css/examiner-home.css`)
```css
.date-box-today {
    background: linear-gradient(135deg, #0c4a3e 0%, #0f766e 60%, #14b8a6 100%);
}
```
Matches the page header gradient.

---

## Scoring Logic

- Each examiner submits one `StationScore` per student per station
- Final score = **average** of all submitted `StationScore` records for that student+station
- Code: `StationScore.get_final_score(session_student_id, station_id)` in `core/models/scoring.py`
- Scores across different sessions/exams are **fully isolated** (SessionStudent is unique per session)
- Only `status='submitted'` scores count; `in_progress` are excluded

---

## Pending Tasks

### Department Auto-select from Course (NOT YET IMPLEMENTED)
**User request:** "make the department droplist disabled and it select according to the course — if it's IM either jr or sr it selects Internal Medicine, and so on"
- Exam `form.html` has department dropdown with 4 options: Internal Medicine, Pediatrics, General Surgery, Obstetrics and Gynecology
- Course model has: `code`, `short_code`, `name`, `year_level` — no department field
- Implementation needed:
  1. Pass courses as JSON to the template (in `creator/views/exams.py`)
  2. JS on `course_id` change → map course name → department value → auto-set + disable dropdown
  3. Mapping by course name keywords (e.g., "internal" → "Internal Medicine")
- Files to modify: `templates/creator/exams/form.html`, possibly `creator/views/exams.py`

---

## Key File Locations

```
osce_project/
├── core/
│   ├── models/
│   │   ├── scoring.py       # StationScore, ItemScore
│   │   ├── session.py       # ExamSession, SessionStudent
│   │   └── exam.py          # Exam
│   └── templatetags/
│       └── osce_filters.py  # status_label, strftime, to_letter, get_item, average_score
├── creator/
│   ├── api/
│   │   └── sessions.py      # _sync_exam_status(), all session API endpoints
│   └── views/
│       ├── exams.py         # exam_create, exam_edit (status read-only)
│       └── sessions.py      # session_create, session_delete
├── examiner/
│   └── views/
│       └── pages.py         # home() — Running Stations + Upcoming logic
├── templates/
│   ├── creator/exams/
│   │   └── form.html        # Exam create/edit form (status badge, no dropdown)
│   └── examiner/
│       └── station_home.html
├── static/css/
│   ├── creator.css          # badge colors
│   └── examiner-home.css    # .date-box-today teal gradient
├── requirements.txt         # ALL versions pinned exactly
└── requirements-dev.txt
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
