# Security policy — Quality Governance Platform

This policy describes how we receive, assess, and remediate security issues for the Quality Governance Platform (QGP).

## Scope

This policy applies to security findings affecting **all backend APIs**, the **frontend** (web client), and **infrastructure** used to build, deploy, and operate QGP (including cloud resources, CI/CD, and supporting services).

Out of scope: physical site security of customer premises and third-party services outside our control (report those to the respective vendor using their disclosure programmes).

## Security contact

Report security vulnerabilities to:

**security@quality-governance.platform**

Use this address for confidential reports only. For general product or support questions, use your normal support channel.

## Responsible disclosure

We support **responsible disclosure**:

1. **Do not** publicly disclose a vulnerability until we have had a reasonable time to investigate and deploy a fix.
2. **Do** provide enough detail to reproduce the issue (affected component, steps, impact, and, if possible, a minimal proof of concept).
3. **Do not** access, modify, or exfiltrate user data beyond what is necessary to demonstrate the issue; avoid denial-of-service testing against production without prior agreement.
4. We will **acknowledge** receipt of your report and work with you on severity and timeline.
5. With your consent, we may **credit** researchers in release notes or advisories.

We do not operate a public bug bounty programme; this policy does not waive applicable laws. Act in good faith and in line with our scope above.

## Vulnerability disclosure process

| Step | Action |
| --- | --- |
| 1 | Reporter sends details to **security@quality-governance.platform** (encrypted mail encouraged for sensitive content). |
| 2 | Security owners triage: confirm validity, scope, and severity (aligned with the patch SLA severities below). |
| 3 | We develop and test a fix; coordinate release and communication with affected parties where required. |
| 4 | We notify the reporter when a fix is deployed or a mitigation is in place, subject to coordinated disclosure agreements. |
| 5 | We track remediation and, where appropriate, update internal runbooks and dependency baselines. |

If you believe an issue is being actively exploited, state that clearly in the subject line so we can prioritise.

## Patch SLA (target response and remediation)

These are **targets** from time of confirmed valid report; complexity, dependencies, or third-party fixes may require adjustment. We will communicate if timelines slip.

| Severity | Definition (indicative) | Target remediation |
| --- | --- | --- |
| **Critical** | Remote code execution, auth bypass, mass data breach, complete confidentiality or integrity loss in production | **24 hours** |
| **High** | Significant privilege escalation, sensitive data exposure, severe availability impact | **7 days** |
| **Medium** | Limited impact bugs, hardening gaps, non-default misconfigurations with real risk | **30 days** |
| **Low** | Minor issues, defence-in-depth improvements, informational findings | **90 days** |

Severity is assessed by impact and exploitability in our environment, not only CVSS in isolation.

## Review

Review this policy **at least annually** or after major architecture or hosting changes.

**Last updated:** 2026-04-03
