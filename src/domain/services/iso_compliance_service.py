"""
ISO Compliance Evidence Management Service

Provides auto-tagging, evidence mapping, and compliance gap analysis
for ISO 9001, 14001, 45001 and other standards.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ISOStandard(str, Enum):
    ISO_9001 = "iso9001"
    ISO_14001 = "iso14001"
    ISO_45001 = "iso45001"


@dataclass
class ISOClause:
    id: str
    standard: ISOStandard
    clause_number: str
    title: str
    description: str
    keywords: List[str]
    parent_clause: Optional[str] = None
    level: int = 1


@dataclass
class EvidenceLink:
    id: str
    entity_type: str  # 'document', 'audit', 'incident', 'policy', 'action', 'risk'
    entity_id: str
    clause_id: str
    linked_by: str  # 'manual' or 'auto'
    confidence: Optional[float] = None
    created_at: datetime = None
    created_by: Optional[str] = None


# ISO 9001:2015 Clauses
ISO_9001_CLAUSES = [
    ISOClause(
        "9001-4",
        ISOStandard.ISO_9001,
        "4",
        "Context of the organization",
        "Understanding the organization and its context",
        ["context", "organization", "stakeholder", "scope"],
    ),
    ISOClause(
        "9001-4.1",
        ISOStandard.ISO_9001,
        "4.1",
        "Understanding the organization and its context",
        "Determine external and internal issues relevant to purpose and strategic direction",
        ["internal issues", "external issues", "strategic direction", "context"],
        "9001-4",
        2,
    ),
    ISOClause(
        "9001-4.2",
        ISOStandard.ISO_9001,
        "4.2",
        "Understanding needs of interested parties",
        "Determine interested parties and their requirements",
        ["interested parties", "stakeholders", "requirements", "needs", "expectations"],
        "9001-4",
        2,
    ),
    ISOClause(
        "9001-4.3",
        ISOStandard.ISO_9001,
        "4.3",
        "Determining the scope of the QMS",
        "Determine boundaries and applicability of the QMS",
        ["scope", "boundaries", "applicability", "QMS"],
        "9001-4",
        2,
    ),
    ISOClause(
        "9001-4.4",
        ISOStandard.ISO_9001,
        "4.4",
        "Quality management system and its processes",
        "Establish, implement, maintain and improve the QMS",
        ["processes", "QMS", "process approach", "inputs", "outputs"],
        "9001-4",
        2,
    ),
    ISOClause(
        "9001-5",
        ISOStandard.ISO_9001,
        "5",
        "Leadership",
        "Leadership and commitment",
        ["leadership", "commitment", "management", "policy"],
    ),
    ISOClause(
        "9001-5.1",
        ISOStandard.ISO_9001,
        "5.1",
        "Leadership and commitment",
        "Top management shall demonstrate leadership",
        ["top management", "leadership", "commitment", "accountability"],
        "9001-5",
        2,
    ),
    ISOClause(
        "9001-5.2",
        ISOStandard.ISO_9001,
        "5.2",
        "Policy",
        "Establishing the quality policy",
        ["quality policy", "policy", "commitment"],
        "9001-5",
        2,
    ),
    ISOClause(
        "9001-5.3",
        ISOStandard.ISO_9001,
        "5.3",
        "Organizational roles and responsibilities",
        "Assign and communicate roles and responsibilities",
        ["roles", "responsibilities", "authorities", "organization chart"],
        "9001-5",
        2,
    ),
    ISOClause(
        "9001-6",
        ISOStandard.ISO_9001,
        "6",
        "Planning",
        "Planning for the QMS",
        ["planning", "risks", "opportunities", "objectives"],
    ),
    ISOClause(
        "9001-6.1",
        ISOStandard.ISO_9001,
        "6.1",
        "Actions to address risks and opportunities",
        "Determine risks and opportunities and plan actions",
        ["risk", "opportunity", "risk assessment", "risk treatment"],
        "9001-6",
        2,
    ),
    ISOClause(
        "9001-6.2",
        ISOStandard.ISO_9001,
        "6.2",
        "Quality objectives",
        "Establish quality objectives at relevant functions",
        ["quality objectives", "objectives", "targets", "KPIs"],
        "9001-6",
        2,
    ),
    ISOClause(
        "9001-7",
        ISOStandard.ISO_9001,
        "7",
        "Support",
        "Resources, competence, awareness, communication",
        ["support", "resources", "competence", "training"],
    ),
    ISOClause(
        "9001-7.1",
        ISOStandard.ISO_9001,
        "7.1",
        "Resources",
        "Determine and provide resources needed",
        ["resources", "infrastructure", "environment", "monitoring", "measuring"],
        "9001-7",
        2,
    ),
    ISOClause(
        "9001-7.2",
        ISOStandard.ISO_9001,
        "7.2",
        "Competence",
        "Determine competence of persons",
        ["competence", "training", "skills", "qualifications", "education"],
        "9001-7",
        2,
    ),
    ISOClause(
        "9001-7.3",
        ISOStandard.ISO_9001,
        "7.3",
        "Awareness",
        "Persons shall be aware of quality policy",
        ["awareness", "quality policy", "contribution"],
        "9001-7",
        2,
    ),
    ISOClause(
        "9001-7.4",
        ISOStandard.ISO_9001,
        "7.4",
        "Communication",
        "Internal and external communications",
        ["communication", "internal communication", "external communication"],
        "9001-7",
        2,
    ),
    ISOClause(
        "9001-7.5",
        ISOStandard.ISO_9001,
        "7.5",
        "Documented information",
        "Control of documented information",
        ["documented information", "documents", "records", "document control"],
        "9001-7",
        2,
    ),
    ISOClause(
        "9001-8",
        ISOStandard.ISO_9001,
        "8",
        "Operation",
        "Operational planning and control",
        ["operation", "operational", "process control"],
    ),
    ISOClause(
        "9001-8.1",
        ISOStandard.ISO_9001,
        "8.1",
        "Operational planning and control",
        "Plan, implement and control processes",
        ["operational planning", "process control", "criteria"],
        "9001-8",
        2,
    ),
    ISOClause(
        "9001-8.2",
        ISOStandard.ISO_9001,
        "8.2",
        "Requirements for products and services",
        "Determine requirements for products and services",
        ["customer requirements", "product requirements", "service requirements"],
        "9001-8",
        2,
    ),
    ISOClause(
        "9001-8.4",
        ISOStandard.ISO_9001,
        "8.4",
        "Control of external providers",
        "Control of external providers",
        ["suppliers", "outsourcing", "external providers", "purchasing"],
        "9001-8",
        2,
    ),
    ISOClause(
        "9001-8.5",
        ISOStandard.ISO_9001,
        "8.5",
        "Production and service provision",
        "Control of production and service provision",
        ["production", "service provision", "traceability", "preservation"],
        "9001-8",
        2,
    ),
    ISOClause(
        "9001-8.7",
        ISOStandard.ISO_9001,
        "8.7",
        "Control of nonconforming outputs",
        "Identify and control nonconforming outputs",
        ["nonconformance", "nonconforming", "defect", "reject"],
        "9001-8",
        2,
    ),
    ISOClause(
        "9001-9",
        ISOStandard.ISO_9001,
        "9",
        "Performance evaluation",
        "Monitoring, measurement, analysis",
        ["performance", "monitoring", "measurement", "analysis"],
    ),
    ISOClause(
        "9001-9.1",
        ISOStandard.ISO_9001,
        "9.1",
        "Monitoring, measurement, analysis",
        "Determine what needs to be monitored",
        ["monitoring", "measurement", "KPIs", "performance indicators"],
        "9001-9",
        2,
    ),
    ISOClause(
        "9001-9.2",
        ISOStandard.ISO_9001,
        "9.2",
        "Internal audit",
        "Conduct internal audits at planned intervals",
        ["internal audit", "audit", "audit program", "audit findings"],
        "9001-9",
        2,
    ),
    ISOClause(
        "9001-9.3",
        ISOStandard.ISO_9001,
        "9.3",
        "Management review",
        "Top management shall review the QMS",
        ["management review", "review", "top management"],
        "9001-9",
        2,
    ),
    ISOClause(
        "9001-10",
        ISOStandard.ISO_9001,
        "10",
        "Improvement",
        "Continual improvement",
        ["improvement", "continual improvement", "corrective action"],
    ),
    ISOClause(
        "9001-10.2",
        ISOStandard.ISO_9001,
        "10.2",
        "Nonconformity and corrective action",
        "React to nonconformities and take corrective action",
        ["nonconformity", "corrective action", "root cause", "CAPA"],
        "9001-10",
        2,
    ),
    ISOClause(
        "9001-10.3",
        ISOStandard.ISO_9001,
        "10.3",
        "Continual improvement",
        "Continually improve the QMS",
        ["continual improvement", "improvement", "effectiveness"],
        "9001-10",
        2,
    ),
]

# ISO 14001:2015 Clauses
ISO_14001_CLAUSES = [
    ISOClause(
        "14001-4",
        ISOStandard.ISO_14001,
        "4",
        "Context of the organization",
        "Understanding the organization and its context",
        ["context", "environmental", "stakeholders"],
    ),
    ISOClause(
        "14001-5",
        ISOStandard.ISO_14001,
        "5",
        "Leadership",
        "Leadership and commitment",
        ["leadership", "environmental policy", "commitment"],
    ),
    ISOClause(
        "14001-5.2",
        ISOStandard.ISO_14001,
        "5.2",
        "Environmental policy",
        "Establish environmental policy",
        ["environmental policy", "pollution prevention", "compliance"],
        "14001-5",
        2,
    ),
    ISOClause(
        "14001-6",
        ISOStandard.ISO_14001,
        "6",
        "Planning",
        "Planning for the EMS",
        ["planning", "environmental aspects", "risks"],
    ),
    ISOClause(
        "14001-6.1.2",
        ISOStandard.ISO_14001,
        "6.1.2",
        "Environmental aspects",
        "Identify environmental aspects and significant impacts",
        ["aspects", "impacts", "significant aspects", "lifecycle"],
        "14001-6",
        2,
    ),
    ISOClause(
        "14001-6.1.3",
        ISOStandard.ISO_14001,
        "6.1.3",
        "Compliance obligations",
        "Identify and access compliance obligations",
        ["legal requirements", "compliance", "regulations", "permits"],
        "14001-6",
        2,
    ),
    ISOClause(
        "14001-7",
        ISOStandard.ISO_14001,
        "7",
        "Support",
        "Resources, competence, awareness, communication",
        ["support", "resources", "competence", "awareness"],
    ),
    ISOClause(
        "14001-8",
        ISOStandard.ISO_14001,
        "8",
        "Operation",
        "Operational planning and control",
        ["operation", "operational control", "emergency"],
    ),
    ISOClause(
        "14001-8.2",
        ISOStandard.ISO_14001,
        "8.2",
        "Emergency preparedness and response",
        "Prepare for and respond to emergencies",
        ["emergency", "emergency response", "spill", "incident"],
        "14001-8",
        2,
    ),
    ISOClause(
        "14001-9",
        ISOStandard.ISO_14001,
        "9",
        "Performance evaluation",
        "Monitoring, measurement, analysis",
        ["performance", "monitoring", "compliance evaluation"],
    ),
    ISOClause(
        "14001-9.1.2",
        ISOStandard.ISO_14001,
        "9.1.2",
        "Evaluation of compliance",
        "Evaluate compliance with obligations",
        ["compliance evaluation", "legal compliance", "audit"],
        "14001-9",
        2,
    ),
    ISOClause(
        "14001-10",
        ISOStandard.ISO_14001,
        "10",
        "Improvement",
        "Continual improvement",
        ["improvement", "corrective action", "continual improvement"],
    ),
]

# ISO 45001:2018 Clauses
ISO_45001_CLAUSES = [
    ISOClause(
        "45001-4",
        ISOStandard.ISO_45001,
        "4",
        "Context of the organization",
        "Understanding the organization and its context",
        ["context", "OH&S", "workers"],
    ),
    ISOClause(
        "45001-5",
        ISOStandard.ISO_45001,
        "5",
        "Leadership and worker participation",
        "Leadership, worker participation",
        ["leadership", "worker participation", "consultation"],
    ),
    ISOClause(
        "45001-5.2",
        ISOStandard.ISO_45001,
        "5.2",
        "OH&S policy",
        "Establish OH&S policy",
        ["OH&S policy", "health and safety policy", "policy"],
        "45001-5",
        2,
    ),
    ISOClause(
        "45001-5.4",
        ISOStandard.ISO_45001,
        "5.4",
        "Consultation and participation of workers",
        "Consult and enable worker participation",
        ["consultation", "participation", "workers", "safety committee"],
        "45001-5",
        2,
    ),
    ISOClause(
        "45001-6", ISOStandard.ISO_45001, "6", "Planning", "Planning for the OHSMS", ["planning", "hazards", "risks"]
    ),
    ISOClause(
        "45001-6.1.2",
        ISOStandard.ISO_45001,
        "6.1.2",
        "Hazard identification",
        "Identify hazards and assess OH&S risks",
        ["hazard identification", "risk assessment", "hazards", "risks"],
        "45001-6",
        2,
    ),
    ISOClause(
        "45001-6.1.3",
        ISOStandard.ISO_45001,
        "6.1.3",
        "Legal requirements",
        "Determine legal and other requirements",
        ["legal requirements", "compliance", "regulations", "legislation"],
        "45001-6",
        2,
    ),
    ISOClause(
        "45001-7",
        ISOStandard.ISO_45001,
        "7",
        "Support",
        "Resources, competence, awareness, communication",
        ["support", "resources", "competence", "training"],
    ),
    ISOClause(
        "45001-7.2",
        ISOStandard.ISO_45001,
        "7.2",
        "Competence",
        "Ensure competence of persons",
        ["competence", "training", "safety training", "qualifications"],
        "45001-7",
        2,
    ),
    ISOClause(
        "45001-8",
        ISOStandard.ISO_45001,
        "8",
        "Operation",
        "Operational planning and control",
        ["operation", "operational control", "emergency"],
    ),
    ISOClause(
        "45001-8.1.2",
        ISOStandard.ISO_45001,
        "8.1.2",
        "Eliminating hazards",
        "Apply hierarchy of controls",
        ["hierarchy of controls", "elimination", "substitution", "engineering", "administrative", "PPE"],
        "45001-8",
        2,
    ),
    ISOClause(
        "45001-8.2",
        ISOStandard.ISO_45001,
        "8.2",
        "Emergency preparedness",
        "Prepare for and respond to emergencies",
        ["emergency", "emergency response", "first aid", "evacuation", "fire"],
        "45001-8",
        2,
    ),
    ISOClause(
        "45001-9",
        ISOStandard.ISO_45001,
        "9",
        "Performance evaluation",
        "Monitoring, measurement, analysis",
        ["performance", "monitoring", "evaluation"],
    ),
    ISOClause(
        "45001-9.2",
        ISOStandard.ISO_45001,
        "9.2",
        "Internal audit",
        "Conduct internal audits",
        ["internal audit", "safety audit", "audit program"],
        "45001-9",
        2,
    ),
    ISOClause(
        "45001-10",
        ISOStandard.ISO_45001,
        "10",
        "Improvement",
        "Incident investigation, nonconformity, continual improvement",
        ["improvement", "incident", "corrective action"],
    ),
    ISOClause(
        "45001-10.2",
        ISOStandard.ISO_45001,
        "10.2",
        "Incident, nonconformity and corrective action",
        "Investigate incidents and take corrective action",
        ["incident investigation", "accident investigation", "nonconformity", "corrective action", "root cause"],
        "45001-10",
        2,
    ),
]

# All clauses combined
ALL_CLAUSES = ISO_9001_CLAUSES + ISO_14001_CLAUSES + ISO_45001_CLAUSES


class ISOComplianceService:
    """Service for ISO compliance evidence management and auto-tagging."""

    def __init__(self, ai_client=None):
        self.ai_client = ai_client
        self.clauses = {clause.id: clause for clause in ALL_CLAUSES}

    def get_all_clauses(self, standard: Optional[ISOStandard] = None) -> List[ISOClause]:
        """Get all ISO clauses, optionally filtered by standard."""
        if standard:
            return [c for c in ALL_CLAUSES if c.standard == standard]
        return ALL_CLAUSES

    def get_clause(self, clause_id: str) -> Optional[ISOClause]:
        """Get a specific clause by ID."""
        return self.clauses.get(clause_id)

    def search_clauses(self, query: str) -> List[ISOClause]:
        """Search clauses by keyword, title, or clause number."""
        query_lower = query.lower()
        results = []

        for clause in ALL_CLAUSES:
            score = 0

            # Clause number match (highest priority)
            if query in clause.clause_number:
                score += 20

            # Title match
            if query_lower in clause.title.lower():
                score += 15

            # Description match
            if query_lower in clause.description.lower():
                score += 10

            # Keyword match
            for keyword in clause.keywords:
                if query_lower in keyword.lower():
                    score += 5

            if score > 0:
                results.append((score, clause))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [clause for _, clause in results[:20]]

    def auto_tag_content(self, content: str, min_confidence: float = 0.3) -> List[Dict[str, Any]]:
        """
        Automatically detect ISO clauses that relate to the given content.
        Uses keyword matching and pattern recognition.

        Returns list of dicts with clause info and confidence score.
        """
        content_lower = content.lower()
        matched_clauses: Dict[str, float] = {}

        for clause in ALL_CLAUSES:
            score = 0.0
            matches = []

            # Check for explicit clause number references (e.g., "9001 clause 7.2")
            clause_patterns = [
                rf"\b{re.escape(clause.clause_number)}\b",
                rf"clause\s*{re.escape(clause.clause_number)}",
                rf"ISO\s*{clause.standard.value[3:]}\s*[:-]?\s*{re.escape(clause.clause_number)}",
            ]

            for pattern in clause_patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    score += 0.4
                    matches.append(f"explicit reference: {pattern}")

            # Title match (strong signal)
            if clause.title.lower() in content_lower:
                score += 0.3
                matches.append(f"title match: {clause.title}")

            # Keyword matching
            keyword_hits = 0
            for keyword in clause.keywords:
                if keyword.lower() in content_lower:
                    keyword_hits += 1
                    matches.append(f"keyword: {keyword}")

            if keyword_hits > 0:
                # Scale score by number of keywords matched
                keyword_score = min(0.3, keyword_hits * 0.1)
                score += keyword_score

            # Description phrases
            desc_words = clause.description.lower().split()
            desc_matches = sum(1 for word in desc_words if len(word) > 4 and word in content_lower)
            if desc_matches >= 2:
                score += 0.1

            if score >= min_confidence:
                matched_clauses[clause.id] = min(1.0, score)

        # Convert to result list
        results = []
        for clause_id, confidence in sorted(matched_clauses.items(), key=lambda x: x[1], reverse=True):
            clause = self.clauses[clause_id]
            results.append(
                {
                    "clause_id": clause.id,
                    "clause_number": clause.clause_number,
                    "title": clause.title,
                    "standard": clause.standard.value,
                    "confidence": round(confidence * 100, 1),
                    "linked_by": "auto",
                }
            )

        return results[:10]  # Return top 10 matches

    async def ai_enhanced_tagging(self, content: str) -> List[Dict[str, Any]]:
        """
        Use AI to analyze content and suggest relevant ISO clauses.
        Falls back to keyword-based tagging if AI is unavailable.
        """
        if not self.ai_client:
            return self.auto_tag_content(content)

        try:
            # Create clause context for AI
            clause_context = "\n".join(
                [f"- {c.id}: {c.clause_number} - {c.title} ({c.standard.value})" for c in ALL_CLAUSES if c.level == 2]
            )

            prompt = f"""Analyze the following content and identify which ISO clauses (9001, 14001, 45001) it relates to.

