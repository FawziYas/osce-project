# 🏥 OSCE Exam Platform

A full-featured **Objective Structured Clinical Examination (OSCE)** management system built with Django 5.2. Designed for medical education institutions to create exams, manage sessions with multi-path rotation circuits, assign examiners, enroll students, score in real time (with offline support), and generate print-ready PDF reports — all from a single platform with full Arabic language support.

---

## ✨ Features

### 🔐 Authentication & Role Management
- Unified login portal with **role-based redirection** and teal-themed UI
- Force-change-password screen on first login (teal-themed, matching login)
- Four-tier access hierarchy:
  - **Superuser** — full system access including Django admin
  - **Admin** — manage coordinators, examiners, exams, sessions, reports
  - **Coordinator** — manage exams and sessions
  - **Examiner** — access examiner interface for scoring
- Activity-based session timeouts (5 min for admin/coordinator, 30 min for examiners)
- Rate-limited login via `django-axes`
- Admin gateway token restricted to staff users only (not leaking to examiner templates)

### 📋 Exam & Course Management
- Create and manage OSCE exams linked to **courses** with **ILOs** (Intended Learning Outcomes) and **themes**
- Support for Year-4 (JR) and Year-6 (SR) course tiers
- Stations with **checklist items** — each item has points, rubric type (binary/partial/scale), category, criticality flag, and ILO linkage
- Station template library for reusable checklist patterns
- Soft delete with restore and permanent delete (admin/superuser only)

### 🔄 Sessions, Paths & Rotation
- Create exam sessions (morning/afternoon) with configurable start times
- Multi-path rotation circuits (e.g. 5 paths per session, 10 per exam)
- Identical station names and checklists replicated across all paths
- Students assigned to specific paths with sequence numbers
- Automatic student redistribution across paths

### 👥 User & Examiner Management
- Create and manage examiners and coordinators
- Bulk import examiners via CSV/Excel
- Examiner assignment to specific stations per session per path
- Password defaults to a configurable setting (not username)

### 📊 Real-time Scoring
- Examiner scores students station-by-station through a dedicated interface
- Offline-capable examiner PWA with background sync
- Session status validation — scoring only allowed when session is `in_progress`
- Assignment verification — examiners can only score stations they are assigned to
- Ownership checks on all scoring record updates

### 📈 Reports & PDF Generation
- Session-level student results with **Total / Max mark** display
- Percentage and pass/fail indicators per student
- **Session Report PDF** (report code: `RPT-XXXX-XXXXXXXX`):
  - A4 portrait format with proper margins (20mm / 15mm / 25mm / 15mm)
  - 5 sections: Session Overview, Participants Summary, Examiner Assignments, Paths & Stations Breakdown, Student List
  - Repeating fixed footer on every printed page with "CONFIDENTIAL" notice
  - Page-break rules preventing mid-row and mid-section cuts
  - Full Arabic text support — browser-native rendering (HarfBuzz / DirectWrite)
  - RTL direction preserved; Arabic name cells use `white-space: nowrap`
- Excel (XLSX) export for all reports
- CSV raw data export with optimized queries

### 🛡 Security (Audited & Hardened)
- **CSRF protection** on all forms and scoring AJAX calls (removed unnecessary `@csrf_exempt`)
- **API path protection** — middleware blocks `/api/creator/` for non-creator roles (not just `/creator/`)
- **Examiner assignment verification** on all scoring endpoints (`get_session_students`, `start_marking`, `sync_offline_data`)
- **Session status validation** — `start_marking` rejects scoring for completed/cancelled sessions
- **JSON body validation** — all 13+ `json.loads()` calls wrapped in try/except returning 400
- **Sync ownership checks** — `sync_offline_data` verifies examiner owns existing records before updating
- **Admin token scoping** — `SECRET_ADMIN_URL` only injected for authenticated staff users
- **Audit logging** for all critical actions (login, scoring, admin operations)
- Django admin restricted to superusers only
- Full audit report: see `SECURITY_PERFORMANCE_AUDIT.md`

### ⚡ Performance (Optimized)
- **N+1 query elimination** across all major API endpoints:
  - `export_raw_csv` — reduced from O(n²) queries to 2 queries via `select_related()`
  - `get_exams` — station/session counts via `annotate()` instead of per-row `.count()`
  - `get_session_summary` / `export_students_xlsx` — path lookups pre-fetched into dictionary
  - `courses` API — ILO and library item counts via `annotate()`
  - `export_stations_csv` — single query with `select_related('path')`
