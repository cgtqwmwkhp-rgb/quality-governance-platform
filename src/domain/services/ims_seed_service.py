"""
IMS Module Seed Service

Seeds all five IMS Dashboard modules with real, standards-aligned data
on application startup if the respective tables are empty.

Data sources:
- ISO 9001:2015 clause structure
- ISO 14001:2015 clause structure
- ISO 45001:2018 clause structure
- ISO 27001:2022 clause structure + Annex A (93 controls)
- UVDB Achilles Verify B2 protocol
- Planet Mark / GHG Protocol

Each seed function is idempotent: it checks for existing rows before inserting.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================================================
# CLAUSE DATA — Real ISO standard structures
# ============================================================================

_ISO_9001_CLAUSES: List[Tuple[str, str, str, int, Optional[str]]] = [
    # (clause_number, title, description, level, parent_clause_number)
    ("4", "Context of the organization", "Understanding the organization and its context", 1, None),
    (
        "4.1",
        "Understanding the organization and its context",
        "Determine external and internal issues relevant to purpose and strategic direction",
        2,
        "4",
    ),
    (
        "4.2",
        "Understanding the needs and expectations of interested parties",
        "Determine interested parties and their requirements",
        2,
        "4",
    ),
    ("4.3", "Determining the scope of the QMS", "Determine boundaries and applicability of the QMS", 2, "4"),
    (
        "4.4",
        "Quality management system and its processes",
        "Establish, implement, maintain and improve the QMS",
        2,
        "4",
    ),
    ("5", "Leadership", "Leadership and commitment", 1, None),
    ("5.1", "Leadership and commitment", "Top management shall demonstrate leadership and commitment", 2, "5"),
    ("5.1.1", "General", "Leadership commitment to QMS", 3, "5.1"),
    ("5.1.2", "Customer focus", "Customer requirements and satisfaction", 3, "5.1"),
    ("5.2", "Policy", "Establishing the quality policy", 2, "5"),
    (
        "5.3",
        "Organizational roles, responsibilities and authorities",
        "Assign and communicate roles and responsibilities",
        2,
        "5",
    ),
    ("6", "Planning", "Planning for the QMS", 1, None),
    ("6.1", "Actions to address risks and opportunities", "Determine risks and opportunities and plan actions", 2, "6"),
    (
        "6.2",
        "Quality objectives and planning to achieve them",
        "Establish quality objectives at relevant functions",
        2,
        "6",
    ),
    ("6.3", "Planning of changes", "Changes to QMS shall be carried out in a planned manner", 2, "6"),
    ("7", "Support", "Resources, competence, awareness, communication, documented information", 1, None),
    ("7.1", "Resources", "Determine and provide resources needed", 2, "7"),
    ("7.1.1", "General", "Determine and provide resources", 3, "7.1"),
    ("7.1.2", "People", "Personnel needed for QMS", 3, "7.1"),
    ("7.1.3", "Infrastructure", "Infrastructure needed for operations", 3, "7.1"),
    ("7.1.4", "Environment for the operation of processes", "Work environment needed", 3, "7.1"),
    ("7.1.5", "Monitoring and measuring resources", "Monitoring and measuring equipment", 3, "7.1"),
    ("7.1.6", "Organizational knowledge", "Knowledge needed for processes", 3, "7.1"),
    ("7.2", "Competence", "Determine competence of persons", 2, "7"),
    ("7.3", "Awareness", "Persons shall be aware of quality policy and objectives", 2, "7"),
    ("7.4", "Communication", "Internal and external communications", 2, "7"),
    ("7.5", "Documented information", "Control of documented information", 2, "7"),
    ("8", "Operation", "Operational planning and control", 1, None),
    ("8.1", "Operational planning and control", "Plan, implement and control processes", 2, "8"),
    ("8.2", "Requirements for products and services", "Determine requirements for products and services", 2, "8"),
    ("8.3", "Design and development", "Design and development of products and services", 2, "8"),
    ("8.4", "Control of externally provided processes, products and services", "Control of external providers", 2, "8"),
    ("8.5", "Production and service provision", "Control of production and service provision", 2, "8"),
    ("8.6", "Release of products and services", "Verify requirements have been met", 2, "8"),
    ("8.7", "Control of nonconforming outputs", "Identify and control nonconforming outputs", 2, "8"),
    ("9", "Performance evaluation", "Monitoring, measurement, analysis and evaluation", 1, None),
    (
        "9.1",
        "Monitoring, measurement, analysis and evaluation",
        "Determine what needs to be monitored and measured",
        2,
        "9",
    ),
    ("9.1.2", "Customer satisfaction", "Monitor customer perception", 3, "9.1"),
    ("9.2", "Internal audit", "Conduct internal audits at planned intervals", 2, "9"),
    ("9.3", "Management review", "Top management shall review the QMS", 2, "9"),
    ("10", "Improvement", "Continual improvement", 1, None),
    ("10.1", "General", "Determine opportunities for improvement", 2, "10"),
    ("10.2", "Nonconformity and corrective action", "React to nonconformities and take corrective action", 2, "10"),
    ("10.3", "Continual improvement", "Continually improve the QMS", 2, "10"),
]

_ISO_14001_CLAUSES: List[Tuple[str, str, str, int, Optional[str]]] = [
    ("4", "Context of the organization", "Understanding the organization and its context", 1, None),
    (
        "4.1",
        "Understanding the organization and its context",
        "Determine environmental conditions affecting the organization",
        2,
        "4",
    ),
    (
        "4.2",
        "Understanding needs and expectations of interested parties",
        "Determine interested parties and their environmental requirements",
        2,
        "4",
    ),
    ("4.3", "Determining the scope of the EMS", "Determine boundaries of the EMS", 2, "4"),
    ("4.4", "Environmental management system", "Establish, implement, maintain and improve the EMS", 2, "4"),
    ("5", "Leadership", "Leadership and commitment", 1, None),
    ("5.1", "Leadership and commitment", "Top management commitment to EMS", 2, "5"),
    ("5.2", "Environmental policy", "Establish environmental policy", 2, "5"),
    (
        "5.3",
        "Organizational roles, responsibilities and authorities",
        "Assign roles and responsibilities for EMS",
        2,
        "5",
    ),
    ("6", "Planning", "Planning for the EMS", 1, None),
    (
        "6.1",
        "Actions to address risks and opportunities",
        "Determine environmental aspects and compliance obligations",
        2,
        "6",
    ),
    ("6.1.2", "Environmental aspects", "Identify environmental aspects and significant impacts", 3, "6.1"),
    ("6.1.3", "Compliance obligations", "Identify and access compliance obligations", 3, "6.1"),
    ("6.2", "Environmental objectives and planning", "Establish environmental objectives", 2, "6"),
    ("7", "Support", "Resources, competence, awareness, communication", 1, None),
    ("7.1", "Resources", "Provide resources for EMS", 2, "7"),
    ("7.2", "Competence", "Ensure competence of persons", 2, "7"),
    ("7.3", "Awareness", "Environmental awareness of persons", 2, "7"),
    ("7.4", "Communication", "Internal and external environmental communication", 2, "7"),
    ("7.5", "Documented information", "Control documented information", 2, "7"),
    ("8", "Operation", "Operational planning and control", 1, None),
    ("8.1", "Operational planning and control", "Plan and control operations", 2, "8"),
    ("8.2", "Emergency preparedness and response", "Prepare for and respond to emergencies", 2, "8"),
    ("9", "Performance evaluation", "Monitoring, measurement, analysis", 1, None),
    ("9.1", "Monitoring, measurement, analysis and evaluation", "Monitor environmental performance", 2, "9"),
    ("9.1.2", "Evaluation of compliance", "Evaluate compliance with obligations", 3, "9.1"),
    ("9.2", "Internal audit", "Conduct internal audits", 2, "9"),
    ("9.3", "Management review", "Top management review of EMS", 2, "9"),
    ("10", "Improvement", "Continual improvement", 1, None),
    ("10.2", "Nonconformity and corrective action", "Address nonconformities", 2, "10"),
    ("10.3", "Continual improvement", "Continually improve environmental performance", 2, "10"),
]

_ISO_45001_CLAUSES: List[Tuple[str, str, str, int, Optional[str]]] = [
    ("4", "Context of the organization", "Understanding the organization and its context", 1, None),
    ("4.1", "Understanding the organization and its context", "Determine issues affecting OH&S performance", 2, "4"),
    (
        "4.2",
        "Understanding needs and expectations of workers and interested parties",
        "Determine interested parties including workers",
        2,
        "4",
    ),
    ("4.3", "Determining the scope of the OH&S management system", "Determine scope of the OHSMS", 2, "4"),
    ("4.4", "OH&S management system", "Establish, implement, maintain the OHSMS", 2, "4"),
    ("5", "Leadership and worker participation", "Leadership, worker participation", 1, None),
    ("5.1", "Leadership and commitment", "Top management leadership and commitment", 2, "5"),
    ("5.2", "OH&S policy", "Establish OH&S policy", 2, "5"),
    ("5.3", "Organizational roles, responsibilities and authorities", "Assign roles and responsibilities", 2, "5"),
    ("5.4", "Consultation and participation of workers", "Consult and enable worker participation", 2, "5"),
    ("6", "Planning", "Planning for the OHSMS", 1, None),
    ("6.1", "Actions to address risks and opportunities", "Determine hazards, risks, opportunities", 2, "6"),
    (
        "6.1.2",
        "Hazard identification and assessment of risks and opportunities",
        "Identify hazards and assess OH&S risks",
        3,
        "6.1",
    ),
    (
        "6.1.3",
        "Determination of legal requirements and other requirements",
        "Determine legal and other requirements",
        3,
        "6.1",
    ),
    ("6.1.4", "Planning action", "Plan actions to address risks and opportunities", 3, "6.1"),
    ("6.2", "OH&S objectives and planning to achieve them", "Establish OH&S objectives", 2, "6"),
    ("7", "Support", "Resources, competence, awareness, communication", 1, None),
    ("7.1", "Resources", "Provide resources for OHSMS", 2, "7"),
    ("7.2", "Competence", "Ensure competence of persons", 2, "7"),
    ("7.3", "Awareness", "Worker awareness of OH&S", 2, "7"),
    ("7.4", "Communication", "Internal and external OH&S communication", 2, "7"),
    ("7.5", "Documented information", "Control documented information", 2, "7"),
    ("8", "Operation", "Operational planning and control", 1, None),
    ("8.1", "Operational planning and control", "Plan and control operations", 2, "8"),
    ("8.1.2", "Eliminating hazards and reducing OH&S risks", "Apply hierarchy of controls", 3, "8.1"),
    ("8.1.3", "Management of change", "Manage changes affecting OH&S", 3, "8.1"),
    ("8.1.4", "Procurement", "Control procurement of products and services", 3, "8.1"),
    ("8.2", "Emergency preparedness and response", "Prepare for and respond to emergencies", 2, "8"),
    ("9", "Performance evaluation", "Monitoring, measurement, analysis", 1, None),
    ("9.1", "Monitoring, measurement, analysis and performance evaluation", "Monitor OH&S performance", 2, "9"),
    ("9.1.2", "Evaluation of compliance", "Evaluate compliance with legal requirements", 3, "9.1"),
    ("9.2", "Internal audit", "Conduct internal audits", 2, "9"),
    ("9.3", "Management review", "Top management review", 2, "9"),
    ("10", "Improvement", "Incident investigation, nonconformity, continual improvement", 1, None),
    (
        "10.2",
        "Incident, nonconformity and corrective action",
        "Investigate incidents and take corrective action",
        2,
        "10",
    ),
    ("10.3", "Continual improvement", "Continually improve OH&S performance", 2, "10"),
]

_ISO_27001_CLAUSES: List[Tuple[str, str, str, int, Optional[str]]] = [
    (
        "4",
        "Context of the organization",
        "Understanding the organization and its context for information security",
        1,
        None,
    ),
    (
        "4.1",
        "Understanding the organization and its context",
        "Determine external and internal issues relevant to information security",
        2,
        "4",
    ),
    (
        "4.2",
        "Understanding the needs and expectations of interested parties",
        "Determine interested parties and their information security requirements",
        2,
        "4",
    ),
    ("4.3", "Determining the scope of the ISMS", "Determine boundaries and applicability of the ISMS", 2, "4"),
    (
        "4.4",
        "Information security management system",
        "Establish, implement, maintain and continually improve the ISMS",
        2,
        "4",
    ),
    ("5", "Leadership", "Leadership and commitment for information security", 1, None),
    (
        "5.1",
        "Leadership and commitment",
        "Top management shall demonstrate leadership and commitment to the ISMS",
        2,
        "5",
    ),
    ("5.2", "Policy", "Establish information security policy", 2, "5"),
    (
        "5.3",
        "Organizational roles, responsibilities and authorities",
        "Assign and communicate roles and responsibilities for information security",
        2,
        "5",
    ),
    ("6", "Planning", "Planning for the ISMS", 1, None),
    ("6.1", "Actions to address risks and opportunities", "Determine risks and opportunities and plan actions", 2, "6"),
    ("6.1.1", "General", "Consider issues and requirements when planning the ISMS", 3, "6.1"),
    (
        "6.1.2",
        "Information security risk assessment",
        "Define and apply information security risk assessment process",
        3,
        "6.1",
    ),
    ("6.1.3", "Information security risk treatment", "Define and apply risk treatment process", 3, "6.1"),
    (
        "6.2",
        "Information security objectives and planning to achieve them",
        "Establish information security objectives",
        2,
        "6",
    ),
    ("6.3", "Planning of changes", "Changes to ISMS shall be carried out in a planned manner", 2, "6"),
    ("7", "Support", "Resources, competence, awareness, communication, documented information", 1, None),
    ("7.1", "Resources", "Determine and provide resources for ISMS", 2, "7"),
    ("7.2", "Competence", "Determine competence of persons affecting information security", 2, "7"),
    ("7.3", "Awareness", "Persons shall be aware of information security policy", 2, "7"),
    ("7.4", "Communication", "Determine internal and external communications for ISMS", 2, "7"),
    ("7.5", "Documented information", "ISMS shall include required documented information", 2, "7"),
    ("8", "Operation", "Operational planning and control", 1, None),
    ("8.1", "Operational planning and control", "Plan, implement and control processes for ISMS", 2, "8"),
    ("8.2", "Information security risk assessment", "Perform risk assessments at planned intervals", 2, "8"),
    ("8.3", "Information security risk treatment", "Implement risk treatment plan", 2, "8"),
    ("9", "Performance evaluation", "Monitoring, measurement, analysis and evaluation", 1, None),
    (
        "9.1",
        "Monitoring, measurement, analysis and evaluation",
        "Determine what needs to be monitored and measured",
        2,
        "9",
    ),
    ("9.2", "Internal audit", "Conduct internal audits at planned intervals", 2, "9"),
    ("9.3", "Management review", "Top management shall review the ISMS", 2, "9"),
    ("10", "Improvement", "Nonconformity, corrective action, continual improvement", 1, None),
    ("10.1", "Continual improvement", "Continually improve the ISMS", 2, "10"),
    ("10.2", "Nonconformity and corrective action", "React to nonconformities and take corrective action", 2, "10"),
]

# ISO 27001:2022 Annex A — all 93 controls
# (control_id, name, description, domain, category, control_type)
_ISO_27001_ANNEX_A: List[Tuple[str, str, str, str, str, str]] = [
    # A.5 Organisational controls (37 controls)
    (
        "A.5.1",
        "Policies for information security",
        "Information security policy and topic-specific policies shall be defined, approved by management, published, communicated to and acknowledged by relevant personnel and relevant interested parties, and reviewed at planned intervals or if significant changes occur.",
        "organizational",
        "Governance",
        "preventive",
    ),
    (
        "A.5.2",
        "Information security roles and responsibilities",
        "Information security roles and responsibilities shall be defined and allocated.",
        "organizational",
        "Governance",
        "preventive",
    ),
    (
        "A.5.3",
        "Segregation of duties",
        "Conflicting duties and conflicting areas of responsibility shall be segregated.",
        "organizational",
        "Governance",
        "preventive",
    ),
    (
        "A.5.4",
        "Management responsibilities",
        "Management shall require all personnel to apply information security in accordance with the established information security policy, topic-specific policies and procedures of the organization.",
        "organizational",
        "Governance",
        "preventive",
    ),
    (
        "A.5.5",
        "Contact with authorities",
        "The organization shall establish and maintain contact with relevant authorities.",
        "organizational",
        "Governance",
        "preventive",
    ),
    (
        "A.5.6",
        "Contact with special interest groups",
        "The organization shall establish and maintain contact with special interest groups or other specialist security forums and professional associations.",
        "organizational",
        "Governance",
        "preventive",
    ),
    (
        "A.5.7",
        "Threat intelligence",
        "Information relating to information security threats shall be collected and analysed to produce threat intelligence.",
        "organizational",
        "Defence",
        "preventive",
    ),
    (
        "A.5.8",
        "Information security in project management",
        "Information security shall be integrated into project management.",
        "organizational",
        "Governance",
        "preventive",
    ),
    (
        "A.5.9",
        "Inventory of information and other associated assets",
        "An inventory of information and other associated assets, including owners, shall be developed and maintained.",
        "organizational",
        "Asset management",
        "preventive",
    ),
    (
        "A.5.10",
        "Acceptable use of information and other associated assets",
        "Rules for the acceptable use and procedures for handling information and other associated assets shall be identified, documented and implemented.",
        "organizational",
        "Asset management",
        "preventive",
    ),
    (
        "A.5.11",
        "Return of assets",
        "Personnel and other interested parties as appropriate shall return all the organization's assets in their possession upon change or termination of their employment, contract or agreement.",
        "organizational",
        "Asset management",
        "preventive",
    ),
    (
        "A.5.12",
        "Classification of information",
        "Information shall be classified according to the information security needs of the organization based on confidentiality, integrity, availability and relevant interested party requirements.",
        "organizational",
        "Information protection",
        "preventive",
    ),
    (
        "A.5.13",
        "Labelling of information",
        "An appropriate set of procedures for information labelling shall be developed and implemented in accordance with the information classification scheme adopted by the organization.",
        "organizational",
        "Information protection",
        "preventive",
    ),
    (
        "A.5.14",
        "Information transfer",
        "Information transfer rules, procedures, or agreements shall be in place for all types of transfer facilities within the organization and between the organization and other parties.",
        "organizational",
        "Information protection",
        "preventive",
    ),
    (
        "A.5.15",
        "Access control",
        "Rules to control physical and logical access to information and other associated assets shall be established and implemented based on business and information security requirements.",
        "organizational",
        "Identity and access management",
        "preventive",
    ),
    (
        "A.5.16",
        "Identity management",
        "The full life cycle of identities shall be managed.",
        "organizational",
        "Identity and access management",
        "preventive",
    ),
    (
        "A.5.17",
        "Authentication information",
        "Allocation and management of authentication information shall be controlled by a management process, including advising personnel on appropriate handling of authentication information.",
        "organizational",
        "Identity and access management",
        "preventive",
    ),
    (
        "A.5.18",
        "Access rights",
        "Access rights to information and other associated assets shall be provisioned, reviewed, modified and removed in accordance with the organization's topic-specific policy on and rules for access control.",
        "organizational",
        "Identity and access management",
        "preventive",
    ),
    (
        "A.5.19",
        "Information security in supplier relationships",
        "Processes and procedures shall be defined and implemented to manage the information security risks associated with the use of supplier's products or services.",
        "organizational",
        "Supplier relationships",
        "preventive",
    ),
    (
        "A.5.20",
        "Addressing information security within supplier agreements",
        "Relevant information security requirements shall be established and agreed with each supplier based on the type of supplier relationship.",
        "organizational",
        "Supplier relationships",
        "preventive",
    ),
    (
        "A.5.21",
        "Managing information security in the ICT supply chain",
        "Processes and procedures shall be defined and implemented to manage the information security risks associated with the ICT products and services supply chain.",
        "organizational",
        "Supplier relationships",
        "preventive",
    ),
    (
        "A.5.22",
        "Monitoring, review and change management of supplier services",
        "The organization shall regularly monitor, review, evaluate and manage change in supplier information security practices and service delivery.",
        "organizational",
        "Supplier relationships",
        "detective",
    ),
    (
        "A.5.23",
        "Information security for use of cloud services",
        "Processes for acquisition, use, management and exit from cloud services shall be established in accordance with the organization's information security requirements.",
        "organizational",
        "Supplier relationships",
        "preventive",
    ),
    (
        "A.5.24",
        "Information security incident management planning and preparation",
        "The organization shall plan and prepare for managing information security incidents by defining, establishing and communicating information security incident management processes, roles and responsibilities.",
        "organizational",
        "Incident management",
        "preventive",
    ),
    (
        "A.5.25",
        "Assessment and decision on information security events",
        "The organization shall assess information security events and decide if they are to be categorized as information security incidents.",
        "organizational",
        "Incident management",
        "detective",
    ),
    (
        "A.5.26",
        "Response to information security incidents",
        "Information security incidents shall be responded to in accordance with the documented procedures.",
        "organizational",
        "Incident management",
        "corrective",
    ),
    (
        "A.5.27",
        "Learning from information security incidents",
        "Knowledge gained from information security incidents shall be used to strengthen and improve the information security controls.",
        "organizational",
        "Incident management",
        "corrective",
    ),
    (
        "A.5.28",
        "Collection of evidence",
        "The organization shall establish and implement procedures for the identification, collection, acquisition and preservation of evidence related to information security events.",
        "organizational",
        "Incident management",
        "detective",
    ),
    (
        "A.5.29",
        "Information security during disruption",
        "The organization shall plan how to maintain information security at an appropriate level during disruption.",
        "organizational",
        "Business continuity",
        "preventive",
    ),
    (
        "A.5.30",
        "ICT readiness for business continuity",
        "ICT readiness shall be planned, implemented, maintained and tested based on business continuity objectives and ICT continuity requirements.",
        "organizational",
        "Business continuity",
        "preventive",
    ),
    (
        "A.5.31",
        "Legal, statutory, regulatory and contractual requirements",
        "Legal, statutory, regulatory and contractual requirements relevant to information security and the organization's approach to meet these requirements shall be identified, documented and kept up to date.",
        "organizational",
        "Compliance",
        "preventive",
    ),
    (
        "A.5.32",
        "Intellectual property rights",
        "The organization shall implement appropriate procedures to protect intellectual property rights.",
        "organizational",
        "Compliance",
        "preventive",
    ),
    (
        "A.5.33",
        "Protection of records",
        "Records shall be protected from loss, destruction, falsification, unauthorized access and unauthorized release.",
        "organizational",
        "Compliance",
        "preventive",
    ),
    (
        "A.5.34",
        "Privacy and protection of personal information",
        "The organization shall identify and meet the requirements regarding the preservation of privacy and protection of personal information as applicable according to relevant laws and regulations and contractual requirements.",
        "organizational",
        "Compliance",
        "preventive",
    ),
    (
        "A.5.35",
        "Independent review of information security",
        "The organization's approach to managing information security and its implementation including people, processes and technologies shall be reviewed independently at planned intervals, or when significant changes occur.",
        "organizational",
        "Assurance",
        "detective",
    ),
    (
        "A.5.36",
        "Compliance with policies, rules and standards for information security",
        "Compliance with the organization's established information security policy, topic-specific policies, rules and standards shall be regularly reviewed.",
        "organizational",
        "Assurance",
        "detective",
    ),
    (
        "A.5.37",
        "Documented operating procedures",
        "Operating procedures for information processing facilities shall be documented and made available to personnel who need them.",
        "organizational",
        "Governance",
        "preventive",
    ),
    # A.6 People controls (8 controls)
    (
        "A.6.1",
        "Screening",
        "Background verification checks on all candidates to become personnel shall be carried out prior to joining the organization and on an ongoing basis taking into consideration applicable laws, regulations and ethics and be proportional to the business requirements, the classification of the information to be accessed and the perceived risks.",
        "people",
        "HR security",
        "preventive",
    ),
    (
        "A.6.2",
        "Terms and conditions of employment",
        "The employment contractual agreements shall state the personnel's and the organization's responsibilities for information security.",
        "people",
        "HR security",
        "preventive",
    ),
    (
        "A.6.3",
        "Information security awareness, education and training",
        "Personnel of the organization and relevant interested parties shall receive appropriate information security awareness, education and training and regular updates of the organization's information security policy, topic-specific policies and procedures, as relevant for their job function.",
        "people",
        "HR security",
        "preventive",
    ),
    (
        "A.6.4",
        "Disciplinary process",
        "A disciplinary process shall be formalized and communicated to take actions against personnel and other relevant interested parties who have committed an information security policy violation.",
        "people",
        "HR security",
        "corrective",
    ),
    (
        "A.6.5",
        "Responsibilities after termination or change of employment",
        "Information security responsibilities and duties that remain valid after termination or change of employment shall be defined, enforced and communicated to relevant personnel and other interested parties.",
        "people",
        "HR security",
        "preventive",
    ),
    (
        "A.6.6",
        "Confidentiality or non-disclosure agreements",
        "Confidentiality or non-disclosure agreements reflecting the organization's needs for the protection of information shall be identified, documented, regularly reviewed and signed by personnel and other relevant interested parties.",
        "people",
        "HR security",
        "preventive",
    ),
    (
        "A.6.7",
        "Remote working",
        "Security measures shall be implemented when personnel are working remotely to protect information accessed, processed or stored outside the organization's premises.",
        "people",
        "HR security",
        "preventive",
    ),
    (
        "A.6.8",
        "Information security event reporting",
        "The organization shall provide a mechanism for personnel to report observed or suspected information security events through appropriate channels in a timely manner.",
        "people",
        "HR security",
        "detective",
    ),
    # A.7 Physical controls (14 controls)
    (
        "A.7.1",
        "Physical security perimeters",
        "Security perimeters shall be defined and used to protect areas that contain information and other associated assets.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.2",
        "Physical entry",
        "Secure areas shall be protected by appropriate entry controls and access points.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.3",
        "Securing offices, rooms and facilities",
        "Physical security for offices, rooms and facilities shall be designed and implemented.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.4",
        "Physical security monitoring",
        "Premises shall be continuously monitored for unauthorized physical access.",
        "physical",
        "Physical security",
        "detective",
    ),
    (
        "A.7.5",
        "Protecting against physical and environmental threats",
        "Protection against physical and environmental threats, such as natural disasters and other intentional or unintentional physical threats to infrastructure shall be designed and implemented.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.6",
        "Working in secure areas",
        "Security measures for working in secure areas shall be designed and implemented.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.7",
        "Clear desk and clear screen",
        "Clear desk rules for papers and removable storage media and clear screen rules for information processing facilities shall be defined and appropriately enforced.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.8",
        "Equipment siting and protection",
        "Equipment shall be sited securely and protected.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.9",
        "Security of assets off-premises",
        "Off-site assets shall be protected.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.10",
        "Storage media",
        "Storage media shall be managed through their life cycle of acquisition, use, transportation and disposal in accordance with the organization's classification scheme and handling requirements.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.11",
        "Supporting utilities",
        "Information processing facilities shall be protected from power failures and other disruptions caused by failures in supporting utilities.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.12",
        "Cabling security",
        "Cables carrying power, data or supporting information services shall be protected from interception, interference or damage.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.13",
        "Equipment maintenance",
        "Equipment shall be maintained correctly to ensure availability, integrity and confidentiality of information.",
        "physical",
        "Physical security",
        "preventive",
    ),
    (
        "A.7.14",
        "Secure disposal or re-use of equipment",
        "Items of equipment containing storage media shall be verified to ensure that any sensitive data and licensed software has been removed or securely overwritten prior to disposal or re-use.",
        "physical",
        "Physical security",
        "preventive",
    ),
    # A.8 Technological controls (34 controls)
    (
        "A.8.1",
        "User endpoint devices",
        "Information stored on, processed by or accessible via user endpoint devices shall be protected.",
        "technological",
        "Endpoint security",
        "preventive",
    ),
    (
        "A.8.2",
        "Privileged access rights",
        "The allocation and use of privileged access rights shall be restricted and managed.",
        "technological",
        "Identity and access management",
        "preventive",
    ),
    (
        "A.8.3",
        "Information access restriction",
        "Access to information and other associated assets shall be restricted in accordance with the established topic-specific policy on access control.",
        "technological",
        "Identity and access management",
        "preventive",
    ),
    (
        "A.8.4",
        "Access to source code",
        "Read and write access to source code, development tools and software libraries shall be appropriately managed.",
        "technological",
        "Application security",
        "preventive",
    ),
    (
        "A.8.5",
        "Secure authentication",
        "Secure authentication technologies and procedures shall be established and implemented based on information access restrictions and the topic-specific policy on access control.",
        "technological",
        "Identity and access management",
        "preventive",
    ),
    (
        "A.8.6",
        "Capacity management",
        "The use of resources shall be monitored and adjusted in line with current and expected capacity requirements.",
        "technological",
        "System security",
        "preventive",
    ),
    (
        "A.8.7",
        "Protection against malware",
        "Protection against malware shall be implemented and supported by appropriate user awareness.",
        "technological",
        "Threat protection",
        "preventive",
    ),
    (
        "A.8.8",
        "Management of technical vulnerabilities",
        "Information about technical vulnerabilities of information systems in use shall be obtained, the organization's exposure to such vulnerabilities shall be evaluated and appropriate measures shall be taken.",
        "technological",
        "Threat protection",
        "preventive",
    ),
    (
        "A.8.9",
        "Configuration management",
        "Configurations, including security configurations, of hardware, software, services and networks shall be established, documented, implemented, monitored and reviewed.",
        "technological",
        "System security",
        "preventive",
    ),
    (
        "A.8.10",
        "Information deletion",
        "Information stored in information systems, devices or in any other storage media shall be deleted when no longer required.",
        "technological",
        "Information protection",
        "preventive",
    ),
    (
        "A.8.11",
        "Data masking",
        "Data masking shall be used in accordance with the organization's topic-specific policy on access control and other related topic-specific policies, and business requirements, taking applicable legislation into consideration.",
        "technological",
        "Information protection",
        "preventive",
    ),
    (
        "A.8.12",
        "Data leakage prevention",
        "Data leakage prevention measures shall be applied to systems, networks and any other devices that process, store or transmit sensitive information.",
        "technological",
        "Information protection",
        "preventive",
    ),
    (
        "A.8.13",
        "Information backup",
        "Backup copies of information, software and systems shall be maintained and regularly tested in accordance with the agreed topic-specific policy on backup.",
        "technological",
        "System security",
        "preventive",
    ),
    (
        "A.8.14",
        "Redundancy of information processing facilities",
        "Information processing facilities shall be implemented with redundancy sufficient to meet availability requirements.",
        "technological",
        "System security",
        "preventive",
    ),
    (
        "A.8.15",
        "Logging",
        "Logs that record activities, exceptions, faults and other relevant events shall be produced, stored, protected and analysed.",
        "technological",
        "Security operations",
        "detective",
    ),
    (
        "A.8.16",
        "Monitoring activities",
        "Networks, systems and applications shall be monitored for anomalous behaviour and appropriate actions taken to evaluate potential information security incidents.",
        "technological",
        "Security operations",
        "detective",
    ),
    (
        "A.8.17",
        "Clock synchronization",
        "The clocks of information processing systems used by the organization shall be synchronized to approved time sources.",
        "technological",
        "Security operations",
        "preventive",
    ),
    (
        "A.8.18",
        "Use of privileged utility programs",
        "The use of utility programs that can be capable of overriding system and application controls shall be restricted and tightly controlled.",
        "technological",
        "System security",
        "preventive",
    ),
    (
        "A.8.19",
        "Installation of software on operational systems",
        "Procedures and measures shall be implemented to securely manage software installation on operational systems.",
        "technological",
        "System security",
        "preventive",
    ),
    (
        "A.8.20",
        "Networks security",
        "Networks and network devices shall be secured, managed and controlled to protect information in systems and applications.",
        "technological",
        "Network security",
        "preventive",
    ),
    (
        "A.8.21",
        "Security of network services",
        "Security mechanisms, service levels and service requirements of network services shall be identified, implemented and monitored.",
        "technological",
        "Network security",
        "preventive",
    ),
    (
        "A.8.22",
        "Segregation of networks",
        "Groups of information services, users and information systems shall be segregated in the organization's networks.",
        "technological",
        "Network security",
        "preventive",
    ),
    (
        "A.8.23",
        "Web filtering",
        "Access to external websites shall be managed to reduce exposure to malicious content.",
        "technological",
        "Network security",
        "preventive",
    ),
    (
        "A.8.24",
        "Use of cryptography",
        "Rules for the effective use of cryptography, including cryptographic key management, shall be defined and implemented.",
        "technological",
        "Cryptography",
        "preventive",
    ),
    (
        "A.8.25",
        "Secure development life cycle",
        "Rules for the secure development of software and systems shall be established and applied.",
        "technological",
        "Application security",
        "preventive",
    ),
    (
        "A.8.26",
        "Application security requirements",
        "Information security requirements shall be identified, specified and approved when developing or acquiring applications.",
        "technological",
        "Application security",
        "preventive",
    ),
    (
        "A.8.27",
        "Secure system architecture and engineering principles",
        "Principles for engineering secure systems shall be established, documented, maintained and applied to any information system development activities.",
        "technological",
        "Application security",
        "preventive",
    ),
    (
        "A.8.28",
        "Secure coding",
        "Secure coding principles shall be applied to software development.",
        "technological",
        "Application security",
        "preventive",
    ),
    (
        "A.8.29",
        "Security testing in development and acceptance",
        "Security testing processes shall be defined and implemented in the development life cycle.",
        "technological",
        "Application security",
        "detective",
    ),
    (
        "A.8.30",
        "Outsourced development",
        "The organization shall direct, monitor and review the activities related to outsourced system development.",
        "technological",
        "Application security",
        "preventive",
    ),
    (
        "A.8.31",
        "Separation of development, test and production environments",
        "Development, testing and production environments shall be separated and secured.",
        "technological",
        "Application security",
        "preventive",
    ),
    (
        "A.8.32",
        "Change management",
        "Changes to information processing facilities and information systems shall be subject to change management procedures.",
        "technological",
        "System security",
        "preventive",
    ),
    (
        "A.8.33",
        "Test information",
        "Test information shall be appropriately selected, protected and managed.",
        "technological",
        "Application security",
        "preventive",
    ),
    (
        "A.8.34",
        "Protection of information systems during audit testing",
        "Audit tests and other assurance activities involving assessment of operational systems shall be planned and agreed between the tester and appropriate management.",
        "technological",
        "Assurance",
        "preventive",
    ),
]


# ============================================================================
# SEED FUNCTIONS
# ============================================================================


async def _seed_standards_library(db: AsyncSession) -> None:
    """Seed ISO 9001, 14001, 45001, 27001 into standards/clauses/controls."""
    from src.domain.models.standard import Clause, Control, Standard

    count = await db.scalar(select(func.count()).select_from(Standard))
    if count and count > 0:
        logger.info("Standards already seeded (%d rows), skipping", count)
        return

    logger.info("Seeding Standards Library with ISO 9001, 14001, 45001, 27001")

    standards_spec: List[Dict[str, Any]] = [
        {
            "code": "ISO9001",
            "name": "ISO 9001:2015",
            "full_name": "Quality Management System",
            "version": "2015",
            "description": "Requirements for a quality management system to demonstrate ability to consistently provide products and services that meet customer and regulatory requirements.",
            "effective_date": "2015-09-15",
            "clauses": _ISO_9001_CLAUSES,
        },
        {
            "code": "ISO14001",
            "name": "ISO 14001:2015",
            "full_name": "Environmental Management System",
            "version": "2015",
            "description": "Requirements for an environmental management system to enhance environmental performance, fulfill compliance obligations, and achieve environmental objectives.",
            "effective_date": "2015-09-15",
            "clauses": _ISO_14001_CLAUSES,
        },
        {
            "code": "ISO45001",
            "name": "ISO 45001:2018",
            "full_name": "Occupational Health and Safety Management System",
            "version": "2018",
            "description": "Requirements for an OH&S management system to prevent work-related injury and ill health to workers and to provide safe and healthy workplaces.",
            "effective_date": "2018-03-12",
            "clauses": _ISO_45001_CLAUSES,
        },
        {
            "code": "ISO27001",
            "name": "ISO 27001:2022",
            "full_name": "Information Security Management System",
            "version": "2022",
            "description": "Requirements for establishing, implementing, maintaining and continually improving an information security management system.",
            "effective_date": "2022-10-25",
            "clauses": _ISO_27001_CLAUSES,
        },
    ]

    for spec in standards_spec:
        std = Standard(
            code=spec["code"],
            name=spec["name"],
            full_name=spec["full_name"],
            version=spec["version"],
            description=spec["description"],
            effective_date=spec["effective_date"],
            is_active=True,
        )
        db.add(std)
        await db.flush()

        clause_map: Dict[str, int] = {}
        clause_data = spec["clauses"]

        for sort_idx, (num, title, desc, level, parent_num) in enumerate(clause_data):
            parent_id = clause_map.get(parent_num) if parent_num else None
            clause = Clause(
                standard_id=std.id,
                clause_number=num,
                title=title,
                description=desc,
                level=level,
                sort_order=sort_idx,
                parent_clause_id=parent_id,
                is_active=True,
            )
            db.add(clause)
            await db.flush()
            clause_map[num] = clause.id

        leaf_clauses = _get_leaf_clauses(clause_data)
        for num in leaf_clauses:
            clause_id = clause_map.get(num)
            if clause_id:
                title_for_clause = next(t for n, t, _d, _l, _p in clause_data if n == num)
                control = Control(
                    clause_id=clause_id,
                    control_number=f"{num}.1",
                    title=f"Compliance with {title_for_clause}",
                    description=f"Assess and implement requirements for clause {num}.",
                    is_active=True,
                    is_applicable=True,
                    implementation_status="not_implemented",
                )
                db.add(control)

        await db.flush()
        logger.info("  Seeded %s with %d clauses", spec["code"], len(clause_data))


def _get_leaf_clauses(
    clauses: List[Tuple[str, str, str, int, Optional[str]]],
) -> List[str]:
    """Return clause numbers that have no children (leaf nodes)."""
    parent_set = {parent for _, _, _, _, parent in clauses if parent}
    return [num for num, _, _, _, _ in clauses if num not in parent_set]


async def _seed_iso27001_controls(db: AsyncSession) -> None:
    """Seed ISO 27001:2022 Annex A controls into the ISMS module."""
    from src.domain.models.iso27001 import ISO27001Control

    count = await db.scalar(select(func.count()).select_from(ISO27001Control))
    if count and count > 0:
        logger.info("ISO 27001 controls already seeded (%d rows), skipping", count)
        return

    logger.info("Seeding ISO 27001:2022 Annex A controls (93 controls)")

    for ctrl_id, name, desc, domain, category, ctrl_type in _ISO_27001_ANNEX_A:
        control = ISO27001Control(
            control_id=ctrl_id,
            control_name=name,
            control_description=desc,
            domain=domain,
            category=category,
            control_type=ctrl_type,
            implementation_status="not_implemented",
            is_applicable=True,
            information_security_properties=["Confidentiality", "Integrity", "Availability"],
        )
        db.add(control)

    await db.flush()
    logger.info("  Seeded %d Annex A controls", len(_ISO_27001_ANNEX_A))


async def _seed_uvdb_baseline(db: AsyncSession) -> None:
    """Seed a baseline UVDB Achilles Verify B2 audit."""
    from src.domain.models.uvdb_achilles import UVDBAudit

    count = await db.scalar(select(func.count()).select_from(UVDBAudit))
    if count and count > 0:
        logger.info("UVDB audits already exist (%d rows), skipping", count)
        return

    logger.info("Seeding UVDB Achilles baseline B2 audit")

    now = datetime.utcnow()
    audit = UVDBAudit(
        audit_reference=f"UVDB-B2-{now.year}-001",
        company_name="Organisation",
        audit_type="B2",
        audit_scope="Full Verify B2 qualification audit covering quality, health & safety, and environmental management.",
        audit_date=now + timedelta(days=30),
        next_audit_due=now + timedelta(days=365),
        status="scheduled",
        max_possible_score=225.0,
    )
    db.add(audit)
    await db.flush()
    logger.info("  Seeded UVDB audit: %s", audit.audit_reference)


async def _seed_planet_mark_year(db: AsyncSession) -> None:
    """Seed a baseline Planet Mark carbon reporting year."""
    from src.domain.models.planet_mark import CarbonReportingYear

    count = await db.scalar(select(func.count()).select_from(CarbonReportingYear))
    if count and count > 0:
        logger.info("Planet Mark years already exist (%d rows), skipping", count)
        return

    logger.info("Seeding Planet Mark baseline reporting year")

    now = datetime.utcnow()
    year_start = datetime(now.year - 1, 4, 1)
    year_end = datetime(now.year, 3, 31)

    reporting_year = CarbonReportingYear(
        year_label=f"YE{now.year}",
        year_number=1,
        period_start=year_start,
        period_end=year_end,
        organization_name="Organisation",
        average_fte=50.0,
        is_baseline_year=True,
        certification_status="draft",
        reduction_target_percent=5.0,
    )
    db.add(reporting_year)
    await db.flush()
    logger.info("  Seeded Planet Mark year: %s", reporting_year.year_label)


# ============================================================================
# CROSS-STANDARD MAPPING DATA
# ============================================================================

_CROSS_STANDARD_MAPPINGS: List[Dict[str, str]] = [
    # Leadership mappings
    {
        "source_standard": "ISO 9001",
        "source_clause": "5.1",
        "target_standard": "ISO 14001",
        "target_clause": "5.1",
        "relationship": "equivalent",
        "description": "Leadership and commitment",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "5.1",
        "target_standard": "ISO 45001",
        "target_clause": "5.1",
        "relationship": "equivalent",
        "description": "Leadership and commitment",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "5.1",
        "target_standard": "ISO 27001",
        "target_clause": "5.1",
        "relationship": "equivalent",
        "description": "Leadership and commitment",
    },
    # Context of the organization
    {
        "source_standard": "ISO 9001",
        "source_clause": "4.1",
        "target_standard": "ISO 14001",
        "target_clause": "4.1",
        "relationship": "equivalent",
        "description": "Understanding the organization and its context",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "4.1",
        "target_standard": "ISO 45001",
        "target_clause": "4.1",
        "relationship": "equivalent",
        "description": "Understanding the organization and its context",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "4.1",
        "target_standard": "ISO 27001",
        "target_clause": "4.1",
        "relationship": "equivalent",
        "description": "Understanding the organization and its context",
    },
    # Interested parties
    {
        "source_standard": "ISO 9001",
        "source_clause": "4.2",
        "target_standard": "ISO 14001",
        "target_clause": "4.2",
        "relationship": "equivalent",
        "description": "Understanding needs and expectations of interested parties",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "4.2",
        "target_standard": "ISO 45001",
        "target_clause": "4.2",
        "relationship": "equivalent",
        "description": "Understanding needs and expectations of interested parties",
    },
    # Risk and opportunity (Planning)
    {
        "source_standard": "ISO 9001",
        "source_clause": "6.1",
        "target_standard": "ISO 14001",
        "target_clause": "6.1",
        "relationship": "equivalent",
        "description": "Actions to address risks and opportunities",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "6.1",
        "target_standard": "ISO 45001",
        "target_clause": "6.1",
        "relationship": "equivalent",
        "description": "Actions to address risks and opportunities",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "6.1",
        "target_standard": "ISO 27001",
        "target_clause": "6.1",
        "relationship": "equivalent",
        "description": "Actions to address risks and opportunities",
    },
    # Corrective action
    {
        "source_standard": "ISO 9001",
        "source_clause": "10.2",
        "target_standard": "ISO 14001",
        "target_clause": "10.2",
        "relationship": "equivalent",
        "description": "Nonconformity and corrective action",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "10.2",
        "target_standard": "ISO 45001",
        "target_clause": "10.2",
        "relationship": "equivalent",
        "description": "Incident, nonconformity and corrective action",
    },
    # Internal audit
    {
        "source_standard": "ISO 9001",
        "source_clause": "9.2",
        "target_standard": "ISO 14001",
        "target_clause": "9.2",
        "relationship": "equivalent",
        "description": "Internal audit",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "9.2",
        "target_standard": "ISO 45001",
        "target_clause": "9.2",
        "relationship": "equivalent",
        "description": "Internal audit",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "9.2",
        "target_standard": "ISO 27001",
        "target_clause": "9.2",
        "relationship": "equivalent",
        "description": "Internal audit",
    },
    # Management review
    {
        "source_standard": "ISO 9001",
        "source_clause": "9.3",
        "target_standard": "ISO 14001",
        "target_clause": "9.3",
        "relationship": "equivalent",
        "description": "Management review",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "9.3",
        "target_standard": "ISO 45001",
        "target_clause": "9.3",
        "relationship": "equivalent",
        "description": "Management review",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "9.3",
        "target_standard": "ISO 27001",
        "target_clause": "9.3",
        "relationship": "equivalent",
        "description": "Management review",
    },
    # Competence
    {
        "source_standard": "ISO 9001",
        "source_clause": "7.2",
        "target_standard": "ISO 14001",
        "target_clause": "7.2",
        "relationship": "equivalent",
        "description": "Competence",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "7.2",
        "target_standard": "ISO 45001",
        "target_clause": "7.2",
        "relationship": "equivalent",
        "description": "Competence",
    },
    # Documented information
    {
        "source_standard": "ISO 9001",
        "source_clause": "7.5",
        "target_standard": "ISO 14001",
        "target_clause": "7.5",
        "relationship": "equivalent",
        "description": "Documented information",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "7.5",
        "target_standard": "ISO 45001",
        "target_clause": "7.5",
        "relationship": "equivalent",
        "description": "Documented information",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "7.5",
        "target_standard": "ISO 27001",
        "target_clause": "7.5",
        "relationship": "equivalent",
        "description": "Documented information",
    },
    # Continual improvement
    {
        "source_standard": "ISO 9001",
        "source_clause": "10.3",
        "target_standard": "ISO 14001",
        "target_clause": "10.3",
        "relationship": "equivalent",
        "description": "Continual improvement",
    },
    {
        "source_standard": "ISO 9001",
        "source_clause": "10.3",
        "target_standard": "ISO 45001",
        "target_clause": "10.3",
        "relationship": "equivalent",
        "description": "Continual improvement",
    },
    # Environmental aspects -> OH&S hazards
    {
        "source_standard": "ISO 14001",
        "source_clause": "6.1.2",
        "target_standard": "ISO 45001",
        "target_clause": "6.1.2",
        "relationship": "related",
        "description": "Environmental aspects / Hazard identification",
    },
    # ISO 27001 specific - Information security risk
    {
        "source_standard": "ISO 27001",
        "source_clause": "6.1.2",
        "target_standard": "ISO 9001",
        "target_clause": "6.1",
        "relationship": "related",
        "description": "Information security risk assessment / Risk-based thinking",
    },
    {
        "source_standard": "ISO 27001",
        "source_clause": "8.1",
        "target_standard": "ISO 9001",
        "target_clause": "8.1",
        "relationship": "related",
        "description": "Operational planning and control",
    },
]

_CLAUSE_TITLE_MAP: Dict[Tuple[str, str], str] = {}
for _std_name, _clauses in [
    ("ISO 9001", _ISO_9001_CLAUSES),
    ("ISO 14001", _ISO_14001_CLAUSES),
    ("ISO 45001", _ISO_45001_CLAUSES),
    ("ISO 27001", _ISO_27001_CLAUSES),
]:
    for _num, _title, _desc, _lvl, _parent in _clauses:
        _CLAUSE_TITLE_MAP[(_std_name, _num)] = _title


async def _ensure_ims_requirement(
    db: AsyncSession,
    standard: str,
    clause_number: str,
    cache: Dict[Tuple[str, str], int],
) -> int:
    """Find or create an IMSRequirement for a standard+clause and return its id."""
    from src.domain.models.ims_unification import IMSRequirement

    key = (standard, clause_number)
    if key in cache:
        return cache[key]

    result = await db.execute(
        select(IMSRequirement).where(
            IMSRequirement.standard == standard,
            IMSRequirement.clause_number == clause_number,
        )
    )
    req = result.scalars().first()
    if req:
        cache[key] = req.id
        return req.id

    title = _CLAUSE_TITLE_MAP.get(key, f"Clause {clause_number}")
    req = IMSRequirement(
        standard=standard,
        clause_number=clause_number,
        clause_title=title,
        clause_text=title,
        is_common_requirement=True,
    )
    db.add(req)
    await db.flush()
    cache[key] = req.id
    return req.id


async def _seed_cross_standard_mappings(db: AsyncSession) -> None:
    """Seed cross-standard ISO clause mappings (idempotent)."""
    from src.domain.models.ims_unification import CrossStandardMapping

    count = await db.scalar(select(func.count()).select_from(CrossStandardMapping))
    if count and count > 0:
        logger.info("Cross-standard mappings already seeded (%d rows), skipping", count)
        return

    logger.info("Seeding cross-standard ISO clause mappings (%d mappings)", len(_CROSS_STANDARD_MAPPINGS))

    req_cache: Dict[Tuple[str, str], int] = {}

    for m in _CROSS_STANDARD_MAPPINGS:
        primary_req_id = await _ensure_ims_requirement(db, m["source_standard"], m["source_clause"], req_cache)
        mapped_req_id = await _ensure_ims_requirement(db, m["target_standard"], m["target_clause"], req_cache)

        mapping = CrossStandardMapping(
            primary_requirement_id=primary_req_id,
            primary_standard=m["source_standard"],
            primary_clause=m["source_clause"],
            mapped_requirement_id=mapped_req_id,
            mapped_standard=m["target_standard"],
            mapped_clause=m["target_clause"],
            mapping_type=m["relationship"],
            mapping_strength=100 if m["relationship"] == "equivalent" else 70,
            mapping_notes=m["description"],
        )
        db.add(mapping)

    await db.flush()
    logger.info("  Seeded %d cross-standard mappings", len(_CROSS_STANDARD_MAPPINGS))


async def seed_all_ims_modules(db: AsyncSession) -> None:
    """Orchestrator: seed all IMS modules if their tables are empty."""
    logger.info("IMS module seed check starting")

    await _seed_standards_library(db)
    await _seed_iso27001_controls(db)
    await _seed_uvdb_baseline(db)
    await _seed_planet_mark_year(db)
    await _seed_cross_standard_mappings(db)

    logger.info("IMS module seed check complete")
