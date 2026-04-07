"""
ISO Compliance Evidence Management Service

Provides auto-tagging, evidence mapping, and compliance gap analysis
for ISO 9001, 14001, 45001 and other standards.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ISOStandard(str, Enum):
    ISO_9001 = "iso9001"
    ISO_14001 = "iso14001"
    ISO_45001 = "iso45001"
    ISO_27001 = "iso27001"


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
    created_at: Optional[datetime] = None
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
        "45001-6",
        ISOStandard.ISO_45001,
        "6",
        "Planning",
        "Planning for the OHSMS",
        ["planning", "hazards", "risks"],
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
        [
            "hierarchy of controls",
            "elimination",
            "substitution",
            "engineering",
            "administrative",
            "PPE",
        ],
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
        [
            "incident investigation",
            "accident investigation",
            "nonconformity",
            "corrective action",
            "root cause",
        ],
        "45001-10",
        2,
    ),
]

# ISO 27001:2022 Clauses (core clauses 4-10 + key Annex A control groups)
ISO_27001_CLAUSES = [
    ISOClause(
        "27001-4",
        ISOStandard.ISO_27001,
        "4",
        "Context of the organization",
        "Understanding the organization and its context for information security",
        ["context", "information security", "stakeholders", "scope", "ISMS"],
    ),
    ISOClause(
        "27001-4.1",
        ISOStandard.ISO_27001,
        "4.1",
        "Understanding the organization and its context",
        "Determine external and internal issues relevant to information security",
        ["context", "internal issues", "external issues", "information security"],
        "27001-4",
        2,
    ),
    ISOClause(
        "27001-4.2",
        ISOStandard.ISO_27001,
        "4.2",
        "Understanding the needs and expectations of interested parties",
        "Determine interested parties and their information security requirements",
        ["interested parties", "stakeholders", "security requirements"],
        "27001-4",
        2,
    ),
    ISOClause(
        "27001-4.3",
        ISOStandard.ISO_27001,
        "4.3",
        "Determining the scope of the ISMS",
        "Determine boundaries and applicability of the ISMS",
        ["scope", "ISMS scope", "boundaries", "applicability"],
        "27001-4",
        2,
    ),
    ISOClause(
        "27001-5",
        ISOStandard.ISO_27001,
        "5",
        "Leadership",
        "Leadership and commitment for information security",
        ["leadership", "management", "information security policy", "commitment"],
    ),
    ISOClause(
        "27001-5.1",
        ISOStandard.ISO_27001,
        "5.1",
        "Leadership and commitment",
        "Top management shall demonstrate leadership and commitment",
        ["top management", "leadership", "commitment", "information security"],
        "27001-5",
        2,
    ),
    ISOClause(
        "27001-5.2",
        ISOStandard.ISO_27001,
        "5.2",
        "Information security policy",
        "Establish and maintain information security policy",
        ["information security policy", "policy", "security objectives"],
        "27001-5",
        2,
    ),
    ISOClause(
        "27001-6",
        ISOStandard.ISO_27001,
        "6",
        "Planning",
        "Planning for the ISMS including risk assessment and treatment",
        ["planning", "risk assessment", "risk treatment", "information security objectives"],
    ),
    ISOClause(
        "27001-6.1",
        ISOStandard.ISO_27001,
        "6.1",
        "Actions to address risks and opportunities",
        "Information security risk assessment and treatment process",
        ["risk assessment", "risk treatment", "risk identification", "threat", "vulnerability"],
        "27001-6",
        2,
    ),
    ISOClause(
        "27001-6.1.2",
        ISOStandard.ISO_27001,
        "6.1.2",
        "Information security risk assessment",
        "Define and apply risk assessment process",
        ["risk assessment", "risk criteria", "threat", "vulnerability", "likelihood", "impact"],
        "27001-6",
        2,
    ),
    ISOClause(
        "27001-6.1.3",
        ISOStandard.ISO_27001,
        "6.1.3",
        "Information security risk treatment",
        "Select and apply risk treatment options",
        ["risk treatment", "risk acceptance", "risk mitigation", "risk transfer", "controls"],
        "27001-6",
        2,
    ),
    ISOClause(
        "27001-6.2",
        ISOStandard.ISO_27001,
        "6.2",
        "Information security objectives",
        "Establish measurable information security objectives",
        ["security objectives", "objectives", "targets", "KPIs", "metrics"],
        "27001-6",
        2,
    ),
    ISOClause(
        "27001-7",
        ISOStandard.ISO_27001,
        "7",
        "Support",
        "Resources, competence, awareness, communication, documented information",
        ["support", "resources", "competence", "awareness", "communication", "training"],
    ),
    ISOClause(
        "27001-7.2",
        ISOStandard.ISO_27001,
        "7.2",
        "Competence",
        "Ensure competence of persons affecting information security",
        ["competence", "training", "skills", "qualifications", "security awareness"],
        "27001-7",
        2,
    ),
    ISOClause(
        "27001-7.5",
        ISOStandard.ISO_27001,
        "7.5",
        "Documented information",
        "Control of documented information required by the ISMS",
        ["documented information", "records", "document control", "procedures"],
        "27001-7",
        2,
    ),
    ISOClause(
        "27001-8",
        ISOStandard.ISO_27001,
        "8",
        "Operation",
        "Operational planning and control for information security",
        ["operation", "operational", "risk treatment implementation", "Annex A controls"],
    ),
    ISOClause(
        "27001-8.2",
        ISOStandard.ISO_27001,
        "8.2",
        "Information security risk assessment (operational)",
        "Perform information security risk assessments at planned intervals",
        ["risk assessment", "periodic review", "risk register", "residual risk"],
        "27001-8",
        2,
    ),
    ISOClause(
        "27001-9",
        ISOStandard.ISO_27001,
        "9",
        "Performance evaluation",
        "Monitoring, measurement, analysis and evaluation",
        ["performance", "monitoring", "measurement", "internal audit", "management review"],
    ),
    ISOClause(
        "27001-9.1",
        ISOStandard.ISO_27001,
        "9.1",
        "Monitoring, measurement, analysis and evaluation",
        "Determine what needs to be monitored and measured",
        ["monitoring", "measurement", "KPIs", "metrics", "performance indicators"],
        "27001-9",
        2,
    ),
    ISOClause(
        "27001-9.2",
        ISOStandard.ISO_27001,
        "9.2",
        "Internal audit",
        "Conduct internal audits at planned intervals",
        ["internal audit", "audit program", "audit findings", "ISMS audit"],
        "27001-9",
        2,
    ),
    ISOClause(
        "27001-9.3",
        ISOStandard.ISO_27001,
        "9.3",
        "Management review",
        "Top management shall review the ISMS",
        ["management review", "ISMS review", "top management", "continual improvement"],
        "27001-9",
        2,
    ),
    ISOClause(
        "27001-10",
        ISOStandard.ISO_27001,
        "10",
        "Improvement",
        "Continual improvement of the ISMS",
        ["improvement", "continual improvement", "corrective action", "nonconformity"],
    ),
    ISOClause(
        "27001-10.1",
        ISOStandard.ISO_27001,
        "10.1",
        "Continual improvement",
        "Continually improve the suitability, adequacy and effectiveness of the ISMS",
        ["continual improvement", "effectiveness", "ISMS improvement"],
        "27001-10",
        2,
    ),
    ISOClause(
        "27001-10.2",
        ISOStandard.ISO_27001,
        "10.2",
        "Nonconformity and corrective action",
        "React to nonconformities and take corrective action",
        ["nonconformity", "corrective action", "root cause", "CAPA", "incident"],
        "27001-10",
        2,
    ),
    # Key Annex A control groups
    ISOClause(
        "27001-A5",
        ISOStandard.ISO_27001,
        "A.5",
        "Organizational controls",
        "37 organizational controls covering policies, roles, threat intelligence, and supplier relationships",
        [
            "organizational controls",
            "information security policy",
            "roles",
            "responsibilities",
            "threat intelligence",
            "supplier",
            "access control",
            "asset management",
        ],
    ),
    ISOClause(
        "27001-A5.1",
        ISOStandard.ISO_27001,
        "A.5.1",
        "Policies for information security",
        "Define, approve and communicate information security policies",
        ["information security policy", "policy", "management approval", "review"],
        "27001-A5",
        2,
    ),
    ISOClause(
        "27001-A5.15",
        ISOStandard.ISO_27001,
        "A.5.15",
        "Access control",
        "Rules to control physical and logical access to information and assets",
        ["access control", "access rights", "least privilege", "need to know", "authorization"],
        "27001-A5",
        2,
    ),
    ISOClause(
        "27001-A5.19",
        ISOStandard.ISO_27001,
        "A.5.19",
        "Information security in supplier relationships",
        "Protecting assets accessible by suppliers",
        ["supplier", "third party", "vendor", "outsourcing", "supplier security"],
        "27001-A5",
        2,
    ),
    ISOClause(
        "27001-A5.24",
        ISOStandard.ISO_27001,
        "A.5.24",
        "Information security incident management planning",
        "Plan and prepare for information security incident management",
        ["incident management", "incident response", "security incident", "preparation"],
        "27001-A5",
        2,
    ),
    ISOClause(
        "27001-A5.25",
        ISOStandard.ISO_27001,
        "A.5.25",
        "Assessment and decision on information security events",
        "Assess and decide whether events are incidents",
        ["incident assessment", "security event", "incident triage", "classification"],
        "27001-A5",
        2,
    ),
    ISOClause(
        "27001-A5.26",
        ISOStandard.ISO_27001,
        "A.5.26",
        "Response to information security incidents",
        "Respond to information security incidents according to procedures",
        ["incident response", "containment", "eradication", "recovery", "lessons learned"],
        "27001-A5",
        2,
    ),
    ISOClause(
        "27001-A5.29",
        ISOStandard.ISO_27001,
        "A.5.29",
        "Information security during disruption",
        "Maintain information security during disruption",
        ["business continuity", "disaster recovery", "disruption", "BCP", "RTO", "RPO"],
        "27001-A5",
        2,
    ),
    ISOClause(
        "27001-A6",
        ISOStandard.ISO_27001,
        "A.6",
        "People controls",
        "8 people controls covering screening, employment, and remote working",
        ["people controls", "screening", "employment", "remote working", "BYOD", "training"],
    ),
    ISOClause(
        "27001-A7",
        ISOStandard.ISO_27001,
        "A.7",
        "Physical controls",
        "14 physical controls covering physical security perimeter and entry",
        ["physical controls", "physical security", "secure areas", "entry controls", "clean desk"],
    ),
    ISOClause(
        "27001-A8",
        ISOStandard.ISO_27001,
        "A.8",
        "Technological controls",
        "34 technological controls covering user endpoints, malware, and cryptography",
        [
            "technological controls",
            "endpoint",
            "malware",
            "cryptography",
            "vulnerability management",
            "logging",
            "monitoring",
            "network security",
            "data masking",
            "backup",
        ],
    ),
    ISOClause(
        "27001-A8.2",
        ISOStandard.ISO_27001,
        "A.8.2",
        "Privileged access rights",
        "Allocate and manage privileged access rights",
        ["privileged access", "admin access", "administrator", "superuser", "privileged accounts"],
        "27001-A8",
        2,
    ),
    ISOClause(
        "27001-A8.8",
        ISOStandard.ISO_27001,
        "A.8.8",
        "Management of technical vulnerabilities",
        "Obtain information about technical vulnerabilities and take action",
        ["vulnerability management", "patch management", "CVE", "vulnerability scanning", "patching"],
        "27001-A8",
        2,
    ),
    ISOClause(
        "27001-A8.15",
        ISOStandard.ISO_27001,
        "A.8.15",
        "Logging",
        "Produce, store, protect and analyse logs",
        ["logging", "audit logs", "log management", "SIEM", "audit trail", "event logs"],
        "27001-A8",
        2,
    ),
    ISOClause(
        "27001-A8.24",
        ISOStandard.ISO_27001,
        "A.8.24",
        "Use of cryptography",
        "Define and implement rules for effective use of cryptography",
        ["cryptography", "encryption", "key management", "PKI", "TLS", "data encryption"],
        "27001-A8",
        2,
    ),
]

# All clauses combined
ALL_CLAUSES = ISO_9001_CLAUSES + ISO_14001_CLAUSES + ISO_45001_CLAUSES + ISO_27001_CLAUSES


class ISOComplianceService:
    """Service for ISO compliance evidence management and auto-tagging."""

    def __init__(self, ai_client: Optional[Any] = None) -> None:
        self.ai_client = ai_client
        self.clauses: Dict[str, ISOClause] = {clause.id: clause for clause in ALL_CLAUSES}

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

        The AI receives the full clause catalog (all standards, all levels)
        and is instructed to return only high-confidence, specific matches
        with evidence snippets explaining each mapping.
        """
        if not self.ai_client:
            logger.debug("AI client not available; falling back to keyword tagging")
            return self.auto_tag_content(content)

        try:
            # Include ALL clauses at all levels and all standards including ISO 27001 Annex A.
            # Previously only level-2 clauses were sent, creating blind spots.
            clause_context = "\n".join(
                f"- {c.id}: [{c.standard.value}] {c.clause_number} — {c.title}" for c in ALL_CLAUSES
            )

            prompt = f"""You are an ISO compliance expert. Analyze the text below and identify which ISO management system clauses it provides evidence for.

ISO CLAUSE CATALOG (id: [standard] number — title):
{clause_context}

TEXT TO ANALYZE:
{content}

INSTRUCTIONS:
1. Only return clauses where the text directly demonstrates conformance or provides evidence.
2. Be precise — prefer specific sub-clauses (e.g. 9001-7.2) over parent clauses (e.g. 9001-7).
3. Confidence 90-100: text explicitly mentions clause requirements or uses standard terminology.
4. Confidence 70-89: text clearly implies the clause even without exact terminology.
5. Confidence 50-69: text is plausibly related but not definitive.
6. Do NOT return clauses just because they share common words like "monitoring" or "risk".
7. Return a valid JSON array ONLY — no other text.

FORMAT: [{{"clause_id": "9001-7.2", "confidence": 85, "evidence_snippet": "brief quote from text"}}]

Return only clauses with confidence >= 60. Maximum 15 results."""

            # Fix: AIClient.complete() takes a prompt string directly; .analyze() takes (text, analysis_type)
            # Use .complete() for free-form prompt-based reasoning.
            response = await self.ai_client.complete(prompt)

            # Strip markdown code fences if model wraps the JSON
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)

            matches = json.loads(cleaned)
            results = []
            for match in matches:
                clause = self.clauses.get(match.get("clause_id", ""))
                if clause:
                    results.append(
                        {
                            "clause_id": clause.id,
                            "clause_number": clause.clause_number,
                            "title": clause.title,
                            "standard": clause.standard.value,
                            "confidence": int(match.get("confidence", 70)),
                            "linked_by": "ai",
                            "evidence_snippet": match.get("evidence_snippet", ""),
                        }
                    )
            # Sort by confidence descending and cap at 15
            results.sort(key=lambda x: x["confidence"], reverse=True)
            return results[:15]

        except json.JSONDecodeError as exc:
            logger.warning("AI tagging: JSON parse failed (%s); falling back to keyword", exc)
            return self.auto_tag_content(content)
        except Exception as exc:
            logger.warning("AI tagging: error (%s); falling back to keyword tagging", exc)
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
                {
                    "clause_id": c.id,
                    "clause_number": c.clause_number,
                    "title": c.title,
                    "standard": c.standard.value,
                }
                for c in no_coverage
            ],
            "by_standard": {
                "iso9001": self._standard_coverage(evidence_links, ISOStandard.ISO_9001),
                "iso14001": self._standard_coverage(evidence_links, ISOStandard.ISO_14001),
                "iso45001": self._standard_coverage(evidence_links, ISOStandard.ISO_45001),
                "iso27001": self._standard_coverage(evidence_links, ISOStandard.ISO_27001),
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

            detail: Dict[str, Any] = {
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

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": coverage,
            "clauses": clause_details,
        }


# Singleton instance
def _make_iso_compliance_service() -> "ISOComplianceService":
    """
    Instantiate ISOComplianceService with a live AI client where possible.
    Falls back to no AI client if the environment is not configured (tests,
    local dev without API keys).  The service's ai_enhanced_tagging() method
    already handles the None-client case gracefully.
    """
    try:
        from src.domain.services.ai_models import get_ai_client

        client = get_ai_client()
        return ISOComplianceService(ai_client=client)
    except Exception as exc:  # noqa: BLE001
        logger.debug("ISO compliance service: AI client unavailable (%s), using keyword fallback", exc)
        return ISOComplianceService()


iso_compliance_service = _make_iso_compliance_service()