- **Bulk operations** — `redistribute_students` uses `bulk_update()` instead of per-row `.save()`
- **Database indexes** — added `db_index=True` to `ExamSession.status` and `SessionStudent.status`
- Full performance report: see `SECURITY_PERFORMANCE_AUDIT.md`

### 🎨 UI / Theme
- Teal-themed login and force-change-password pages
- Examiner interface with custom header colors and dashboard styling
- Responsive design for mobile examiner use during exams

---

## 🛠 Tech Stack

| Layer        | Technology                                      |
|--------------|-------------------------------------------------|
| Backend      | Django 5.2.11 (Python 3.13)                     |
| Database     | SQLite (dev) / PostgreSQL (prod via `psycopg2`) |
| Auth         | Custom `Examiner` user model + `django-axes`    |
| Static Files | WhiteNoise                                      |
| Excel Export | openpyxl                                        |
| PDF / Print  | Browser print (HTML window) — Arabic via native HarfBuzz |
| Arabic Text  | arabic-reshaper, python-bidi (server-side where needed)  |
| Server       | Gunicorn (production)                           |
| Config       | django-environ (`.env` files)                   |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/FawziYas/osce-project.git
cd osce-project

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
copy .env.example .env
# Edit .env with your settings

# 5. Apply database migrations
python manage.py migrate

# 6. Create a superuser account
python manage.py create_admin

