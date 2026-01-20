# Quality Governance Platform - Administrator Guide

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [User Management](#user-management)
4. [Configuration](#configuration)
5. [Security](#security)
6. [Monitoring & Logging](#monitoring--logging)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)
9. [API Reference](#api-reference)

---

## Overview

This guide is intended for system administrators responsible for managing the Quality Governance Platform (QGP).

### System Requirements

**Backend:**
- Python 3.11+
- PostgreSQL 14+
- Redis 7+ (optional, for caching)

**Frontend:**
- Node.js 18+
- Modern browser (Chrome, Firefox, Safari, Edge)

**Infrastructure:**
- Azure App Service (backend)
- Azure Static Web Apps (frontend)
- Azure Database for PostgreSQL
- Azure Key Vault (secrets)
- Azure Application Insights (monitoring)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Azure Front Door                          │
│                    (CDN + WAF + SSL)                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         │                                  │
         ▼                                  ▼
┌─────────────────────┐          ┌─────────────────────┐
│   Azure Static      │          │   Azure App         │
│   Web Apps          │          │   Service           │
│   (Frontend)        │          │   (Backend API)     │
└─────────────────────┘          └──────────┬──────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
         ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
         │   PostgreSQL     │    │   Redis Cache    │    │   Azure Blob     │
         │   Database       │    │   (Optional)     │    │   Storage        │
         └──────────────────┘    └──────────────────┘    └──────────────────┘
```

### Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| Frontend | User interface | React + Vite + TypeScript |
| Backend API | Business logic | FastAPI + Python |
| Database | Data storage | PostgreSQL |
| Cache | Performance | Redis |
| File Storage | Documents | Azure Blob |
| Auth | Authentication | Azure AD / JWT |
| Monitoring | Observability | Application Insights |

---

## User Management

### Access Levels

| Role | Permissions |
|------|-------------|
| **Super Admin** | Full system access, user management, configuration |
| **Admin** | Module management, user creation, reporting |
| **Manager** | Team oversight, approval workflows, analytics |
| **Auditor** | Audit execution, findings, read-only reports |
| **User** | Create/edit own records, view assigned items |
| **Portal User** | Employee portal only, self-service reporting |

### Creating Users

**Via Admin UI:**
1. Navigate to Settings → User Management
2. Click "Add User"
3. Enter email, name, role
4. Set initial password or send invite
5. Assign to departments/teams

**Via API:**
```bash
POST /api/users
{
  "email": "user@plantexpand.com",
  "name": "John Doe",
  "role": "user",
  "department": "Operations"
}
```

### SSO Configuration

**Azure AD Setup:**
1. Register application in Azure AD
2. Configure redirect URIs:
   - `https://qgp.plantexpand.com/auth/callback`
   - `https://qgp.plantexpand.com/portal/auth/callback`
3. Set required permissions:
   - `User.Read`
   - `openid`
   - `profile`
   - `email`
4. Add client credentials to Key Vault

**Environment Variables:**
```
AZURE_AD_CLIENT_ID=your-client-id
AZURE_AD_CLIENT_SECRET=your-client-secret
AZURE_AD_TENANT_ID=your-tenant-id
```

### Bulk User Import

```bash
# CSV format: email,name,role,department
python scripts/import_users.py --file users.csv --send-invites
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Optional |
| `SECRET_KEY` | JWT signing key | Required |
| `AZURE_AD_*` | Azure AD configuration | For SSO |
| `OPENAI_API_KEY` | OpenAI API key | For AI features |
| `APPINSIGHTS_*` | Application Insights | For monitoring |

### Feature Flags

```python
# config/features.py
FEATURES = {
    "ai_analysis": True,
    "offline_mode": True,
    "push_notifications": True,
    "sms_alerts": False,
    "advanced_analytics": True,
}
```

### Email Configuration

```python
# For SMTP
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=notifications@plantexpand.com
SMTP_PASSWORD=****

# For SendGrid
SENDGRID_API_KEY=****
```

### Notification Templates

Templates are stored in `templates/notifications/`:
- `incident_created.html`
- `action_assigned.html`
- `action_due_reminder.html`
- `audit_scheduled.html`

---

## Security

### Authentication

**JWT Configuration:**
- Algorithm: HS256
- Expiry: 24 hours
- Refresh: 7 days

**Rate Limiting:**
- Login: 10 requests/minute
- API: 60 requests/minute (authenticated)
- Portal: 30 requests/minute

### RBAC (Role-Based Access Control)

Permissions are defined in `config/permissions.py`:

```python
PERMISSIONS = {
    "incidents": {
        "create": ["admin", "manager", "user"],
        "read": ["admin", "manager", "user", "auditor"],
        "update": ["admin", "manager"],
        "delete": ["admin"],
    },
    # ... other modules
}
```

### Audit Logging

All actions are logged to `audit_events` table:
- User ID
- Action type
- Resource affected
- Timestamp
- IP address
- Request details

### Security Headers

```python
# Configured in middleware
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
Content-Security-Policy: default-src 'self'
```

### Data Encryption

- **At rest:** Azure Storage encryption (AES-256)
- **In transit:** TLS 1.3
- **Sensitive fields:** Application-level encryption for PII

---

## Monitoring & Logging

### Application Insights

**Configured metrics:**
- Request duration
- Failure rate
- Dependency calls
- Custom events

**Custom events tracked:**
- User logins
- Report submissions
- Audit completions
- File uploads

### Log Levels

```python
# Production
LOG_LEVEL=INFO

# Development
LOG_LEVEL=DEBUG
```

### Health Checks

```bash
# API health
GET /health

# Detailed status
GET /api/health/detailed

# Response
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}
```

### Alerting

Configure alerts in Azure Monitor for:
- 5xx error rate > 1%
- Response time P95 > 2s
- Database connection failures
- Memory/CPU thresholds

---

## Backup & Recovery

### Database Backups

**Automated (Azure):**
- Point-in-time restore: 7 days
- Geo-redundant backups: enabled

**Manual:**
```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

### File Storage Backups

Azure Blob Storage with:
- Soft delete: 14 days
- Versioning: enabled
- Geo-redundancy: enabled

### Disaster Recovery

**RTO:** 4 hours
**RPO:** 1 hour

**Procedure:**
1. Verify backups are available
2. Provision new infrastructure (via Terraform)
3. Restore database from backup
4. Restore file storage
5. Update DNS
6. Verify functionality

---

## Troubleshooting

### Common Issues

**Database Connection Errors**
```bash
# Check connection
psql $DATABASE_URL -c "SELECT 1"

# Check pool exhaustion
SELECT count(*) FROM pg_stat_activity;
```

**Redis Connection Issues**
```bash
# Test connection
redis-cli -u $REDIS_URL ping
```

**High Memory Usage**
- Check for memory leaks in API logs
- Review large file uploads
- Check cache size

**Slow API Responses**
- Check database query performance
- Review Application Insights traces
- Check external dependencies

### Log Analysis

```bash
# View recent errors
az webapp log tail --name qgp-api --resource-group qgp-prod

# Query Application Insights
az monitor app-insights query \
  --app qgp-insights \
  --analytics-query "exceptions | take 100"
```

### Database Maintenance

```sql
-- Vacuum and analyze
VACUUM ANALYZE;

-- Check table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

-- Check long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';
```

---

## API Reference

### Authentication

```bash
# Login
POST /api/auth/login
Content-Type: application/json

{"username": "user@example.com", "password": "****"}

# Response
{"access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400}
```

### Common Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/incidents` | GET/POST | List/create incidents |
| `/api/incidents/{id}` | GET/PUT/DELETE | Incident operations |
| `/api/audits/runs` | GET/POST | Audit runs |
| `/api/audits/templates` | GET/POST | Audit templates |
| `/api/users` | GET/POST | User management |
| `/api/analytics/summary` | GET | Analytics data |

### Pagination

```bash
GET /api/incidents?page=1&per_page=20&sort=created_at&order=desc
```

### Filtering

```bash
GET /api/incidents?status=open&severity=high&date_from=2026-01-01
```

### Error Responses

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [
      {"field": "email", "message": "Invalid email format"}
    ]
  }
}
```

---

## Support

**Technical Support:** support@plantexpand.com
**Emergency:** +44 (0)1XXX XXXXXX

---

*Document Version: 1.0*
*Last Updated: January 2026*
