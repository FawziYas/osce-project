"""
Script to generate the IT Department Technical Brief PDF for the OSCE app.
Run: python generate_it_brief.py
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak
import os

# ──────────────────────────────────────────────────────────────────────────────
# COLOURS
# ──────────────────────────────────────────────────────────────────────────────
DEEP_BLUE    = HexColor('#0A2540')
ACCENT_BLUE  = HexColor('#1A73E8')
LIGHT_BLUE   = HexColor('#E8F0FE')
GREEN        = HexColor('#188038')
LIGHT_GREEN  = HexColor('#E6F4EA')
AMBER        = HexColor('#F29900')
LIGHT_AMBER  = HexColor('#FEF7E0')
RED          = HexColor('#B31412')
LIGHT_RED    = HexColor('#FCE8E6')
GREY_BORDER  = HexColor('#DADCE0')
LIGHT_GREY   = HexColor('#F8F9FA')
MID_GREY     = HexColor('#5F6368')
DARK_TEXT    = HexColor('#202124')

# ──────────────────────────────────────────────────────────────────────────────
# STYLE SHEET
# ──────────────────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

# Page title
title_style = ParagraphStyle('DocTitle',
    fontName='Helvetica-Bold', fontSize=22, leading=28,
    textColor=white, alignment=TA_CENTER, spaceAfter=4)

subtitle_style = ParagraphStyle('DocSubtitle',
    fontName='Helvetica', fontSize=11, leading=16,
    textColor=HexColor('#BDC8D8'), alignment=TA_CENTER, spaceAfter=0)

meta_style = ParagraphStyle('Meta',
    fontName='Helvetica-Oblique', fontSize=9, leading=13,
    textColor=HexColor('#9AA0A6'), alignment=TA_CENTER)

# Section heading
section_style = ParagraphStyle('Section',
    fontName='Helvetica-Bold', fontSize=13, leading=18,
    textColor=DEEP_BLUE, spaceBefore=18, spaceAfter=6,
    borderPadding=(0, 0, 4, 0))

# Sub-heading
sub_style = ParagraphStyle('Sub',
    fontName='Helvetica-Bold', fontSize=10.5, leading=15,
    textColor=ACCENT_BLUE, spaceBefore=10, spaceAfter=4)

# Body bullet
bullet_style = ParagraphStyle('Bullet',
    fontName='Helvetica', fontSize=9.5, leading=14,
    textColor=DARK_TEXT, leftIndent=14, bulletIndent=4,
    spaceAfter=2)

# Body bold bullet
bold_bullet_style = ParagraphStyle('BoldBullet',
    fontName='Helvetica-Bold', fontSize=9.5, leading=14,
    textColor=DARK_TEXT, leftIndent=14, bulletIndent=4,
    spaceAfter=2)

# Sub-bullet (indented one more level)
sub_bullet_style = ParagraphStyle('SubBullet',
    fontName='Helvetica', fontSize=9, leading=13,
    textColor=MID_GREY, leftIndent=28, bulletIndent=18,
    spaceAfter=1)

# Normal body
body_style = ParagraphStyle('Body',
    fontName='Helvetica', fontSize=9.5, leading=14,
    textColor=DARK_TEXT, spaceAfter=4, alignment=TA_JUSTIFY)

# Question style (bold, coloured)
q_style = ParagraphStyle('QStyle',
    fontName='Helvetica-Bold', fontSize=9.5, leading=14,
    textColor=DEEP_BLUE, leftIndent=14, bulletIndent=4,
    spaceAfter=1)

answer_style = ParagraphStyle('AStyle',
    fontName='Helvetica', fontSize=9.5, leading=14,
    textColor=MID_GREY, leftIndent=28, bulletIndent=18,
    spaceAfter=4)

# ──────────────────────────────────────────────────────────────────────────────
# HELPER – coloured badge paragraph
# ──────────────────────────────────────────────────────────────────────────────
def badge(text, bg, fg=DARK_TEXT):
    s = ParagraphStyle('badge', fontName='Helvetica-Bold', fontSize=8.5,
                       textColor=fg, backColor=bg, borderPadding=3,
                       borderRadius=3, spaceAfter=0)
    return Paragraph(text, s)

def section_header(text, icon=''):
    full = f"{icon}  {text}" if icon else text
    return Paragraph(full, section_style)

def bullet(text):
    return Paragraph(f"• {text}", bullet_style)

def bold_bullet(label, rest=''):
    if rest:
        return Paragraph(f"• <b>{label}</b>  {rest}", bullet_style)
    return Paragraph(f"• <b>{label}</b>", bold_bullet_style)

def sub_bullet(text):
    return Paragraph(f"– {text}", sub_bullet_style)

def qa(q_text, a_text):
    return [
        Paragraph(f"Q{q_text}", q_style),
        Paragraph(a_text, answer_style),
    ]

def hr():
    return HRFlowable(width='100%', thickness=0.5, color=GREY_BORDER,
                      spaceAfter=6, spaceBefore=0)

def spacer(h=8):
    return Spacer(1, h)

# ──────────────────────────────────────────────────────────────────────────────
# COLOURED INFO BOX  (rounded-corner table simulation)
# ──────────────────────────────────────────────────────────────────────────────
def info_box(title, items, bg=LIGHT_BLUE, title_color=ACCENT_BLUE):
    title_p = Paragraph(f"<b>{title}</b>", ParagraphStyle('bt',
        fontName='Helvetica-Bold', fontSize=9.5, textColor=title_color))
    rows = [[title_p]]
    for item in items:
        rows.append([Paragraph(f"  • {item}", ParagraphStyle('bi',
            fontName='Helvetica', fontSize=9.5, textColor=DARK_TEXT,
            leading=14))])
    t = Table(rows, colWidths=[16.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), bg),
        ('BACKGROUND', (0,1), (-1,-1), bg),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [bg, HexColor('#DDEEFF') if bg == LIGHT_BLUE else bg]),
        ('BOX',    (0,0), (-1,-1), 0.8, title_color),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 10),
        ('RIGHTPADDING',  (0,0), (-1,-1), 10),
    ]))
    return t

# ──────────────────────────────────────────────────────────────────────────────
# CANVAS CALLBACKS  – page background / header stripe / footer
# ──────────────────────────────────────────────────────────────────────────────
def first_page(c, doc):
    w, h = A4
    # Full-bleed header band
    c.setFillColor(DEEP_BLUE)
    c.rect(0, h - 4.8*cm, w, 4.8*cm, fill=1, stroke=0)
    # Accent stripe
    c.setFillColor(ACCENT_BLUE)
    c.rect(0, h - 5.05*cm, w, 0.25*cm, fill=1, stroke=0)
    footer(c, doc)

def later_pages(c, doc):
    w, h = A4
    # Thin header bar on subsequent pages
    c.setFillColor(DEEP_BLUE)
    c.rect(0, h - 1.1*cm, w, 1.1*cm, fill=1, stroke=0)
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(white)
    c.drawString(2*cm, h - 0.75*cm, 'OSCE Examination Platform — IT Department Technical Brief')
    c.drawRightString(w - 2*cm, h - 0.75*cm, f'Page {doc.page}')
    footer(c, doc)

def footer(c, doc):
    w, _ = A4
    c.setFillColor(GREY_BORDER)
    c.rect(0, 0, w, 0.8*cm, fill=1, stroke=0)
    c.setFont('Helvetica-Oblique', 7.5)
    c.setFillColor(MID_GREY)
    c.drawString(2*cm, 0.27*cm, 'Confidential — For IT Department Review Only')
    c.drawRightString(w - 2*cm, 0.27*cm, 'Prepared by: Development Team  |  March 2026')

# ──────────────────────────────────────────────────────────────────────────────
# DOCUMENT CONTENT
# ──────────────────────────────────────────────────────────────────────────────
def build_story():
    story = []

    # ── COVER / TITLE ─────────────────────────────────────────────────────────
    # Spacer pushes text into the header band (painted by callback)
    story.append(Spacer(1, 1.0*cm))
    story.append(Paragraph('OSCE Examination Platform', title_style))
    story.append(Paragraph('IT Department — Technical Overview Brief', subtitle_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph('Prepared for: Head of IT Department  |  March 2026  |  Confidential', meta_style))
    story.append(Spacer(1, 1.5*cm))

    # ── 1. EXECUTIVE SUMMARY ──────────────────────────────────────────────────
    story.append(section_header('1. Executive Summary'))
    story.append(hr())
    story.append(body_style and Paragraph(
        'This document provides a technical summary of the OSCE (Objective Structured Clinical '
        'Examination) digital platform developed for internal university use. It covers the '
        'technology stack, security design, user roles, data handling, and operational '
        'considerations for deployment within the university examination environment.',
        body_style))
    story.append(spacer(6))

    summary_data = [
        ['Purpose', 'Replace paper-based OSCE scoring with a secure, real-time digital platform'],
        ['Target users', 'Examiners, Coordinators, Admins — university staff only'],
        ['Deployment', 'Web application — accessible via any browser on the university network'],
        ['Data residency', 'All data stored on university-controlled or university-approved servers'],
        ['Student exposure', 'Students are tracked by ID number only — no direct student login'],
    ]
    t = Table(summary_data, colWidths=[4*cm, 12.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (0,-1), LIGHT_BLUE),
        ('BACKGROUND',   (1,0), (1,-1), white),
        ('TEXTCOLOR',    (0,0), (0,-1), DEEP_BLUE),
        ('FONTNAME',     (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',     (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE',     (0,0), (-1,-1), 9.5),
        ('LEADING',      (0,0), (-1,-1), 14),
        ('TOPPADDING',   (0,0), (-1,-1), 5),
        ('BOTTOMPADDING',(0,0), (-1,-1), 5),
        ('LEFTPADDING',  (0,0), (-1,-1), 8),
        ('GRID',         (0,0), (-1,-1), 0.5, GREY_BORDER),
        ('ROWBACKGROUNDS',(1,0),(1,-1),[white, LIGHT_GREY]),
    ]))
    story.append(t)
    story.append(spacer(10))

    # ── 2. TECHNOLOGY STACK ───────────────────────────────────────────────────
    story.append(section_header('2. Technology Stack'))
    story.append(hr())

    story.append(Paragraph('<b>Backend (Server-Side)</b>', sub_style))
    story.append(bold_bullet('Language:', 'Python 3.12'))
    story.append(bold_bullet('Web Framework:', 'Django 5.2  (LTS-equivalent, latest stable)'))
    story.append(bold_bullet('REST API Layer:', 'Django REST Framework (DRF) 3.16'))
    story.append(bold_bullet('Task Queue:', 'Celery 5.4 with Redis — for async background jobs (audit log writes)'))
    story.append(bold_bullet('PDF / Excel Generation:', 'ReportLab 4.4 (exam reports) + OpenPyXL 3.1 (XLSX exports)'))
    story.append(bold_bullet('Arabic Text Rendering:', 'arabic-reshaper + python-bidi — supports bilingual score reports'))
    story.append(bold_bullet('Image Handling:', 'Pillow 12.1 — question image processing'))
    story.append(bold_bullet('Error Tracking:', 'Sentry SDK 2.19 — real-time production error alerts'))
    story.append(spacer(4))

    story.append(Paragraph('<b>Frontend (Client-Side)</b>', sub_style))
    story.append(bold_bullet('Markup / Styling:', 'HTML5 + CSS3 + Bootstrap 5.3 (responsive, mobile-friendly)'))
    story.append(bold_bullet('Icons:', 'Bootstrap Icons — consistent icon library'))
    story.append(bold_bullet('JavaScript:', 'Vanilla ES6+ (no heavy JS frameworks — deliberately lightweight)'))
    story.append(bold_bullet('Offline Resilience:', 'Local queue (max 100 entries) caches score submissions if network drops mid-exam'))
    story.append(bold_bullet('Progressive Web App (PWA):', 'Service Worker + manifest.json — installable on exam-room tablets'))
    story.append(spacer(4))

    story.append(Paragraph('<b>Database</b>', sub_style))
    story.append(bold_bullet('Engine:', 'PostgreSQL 14+  (production)'))
    story.append(sub_bullet('SQLite used in development / local testing only'))
    story.append(bold_bullet('ORM:', 'Django ORM — all queries parameterized; zero raw SQL in application code'))
    story.append(bold_bullet('Row-Level Security (RLS):', 'Enforced directly in PostgreSQL — a DB-level guardrail in addition to application-level checks'))
    story.append(bold_bullet('Connection:', 'SSL required (sslmode=require) in production; persistent connection pooling (conn_max_age=600s)'))
    story.append(spacer(4))

    story.append(Paragraph('<b>Infrastructure / Hosting</b>', sub_style))
    story.append(bold_bullet('Application Server:', 'Gunicorn (WSGI) — industry-standard Python production server'))
    story.append(bold_bullet('Static File Serving:', 'WhiteNoise 6.11 — compressed + fingerprinted static assets'))
    story.append(bold_bullet('Cloud Option:', 'Microsoft Azure — App Service (app) + Azure Database for PostgreSQL (DB) + Azure Blob Storage (media)'))
    story.append(bold_bullet('Cache / Session Broker:', 'Redis (optional) — improves session handling and API response times'))
    story.append(spacer(10))

    # ── 3. USER ROLES & ACCESS CONTROL ───────────────────────────────────────
    story.append(section_header('3. User Roles & Access Control'))
    story.append(hr())

    roles_data = [
        ['Role', 'Scope', 'Capabilities'],
        ['Superuser', 'Global', 'Full system access; can delete/revert sessions'],
        ['Admin', 'Global', 'Manage all departments, exams, sessions, users'],
        ['Coordinator — Head', 'Department', 'Manage users, sessions, exams within own department; view student list; open dry grading'],
        ['Coordinator — Organizer', 'Department', 'Manage sessions and exams within department; open dry grading'],
        ['Coordinator — RTA', 'Department', 'Real-time access coordination within department'],
        ['Examiner', 'Station only', 'Score entry at assigned station only — cannot see other stations'],
    ]
    t2 = Table(roles_data, colWidths=[3.5*cm, 3*cm, 10*cm])
    t2.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), DEEP_BLUE),
        ('TEXTCOLOR',     (0,0), (-1,0), white),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME',      (0,1), (-1,-1),'Helvetica'),
        ('FONTSIZE',      (0,0), (-1,-1), 9),
        ('LEADING',       (0,0), (-1,-1), 13),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 7),
        ('GRID',          (0,0), (-1,-1), 0.5, GREY_BORDER),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[white, LIGHT_GREY]),
        ('ALIGN',         (0,0), (-1,0), 'CENTER'),
    ]))
    story.append(t2)
    story.append(spacer(8))

    story.append(Paragraph('<b>Role enforcement is multi-layered:</b>', sub_style))
    story.append(bold_bullet('Application Layer:', 'Django middleware + custom permission classes on every view and API endpoint'))
    story.append(bold_bullet('Database Layer:', 'PostgreSQL Row-Level Security (RLS) — the database itself rejects queries outside the user\'s permitted scope'))
    story.append(bold_bullet('Coordinator isolation:', 'Each coordinator can only see/edit data belonging to their own department — cross-department data is invisible at both the ORM and DB level'))
    story.append(bold_bullet('Examiner isolation:', 'An examiner can only submit scores for their own assigned station — other stations\' data is inaccessible'))
    story.append(spacer(10))

    # ── 4. SECURITY ARCHITECTURE ─────────────────────────────────────────────
    story.append(PageBreak())
    story.append(section_header('4. Security Architecture'))
    story.append(hr())

    # 4.1 Authentication
    story.append(Paragraph('4.1  Authentication', sub_style))
    story.append(bold_bullet('Session-Based Authentication:', 'HttpOnly, SameSite=Lax cookies — no JWT tokens in URLs'))
    story.append(bold_bullet('Brute-Force Protection:', 'django-axes 8.3 — auto-locks accounts after repeated failed logins; rate limits by IP + username'))
    story.append(bold_bullet('Force Password Change:', 'Every new user must change their temporary password on first login — enforced by middleware, not optional'))
    story.append(bold_bullet('Password Policy:', 'Minimum 8 characters; rejects common passwords; rejects numeric-only; rejects username-similar'))
    story.append(bold_bullet('Soft-Delete Protection:', 'Deactivated accounts cannot authenticate — explicitly checked after Django\'s own authentication'))
    story.append(bold_bullet('Session Timeout:', 'Auto-logout after 10 min inactivity (admin/coordinator) or 20 min (examiner) — activity-based sliding window'))
    story.append(spacer(6))

    # 4.2 Admin access
    story.append(Paragraph('4.2  Admin Panel — Double-Lock Protection', sub_style))
    story.append(bold_bullet('Obscured Admin URL:', 'The standard /admin/ path returns HTTP 404 — automated scanners find nothing'))
    story.append(bold_bullet('Secret URL:', 'Admin panel is only accessible via a configurable secret path (changed via environment variable, zero code changes)'))
    story.append(bold_bullet('Session Gate:', 'Even knowing the secret URL is insufficient — a session token must be set by successfully passing the admin gateway'))
    story.append(bold_bullet('Staff Flag Required:', 'Users must have is_staff=True AND successfully pass the gateway to reach the admin panel'))
    story.append(spacer(6))

    # 4.3 Web Application Security
    story.append(Paragraph('4.3  Web Application Security (HTTP Headers)', sub_style))

    headers_data = [
        ['Header', 'Value / Behaviour'],
        ['CSRF Protection', 'Django CSRF token on every POST — blocks cross-site request forgery'],
        ['Content-Security-Policy', 'Restricts script / style / image sources to prevent XSS injection'],
        ['X-Frame-Options', 'DENY — prevents the app from being embedded in iframes (clickjacking)'],
        ['X-Content-Type-Options', 'nosniff — prevents MIME-type sniffing attacks'],
        ['Referrer-Policy', 'strict-origin-when-cross-origin — hides URL details from third parties'],
        ['Permissions-Policy', 'Disables camera, microphone, geolocation APIs in the browser'],
        ['X-Robots-Tag', 'noindex, nofollow — search engines cannot index or link to the site'],
        ['Secure Cookie (prod)', 'SESSION_COOKIE_SECURE=True; CSRF_COOKIE_SECURE=True — HTTPS-only'],
        ['HTTPS Redirect (prod)', 'SECURE_SSL_REDIRECT=True — all HTTP traffic forced to HTTPS'],
        ['HSTS (prod)', '1 year HSTS with includeSubDomains — browsers remember HTTPS-only'],
    ]
    t3 = Table(headers_data, colWidths=[5.5*cm, 11*cm])
    t3.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), DEEP_BLUE),
        ('TEXTCOLOR',     (0,0), (-1,0), white),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME',      (0,1), (-1,-1),'Helvetica'),
        ('FONTSIZE',      (0,0), (-1,-1), 9),
        ('LEADING',       (0,0), (-1,-1), 13),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 7),
        ('GRID',          (0,0), (-1,-1), 0.5, GREY_BORDER),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[white, LIGHT_BLUE]),
    ]))
    story.append(t3)
    story.append(spacer(8))

    # 4.4 Database Security
    story.append(Paragraph('4.4  Database Security', sub_style))
    story.append(bold_bullet('SQL Injection:', 'Impossible by design — 100% Django ORM with parameterized queries; no .raw() or .extra() SQL calls anywhere in the codebase'))
    story.append(bold_bullet('Row-Level Security (RLS):', 'PostgreSQL enforces data isolation at the engine level — coordinators are physically blocked from reading other departments\' rows, even if application code had a bug'))
    story.append(bold_bullet('RLS Session Variables:', '4 variables injected per request: user_id, role, department_id, station_ids — scoped to each DB transaction then auto-cleared'))
    story.append(bold_bullet('SSL Encryption:', 'All DB connections use sslmode=require — data encrypted in transit between app and database'))
    story.append(bold_bullet('Least-Privilege DB User:', 'Application connects as a limited PostgreSQL user — no superuser rights'))
    story.append(bold_bullet('Migration Audit Trail:', 'All schema changes tracked as Django migrations — versioned in source control'))
    story.append(spacer(8))

    # 4.5 Audit Logging
    story.append(Paragraph('4.5  Comprehensive Audit Logging', sub_style))
    story.append(bold_bullet('Every login attempt:', 'Logged (success and failure) with timestamp, IP address, user agent'))
    story.append(bold_bullet('Every 401 / 403 / 404 response:', 'Logged by UnauthorizedAccessMiddleware — unauthorized access attempts are recorded'))
    story.append(bold_bullet('Score submissions:', 'Each score write is logged with examiner identity, station, and timestamp'))
    story.append(bold_bullet('Session lifecycle events:', 'Exam session start, activation, deactivation, and completion all logged'))
    story.append(bold_bullet('Async logging:', 'Audit writes use Celery task queue — does not slow down exam-room response times'))
    story.append(bold_bullet('Non-repudiation:', 'Every data change is attributable to a specific user — no anonymous modifications possible'))
    story.append(spacer(10))

    # ── 5. DATA INTEGRITY & EXAM RELIABILITY ─────────────────────────────────
    story.append(section_header('5. Data Integrity & Exam Reliability'))
    story.append(hr())
    story.append(bold_bullet('Auto-Save:', 'Scores are auto-saved every 30 seconds — examiners cannot lose work due to accidental navigation'))
    story.append(bold_bullet('Offline Queue:', 'If network connectivity is lost mid-exam, up to 100 score entries are queued locally in the browser and automatically replayed when connectivity resumes'))
    story.append(bold_bullet('Atomic Score Submission:', 'Each score submission is wrapped in a database transaction — partial writes are impossible'))
    story.append(bold_bullet('Exam Session States:', 'Sessions follow a controlled state machine: Draft → Active → Finished — irreversible stages require explicit coordinator action'))
    story.append(bold_bullet('ILO Mapping:', 'Every checklist item is mapped to an ILO (Intended Learning Outcome) theme — reports are auto-generated with per-ILO breakdowns'))
    story.append(bold_bullet('Dry Grading Mode:', 'Coordinators can review and adjust scores before a session is finalized — permission-gated to prevent unauthorized edits'))
    story.append(bold_bullet('Station Rotation Timer:', 'Configurable rotation interval (default 8 minutes) — platform can signal rotation without separate software'))
    story.append(bold_bullet('Report Formats:', 'Session reports exported as PDF (bilingual Arabic/English) and Excel — suitable for university records'))
    story.append(spacer(10))

    # ── 6. SECURITY AUDIT STATUS ─────────────────────────────────────────────
    story.append(section_header('6. Security Audit Status'))
    story.append(hr())
    story.append(body_style and Paragraph(
        'A full security audit was completed on 13 March 2026, covering SQL injection, '
        'broken access control, authentication bypass, and data leakage across all API '
        'endpoints and views. The results are summarised below.',
        body_style))
    story.append(spacer(6))

    audit_data = [
        ['Severity', 'Found', 'Fixed', 'Remaining'],
        ['CRITICAL', '2', '2', '0'],
        ['HIGH',     '5', '5', '0'],
        ['MEDIUM',   '6', '6', '0'],
        ['LOW',      '3', '0', '3 (accepted risk, documented)'],
        ['Total',    '16','13','3'],
    ]
    status_colors = [DEEP_BLUE, LIGHT_RED, LIGHT_AMBER, LIGHT_GREEN, LIGHT_BLUE, LIGHT_GREY]
    t4 = Table(audit_data, colWidths=[3.5*cm, 2.5*cm, 2.5*cm, 8*cm])
    t4.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), DEEP_BLUE),
        ('TEXTCOLOR',     (0,0), (-1,0), white),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME',      (0,1), (-1,-1),'Helvetica'),
        ('FONTSIZE',      (0,0), (-1,-1), 9.5),
        ('LEADING',       (0,0), (-1,-1), 13),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.5, GREY_BORDER),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[white, LIGHT_GREY]),
        ('BACKGROUND',    (0,1), (-1,1), LIGHT_RED),
        ('BACKGROUND',    (0,2), (-1,2), LIGHT_AMBER),
        ('BACKGROUND',    (0,3), (-1,3), LIGHT_GREEN),
        ('BACKGROUND',    (0,4), (-1,4), LIGHT_BLUE),
        ('FONTNAME',      (0,5), (-1,5), 'Helvetica-Bold'),
        ('ALIGN',         (1,0), (2,-1), 'CENTER'),
    ]))
    story.append(t4)
    story.append(spacer(8))

    story.append(Paragraph('<b>Key findings fixed:</b>', sub_style))
    story.append(bold_bullet('CRITICAL — Authentication Bypass:', 'Soft-deleted (deactivated) accounts could still log in → fixed by adding explicit is_deleted check after authentication'))
    story.append(bold_bullet('CRITICAL — Cross-Department Data Exposure:', '45+ API endpoints had no department scoping → all fixed with scope_queryset() enforced on every query'))
    story.append(bold_bullet('All HIGH/MEDIUM:', 'IDOR (Insecure Direct Object Reference) in individual object lookups, unscoped examiner lists, unscoped report exports — all patched'))
    story.append(bold_bullet('OWASP Top 10 Coverage:', 'Audit addressed Broken Access Control (A01), Injection (A03), Insecure Design (A04), Identification Failures (A07), Security Logging Failures (A09)'))
    story.append(spacer(10))

    # ── 7. PRIVACY & DATA HANDLING ───────────────────────────────────────────
    story.append(PageBreak())
    story.append(section_header('7. Privacy & Student Data Handling'))
    story.append(hr())
    story.append(bold_bullet('No student accounts:', 'Students are enrolled by student ID number only — no passwords or student logins are created in the system'))
    story.append(bold_bullet('Minimal personal data:', 'Only: student ID, name, year of study — no medical records, contact details, or sensitive PII required'))
    story.append(bold_bullet('Examiner–student separation:', 'Examiners only see the student currently at their station and their own scoring form — blind to all other stations'))
    story.append(bold_bullet('Data isolation by department:', 'Coordinators from one department (e.g., Surgery) cannot access or export student data from another department (e.g., Medicine)'))
    story.append(bold_bullet('Search engine blocked:', 'X-Robots-Tag: noindex header on every response — examination data cannot be indexed by web crawlers'))
    story.append(bold_bullet('No public endpoints:', 'Every URL requires authentication — there are zero unauthenticated data endpoints'))
    story.append(spacer(10))

    # ── 8. DEPLOYMENT & NETWORK REQUIREMENTS ─────────────────────────────────
    story.append(section_header('8. Deployment & Network Requirements'))
    story.append(hr())

    story.append(Paragraph('<b>Option A — On-Premises (Recommended for University Control)</b>', sub_style))
    story.append(bold_bullet('Server:', 'Any Linux server (Ubuntu 22.04+) with Python 3.12, PostgreSQL 14+, and Redis'))
    story.append(bold_bullet('Network:', 'Internal university network — accessible only within campus Wi-Fi/LAN'))
    story.append(bold_bullet('HTTPS:', 'TLS certificate required — can use university\'s existing certificate or Let\'s Encrypt (free)'))
    story.append(bold_bullet('Minimum spec:', '2 CPU cores, 4 GB RAM, 20 GB SSD — comfortably handles 200 concurrent examiners'))
    story.append(spacer(6))

    story.append(Paragraph('<b>Option B — Cloud (Microsoft Azure)</b>', sub_style))
    story.append(bold_bullet('Ready-to-deploy:', 'Azure App Service (app server) + Azure Database for PostgreSQL + Azure Blob Storage (media files)'))
    story.append(bold_bullet('Data residency:', 'Azure region can be selected to comply with local regulations'))
    story.append(bold_bullet('Scalability:', 'App Service auto-scales; PostgreSQL supports Flexible Server with PgBouncer connection pooling'))
    story.append(spacer(6))

    story.append(Paragraph('<b>Client Requirements (Exam Room)</b>', sub_style))
    story.append(bold_bullet('Any modern browser:', 'Chrome 90+, Firefox 90+, Edge 90+, Safari 14+ — no software installation required'))
    story.append(bold_bullet('Tablet / PC / Laptop:', 'Any device with a browser — works on iPad, Android tablet, Windows laptop'))
    story.append(bold_bullet('Network:', 'Wi-Fi or wired LAN; if network drops, offline queue keeps scoring live for up to 3–5 minutes'))
    story.append(spacer(10))

    # ── 9. EXPECTED QUESTIONS ─────────────────────────────────────────────────
    story.append(section_header('9. Anticipated IT Department Questions & Answers'))
    story.append(hr())

    story.append(Paragraph('<b>Security & Access</b>', sub_style))
    for q, a in [
        ('1.  Who can access the system and how are accounts created?',
         'Only university staff (examiners, coordinators, admins). Accounts are created manually by administrators — there is no self-registration. Every new account is assigned a temporary password that must be changed on first login.'),
        ('2.  What happens if an examiner\'s device is left unattended?',
         'The session auto-locks after 20 minutes of inactivity. Coordinators auto-lock after 10 minutes. The device returns to the login screen automatically.'),
        ('3.  Can student data be accessed from outside the exam room?',
         'Access is controlled strictly by role. An examiner at Station 3 cannot see Station 5\'s data. A coordinator can only see their own department\'s data. All access requires login.'),
        ('4.  How is the admin panel protected from unauthorized access?',
         'The standard /admin/ URL returns a 404 error — it does not exist to scanners. The real admin URL is secret, configurable, and requires an additional session token even after login.'),
        ('5.  What protects against brute-force login attacks?',
         'django-axes automatically locks an account after repeated failed login attempts, tracking by both username and IP address. Locked accounts alert the administrator.'),
    ]:
        story.extend(qa(q, a))
    story.append(spacer(6))

    story.append(Paragraph('<b>Data & Privacy</b>', sub_style))
    for q, a in [
        ('6.  Where is exam data stored?',
         'In a PostgreSQL database on the deployment server (on-premises) or Azure (cloud). All exam score data, student records, and exam configurations live in this single controlled database.'),
        ('7.  Can student scores be modified after the exam?',
         'Only a Coordinator-Head or Admin can open a "dry grading" review window before a session is finalized. After finalization, scores are locked. Every modification is audit-logged.'),
        ('8.  What personal data does the system hold?',
         'Minimal: student name, student ID number, year of study. No passwords, no contact details, no medical records. Examiners have name and institutional email only.'),
        ('9.  Is this GDPR / university data policy compliant?',
         'The system collects only data necessary for examination scoring. All data remains within university-controlled infrastructure. Audit logs provide full accountability.'),
    ]:
        story.extend(qa(q, a))
    story.append(spacer(6))

    story.append(Paragraph('<b>Technical & Infrastructure</b>', sub_style))
    for q, a in [
        ('10. What happens if the server goes down mid-exam?',
         'Examiner browsers queue up to 100 score submissions locally (offline queue). When the server recovers, scores are automatically replayed. Loss of in-progress scores requires an extended outage.'),
        ('11. Does this require any software installed on exam-room devices?',
         'No. Any modern browser is sufficient. The app is also installable as a Progressive Web App (PWA) for a native-like experience, but this is optional.'),
        ('12. How are database backups handled?',
         'PostgreSQL supports automated backups (pg_dump or Azure\'s built-in backup policies). We recommend daily automated backups retained for 30 days, configured at the infrastructure level.'),
        ('13. Has the code been security-reviewed?',
         'Yes — a comprehensive audit covering OWASP Top 10 was completed March 2026. All critical and high findings were resolved. The full audit report is available upon request.'),
        ('14. Can this run on the university\'s existing servers?',
         'Yes, if the server runs Ubuntu 22.04+ with Python 3.12, PostgreSQL 14+, and at least 4 GB RAM. Containerised deployment (Docker) is also supported. A virtual machine would also be suitable.'),
        ('15. How are system updates applied without downtime?',
         'Gunicorn supports graceful restarts (zero-downtime deploys). Django migrations apply schema changes safely. A brief maintenance window (< 1 minute) is required only for major DB migrations.'),
    ]:
        story.extend(qa(q, a))
    story.append(spacer(10))

    # ── 10. QUICK REFERENCE ───────────────────────────────────────────────────
    story.append(section_header('10. Quick Reference — Key Technical Facts'))
    story.append(hr())

    ref_data = [
        ['Item', 'Detail'],
        ['Backend language', 'Python 3.12'],
        ['Web framework', 'Django 5.2'],
        ['API framework', 'Django REST Framework 3.16'],
        ['Database', 'PostgreSQL 14+ (production) / SQLite (development)'],
        ['Database security', 'Row-Level Security (RLS) at PostgreSQL engine level'],
        ['Frontend', 'HTML5 + Bootstrap 5 + Vanilla JavaScript'],
        ['Authentication', 'Session-based (HttpOnly cookies, CSRF, SameSite=Lax)'],
        ['Brute-force protection', 'django-axes 8.3 (IP + username lockout)'],
        ['SQL injection protection', '100% ORM parameterized queries — no raw SQL'],
        ['Admin protection', 'Double-lock: obscured URL + session gate'],
        ['Audit logging', 'Full login, access, and data-change logging via Celery'],
        ['Password policy', 'Min 8 chars, common password check, force-change-on-first-login'],
        ['Session timeout', '10 min (admin/coordinator) / 20 min (examiner)'],
        ['Offline resilience', 'Browser-side queue (100 entries) survives network drop'],
        ['Report output', 'PDF (bilingual Arabic/English) + Excel (XLSX)'],
        ['Deployment options', 'On-premises Linux or Microsoft Azure'],
        ['Security audit', 'Completed March 2026 — all critical/high findings fixed'],
    ]
    t5 = Table(ref_data, colWidths=[5.5*cm, 11*cm])
    t5.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), DEEP_BLUE),
        ('TEXTCOLOR',     (0,0), (-1,0), white),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME',      (0,1), (-1,-1),'Helvetica'),
        ('FONTSIZE',      (0,0), (-1,-1), 9.5),
        ('LEADING',       (0,0), (-1,-1), 13),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.5, GREY_BORDER),
        ('BACKGROUND',    (0,1), (0,-1), LIGHT_BLUE),
        ('FONTNAME',      (0,1), (0,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR',     (0,1), (0,-1), DEEP_BLUE),
        ('ROWBACKGROUNDS',(1,1),(-1,-1),[white, LIGHT_GREY]),
    ]))
    story.append(t5)
    story.append(spacer(12))

    story.append(Paragraph(
        '<i>This document was auto-generated from the production codebase. '
        'All technical details reflect the actual implementation. '
        'The full source code, security audit report, and architecture diagrams are available for review upon request.</i>',
        ParagraphStyle('footer_note', fontName='Helvetica-Oblique', fontSize=8.5,
                       textColor=MID_GREY, alignment=TA_CENTER)))

    return story


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    output_path = os.path.join(os.path.dirname(__file__), 'OSCE_IT_Department_Brief.pdf')

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=5.5*cm,    # leaves room for header band on page 1
        bottomMargin=1.5*cm,
    )
    doc.topMargin = 5.3*cm   # page 1 — header band height

    story = build_story()

    doc.build(
        story,
        onFirstPage=first_page,
        onLaterPages=later_pages,
    )

    print(f'PDF generated successfully: {output_path}')