# 7. Run the development server
python manage.py runserver
```

The app will be available at **http://127.0.0.1:8000**

### Seed Demo Data (Development Only)

```bash
python scripts/seed_demo_data.py
```

This inserts 4 complete OSCE exams (Internal Medicine, Pediatrics, Surgery, OB/GY) with:
- 2 sessions each (morning + afternoon), 10 paths per exam
- 4 stations per path with 14 clinically realistic checklist items (10 marks each)
- 100 Arabic-named students per exam (400 total)
- All linked to existing Year-6 SR courses and ILOs

> **Warning:** Never run the seed script against a production database.

---

## 👤 User Roles

| Role        | Access                                      |
|-------------|---------------------------------------------|
| Superuser   | Everything + Django admin (`/admin/`)        |
| Admin       | Creator interface + manage coordinators      |
| Coordinator | Creator interface (exams, sessions, reports) |
| Examiner    | Examiner interface only (`/examiner/home/`)  |

Login at: **http://127.0.0.1:8000/login/**

---

## 📁 Project Structure

```
OSCE_PROJECT/
├── manage.py                         # Django management entry point
├── requirements.txt                  # Production dependencies
├── requirements-dev.txt              # Dev/test dependencies
├── runtime.txt                       # Python version for deployment
├── Procfile                          # Gunicorn process definition
├── gunicorn.conf.py                  # Gunicorn configuration
├── run.bat / run.ps1 / run.sh        # Quick-start scripts (Win/PS/Linux)
│
├── osce_project/                     # Django project package
│   ├── urls.py                       # Root URL configuration
│   ├── wsgi.py                       # WSGI application
│   ├── asgi.py                       # ASGI application
│   └── settings/
│       ├── base.py                   # Shared settings
│       ├── development.py            # Dev overrides (DEBUG=True, SQLite)
│       └── production.py             # Prod overrides (PostgreSQL, security)
│
├── core/                             # Domain models, auth, middleware
│   ├── models/                       # 20+ model files (see Exam Hierarchy below)
│   │   ├── department.py             #   Department
│   │   ├── course.py                 #   Course, ILO
│   │   ├── exam.py                   #   Exam, Station, ChecklistItem
│   │   ├── session.py                #   ExamSession, SessionStudent
│   │   ├── path.py                   #   Path, PathStation
│   │   ├── scoring.py                #   StationScore, ItemScore
│   │   ├── examiner.py               #   Examiner, ExaminerAssignment
│   │   ├── library.py                #   ChecklistLibrary
│   │   ├── template_library.py       #   TemplateLibrary
│   │   ├── station_template.py       #   StationTemplate
│   │   ├── station_variant.py        #   StationVariant
│   │   ├── dry_station.py            #   DryQuestion, MCQOption, DryStationResponse
│   │   ├── osce_paths.py             #   OSCEExamPath, OSCERoomAssignment, OSCEPathStudent
│   │   ├── theme.py                  #   Theme
│   │   ├── audit.py                  #   AuditLog
│   │   ├── login_audit.py            #   LoginAuditLog
│   │   ├── user_session.py           #   UserSession
│   │   ├── user_profile.py           #   UserProfile
│   │   └── mixins.py                 #   TimestampMixin (shared base)
│   ├── middleware.py                  # Role-based access + session timeout + API guard
│   ├── context_processors.py         # Admin token (staff-only), version info
│   ├── views.py                      # Unified login / logout
│   ├── admin.py                      # Django admin registrations
│   ├── forms.py                      # Auth & profile forms
│   ├── signals.py                    # Post-save signals
│   ├── error_handlers.py             # Custom 400/403/404/500 views
│   ├── templatetags/
│   │   └── osce_filters.py           # Custom template filters
│   ├── utils/
│   │   ├── audit.py                  # Audit logging helpers
│   │   └── naming.py                 # Name formatting utilities
│   └── management/commands/
│       ├── create_admin.py           # Create initial superuser
│       └── init_themes.py            # Seed default themes
│
├── creator/                          # Coordinator / Admin interface
│   ├── dept_access.py                # Department-based access control helpers
│   ├── urls.py                       # Page URL routes
│   ├── api_urls.py                   # JSON API URL routes
│   ├── views/                        # Template-based views
│   │   ├── dashboard.py              #   Dashboard (stats overview)
│   │   ├── exams.py                  #   Exam CRUD + wizard
│   │   ├── sessions.py               #   Session CRUD + management
│   │   ├── paths.py                  #   Path CRUD
│   │   ├── stations.py               #   Station CRUD
│   │   ├── courses.py                #   Course CRUD
│   │   ├── students.py               #   Student enrollment + XLSX upload
│   │   ├── examiners.py              #   Examiner management + assignments
│   │   ├── reports.py                #   Reports index + scoresheets
│   │   ├── library.py                #   Checklist library management
│   │   └── templates_views.py        #   Station template management
│   └── api/                          # JSON API endpoints
│       ├── exams.py                  #   Exam data API
│       ├── sessions.py               #   Session data API
│       ├── paths.py                  #   Path data API
│       ├── stations.py               #   Station + checklist API
│       ├── courses.py                #   Course + ILO API
│       ├── students.py               #   Student data API
│       ├── examiners.py              #   Examiner + assignment API
│       ├── library.py                #   Library items API
│       ├── reports.py                #   Report data API
│       └── stats.py                  #   Dashboard statistics API
│
├── examiner/                         # Examiner scoring interface
│   ├── urls.py                       # Examiner page routes
│   ├── api_urls.py                   # Examiner API routes
│   └── views/
│       ├── pages.py                  #   Examiner pages (home, marking, sessions)
│       └── api.py                    #   Scoring + sync API
│
├── templates/
│   ├── login.html                    # Teal-themed unified login
│   ├── force_change_password.html    # First-login password change
│   ├── profile.html                  # User profile page
│   ├── errors/                       # 400, 403, 404, 500 error pages
│   ├── creator/
│   │   ├── base_creator.html         # Creator layout (sidebar, navbar)
│   │   ├── dashboard.html            # Dashboard page
│   │   ├── exams/                    # list, detail, form, wizard, library_form…
│   │   ├── sessions/                 # list, detail, form, path_form, bulk_stations…
│   │   ├── paths/                    # detail, form
│   │   ├── stations/                 # detail, form, form_simple, template_form
│   │   ├── courses/                  # list, detail, form
│   │   ├── students/                 # list
│   │   ├── examiners/                # list, detail, form
│   │   ├── coordinators/             # list, form, edit
│   │   ├── departments/              # list, form, edit
│   │   ├── reports/                  # index, scoresheets
│   │   ├── library/                  # list, form
│   │   └── ilos/                     # form
│   └── examiner/
│       ├── base_examiner.html        # Examiner layout
│       ├── all_sessions.html         # Session list
│       ├── station_home.html         # Station home (pick station)
│       ├── station_dashboard.html    # Station dashboard
│       ├── select_student.html       # Student selection for scoring
│       ├── marking.html              # Scoring checklist page
│       └── offline.html              # Offline fallback page
│
├── static/
│   ├── manifest.json                 # PWA manifest
│   ├── sw.js                         # Service worker (offline support)
│   ├── css/
│   │   ├── creator.css               # Creator interface styles
│   │   ├── examiner.css              # Examiner shared styles
│   │   ├── examiner-home.css         # Examiner home page
│   │   ├── examiner-dashboard.css    # Examiner dashboard styles
│   │   ├── examiner-evaluation.css   # Scoring evaluation styles
│   │   └── examiner-home-session-layout.css
│   ├── js/
│   │   ├── examiner-app.js           # Examiner SPA logic
│   │   ├── examiner.js               # Examiner utilities
│   │   ├── exam-timer.js             # Station timer
│   │   ├── offline-storage.js        # IndexedDB offline queue
│   │   └── session-report-pdf.js     # HTML-print PDF report generator
│   └── icons/ images/                # App icons & static images
│
├── scripts/
│   ├── seed_demo_data.py             # Demo data seeder (dev only)
│   ├── generate_executive_doc.py     # Executive briefing generator
│   ├── generate_exec_doc.py          # Executive doc (alt)
│   └── generate_workflow_doc.py      # Workflow guide generator
│
└── logs/                             # Application log files
```

---

## 🏗️ Exam Hierarchy (Entity Relationship)

The OSCE exam data is organized in a strict hierarchical tree. Every entity inherits access permissions from its parent — department-based access control is enforced at every level.

```
Department
│   name, description, is_active
│   ↳ head_coordinator, rta_coordinators (Examiner FK)
│
├── Course  (FK → Department)
│   │   code, name, year_level, osce_mark
│   │
│   └── ILO  (FK → Course)
│       number, description, osce_marks
│
└── Exam  (FK → Course, department CharField)
    │   name, exam_date, status, number_of_stations, station_duration_minutes
    │   exam_weight, is_deleted (soft delete)
    │
    ├── Station  (FK → Exam)
    │   │   name, station_number, station_type, duration_minutes
    │   │   max_score, passing_score, theme (FK → Theme)
    │   │
    │   └── ChecklistItem  (FK → Station)
    │       name, points, rubric_type (binary/partial/scale)
    │       category, is_critical, ilo (FK → ILO)
    │
    └── ExamSession  (FK → Exam)
        │   name, session_date, session_type (morning/afternoon)
        │   start_time, number_of_stations, number_of_paths
        │   status (scheduled → in_progress → completed / cancelled)
        │
        ├── Path  (FK → ExamSession)
        │   │   name (A, B, C…), rotation_minutes, is_active
        │   │
        │   └── PathStation  (FK → Path, FK → Station)
        │       station_number (order within path)
        │
        ├── SessionStudent  (FK → ExamSession)
        │   student_name, student_number, path (FK → Path)
        │   sequence_number, status
        │
        ├── ExaminerAssignment  (FK → ExamSession, FK → Station, FK → Examiner)
        │   Links an examiner to a specific station in a session
        │
        └── Scoring
            ├── StationScore  (FK → ExamSession, FK → Station, FK → SessionStudent)
            │   examiner (FK → Examiner), total_score, max_score, is_passed
            │
            └── ItemScore  (FK → StationScore, FK → ChecklistItem)
                score, notes
