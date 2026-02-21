# ADR-0009: Celery Background Task Architecture with Redis Broker

**Status:** Accepted
**Date:** 2026-02-21
**Authors:** Platform Engineering Team

## Context

Several platform operations are too long-running to execute synchronously within API request handlers: sending email notifications, generating compliance reports, processing bulk imports, and running data retention cleanup. Executing these inline causes request timeouts, degrades user experience, and blocks API worker threads from serving other requests.

## Decision

We adopt Celery as the distributed task queue with Redis as the message broker. Tasks are organized into 5 named queues: `default` (general tasks), `email` (delivery), `reports` (generation), `notifications` (real-time alerts), and `cleanup` (data retention). Celery Beat runs as a single-instance scheduler for periodic tasks such as token blacklist cleanup and report generation. Each queue can be scaled independently by running dedicated worker processes.

## Consequences

### Positive
- API responses return immediately, with background processing handled asynchronously
- Queue isolation prevents slow report generation from blocking email delivery
- Horizontal scalability — workers can be added per queue based on load
- Celery Beat provides reliable periodic task scheduling without cron dependencies

### Negative
- Introduces operational complexity — Redis and Celery workers must be deployed and monitored
- Task failures require retry logic, dead-letter handling, and alerting
- Celery Beat must run as a single instance to prevent duplicate scheduled task execution

### Neutral
- Redis serves dual purpose as both Celery broker and application cache
- Task results are not stored (fire-and-forget pattern) unless explicitly configured
- Worker health is monitored via the `/healthz` endpoint's Celery worker check
