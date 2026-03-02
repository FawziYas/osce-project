# Azure Deployment Guide — OSCE Exam System

**Project:** Django OSCE Exam System  
**Target:** 1000 concurrent examiners, < 200ms response time  
**Budget:** $100/month university Azure credit  
**Last Updated:** March 2, 2026

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Azure Account Setup](#2-azure-account-setup)
3. [Create Resource Group](#3-create-resource-group)
4. [Create PostgreSQL Database](#4-create-postgresql-database)
5. [Create Azure Cache for Redis](#5-create-azure-cache-for-redis)
6. [Prepare Your Code for Azure](#6-prepare-your-code-for-azure)
7. [Create Azure App Service](#7-create-azure-app-service)
8. [Configure Environment Variables](#8-configure-environment-variables)
9. [Deploy Your Code](#9-deploy-your-code)
10. [Run Migrations & Create Superuser](#10-run-migrations--create-superuser)
11. [Configure Custom Domain & SSL](#11-configure-custom-domain--ssl)
12. [Enable Autoscaling](#12-enable-autoscaling)
13. [Enable Monitoring](#13-enable-monitoring)
14. [Post-Deployment Verification](#14-post-deployment-verification)
15. [Cost Monitoring](#15-cost-monitoring)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Prerequisites

Before starting, make sure you have:

- [ ] **Azure account** with $100/month university credit activated
- [ ] **Azure CLI** installed on your machine
- [ ] **Git** installed and project pushed to a GitHub repository
- [ ] **Python 3.11+** installed locally
- [ ] Project runs locally with `python manage.py runserver`

### Install Azure CLI

```powershell
# Windows — run in PowerShell as Administrator
winget install Microsoft.AzureCLI
```

After restart, verify:
```powershell
az --version
```

### Login to Azure

```powershell
az login
```

This opens your browser — sign in with your university Azure account.

### Verify your subscription

```powershell
az account show --query "{name:name, id:id, state:state}" -o table
```

You should see your university subscription with the $100 credit.

---

## 2. Azure Account Setup

### Activate Azure for Students

If you haven't already:

1. Go to [azure.microsoft.com/en-us/free/students](https://azure.microsoft.com/en-us/free/students/)
2. Sign in with your **university email** (`.edu` or university domain)
3. Verify your student status
4. You get **$100 credit/month** — no credit card required

### Set Default Subscription

```powershell
# List all subscriptions
az account list -o table

# Set your student subscription as default
az account set --subscription "Azure for Students"
```

---

## 3. Create Resource Group

A resource group is a container for all your Azure resources. Put everything in one group for easy management.

```powershell
# Create resource group — choose a region close to your users
# Common choices: "eastus", "westeurope", "uaenorth" (Middle East), "southeastasia"
az group create --name osce-production --location eastus
```

> **Tip:** If your university is in the Middle East, use `uaenorth` or `westeurope` for lower latency.

---

## 4. Create PostgreSQL Database

### 4.1 Create the Server

```powershell
az postgres flexible-server create `
  --resource-group osce-production `
  --name osce-db-server `
  --location eastus `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32 `
  --version 16 `
  --admin-user osceadmin `
  --admin-password "YourStrongPassword123!" `
  --yes
```

| Parameter | Value | Why |
|-----------|-------|-----|
| `Standard_B1ms` | 1 vCPU, 2GB RAM | Handles 1000 users with PgBouncer — costs ~$25/mo |
| `--storage-size 32` | 32 GB | Plenty for exam data — can grow later |
| `--version 16` | PostgreSQL 16 | Latest stable with best performance |

> ⚠️ **SAVE THE PASSWORD!** You'll need it later. Use a strong password (16+ chars, mixed case, numbers, symbols).

### 4.2 Create the Database

```powershell
az postgres flexible-server db create `
  --resource-group osce-production `
  --server-name osce-db-server `
  --database-name osce_production
```

### 4.3 Enable PgBouncer (Built-in Connection Pooling)

This is **critical** for 1000 users — without it, PostgreSQL will run out of connections.

```powershell
az postgres flexible-server parameter set `
  --resource-group osce-production `
  --server-name osce-db-server `
  --name pgbouncer.enabled `
  --value true

az postgres flexible-server parameter set `
  --resource-group osce-production `
  --server-name osce-db-server `
  --name pgbouncer.default_pool_size `
  --value 50
```

### 4.4 Allow Azure Services to Connect

```powershell
# Allow connections from Azure services (App Service → PostgreSQL)
az postgres flexible-server firewall-rule create `
  --resource-group osce-production `
  --name osce-db-server `
  --rule-name AllowAzureServices `
  --start-ip-address 0.0.0.0 `
  --end-ip-address 0.0.0.0
```

### 4.5 Verify Connection Locally (Optional)

```powershell
# Install psql client if needed
# Then test:
psql "host=osce-db-server.postgres.database.azure.com port=6432 dbname=osce_production user=osceadmin password=YourStrongPassword123! sslmode=require"
```

> **Note:** Port `6432` is PgBouncer. Port `5432` is direct PostgreSQL. Use `6432` in production.

---

## 5. Create Azure Cache for Redis

```powershell
az redis create `
  --resource-group osce-production `
  --name osce-redis-cache `
  --location eastus `
  --sku Basic `
  --vm-size C0 `
  --redis-version 6
```

> ⏳ This takes 10-15 minutes to provision. Continue with step 6 while waiting.

### Get Redis Connection String

```powershell
# Get the hostname
az redis show --resource-group osce-production --name osce-redis-cache --query hostName -o tsv

# Get the primary key
az redis list-keys --resource-group osce-production --name osce-redis-cache --query primaryKey -o tsv
```

The Redis URL format will be:
```
rediss://:YOUR_PRIMARY_KEY@osce-redis-cache.redis.cache.windows.net:6380/0
```

> **Note:** Azure Redis uses `rediss://` (with double-s) for SSL on port `6380`.

---

## 6. Prepare Your Code for Azure

### 6.1 Update `requirements.txt`

Make sure these packages are in your `requirements.txt`:

```
Django>=5.0,<6.0
django-environ>=0.11.0
django-axes>=6.4.0
whitenoise>=6.5
gunicorn>=21.0
psycopg2-binary>=2.9
django-redis>=5.4.0
redis>=5.0
sentry-sdk>=2.0

# Excel, PDF, Arabic support
openpyxl>=3.1.0
reportlab>=4.0
arabic-reshaper>=3.0.0
python-bidi>=0.4.2
```

### 6.2 Update `production.py` Settings

Update `osce_project/settings/production.py`:

```python
"""
Production settings for Azure deployment.
"""
import os
from .base import *

DEBUG = False

SECRET_KEY = env('SECRET_KEY')  # REQUIRED in production
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# ============================================================
# DATABASE — Azure PostgreSQL Flexible Server with PgBouncer
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', default='osce_production'),
        'USER': env('DB_USER', default='osceadmin'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),                    # osce-db-server.postgres.database.azure.com
        'PORT': env('DB_PORT', default='6432'),    # 6432 for PgBouncer, 5432 for direct
        'CONN_MAX_AGE': 600,                       # Reuse connections for 10 min
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'sslmode': 'require',                  # Azure requires SSL
            'connect_timeout': 10,
        },
    }
}

# ============================================================
# REDIS CACHE — Azure Cache for Redis
# ============================================================
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='rediss://localhost:6380/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# Use Redis for sessions (faster than DB sessions)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# ============================================================
# STATIC FILES — WhiteNoise
# ============================================================
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ============================================================
# SECURITY
# ============================================================
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

# ============================================================
# SENTRY ERROR MONITORING (Optional but recommended)
# ============================================================
SENTRY_DSN = env('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,       # 10% of requests for performance
        profiles_sample_rate=0.1,
    )

# ============================================================
# PASSWORD VALIDATION — Stricter in production
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================================
# LOGGING — Azure App Service captures stdout
# ============================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'azure': {
            'format': '[{asctime}] {levelname} {name} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'azure',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'osce.audit': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'osce.auth': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### 6.3 Add WhiteNoise Middleware

In `osce_project/settings/base.py`, add WhiteNoise right after `SecurityMiddleware`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',        # ← Add this line
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... rest of middleware ...
]
```

### 6.4 Create Startup Script

Create a file called `startup.sh` in your project root:

```bash
#!/bin/bash

# Azure App Service startup script for Django OSCE

# Run migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn
gunicorn osce_project.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 8 \
  --threads 4 \
  --worker-class gthread \
  --timeout 120 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --access-logfile - \
  --error-logfile -
```

### 6.5 Create `.deployment` File (Optional — for GitHub deployment)

Create `.deployment` in project root:

```ini
[config]
SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

### 6.6 Commit and Push

```powershell
git add .
git commit -m "Configure for Azure production deployment"
git push origin main
```

---

## 7. Create Azure App Service

### 7.1 Create App Service Plan

```powershell
az appservice plan create `
  --resource-group osce-production `
  --name osce-app-plan `
  --location eastus `
  --sku B2 `
  --is-linux
```

| SKU | vCPU | RAM | Cost | 1000 Users |
|-----|------|-----|------|------------|
| B1 | 1 | 1.75 GB | ~$13/mo | ❌ Too small |
| **B2** | **2** | **3.5 GB** | **~$54/mo** | **✅ Recommended** |
| B3 | 4 | 7 GB | ~$108/mo | ✅ Overkill unless heavy reports |

### 7.2 Create the Web App

```powershell
az webapp create `
  --resource-group osce-production `
  --plan osce-app-plan `
  --name osce-exam-app `
  --runtime "PYTHON:3.11" `
  --startup-file "startup.sh"
```

> **Note:** The app name must be globally unique. If `osce-exam-app` is taken, use something like `osce-exam-youruni`.

Your app will be available at: `https://osce-exam-app.azurewebsites.net`

### 7.3 Set Django Settings Module

```powershell
az webapp config appsettings set `
  --resource-group osce-production `
  --name osce-exam-app `
  --settings DJANGO_SETTINGS_MODULE=osce_project.settings.production
```

---

## 8. Configure Environment Variables

### 8.1 Generate a Secret Key

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output — you'll use it below.

### 8.2 Set All Environment Variables

```powershell
az webapp config appsettings set `
  --resource-group osce-production `
  --name osce-exam-app `
  --settings `
    DJANGO_SETTINGS_MODULE=osce_project.settings.production `
    SECRET_KEY="paste-your-generated-secret-key-here" `
    DEBUG=False `
    ALLOWED_HOSTS="osce-exam-app.azurewebsites.net,yourdomain.com" `
    DB_NAME=osce_production `
    DB_USER=osceadmin `
    DB_PASSWORD="YourStrongPassword123!" `
    DB_HOST=osce-db-server.postgres.database.azure.com `
    DB_PORT=6432 `
    REDIS_URL="rediss://:YOUR_REDIS_KEY@osce-redis-cache.redis.cache.windows.net:6380/0" `
    SECRET_ADMIN_URL="your-secret-admin-path" `
    DEFAULT_USER_PASSWORD="ChangeOnFirstLogin123!"
```

> ⚠️ **Replace all placeholder values** with your actual passwords and keys!

### 8.3 Verify Settings

```powershell
az webapp config appsettings list `
  --resource-group osce-production `
  --name osce-exam-app `
  -o table
```

---

## 9. Deploy Your Code

### Option A: Deploy from Local (Fastest for First Deploy)

```powershell
# Navigate to your project directory
cd C:\Users\M7md\Desktop\dev\osce_project

# Deploy using ZIP deploy
az webapp up `
  --resource-group osce-production `
  --name osce-exam-app `
  --runtime "PYTHON:3.11"
```

### Option B: Deploy from GitHub (Recommended for Ongoing)

```powershell
# Connect to GitHub for automatic deployments
az webapp deployment source config `
  --resource-group osce-production `
  --name osce-exam-app `
  --repo-url "https://github.com/YOUR_USERNAME/osce-project" `
  --branch main `
  --manual-integration
```

Or use **GitHub Actions** (best for CI/CD):

1. Go to Azure Portal → your App Service → **Deployment Center**
2. Select **GitHub** as source
3. Select your repository and branch
4. Azure auto-generates a GitHub Actions workflow file
5. Every push to `main` auto-deploys

### Option C: Deploy via VS Code (Easiest)

1. Install the **Azure App Service** extension in VS Code
2. Sign in to Azure in VS Code
3. Right-click your App Service → **Deploy to Web App**
4. Select your project folder

---

## 10. Run Migrations & Create Superuser

### 10.1 Open SSH to Your App

```powershell
az webapp ssh --resource-group osce-production --name osce-exam-app
```

Or in Azure Portal: App Service → **SSH** (under Development Tools)

### 10.2 Run Migrations

```bash
# Inside the SSH session:
cd /home/site/wwwroot
python manage.py migrate --noinput
```

### 10.3 Create Superuser

```bash
python manage.py createsuperuser
```

Enter your admin username, email, and password when prompted.

### 10.4 Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 10.5 Verify Deployment Check

```bash
python manage.py check --deploy
```

Fix any warnings that appear.

---

## 11. Configure Custom Domain & SSL

### 11.1 Add Custom Domain (If You Have One)

```powershell
# Add your domain
az webapp config hostname add `
  --resource-group osce-production `
  --webapp-name osce-exam-app `
  --hostname yourdomain.com
```

Then add a **CNAME record** in your DNS provider:
- **Type:** CNAME
- **Name:** @ (or www)
- **Value:** `osce-exam-app.azurewebsites.net`

### 11.2 Get Free SSL Certificate

```powershell
# Azure provides free managed certificates
az webapp config ssl create `
  --resource-group osce-production `
  --name osce-exam-app `
  --hostname yourdomain.com
```

Or in Azure Portal:
1. App Service → **TLS/SSL settings** → **Private Key Certificates**
2. Click **Create App Service Managed Certificate**
3. Select your domain → Create
4. Go to **Custom domains** → Add binding → select the certificate

> **Without a custom domain:** Your app already has SSL at `https://osce-exam-app.azurewebsites.net` — no extra setup needed.

---

## 12. Enable Autoscaling

Autoscaling adds more instances during exam time and scales down when idle.

### 12.1 Configure Autoscale Rules

In Azure Portal:
1. Go to App Service → **Scale out (App Service plan)**
2. Click **Custom autoscale**
3. Configure:
   - **Minimum instances:** 1
   - **Maximum instances:** 3
   - **Default instances:** 1

4. Add scale-out rule:
   - **Metric:** CPU Percentage
   - **Threshold:** > 70%
   - **Action:** Increase count by 1
   - **Cool down:** 5 minutes

5. Add scale-in rule:
   - **Metric:** CPU Percentage
   - **Threshold:** < 30%
   - **Action:** Decrease count by 1
   - **Cool down:** 10 minutes

Or via CLI:

```powershell
az monitor autoscale create `
  --resource-group osce-production `
  --resource osce-app-plan `
  --resource-type Microsoft.Web/serverfarms `
  --name osce-autoscale `
  --min-count 1 `
  --max-count 3 `
  --count 1

az monitor autoscale rule create `
  --resource-group osce-production `
  --autoscale-name osce-autoscale `
  --condition "CpuPercentage > 70 avg 5m" `
  --scale out 1

az monitor autoscale rule create `
  --resource-group osce-production `
  --autoscale-name osce-autoscale `
  --condition "CpuPercentage < 30 avg 10m" `
  --scale in 1
```

### 12.2 Manual Scale for Exam Day

If you know an exam is coming, pre-scale to 2 or 3 instances:

```powershell
# Scale to 2 instances before exam starts
az appservice plan update `
  --resource-group osce-production `
  --name osce-app-plan `
  --number-of-workers 2

# Scale back to 1 after exam ends
az appservice plan update `
  --resource-group osce-production `
  --name osce-app-plan `
  --number-of-workers 1
```

---

## 13. Enable Monitoring

### 13.1 Enable Application Insights (Free Tier)

```powershell
# Create Application Insights
az monitor app-insights component create `
  --resource-group osce-production `
  --app osce-insights `
  --location eastus `
  --application-type web

# Get the instrumentation key
az monitor app-insights component show `
  --resource-group osce-production `
  --app osce-insights `
  --query instrumentationKey -o tsv
```

Add to environment variables:
```powershell
az webapp config appsettings set `
  --resource-group osce-production `
  --name osce-exam-app `
  --settings APPINSIGHTS_INSTRUMENTATIONKEY="your-key-here"
```

### 13.2 Enable Diagnostic Logs

```powershell
az webapp log config `
  --resource-group osce-production `
  --name osce-exam-app `
  --application-logging filesystem `
  --level information `
  --web-server-logging filesystem
```

### 13.3 View Live Logs

```powershell
az webapp log tail `
  --resource-group osce-production `
  --name osce-exam-app
```

### 13.4 Set Up Alerts

In Azure Portal:
1. App Service → **Alerts** → **Create alert rule**
2. Add conditions:
   - **HTTP Server Errors** > 10 in 5 minutes → Email alert
   - **Response Time** > 2 seconds avg → Email alert
   - **CPU Percentage** > 90% for 10 minutes → Email alert

---

## 14. Post-Deployment Verification

### Checklist — Run After Every Deployment

- [ ] Open `https://osce-exam-app.azurewebsites.net` — loads login page
- [ ] Login as superuser → dashboard loads
- [ ] Create a test exam with stations and checklist items
- [ ] Assign test examiner and test session
- [ ] Open examiner interface on a phone/tablet
- [ ] Submit a test score — verify it saves
- [ ] Generate a report — verify PDF/XLSX download
- [ ] Check `python manage.py check --deploy` → 0 warnings
- [ ] Verify HTTPS redirect works (http:// → https://)
- [ ] Check Azure Monitor for errors

### Run Django Deploy Check

```powershell
# Via SSH:
az webapp ssh --resource-group osce-production --name osce-exam-app

# Inside SSH:
python manage.py check --deploy
```

---

## 15. Cost Monitoring

### Track Your Spending

```powershell
# See current month costs
az consumption usage list `
  --query "[?contains(instanceName, 'osce')].{Name:instanceName, Cost:pretaxCost, Currency:currency}" `
  -o table
```

Or in Azure Portal: **Cost Management + Billing** → **Cost Analysis**

### Expected Monthly Costs

| Service | SKU | Estimated Cost |
|---------|-----|---------------|
| App Service Plan | B2 Linux | ~$54 |
| PostgreSQL Flexible Server | B1ms (1 vCPU, 2GB) | ~$25 |
| Azure Cache for Redis | Basic C0 | ~$13 |
| Application Insights | Free tier (5GB/mo) | $0 |
| Managed SSL Certificate | Free | $0 |
| **Total** | | **~$92/month** |
| **University Credit** | | **$100/month** |
| **Remaining** | | **~$8 buffer** |

### Set Budget Alert

```powershell
# Get notified when spending hits $80 (80% of budget)
az consumption budget create `
  --budget-name osce-budget `
  --amount 100 `
  --category Cost `
  --time-grain Monthly `
  --start-date 2026-03-01 `
  --end-date 2027-03-01
```

Or in Azure Portal: **Cost Management** → **Budgets** → **Add**
- Amount: $100
- Alert at: 80% ($80)
- Email notification to your email

---

## 16. Troubleshooting

### App Won't Start

```powershell
# Check logs
az webapp log tail --resource-group osce-production --name osce-exam-app

# Check deployment logs
az webapp log download --resource-group osce-production --name osce-exam-app

# Restart the app
az webapp restart --resource-group osce-production --name osce-exam-app
```

### Database Connection Failed

1. Verify firewall rule allows Azure services:
   ```powershell
   az postgres flexible-server firewall-rule list `
     --resource-group osce-production `
     --name osce-db-server -o table
   ```

2. Verify connection string in environment variables:
   ```powershell
   az webapp config appsettings list `
     --resource-group osce-production `
     --name osce-exam-app `
     --query "[?name=='DB_HOST']" -o table
   ```

3. Test connection from SSH:
   ```bash
   python -c "import psycopg2; conn = psycopg2.connect(host='osce-db-server.postgres.database.azure.com', port=6432, dbname='osce_production', user='osceadmin', password='YourPassword', sslmode='require'); print('OK'); conn.close()"
   ```

### Redis Connection Failed

1. Verify Redis is provisioned:
   ```powershell
   az redis show --resource-group osce-production --name osce-redis-cache --query provisioningState -o tsv
   ```

2. Verify `REDIS_URL` is correct in environment variables
3. Make sure you're using `rediss://` (with double-s) and port `6380`

### Static Files Not Loading

```bash
# SSH into app:
python manage.py collectstatic --noinput

# Verify WhiteNoise is in MIDDLEWARE (after SecurityMiddleware)
python -c "from django.conf import settings; print('whitenoise' in str(settings.MIDDLEWARE))"
```

### Slow Performance

1. Check App Service metrics in Azure Portal → **Metrics**
   - CPU > 80%? → Scale up to B3 or scale out to 2 instances
   - Memory > 80%? → Check for memory leaks, restart app

2. Check PostgreSQL metrics:
   ```powershell
   az monitor metrics list `
     --resource osce-db-server `
     --resource-group osce-production `
     --resource-type Microsoft.DBforPostgreSQL/flexibleServers `
     --metric cpu_percent,active_connections `
     --interval PT5M -o table
   ```

3. Enable PgBouncer if not already enabled (Step 4.3)

### Common Azure CLI Commands Reference

```powershell
# Restart app
az webapp restart -g osce-production -n osce-exam-app

# View live logs
az webapp log tail -g osce-production -n osce-exam-app

# SSH into container
az webapp ssh -g osce-production -n osce-exam-app

# Stop app (saves money when not in use)
az webapp stop -g osce-production -n osce-exam-app

# Start app
az webapp start -g osce-production -n osce-exam-app

# View environment variables
az webapp config appsettings list -g osce-production -n osce-exam-app -o table

# Scale up (change plan size)
az appservice plan update -g osce-production -n osce-app-plan --sku B3

# Scale out (add instances)
az appservice plan update -g osce-production -n osce-app-plan --number-of-workers 2

# View PostgreSQL status
az postgres flexible-server show -g osce-production -n osce-db-server -o table

# Database backup (automatic daily backups are enabled by default)
# Manual backup:
az postgres flexible-server backup create -g osce-production -n osce-db-server --backup-name manual-backup-01
```

---

## Quick Reference — Exam Day Checklist

### 1 Hour Before Exam

- [ ] Pre-scale to 2 instances:
  ```powershell
  az appservice plan update -g osce-production -n osce-app-plan --number-of-workers 2
  ```
- [ ] Verify app is running: open `https://osce-exam-app.azurewebsites.net`
- [ ] Open Azure Portal → App Service → **Metrics** → watch CPU and response time
- [ ] Open log stream:
  ```powershell
  az webapp log tail -g osce-production -n osce-exam-app
  ```

### During Exam

- [ ] Monitor Azure Portal metrics dashboard
- [ ] Watch for error alerts in email
- [ ] If CPU > 85%, scale to 3 instances:
  ```powershell
  az appservice plan update -g osce-production -n osce-app-plan --number-of-workers 3
  ```

### After Exam

- [ ] Scale back to 1 instance:
  ```powershell
  az appservice plan update -g osce-production -n osce-app-plan --number-of-workers 1
  ```
- [ ] Review error logs in Azure Portal
- [ ] Verify all scores were saved correctly

---

## Cleanup — Delete All Resources (if needed)

> ⚠️ **This deletes EVERYTHING — database, app, cache. Make a backup first!**

```powershell
# Backup database before deleting
az postgres flexible-server backup create -g osce-production -n osce-db-server --backup-name final-backup

# Delete entire resource group and all resources
az group delete --name osce-production --yes --no-wait
```

---

> **Next Steps:** After deploying, run through the [Post-Deployment Verification](#14-post-deployment-verification) checklist, then do a dry run with 5-10 examiners before the real exam.