```

### Access Control Model

| Role | Scope | Description |
|------|-------|-------------|
| **Superuser** | Global | Full access to all departments, exams, sessions, and Django admin |
| **Admin** | Global | Full access to all departments, exams, sessions (no Django admin) |
| **Coordinator (Head)** | Department | Can only view/edit exams, sessions, paths, stations, courses, reports, and students within their assigned department |
| **Coordinator (RTA)** | Department | Same department-scoped access as Head coordinator |
| **Coordinator (Organizer)** | Department | Same department-scoped access |
| **Examiner** | Assignment | Can only access scoring for stations they are assigned to |

> Every URL-accessible view enforces row-level department checks. Sharing a direct URL to a path, station, or session will return **403 Forbidden** for users outside the owning department.

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and configure:

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=sqlite:///db.sqlite3
```

---

## 📦 Production Deployment

See `PRODUCTION_TODO.md` for the full deployment checklist including:
- SQLite → PostgreSQL migration
- `DEBUG=False`, `ALLOWED_HOSTS`, `SECRET_KEY` from environment
- WhiteNoise for static files, Gunicorn as WSGI server
- File cleanup (one-off scripts, dev DB, log rotation)
- Railway / Render hosting guides

```bash
# Install production dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run deployment checks
python manage.py check --deploy

# Run with Gunicorn
gunicorn osce_project.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

---

## 📋 Documentation

| Document | Description |
|----------|-------------|
| `PRODUCTION_TODO.md` | Full production deployment checklist with hosting guides |
| `SECURITY_PERFORMANCE_AUDIT.md` | Security (9 fixes) & performance (7 fixes) audit report |
| `SECURITY_AUDIT_REPORT.md` | Detailed security audit findings |
| `PERFORMANCE_OPTIMIZATION_REPORT.md` | Query optimization details |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License.

---

> Built for medical education — streamlining OSCE exam delivery and scoring.
