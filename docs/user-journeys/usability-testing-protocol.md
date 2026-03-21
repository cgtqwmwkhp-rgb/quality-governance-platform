# Usability testing protocol — Quality Governance Platform

**Version:** 1.0  
**Effective:** 2026-03-20  
**Owner:** Product / UX (with HSQE business partners)

---

## 1. Objectives

- Validate that **critical user journeys** (CUJs) can be completed with acceptable effort, errors, and subjective satisfaction.  
- Identify **navigation, language, and workflow** issues early, especially for field and mobile use.  
- Produce **actionable findings** mapped to CUJs and backlog items (no “opinion-only” outcomes).  
- Track **quarter-over-quarter trends** for success rate, time-on-task, and System Usability Scale (SUS).

---

## 2. Participant profiles (five personas)

Sessions are recruited to match these archetypes (one primary persona per session; mixed tasks allowed).

| Persona | Typical goals in-session | Experience level | Devices |
|---------|-------------------------|------------------|---------|
| **HSQE Manager** | Triage incidents, open investigations, verify audit readiness | Medium — daily business apps | Laptop |
| **Operations Manager** | Review open actions, assign ownership, check dashboards | Medium | Laptop |
| **Driver / Field reporter** | Submit incident or vehicle checklist quickly; minimal typing | Low–medium — mobile-first | Smartphone |
| **Administrator** | Configure users/roles, run audits, export evidence | High — admin tools | Laptop |
| **Senior management** | Consume KPIs and assurance views; minimal detail | Low — dashboards only | Laptop or tablet |

**Recruitment:** n = **5–8** participants per round (at least one session per persona where possible). Avoid-only colleagues who built the feature under test.

---

## 3. Test scenarios (mapped to CUJs)

Run **8–10** scenarios per session (subset adjusted for role). Each scenario starts from a realistic seed data state.

| # | Scenario (participant-facing title) | Maps to CUJ | Success criteria (observer) |
|---|--------------------------------------|-------------|-----------------------------|
| S1 | “You noticed a safety issue on site—report it.” | CUJ-01 | Report submitted; reference/confirmation visible. |
| S2 | “An incident needs a formal follow-up—log what you’d do next.” | CUJ-02 / CUJ-10 | Correct module opened; action/investigation recorded (or clear blocker noted). |
| S3 | “Complete your daily vehicle check before shift.” | CUJ-03 | Checklist saved; timestamp/status visible. |
| S4 | “You were in a minor collision—record the other party’s details.” | CUJ-04 | RTA record created with third-party fields populated. |
| S5 | “Add a witness statement to the collision record.” | CUJ-05 | Witness saved and visible on record. |
| S6 | “Attach photos from the scene.” | CUJ-06 | Files uploaded and visible on record. |
| S7 | “Add a running sheet note for insurers.” | CUJ-07 | Running sheet entry saved with time/user. |
| S8 | “Plan and assign an internal audit for next week.” | CUJ-08 | Audit created/assigned; appears in list. |
| S9 | “A customer has complained by phone—log it.” | CUJ-09 | Complaint captured with category and contact path. |
| S10 | “Close the loop: investigation outcome and actions.” | CUJ-10 | Investigation updated; actions tracked to closure state. |

Facilitators **may drop** scenarios that are impossible due to test environment limits, but must log the omission as a **finding**.

---

## 4. Task completion metrics

| Metric | Definition | Collection |
|--------|------------|------------|
| **Success rate** | % tasks completed without facilitator intervention beyond neutral prompts | Pass/fail per scenario |
| **Time-on-task** | Seconds from scenario start to successful end state | Stopwatch / session recording |
| **Error rate** | Count of user-induced mistakes (wrong navigation, invalid submit, backtracking) per scenario | Observer tally sheet |
| **SUS score** | Standard System Usability Scale (0–100) | Post-test questionnaire |

**Targets (informative, adjust per release):** success ≥ **85%** on CUJ-linked scenarios; SUS ≥ **75** for internal tools (baseline to be set after first round).

---

## 5. Think-aloud protocol (participants)

- “Please **say what you’re thinking** as you go: expectations, confusion, surprises.”  
- There are **no wrong answers**; we are testing the software, not you.  
- If silent for **20 seconds**, facilitator says: “What are you thinking right now?”  
- If stuck, facilitator may use **neutral prompts** only after **60 seconds** (e.g. “What would you try next?”).  
- **Do not** lead with UI labels (“Click the blue button…”) unless the session is aborted as unusable.

---

## 6. Facilitator guide

**Before session (15 min)**  
- Confirm consent, recording preferences, and persona fit.  
- Reset test tenant data; verify login and seed records.  

**Intro (5 min)**  
- Explain objectives, think-aloud, and that facilitator may stay quiet.  

**Tasks (45–55 min)**  
- Present scenarios one at a time; read verbatim from script.  
- Log **first click**, **hesitations**, **errors**, and **workarounds**.  
- After each scenario: “How did that compare to what you expected?”  

**Debrief (5–10 min)**  
- Open questions: “What one change would save you the most time?”  

**Neutrality rules**  
- No product defence; acknowledge frustration.  
- Stop if PII appears — redact from notes.

---

## 7. Post-test questionnaire template (System Usability Scale)

*Instructions to participant:* “Rate each statement from **1 (Strongly disagree)** to **5 (Strongly agree)**.”

1. I think that I would like to use this system frequently.  
2. I found the system unnecessarily complex.  
3. I thought the system was easy to use.  
4. I think that I would need the support of a technical person to be able to use this system.  
5. I found the various functions in this system were well integrated.  
6. I thought there was too much inconsistency in this system.  
7. I would imagine that most people would learn to use this system very quickly.  
8. I found the system very cumbersome to use.  
9. I felt very confident using the system.  
10. I needed to learn a lot of things before I could get going with this system.  

**Scoring:** Use the standard SUS scoring method (odd items: score − 1; even items: 5 − score; sum × 2.5).

---

## 8. Data analysis and reporting plan

- **Within 5 business days** of each round: de-identify notes; tag findings with **severity** (blocks task / major friction / minor) and **CUJ ID**.  
- **Quantitative:** summarise success rate, median time-on-task, error counts, mean SUS with confidence interval if n ≥ 8.  
- **Qualitative:** affinity-map themes (navigation, language, mobile, trust, governance).  
- **Output:** 2–4 page summary for SLT + Jira/ADO tickets for actionable items.  
- **Trend:** compare to prior quarter on the same CUJ set where possible.

---

## 9. Schedule — quarterly cadence

| Milestone | Timing |
|-----------|--------|
| Round planning & script refresh | Week 1 of quarter |
| Recruitment & pilot (internal dry run) | Weeks 2–3 |
| Live sessions | Weeks 4–6 |
| Analysis & readout | By end of month following sessions |
| Backlog grooming for fixes | Within two weeks of readout |

**Cadence:** **Quarterly** (four rounds per year), plus **ad hoc** rounds after major navigation or CUJ-affecting releases.