Available clauses:
{clause_context}

Content to analyze:
{content}

Return a JSON array of matching clause IDs with confidence scores (0-100).
Format: [{{"clause_id": "9001-7.2", "confidence": 85}}, ...]

Only return clauses with confidence > 50. Be specific - don't over-match."""

            response = await self.ai_client.analyze(prompt)

            # Parse AI response
            try:
                matches = json.loads(response)
                results = []
                for match in matches:
                    clause = self.clauses.get(match["clause_id"])
                    if clause:
                        results.append(
                            {
                                "clause_id": clause.id,
                                "clause_number": clause.clause_number,
                                "title": clause.title,
                                "standard": clause.standard.value,
                                "confidence": match["confidence"],
                                "linked_by": "ai",
                            }
                        )
                return results
            except json.JSONDecodeError:
                return self.auto_tag_content(content)

        except Exception:
            # Fallback to keyword matching
            return self.auto_tag_content(content)

    def calculate_compliance_coverage(
        self, evidence_links: List[EvidenceLink], standard: Optional[ISOStandard] = None
    ) -> Dict[str, Any]:
        """
        Calculate compliance coverage statistics.

        Returns coverage percentages and gap analysis.
        """
        clauses = self.get_all_clauses(standard)
        level_2_clauses = [c for c in clauses if c.level == 2]

        # Count evidence per clause
        clause_evidence_count: Dict[str, int] = {}
        for link in evidence_links:
            clause_id = link.clause_id
            clause_evidence_count[clause_id] = clause_evidence_count.get(clause_id, 0) + 1

        # Categorize coverage
        full_coverage = []  # 2+ evidence items
        partial_coverage = []  # 1 evidence item
        no_coverage = []  # 0 evidence items

        for clause in level_2_clauses:
            count = clause_evidence_count.get(clause.id, 0)
            if count >= 2:
                full_coverage.append(clause)
            elif count == 1:
                partial_coverage.append(clause)
            else:
                no_coverage.append(clause)

        total = len(level_2_clauses)

        return {
            "total_clauses": total,
            "full_coverage": len(full_coverage),
            "partial_coverage": len(partial_coverage),
            "gaps": len(no_coverage),
            "coverage_percentage": (
                round((len(full_coverage) + len(partial_coverage) * 0.5) / total * 100, 1) if total > 0 else 0
            ),
            "gap_clauses": [
                {"clause_id": c.id, "clause_number": c.clause_number, "title": c.title, "standard": c.standard.value}
                for c in no_coverage
            ],
            "by_standard": {
                "iso9001": self._standard_coverage(evidence_links, ISOStandard.ISO_9001),
                "iso14001": self._standard_coverage(evidence_links, ISOStandard.ISO_14001),
                "iso45001": self._standard_coverage(evidence_links, ISOStandard.ISO_45001),
            },
        }

    def _standard_coverage(self, evidence_links: List[EvidenceLink], standard: ISOStandard) -> Dict[str, Any]:
        """Calculate coverage for a specific standard."""
        clauses = [c for c in ALL_CLAUSES if c.standard == standard and c.level == 2]
        clause_ids = {c.id for c in clauses}

        covered = set()
        for link in evidence_links:
            if link.clause_id in clause_ids:
                covered.add(link.clause_id)

        total = len(clauses)
        return {
            "total": total,
            "covered": len(covered),
            "percentage": round(len(covered) / total * 100, 1) if total > 0 else 0,
        }

    def generate_audit_report(
        self,
        evidence_links: List[EvidenceLink],
        standard: Optional[ISOStandard] = None,
        include_evidence_details: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive audit-ready compliance report.

        Shows all clauses with their linked evidence for certification audits.
        """
        coverage = self.calculate_compliance_coverage(evidence_links, standard)
        clauses = self.get_all_clauses(standard)

        # Group evidence by clause
        clause_evidence: Dict[str, List[EvidenceLink]] = {}
        for link in evidence_links:
            if link.clause_id not in clause_evidence:
                clause_evidence[link.clause_id] = []
            clause_evidence[link.clause_id].append(link)

        # Build clause details
        clause_details = []
        for clause in clauses:
            if clause.level != 2:
                continue

            evidence = clause_evidence.get(clause.id, [])
            status = "full" if len(evidence) >= 2 else "partial" if len(evidence) == 1 else "gap"

            detail = {
                "clause_id": clause.id,
                "clause_number": clause.clause_number,
                "title": clause.title,
                "description": clause.description,
                "standard": clause.standard.value,
                "status": status,
                "evidence_count": len(evidence),
            }

            if include_evidence_details:
                detail["evidence"] = [
                    {
                        "entity_type": e.entity_type,
                        "entity_id": e.entity_id,
                        "linked_by": e.linked_by,
                        "confidence": e.confidence,
                    }
                    for e in evidence
                ]

            clause_details.append(detail)

        return {"generated_at": datetime.utcnow().isoformat(), "summary": coverage, "clauses": clause_details}


# Singleton instance
iso_compliance_service = ISOComplianceService()
