# 🏥 OSCE Exam Platform

A full-featured **Objective Structured Clinical Examination (OSCE)** management system built with Django. Designed for medical education institutions to manage exams, sessions, examiners, students, scoring, and reporting — all from a single platform.

---

## ✨ Features

### 🔐 Authentication & Role Management
- Unified login portal with **role-based redirection**
- Four-tier access hierarchy:
  - **Superuser** — full system access including Django admin
  - **Admin** — manage coordinators, examiners, exams, sessions, reports
  - **Coordinator** — manage exams and sessions
  - **Examiner** — access examiner interface for scoring
- Activity-based session timeouts (5 min for admin/coordinator, 30 min for examiners)
- Rate-limited login via `django-axes`

### 📋 Exam Management
- Create and manage OSCE exams with stations and checklist items
- Support for multiple exam paths and rotation-based sessions
- Station variants and template library
- Soft delete with restore and permanent delete (admin/superuser only)

### 👥 User Management
- Create and manage examiners, coordinators
- Bulk import examiners via CSV/Excel
- Examiner assignment to stations and sessions

### 📊 Sessions & Scoring
- Create exam sessions with student enrollment
- Assign examiners to stations per session
- Real-time scoring through the examiner interface
- Offline-capable examiner PWA with sync support

### 📈 Reports
- Session-level student results with **Total / Max mark** display
- Percentage and pass/fail indicators
- Scoresheet generation per student
- Excel (XLSX) export for all reports

### 🛡 Security
- CSRF protection on all forms and AJAX calls
- Django admin restricted to superusers only
- Role-based access middleware on all routes
- Audit logging for all critical actions

---

## 🛠 Tech Stack

| Layer       | Technology                         |
|-------------|-------------------------------------|
| Backend     | Django 6.0.2 (Python 3.13)          |
| Database    | SQLite (dev) / PostgreSQL (prod)    |
| Auth        | Custom `Examiner` user model        |
| Rate Limit  | django-axes                         |
| Static Files| WhiteNoise                          |
| Excel Export| openpyxl                            |
| PDF/Arabic  | ReportLab, arabic-reshaper, bidi    |
| Server      | Gunicorn (production)               |

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

---

## 👤 Default User Roles

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
osce_project/
├── core/                   # Models, middleware, auth, admin
│   ├── models/             # Exam, Station, Examiner, Session, Scoring...
│   ├── middleware.py        # Role-based access + session timeout
│   ├── views.py            # Unified login/logout
│   └── admin.py            # Django admin registrations
├── creator/                # Coordinator/admin interface
│   ├── views/              # Dashboard, exams, sessions, reports...
│   └── api/                # JSON API endpoints for the creator UI
├── examiner/               # Examiner scoring interface
│   └── views/              # Examiner pages + API
├── templates/
│   ├── login.html          # Unified login page
│   ├── creator/            # Creator interface templates
│   └── examiner/           # Examiner interface templates
├── static/                 # CSS, JS, PWA manifest
└── osce_project/
    └── settings/           # base.py, development.py, production.py
```

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

```bash
# Install production dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run with Gunicorn
gunicorn osce_project.wsgi:application --bind 0.0.0.0:8000
```

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
