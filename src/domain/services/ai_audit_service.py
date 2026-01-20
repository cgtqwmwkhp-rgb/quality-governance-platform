"""
AI-Powered Audit Assistant Service

Features:
- Smart Questionnaire Generation from regulations
- Evidence Matching
- Finding Classification
- Audit Report Generation
- Trend Analysis
"""

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

# AI Integration
try:
    import anthropic

    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False


class AuditQuestionGenerator:
    """Generate audit questions from regulations and standards"""

    # Pre-defined question templates by standard clause
    ISO_45001_QUESTIONS = {
        "4.1": [
            "How does the organization determine external and internal issues relevant to OH&S?",
            "What processes are in place to monitor and review these issues?",
            "Can you provide evidence of the documented context analysis?",
        ],
        "4.2": [
            "How are interested parties and their OH&S requirements identified?",
            "What are the needs and expectations of workers regarding OH&S?",
            "How are legal and other requirements determined?",
        ],
        "5.1": [
            "How does top management demonstrate leadership and commitment to OH&S?",
            "What evidence shows management taking accountability for OH&S?",
            "How are resources allocated for the OH&S management system?",
        ],
        "5.2": [
            "Is the OH&S policy documented and communicated?",
            "Does the policy include commitment to eliminate hazards and reduce risks?",
            "Does the policy commit to consultation and participation of workers?",
        ],
        "6.1": [
            "How are OH&S hazards identified?",
            "What methodology is used for risk assessment?",
            "How are opportunities for OH&S improvement identified?",
        ],
        "6.2": [
            "Are OH&S objectives established at relevant functions and levels?",
            "Are objectives measurable and monitored?",
            "Are objectives consistent with the OH&S policy?",
        ],
        "7.2": [
            "How is competence determined for workers affecting OH&S performance?",
            "What training is provided to address competence gaps?",
            "How are training records maintained?",
        ],
        "8.1.2": [
            "What is the hierarchy of controls used for risk reduction?",
            "How is the effectiveness of controls verified?",
            "How are changes to hazard controls managed?",
        ],
        "9.1": [
            "What OH&S performance indicators are monitored?",
            "How is equipment for monitoring calibrated or verified?",
            "How is legal compliance evaluated?",
        ],
        "10.2": [
            "What is the process for incident investigation?",
            "How are corrective actions implemented and verified?",
            "How is the effectiveness of corrective actions evaluated?",
        ],
    }

    ISO_9001_QUESTIONS = {
        "4.1": [
            "How does the organization determine external and internal issues?",
            "How are these issues monitored and reviewed?",
        ],
        "4.2": [
            "Who are the organization's interested parties?",
            "What are their requirements relevant to the QMS?",
        ],
        "5.1": [
            "How does top management demonstrate leadership?",
            "How is customer focus ensured?",
        ],
        "6.1": [
            "How are risks and opportunities identified?",
            "What actions are taken to address them?",
        ],
        "7.1.5": [
            "What monitoring and measuring equipment is used?",
            "How is traceability of calibration maintained?",
        ],
        "8.2.1": [
            "How are customer requirements determined?",
            "How are requirements reviewed before acceptance?",
        ],
        "8.5.1": [
            "How is production/service provision controlled?",
            "What documented information exists for processes?",
        ],
        "9.1.2": [
            "How is customer satisfaction monitored?",
            "What methods are used to obtain customer feedback?",
        ],
        "9.2": [
            "Is there an internal audit program?",
            "How is auditor objectivity ensured?",
        ],
        "10.2": [
            "How are nonconformities handled?",
            "How is the effectiveness of corrective actions evaluated?",
        ],
    }

    ISO_14001_QUESTIONS = {
        "4.1": [
            "How are environmental issues (internal/external) determined?",
            "How are environmental conditions affecting the organization identified?",
        ],
        "6.1.2": [
            "What methodology is used to identify environmental aspects?",
            "How are significant aspects determined?",
            "How are aspects across the life cycle considered?",
        ],
        "6.1.3": [
            "What legal and other requirements apply to environmental aspects?",
            "How is compliance with these requirements ensured?",
        ],
        "7.4": [
            "How are internal environmental communications managed?",
            "How are external communications handled?",
        ],
        "8.1": [
            "What operational controls are in place for significant aspects?",
            "How are outsourced processes controlled?",
        ],
        "8.2": [
            "What is the emergency preparedness and response plan?",
            "How are potential emergencies identified?",
            "When was the last emergency drill conducted?",
        ],
        "9.1.2": [
            "How is compliance with legal requirements evaluated?",
            "What is the frequency of compliance evaluation?",
        ],
    }

    # ISO 27001:2022 Information Security Management System Questions
    ISO_27001_QUESTIONS = {
        "4.1": [
            "How are external and internal issues relevant to information security identified?",
            "What process exists to monitor and review these issues?",
            "How do you consider legal, regulatory, and contractual requirements?",
        ],
        "4.2": [
            "Who are the interested parties relevant to the ISMS?",
            "What are their requirements for information security?",
            "How are these requirements addressed in the ISMS?",
        ],
        "4.3": [
            "How is the scope of the ISMS determined and documented?",
            "What boundaries and applicability have been considered?",
            "How are interfaces and dependencies managed?",
        ],
        "5.1": [
            "How does top management demonstrate leadership and commitment to the ISMS?",
            "How are information security policy and objectives established?",
            "How are ISMS requirements integrated into business processes?",
        ],
        "5.2": [
            "Is the information security policy documented and communicated?",
            "Does the policy include commitment to continual improvement?",
            "How is the policy reviewed and maintained?",
        ],
        "5.3": [
            "How are roles, responsibilities, and authorities for information security assigned?",
            "How are these communicated within the organization?",
            "Is there an Information Security Manager or CISO appointed?",
        ],
        "6.1": [
            "How does the organization assess information security risks?",
            "What risk assessment methodology is used?",
            "How are risk criteria defined (acceptance, likelihood, impact)?",
            "How are risks documented and prioritized?",
        ],
        "6.1.3": [
            "How is the risk treatment plan developed?",
            "What criteria are used to select treatment options?",
            "How is the Statement of Applicability maintained?",
        ],
        "6.2": [
            "What are the information security objectives?",
            "Are objectives measurable and consistent with the policy?",
            "How is progress toward objectives monitored?",
        ],
        "7.1": [
            "What resources are provided for the ISMS?",
            "How are resource requirements identified?",
        ],
        "7.2": [
            "How is competence determined for roles affecting information security?",
            "What security awareness training is provided?",
            "How are training records maintained?",
        ],
        "7.3": [
            "How is security awareness maintained across the organization?",
            "What programs exist to promote security culture?",
        ],
        "7.4": [
            "How are internal and external communications on security managed?",
            "What is communicated, when, and to whom?",
        ],
        "7.5": [
            "How is documented information controlled?",
            "How is information classified and protected?",
            "What is the document retention policy?",
        ],
        "8.1": [
            "How are information security processes planned and controlled?",
            "How are changes to processes managed?",
            "How are outsourced processes controlled?",
        ],
        "8.2": [
            "How often are information security risk assessments performed?",
            "What triggers a new risk assessment?",
            "How are risk assessment results documented?",
        ],
        "8.3": [
            "How is the risk treatment plan implemented?",
            "How is effectiveness of treatments evaluated?",
            "How are residual risks documented and accepted?",
        ],
        "9.1": [
            "What security metrics and KPIs are monitored?",
            "How is the effectiveness of the ISMS measured?",
            "How is compliance with security requirements evaluated?",
        ],
        "9.2": [
            "Is there an internal audit program for the ISMS?",
            "How are auditor independence and objectivity ensured?",
            "How are audit findings addressed?",
        ],
        "9.3": [
            "How often is management review conducted?",
            "What inputs are considered in management review?",
            "How are decisions and actions from reviews documented?",
        ],
        "10.1": [
            "How does the organization drive continual improvement of the ISMS?",
            "What improvement initiatives are in place?",
        ],
        "10.2": [
            "How are nonconformities identified and addressed?",
            "What is the corrective action process?",
            "How is effectiveness of corrective actions verified?",
        ],
        # Annex A Controls - Key Questions
        "A.5.1": [
            "Are information security policies defined and approved by management?",
            "How often are policies reviewed?",
            "How are policies communicated to relevant parties?",
        ],
        "A.5.9": [
            "Is there an inventory of information and associated assets?",
            "How is asset ownership defined?",
            "How are assets classified?",
        ],
        "A.5.10": [
            "What are the acceptable use policies for information assets?",
            "How is acceptable use monitored?",
        ],
        "A.5.15": [
            "What is the access control policy?",
            "How is access granted and reviewed?",
            "How is privileged access managed?",
        ],
        "A.5.24": [
            "How are security incidents detected and reported?",
            "What is the incident response process?",
            "How are lessons learned from incidents?",
        ],
        "A.5.29": [
            "How is information security maintained during disruption?",
            "How are business continuity plans tested?",
        ],
        "A.5.31": [
            "How are legal, statutory, and contractual requirements identified?",
            "How is compliance verified?",
        ],
        "A.6.1": [
            "What screening is performed before employment?",
            "Are confidentiality agreements used?",
        ],
        "A.6.3": [
            "What security awareness and training is provided?",
            "How often is training conducted?",
            "How is training effectiveness measured?",
        ],
        "A.7.1": [
            "What physical security perimeters are defined?",
            "How is access to secure areas controlled?",
        ],
        "A.7.4": [
            "How is physical security monitored?",
            "What surveillance systems are in place?",
        ],
        "A.8.1": [
            "How are user endpoints secured?",
            "What endpoint protection is deployed?",
        ],
        "A.8.7": [
            "What malware protection is implemented?",
            "How is malware protection monitored and updated?",
        ],
        "A.8.8": [
            "How are technical vulnerabilities managed?",
            "What is the vulnerability management process?",
            "How quickly are vulnerabilities remediated?",
        ],
        "A.8.9": [
            "How is system configuration managed?",
            "Are configuration standards documented?",
        ],
        "A.8.15": [
            "How are system activities logged?",
            "How are logs protected from tampering?",
            "How long are logs retained?",
        ],
        "A.8.16": [
            "How are logs monitored for security events?",
            "What SIEM or monitoring tools are used?",
        ],
        "A.8.24": [
            "What cryptographic controls are implemented?",
            "How are cryptographic keys managed?",
        ],
        "A.8.25": [
            "How is secure development lifecycle implemented?",
            "What security testing is performed on applications?",
        ],
        "A.8.32": [
            "How is change management performed?",
            "What controls exist for system changes?",
        ],
    }

    def __init__(self, db: Session):
        self.db = db
        self.claude_client = None
        if CLAUDE_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            self.claude_client = anthropic.Anthropic()

    def generate_questions_for_clause(
        self, standard: str, clause: str, context: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Generate audit questions for a specific standard clause"""
        questions = []

        # Get pre-defined questions
        if standard.upper() == "ISO 45001" and clause in self.ISO_45001_QUESTIONS:
            for q in self.ISO_45001_QUESTIONS[clause]:
                questions.append(
                    {
                        "question": q,
                        "clause": clause,
                        "standard": standard,
                        "type": "compliance",
                        "evidence_required": self._suggest_evidence(q),
                    }
                )
        elif standard.upper() == "ISO 9001" and clause in self.ISO_9001_QUESTIONS:
            for q in self.ISO_9001_QUESTIONS[clause]:
                questions.append(
                    {
                        "question": q,
                        "clause": clause,
                        "standard": standard,
                        "type": "compliance",
                        "evidence_required": self._suggest_evidence(q),
                    }
                )
        elif standard.upper() == "ISO 27001" and clause in self.ISO_27001_QUESTIONS:
            for q in self.ISO_27001_QUESTIONS[clause]:
                questions.append(
                    {
                        "question": q,
                        "clause": clause,
                        "standard": standard,
                        "type": "compliance",
                        "evidence_required": self._suggest_evidence(q),
                    }
                )
        elif standard.upper() == "ISO 14001" and clause in self.ISO_14001_QUESTIONS:
            for q in self.ISO_14001_QUESTIONS[clause]:
                questions.append(
                    {
                        "question": q,
                        "clause": clause,
                        "standard": standard,
                        "type": "compliance",
                        "evidence_required": self._suggest_evidence(q),
                    }
                )

        # Use AI to generate additional context-specific questions
        if self.claude_client and context:
            try:
                ai_questions = self._generate_ai_questions(standard, clause, context)
                questions.extend(ai_questions)
            except Exception:
                pass

        return questions

    def _suggest_evidence(self, question: str) -> list[str]:
        """Suggest evidence types based on question"""
        evidence = []
        q_lower = question.lower()

        if any(word in q_lower for word in ["documented", "document", "record"]):
            evidence.append("Documented procedure or record")
        if any(word in q_lower for word in ["training", "competence", "competent"]):
            evidence.append("Training records")
            evidence.append("Competency matrix")
        if any(word in q_lower for word in ["audit", "review"]):
            evidence.append("Audit reports")
            evidence.append("Review minutes")
        if any(word in q_lower for word in ["policy"]):
            evidence.append("Policy document")
        if any(word in q_lower for word in ["risk", "hazard", "assessment"]):
            evidence.append("Risk assessment")
        if any(word in q_lower for word in ["objective", "target", "kpi"]):
            evidence.append("Objectives register")
            evidence.append("KPI dashboard")
        if any(word in q_lower for word in ["calibration", "equipment"]):
            evidence.append("Calibration certificates")
            evidence.append("Equipment register")
        if any(word in q_lower for word in ["communication"]):
            evidence.append("Communication records")
            evidence.append("Meeting minutes")

        return evidence if evidence else ["Interview response", "Visual observation"]

    def _generate_ai_questions(
        self, standard: str, clause: str, context: str
    ) -> list[dict[str, Any]]:
        """Generate context-specific questions using AI"""
        prompt = f"""Generate 3 specific audit questions for {standard} clause {clause}.

Context about the organization: {context}

The questions should:
1. Be specific to the organization's context
2. Be open-ended to encourage detailed responses
3. Focus on practical implementation evidence

Format as JSON array with objects containing: question, type (compliance/effectiveness/improvement), evidence_required (array)"""

        message = self.claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            content = message.content[0].text
            json_match = re.search(r"\[[\s\S]*\]", content)
            if json_match:
                questions = json.loads(json_match.group())
                for q in questions:
                    q["clause"] = clause
                    q["standard"] = standard
                    q["ai_generated"] = True
                return questions
        except (json.JSONDecodeError, IndexError):
            pass

        return []

    def generate_full_audit_checklist(
        self, standard: str, scope_clauses: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """Generate complete audit checklist for a standard"""
        all_questions = []

        # Select appropriate question bank
        if standard.upper() == "ISO 45001":
            question_bank = self.ISO_45001_QUESTIONS
        elif standard.upper() == "ISO 9001":
            question_bank = self.ISO_9001_QUESTIONS
        elif standard.upper() == "ISO 14001":
            question_bank = self.ISO_14001_QUESTIONS
        elif standard.upper() == "ISO 27001":
            question_bank = self.ISO_27001_QUESTIONS
        else:
            return []

        clauses = scope_clauses or list(question_bank.keys())

        for clause in clauses:
            if clause in question_bank:
                for q in question_bank[clause]:
                    all_questions.append(
                        {
                            "question": q,
                            "clause": clause,
                            "standard": standard,
                            "type": "compliance",
                            "evidence_required": self._suggest_evidence(q),
                            "response": None,
                            "conformance": None,  # conforming, minor_nc, major_nc, observation, opportunity
                            "notes": None,
                        }
                    )

        return all_questions


class EvidenceMatcher:
    """Match evidence to audit requirements"""

    def __init__(self, db: Session):
        self.db = db

    def find_evidence_for_clause(self, standard: str, clause: str) -> list[dict[str, Any]]:
        """Find existing evidence that may satisfy a clause"""
        from src.domain.models.document_control import ControlledDocument
        from src.domain.models.iso_compliance import ComplianceEvidence

        evidence = []

        # Search compliance evidence
        compliance_evidence = (
            self.db.query(ComplianceEvidence)
            .filter(
                ComplianceEvidence.iso_clauses.contains([{"standard": standard, "clause": clause}])
            )
            .all()
        )

        for ce in compliance_evidence:
            evidence.append(
                {
                    "type": "compliance_evidence",
                    "id": ce.id,
                    "title": ce.title,
                    "description": ce.description,
                    "file_path": ce.file_path,
                    "last_updated": ce.updated_at.isoformat() if ce.updated_at else None,
                    "match_confidence": 95,
                }
            )

        # Search controlled documents
        clause_pattern = f"%{clause}%"
        documents = (
            self.db.query(ControlledDocument)
            .filter(
                and_(
                    ControlledDocument.relevant_clauses.isnot(None),
                    ControlledDocument.status == "active",
                )
            )
            .limit(100)
            .all()
        )

        for doc in documents:
            if doc.relevant_clauses:
                for rc in doc.relevant_clauses:
                    if clause in str(rc):
                        evidence.append(
                            {
                                "type": "document",
                                "id": doc.id,
                                "document_number": doc.document_number,
                                "title": doc.title,
                                "version": doc.current_version,
                                "file_path": doc.file_path,
                                "match_confidence": 80,
                            }
                        )
                        break

        return evidence

    def suggest_evidence_gaps(self, audit_id: int) -> list[dict[str, Any]]:
        """Identify clauses lacking sufficient evidence"""
        # Get audit findings
        from src.domain.models.audit import AuditFinding

        findings = (
            self.db.query(AuditFinding)
            .filter(
                and_(
                    AuditFinding.audit_id == audit_id,
                    AuditFinding.conformance.in_(["minor_nc", "major_nc", "observation"]),
                )
            )
            .all()
        )

        gaps = []
        for finding in findings:
            existing_evidence = self.find_evidence_for_clause(
                finding.standard or "", finding.clause or ""
            )
            if len(existing_evidence) < 2:
                gaps.append(
                    {
                        "clause": finding.clause,
                        "standard": finding.standard,
                        "finding": finding.description,
                        "conformance": finding.conformance,
                        "evidence_count": len(existing_evidence),
                        "recommendation": f"Increase documented evidence for clause {finding.clause}",
                    }
                )

        return gaps


class FindingClassifier:
    """Classify audit findings by severity and root cause"""

    SEVERITY_KEYWORDS = {
        "major_nc": [
            "absence",
            "no evidence",
            "complete failure",
            "total lack",
            "systematic failure",
            "regulatory breach",
            "legal non-compliance",
            "significant risk",
            "potential harm",
        ],
        "minor_nc": [
            "partial",
            "incomplete",
            "isolated",
            "single instance",
            "minor deviation",
            "documentation gap",
            "inconsistent",
        ],
        "observation": [
            "opportunity",
            "could improve",
            "consider",
            "enhance",
            "suggestion",
            "best practice",
        ],
    }

    ROOT_CAUSE_CATEGORIES = {
        "training": ["competence", "skill", "knowledge", "awareness", "training"],
        "procedure": ["procedure", "process", "method", "instruction", "documentation"],
        "equipment": ["equipment", "tool", "machine", "resource", "infrastructure"],
        "communication": ["communication", "information", "understanding", "clarity"],
        "management": ["leadership", "commitment", "resource", "priority", "attention"],
        "monitoring": ["monitoring", "measurement", "verification", "check", "review"],
    }

    def __init__(self, db: Session):
        self.db = db
        self.claude_client = None
        if CLAUDE_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            self.claude_client = anthropic.Anthropic()

    def classify_finding(self, finding_text: str) -> dict[str, Any]:
        """Classify a finding by severity and root cause"""
        text_lower = finding_text.lower()

        # Determine severity
        severity = "observation"  # Default
        for level, keywords in self.SEVERITY_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    severity = level
                    break
            if severity != "observation":
                break

        # Determine root cause category
        root_cause = "other"
        root_cause_score = 0
        for category, keywords in self.ROOT_CAUSE_CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > root_cause_score:
                root_cause = category
                root_cause_score = score

        return {
            "severity": severity,
            "severity_confidence": 0.8 if any(kw in text_lower for kws in self.SEVERITY_KEYWORDS.values() for kw in kws) else 0.5,
            "root_cause_category": root_cause,
            "root_cause_confidence": min(root_cause_score * 0.3, 0.9),
        }

    def batch_classify(self, findings: list[str]) -> list[dict[str, Any]]:
        """Classify multiple findings"""
        return [self.classify_finding(f) for f in findings]


class AuditReportGenerator:
    """Generate professional audit reports"""

    def __init__(self, db: Session):
        self.db = db
        self.claude_client = None
        if CLAUDE_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            self.claude_client = anthropic.Anthropic()

    def generate_executive_summary(self, audit_id: int) -> str:
        """Generate executive summary for audit"""
        from src.domain.models.audit import Audit, AuditFinding

        audit = self.db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            return "Audit not found"

        findings = (
            self.db.query(AuditFinding)
            .filter(AuditFinding.audit_id == audit_id)
            .all()
        )

        # Count findings by type
        finding_counts = Counter(f.conformance for f in findings if f.conformance)

        major_nc = finding_counts.get("major_nc", 0)
        minor_nc = finding_counts.get("minor_nc", 0)
        observations = finding_counts.get("observation", 0)
        opportunities = finding_counts.get("opportunity", 0)

        # Determine overall conclusion
        if major_nc > 0:
            conclusion = "The audit identified significant non-conformances that require immediate attention."
            recommendation = "Certification cannot be recommended until major non-conformances are closed."
        elif minor_nc > 3:
            conclusion = "The audit identified several minor non-conformances requiring corrective action."
            recommendation = "Conditional certification/continuation recommended subject to corrective action implementation."
        elif minor_nc > 0:
            conclusion = "The audit identified minor non-conformances. The management system is generally effective."
            recommendation = "Certification/continuation is recommended. Corrective actions should be implemented before next surveillance."
        else:
            conclusion = "The audit found the management system to be effectively implemented and maintained."
            recommendation = "Certification/continuation is recommended without conditions."

        summary = f"""EXECUTIVE SUMMARY

Audit Reference: {audit.audit_ref}
Audit Type: {audit.audit_type}
Audit Date: {audit.audit_date.strftime('%d %B %Y') if audit.audit_date else 'N/A'}
Lead Auditor: {audit.lead_auditor}

FINDINGS OVERVIEW:
- Major Non-Conformances: {major_nc}
- Minor Non-Conformances: {minor_nc}
- Observations: {observations}
- Opportunities for Improvement: {opportunities}
- Total Findings: {len(findings)}

CONCLUSION:
{conclusion}

RECOMMENDATION:
{recommendation}
"""

        return summary

    def generate_findings_report(self, audit_id: int) -> list[dict[str, Any]]:
        """Generate detailed findings report"""
        from src.domain.models.audit import AuditFinding

        findings = (
            self.db.query(AuditFinding)
            .filter(AuditFinding.audit_id == audit_id)
            .order_by(
                desc(AuditFinding.conformance == "major_nc"),
                desc(AuditFinding.conformance == "minor_nc"),
            )
            .all()
        )

        report = []
        for i, finding in enumerate(findings, 1):
            classification = FindingClassifier(self.db).classify_finding(finding.description or "")

            report.append(
                {
                    "finding_number": i,
                    "clause": finding.clause,
                    "standard": finding.standard,
                    "conformance": finding.conformance,
                    "description": finding.description,
                    "objective_evidence": finding.evidence,
                    "root_cause_category": classification["root_cause_category"],
                    "corrective_action_required": finding.corrective_action,
                    "due_date": finding.due_date.isoformat() if finding.due_date else None,
                    "status": finding.status,
                }
            )

        return report


class AuditTrendAnalyzer:
    """Analyze trends across audits"""

    def __init__(self, db: Session):
        self.db = db

    def get_finding_trends(self, months: int = 24) -> dict[str, Any]:
        """Analyze finding trends over time"""
        from src.domain.models.audit import Audit, AuditFinding

        cutoff = datetime.utcnow() - timedelta(days=months * 30)

        audits = (
            self.db.query(Audit)
            .filter(Audit.audit_date >= cutoff)
            .order_by(Audit.audit_date)
            .all()
        )

        monthly_data: dict[str, dict] = defaultdict(
            lambda: {"major_nc": 0, "minor_nc": 0, "observation": 0, "opportunity": 0}
        )

        for audit in audits:
            if not audit.audit_date:
                continue
            month_key = audit.audit_date.strftime("%Y-%m")

            findings = (
                self.db.query(AuditFinding)
                .filter(AuditFinding.audit_id == audit.id)
                .all()
            )

            for finding in findings:
                if finding.conformance in monthly_data[month_key]:
                    monthly_data[month_key][finding.conformance] += 1

        # Convert to list
        trends = []
        for month, counts in sorted(monthly_data.items()):
            trends.append(
                {
                    "month": month,
                    "major_nc": counts["major_nc"],
                    "minor_nc": counts["minor_nc"],
                    "observation": counts["observation"],
                    "opportunity": counts["opportunity"],
                    "total": sum(counts.values()),
                }
            )

        # Calculate averages and trends
        total_major = sum(t["major_nc"] for t in trends)
        total_minor = sum(t["minor_nc"] for t in trends)

        # Trend direction (comparing first and last half)
        if len(trends) >= 4:
            mid = len(trends) // 2
            first_half_avg = sum(t["total"] for t in trends[:mid]) / mid
            second_half_avg = sum(t["total"] for t in trends[mid:]) / (len(trends) - mid)
            trend_direction = (
                "improving"
                if second_half_avg < first_half_avg * 0.9
                else "declining" if second_half_avg > first_half_avg * 1.1 else "stable"
            )
        else:
            trend_direction = "insufficient_data"

        return {
            "trends": trends,
            "summary": {
                "total_audits": len(audits),
                "total_major_nc": total_major,
                "total_minor_nc": total_minor,
                "avg_findings_per_audit": (
                    sum(t["total"] for t in trends) / len(audits) if audits else 0
                ),
                "trend_direction": trend_direction,
            },
        }

    def get_recurring_findings(self, min_occurrences: int = 3) -> list[dict[str, Any]]:
        """Identify recurring findings across audits"""
        from src.domain.models.audit import AuditFinding

        # Group findings by clause
        clause_findings: dict[str, list] = defaultdict(list)

        findings = (
            self.db.query(AuditFinding)
            .filter(AuditFinding.conformance.in_(["major_nc", "minor_nc"]))
            .all()
        )

        for finding in findings:
            if finding.clause:
                clause_findings[finding.clause].append(finding)

        recurring = []
        for clause, clause_list in clause_findings.items():
            if len(clause_list) >= min_occurrences:
                recurring.append(
                    {
                        "clause": clause,
                        "occurrence_count": len(clause_list),
                        "findings": [
                            {
                                "description": f.description,
                                "audit_date": (
                                    f.created_at.isoformat() if f.created_at else None
                                ),
                                "conformance": f.conformance,
                            }
                            for f in clause_list[:5]  # Show first 5
                        ],
                        "priority": (
                            "high"
                            if len(clause_list) >= 5 or any(f.conformance == "major_nc" for f in clause_list)
                            else "medium"
                        ),
                        "recommendation": f"Implement systemic improvement for clause {clause}",
                    }
                )

        recurring.sort(key=lambda x: x["occurrence_count"], reverse=True)
        return recurring
