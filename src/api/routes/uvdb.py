"""
UVDB Achilles Verify B2 Audit Protocol API Routes

Provides endpoints for:
- UVDB Audit management
- Section and question management
- Audit responses and scoring
- KPI tracking (Section 15)
- ISO cross-mapping
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.uvdb_achilles import (
    UVDBAudit,
    UVDBAuditResponse,
    UVDBISOCrossMapping,
    UVDBKPIRecord,
    UVDBQuestion,
    UVDBSection,
)
from src.infrastructure.database import get_db

router = APIRouter()


# ============ UVDB B2 Protocol Structure ============

# Complete UVDB B2 Audit Protocol Sections and Questions
# Based on UVDB-QS-003 - Verify B2 Audit Protocol V11.2

UVDB_B2_SECTIONS = [
    {
        "number": "1",
        "title": "System Assurance and Compliance",
        "max_score": 21,
        "iso_mapping": {"9001": "4-5", "14001": "4-5", "45001": "4-5"},
        "questions": [
            {
                "number": "1.1",
                "text": "Can the company demonstrate that their Quality Management Systems are assured?",
                "sub_questions": [
                    "Does the company have any formal 3rd party certification for their management systems as awarded by an independent accreditation body for quality?",
                    "Does the company's accreditation apply to more than one country if the company has international operations?",
                    "Is the accrediting body registered with UKAS or other international equivalent?",
                    "Where 3rd party accreditation has not been sought, can the company demonstrate that its Quality Management Systems are based on a recognised Standard?",
                ],
                "iso_mapping": {"9001": ["4.4", "5.1", "9.2"]},
                "evidence": ["ISO 9001 certificate", "UKAS accreditation", "Quality Manual"],
            },
            {
                "number": "1.2",
                "text": "Can the company demonstrate that their Health and Safety Management Systems are assured?",
                "sub_questions": [
                    "Does the company have any formal 3rd party certification for their management systems as awarded by an independent accreditation body for health and safety?",
                    "Does the company's accreditation apply to more than one country if the company has international operations?",
                    "Is the accrediting body registered with UKAS or other international equivalent?",
                    "Where 3rd party accreditation has not been sought, can the company demonstrate that its Health and Safety Management Systems are based on a recognised Standard?",
                ],
                "iso_mapping": {"45001": ["4.4", "5.1", "9.2"]},
                "evidence": ["ISO 45001 certificate", "UKAS accreditation", "H&S Policy"],
            },
            {
                "number": "1.3",
                "text": "Can the company demonstrate that their Environmental Management Systems are assured?",
                "sub_questions": [
                    "Does the company have any formal 3rd party certification for their management systems as awarded by an independent accreditation body for environment?",
                    "Does the company's accreditation apply to more than one country if the company has international operations?",
                    "Is the accrediting body registered with UKAS or other international equivalent?",
                    "Where 3rd party accreditation has not been sought, can the company demonstrate that its Environmental Systems are based on a recognised Standard?",
                ],
                "iso_mapping": {"14001": ["4.4", "5.1", "9.2"]},
                "evidence": ["ISO 14001 certificate", "UKAS accreditation", "Environmental Policy"],
            },
            {
                "number": "1.4",
                "text": "Can the company identify their role under the Construction (Design and Management) Regulations 2015?",
                "sub_questions": [
                    "Has the company identified and documented its responsibilities as defined within the CDM Regulations e.g. Contractor, Principal Contractor, Designer, Principal Designer?",
                    "Do management systems identify processes for meeting and discharging duties as required by the CDM regulations?",
                    "Can the company demonstrate that appropriate documented information relating to construction works is retained (i.e. Construction Phase Plan, H&S File, F10 Notification)?",
                ],
                "iso_mapping": {"45001": ["6.1", "8.1"]},
                "evidence": ["CDM duties register", "Construction Phase Plan template", "F10 records"],
                "site_applicable": True,
            },
            {
                "number": "1.5",
                "text": "Has the company identified all permit and licensing requirements applicable to the scope of services provided?",
                "sub_questions": [
                    "Has the company identified the necessary licenses and permits applicable to the scope of services provided (i.e. Goods Vehicles Operators Licence, waste licence)?",
                    "Is the organisation accredited to FORS, if yes which level of accreditation is held?",
                    "Can the company demonstrate that all applicable licenses and permits are held and in date?",
                    "Can the company demonstrate it is implementing the requirements of each permit or license that is held?",
                ],
                "iso_mapping": {"14001": ["6.1.3"], "45001": ["6.1.3"]},
                "evidence": ["O-Licence", "Waste carrier licence", "FORS certificate"],
                "site_applicable": True,
            },
        ],
    },
    {
        "number": "2",
        "title": "Quality Control and Assurance",
        "max_score": 21,
        "iso_mapping": {"9001": "7-8", "27001": "7.5"},
        "questions": [
            {
                "number": "2.1",
                "text": "Do Top Management assure the quality of their company's service offerings?",
                "sub_questions": [
                    "Has a quality policy statement been endorsed and communicated by Top Management?",
                    "Does the policy statement commit to continual improvement through the setting of objectives?",
                    "Is the policy statement adequately communicated to internal and external interested parties?",
                    "Have responsibilities for quality management been appropriately assigned within the organisation?",
                    "Are persons identified as responsible for quality assurance suitably qualified or experienced?",
                ],
                "iso_mapping": {"9001": ["5.1", "5.2", "5.3"]},
                "evidence": ["Quality Policy", "Org chart", "Job descriptions"],
            },
            {
                "number": "2.2",
                "text": "Does the company use processes or systems for the management and control of documented information?",
                "sub_questions": [
                    "Is there a documented management procedure for the control of documented information?",
                    "Does the documented information control system identify the key documented information requiring management?",
                    "Is there a process in place for withdrawing and re-issuing of updated documents?",
                    "Are the following controls included: distribution, access, retrieval, retention and change control?",
                    "Is there a process or system in place for the secure disposal of confidential documentation?",
                ],
                "iso_mapping": {"9001": ["7.5"], "27001": ["7.5"]},
                "evidence": ["Document control procedure", "Master document list", "Retention schedule"],
            },
            {
                "number": "2.3",
                "text": "How does the company guarantee the confidentiality, availability and integrity of information and supporting IT systems?",
                "sub_questions": [
                    "Does the company have third party certification for IT management? e.g. ISO/IEC 27001",
                    "Is electronic information backed up on site or remotely?",
                    "Does the company utilise a third party to store confidential data?",
                    "Does the company have protective systems in place to reduce the occurrence of malicious software / IT downtime?",
                    "Does the company have a process or procedure relating to the back up of confidential data?",
                ],
                "iso_mapping": {"27001": ["5.1", "8.1", "A.8"]},
                "evidence": ["ISO 27001 certificate", "Backup procedures", "IT security policy"],
            },
            {
                "number": "2.4",
                "text": "Does the company have documented processes for the provision and subsequent hand over of services?",
                "sub_questions": [
                    "Does specific Quality Control documentation fall within the scope of the company's documented Information control processes (i.e. ITPs available at site)?",
                    "Does the company undertake any analysis to monitor the effectiveness of the procedures and processes in place?",
                    "Does the company have a documented process that demonstrates the controlled hand over of completed works or services?",
                ],
                "iso_mapping": {"9001": ["8.5", "8.6"]},
                "evidence": ["ITP templates", "Handover certificates", "Commissioning reports"],
                "site_applicable": True,
            },
            {
                "number": "2.5",
                "text": "Does the company have in place an internal auditing/inspection programme to monitor the performance of their systems?",
                "sub_questions": [
                    "Are the audits at regular/programmed intervals?",
                    "Does the company ensure all areas of the business are covered by this programme?",
                    "Are non-conformances or other observations identified during audits?",
                    "Are non-conformances or other observations tracked to closure?",
                    "Are internal auditors suitably qualified or experienced?",
                ],
                "iso_mapping": {"9001": ["9.2"], "14001": ["9.2"], "45001": ["9.2"]},
                "evidence": ["Audit schedule", "Audit reports", "NCR register"],
                "site_applicable": True,
            },
        ],
    },
    {
        "number": "12",
        "title": "Selection and Management of Sub-contractors",
        "max_score": 12,
        "iso_mapping": {"9001": "8.4", "45001": "8.1.4"},
        "questions": [
            {
                "number": "12.1",
                "text": "Does the company have a defined process for the selection and on-boarding of sub-contractors?",
                "sub_questions": [
                    "Is there a documented procedure for selection of sub-contractors?",
                    "Does the company carry out due diligence assessments?",
                    "Are sub-contractors required to provide evidence of competency and capability?",
                    "Is there a process for ongoing monitoring of sub-contractor performance?",
                ],
                "iso_mapping": {"9001": ["8.4.1", "8.4.2"]},
                "evidence": ["Supplier approval procedure", "Approved contractor list", "Due diligence forms"],
            },
            {
                "number": "12.2",
                "text": "Does the company undertake any reviews of sub-contractors performance?",
                "sub_questions": [
                    "Does the company have processes to assess the performance of subcontractors?",
                    "Does this include review of H&S, Environmental and Quality performance?",
                    "Are subcontractor audits undertaken where applicable?",
                    "Does the company instigate improvements based on performance reviews?",
                    "Does the company have a mechanism for periodic monitoring of subcontractors insurances, licenses and professional memberships?",
                    "Does the company capture/analyse subcontractors accidents/incidents statistics and reports?",
                    "Does the company have a process to investigate contractor/supplier, Accidents/Incidents and track actions?",
                ],
                "iso_mapping": {"9001": ["8.4.3"], "45001": ["8.1.4"]},
                "evidence": ["Supplier performance reviews", "Audit reports", "Incident tracking"],
            },
        ],
    },
    {
        "number": "13",
        "title": "Sourcing of Goods and Products",
        "max_score": 12,
        "iso_mapping": {"9001": "8.4"},
        "questions": [
            {
                "number": "13.1",
                "text": "Can the company demonstrate that they have put in place formal arrangements for the identification, mitigation and prevention of Counterfeit, Fraudulent and Suspect Items (CFSI)?",
                "sub_questions": [
                    "Are arrangements integrated into the company's management processes/procedures?",
                    "Has the company established measures to ensure that its staff are aware of the risks of CFSI?",
                    "Has the company taken measures to raise awareness throughout all levels of its supply chain?",
                    "Have assurance methods been deployed to ensure material and component traceability back to source suppliers?",
                    "If examples of CFSI have been identified have appropriate remedial actions have been taken?",
                    "For companies working in the Nuclear Industry, have CFSI examples been notified to ONR?",
                ],
                "iso_mapping": {"9001": ["8.4.2", "8.5.2"]},
                "evidence": ["CFSI procedure", "Material traceability records", "Supplier audits"],
            },
            {
                "number": "13.2",
                "text": "Does the company procure materials from legal and sustainable sources, can they demonstrate chain of custody certification?",
                "sub_questions": [
                    "If purchasing raw materials is there a mandated requirement to use materials that possess a Chain of Custody e.g. FSC timber?",
                    "Do delivery notes contain a chain of custody certificate?",
                ],
                "iso_mapping": {"14001": ["8.1"]},
                "evidence": ["FSC certificates", "Sustainable procurement policy"],
            },
            {
                "number": "13.3",
                "text": "Does the company work with its top level suppliers to prevent bribery & corruption throughout its supply chain?",
                "sub_questions": [
                    "Does the company have an anti-bribery and corruption policy?",
                    "Are suppliers required to acknowledge/comply with anti-bribery requirements?",
                ],
                "iso_mapping": {},
                "evidence": ["Anti-bribery policy", "Supplier agreements"],
            },
            {
                "number": "13.4",
                "text": "Can the company demonstrate that they actively assess their supply chain for the potential of child labour being involved in the work process?",
                "sub_questions": [
                    "Can the company demonstrate that they ask their suppliers about child labour in the supply chain?",
                    "If sourcing goods where there is a higher probability of children being involved, what processes are in place to mitigate this?",
                ],
                "iso_mapping": {},
                "evidence": ["Modern slavery statement", "Supplier questionnaires"],
            },
        ],
    },
    {
        "number": "14",
        "title": "Use of Work Equipment, Vehicles and Machines",
        "max_score": 6,
        "iso_mapping": {"45001": "8.1"},
        "questions": [
            {
                "number": "14.1",
                "text": "Does the company have arrangements in place for ensuring that all plant and equipment is maintained and approved prior to use?",
                "sub_questions": [
                    "Does the company have documented processes for the maintenance of plant and equipment?",
                    "Does the company have processes for the receipt and inspection of hired-in plant and equipment?",
                    "Does the company retain records of maintenance of plant items and equipment?",
                    "Does the company retain calibration records?",
                    "Does the company have a process for reporting and repairing defects on plant items and equipment?",
                    "Does the company produce a scheduled maintenance plan for each individual plant item?",
                    "Have operator competency requirements been defined by the company?",
                    "Does the company ensure that plant items and equipment are inspected and maintained by competent personnel?",
                    "Where applicable, are records of thorough examination/certificates for statutory inspections and tests available?",
                ],
                "iso_mapping": {"45001": ["7.1.3", "8.1"]},
                "evidence": ["Maintenance schedules", "LOLER/PUWER records", "Calibration certificates"],
                "site_applicable": True,
            },
        ],
    },
    {
        "number": "15",
        "title": "Key Performance Indicators",
        "max_score": 0,  # KPIs are metrics, not scored
        "iso_mapping": {"45001": "9.1", "14001": "9.1"},
        "questions": [
            {
                "number": "15.1",
                "text": "Total Man Hours Worked",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.2",
                "text": "Fatalities",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.3",
                "text": "HSE Reportable Injuries (RIDDOR)",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.4",
                "text": "Lost Time Incidents (1-7 days)",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.5",
                "text": "Incidents Requiring Medical Treatment (MTI)",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.6",
                "text": "Incidents Requiring First Aid",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.7",
                "text": "Dangerous Occurrences",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.8",
                "text": "Near Hits/Misses",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.9",
                "text": "HSE/HSA Improvement Notices",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.10",
                "text": "HSE/HSA Prohibition Notices",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.11",
                "text": "HSE/HSA Prosecutions",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.12",
                "text": "Environmental Minor Non-Reportable Incidents",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.13",
                "text": "Environmental Reportable Incidents",
                "type": "kpi_numeric",
                "years": 5,
            },
            {
                "number": "15.14",
                "text": "Environmental Enforcement Actions (Warning letters, prosecutions)",
                "type": "kpi_numeric",
                "years": 5,
            },
        ],
    },
]


# ============ Pydantic Schemas ============


class AuditCreate(BaseModel):
    company_name: str = Field(..., min_length=3, max_length=255)
    company_id: Optional[str] = None
    audit_type: str = Field(default="B2")
    audit_scope: Optional[str] = None
    audit_date: Optional[datetime] = None
    lead_auditor: Optional[str] = None


class AuditUpdate(BaseModel):
    status: Optional[str] = None
    total_score: Optional[float] = None
    audit_notes: Optional[str] = None
    lead_auditor: Optional[str] = None


class ResponseCreate(BaseModel):
    question_id: int
    mse_response: Optional[int] = Field(None, ge=0, le=3)
    site_response: Optional[int] = Field(None, ge=0, le=3)
    sub_question_responses: Optional[dict] = None
    evidence_provided: Optional[str] = None
    documents_presented: Optional[list] = None
    finding_type: Optional[str] = None
    finding_description: Optional[str] = None
    auditor_notes: Optional[str] = None


class KPICreate(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    total_man_hours: Optional[int] = None
    fatalities: int = Field(default=0)
    riddor_reportable: int = Field(default=0)
    lost_time_incidents_1_7_days: int = Field(default=0)
    medical_treatment_incidents: int = Field(default=0)
    first_aid_incidents: int = Field(default=0)
    dangerous_occurrences: int = Field(default=0)
    near_misses: int = Field(default=0)
    hse_improvement_notices: int = Field(default=0)
    hse_prohibition_notices: int = Field(default=0)
    hse_prosecutions: int = Field(default=0)
    env_minor_incidents: int = Field(default=0)
    env_reportable_incidents: int = Field(default=0)
    env_enforcement_actions: int = Field(default=0)


# ============ Protocol Structure Endpoints ============


@router.get("/protocol", response_model=dict)
async def get_protocol_structure() -> dict[str, Any]:
    """Get the complete UVDB B2 Audit Protocol structure"""
    return {
        "protocol_name": "UVDB Verify B2 Audit Protocol",
        "version": "V11.2",
        "reference": "UVDB-QS-003",
        "description": "Comprehensive supply chain qualification audit for UK utilities sector",
        "sections": UVDB_B2_SECTIONS,
        "total_sections": len(UVDB_B2_SECTIONS),
        "scoring": {
            "0": "Non-Compliant - No evidence or systems in place",
            "1": "Partially Compliant - Some evidence but gaps identified",
            "2": "Largely Compliant - Minor improvements needed",
            "3": "Compliant - Full evidence and effective implementation",
        },
        "iso_cross_mapping": {
            "1.1": "ISO 9001:2015 (Quality Management)",
            "1.2": "ISO 45001:2018 (OH&S Management)",
            "1.3": "ISO 14001:2015 (Environmental Management)",
            "2.3": "ISO 27001:2022 (Information Security)",
        },
    }


@router.get("/sections", response_model=dict)
async def list_sections(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all UVDB B2 sections"""
    # Return from static data or database
    sections = []
    for section in UVDB_B2_SECTIONS:
        sections.append(
            {
                "number": section["number"],
                "title": section["title"],
                "max_score": section["max_score"],
                "question_count": len(section.get("questions", [])),
                "iso_mapping": section.get("iso_mapping", {}),
            }
        )

    return {
        "total_sections": len(sections),
        "sections": sections,
    }


@router.get("/sections/{section_number}/questions", response_model=dict)
async def get_section_questions(
    section_number: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get questions for a specific UVDB section"""
    section_data = None
    for section in UVDB_B2_SECTIONS:
        if section["number"] == section_number:
            section_data = section
            break

    if not section_data:
        raise HTTPException(status_code=404, detail="Section not found")

    return {
        "section_number": section_data["number"],
        "section_title": section_data["title"],
        "max_score": section_data["max_score"],
        "iso_mapping": section_data.get("iso_mapping", {}),
        "questions": section_data.get("questions", []),
    }


# ============ Audit Management ============


@router.get("/audits", response_model=dict)
async def list_audits(
    status: Optional[str] = Query(None),
    company_name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List UVDB audits"""
    stmt = select(UVDBAudit)

    if status:
        stmt = stmt.where(UVDBAudit.status == status)
    if company_name:
        stmt = stmt.where(UVDBAudit.company_name.ilike(f"%{company_name}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = stmt.order_by(UVDBAudit.audit_date.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    audits = result.scalars().all()

    return {
        "total": total,
        "audits": [
            {
                "id": a.id,
                "audit_reference": a.audit_reference,
                "company_name": a.company_name,
                "audit_type": a.audit_type,
                "audit_date": a.audit_date.isoformat() if a.audit_date else None,
                "status": a.status,
                "percentage_score": a.percentage_score,
                "lead_auditor": a.lead_auditor,
            }
            for a in audits
        ],
    }


@router.post("/audits", response_model=dict, status_code=201)
async def create_audit(
    audit_data: AuditCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new UVDB audit"""
    count = await db.scalar(select(func.count()).select_from(UVDBAudit)) or 0
    audit_reference = f"UVDB-{datetime.utcnow().year}-{(count + 1):04d}"

    audit = UVDBAudit(
        audit_reference=audit_reference,
        status="scheduled",
        **audit_data.model_dump(),
    )
    db.add(audit)
    await db.flush()
    await db.refresh(audit)

    return {
        "id": audit.id,
        "audit_reference": audit_reference,
        "message": "UVDB audit created",
    }


@router.get("/audits/{audit_id}", response_model=dict)
async def get_audit(
    audit_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get audit details"""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    return {
        "id": audit.id,
        "audit_reference": audit.audit_reference,
        "company_name": audit.company_name,
        "company_id": audit.company_id,
        "audit_type": audit.audit_type,
        "audit_scope": audit.audit_scope,
        "audit_date": audit.audit_date.isoformat() if audit.audit_date else None,
        "status": audit.status,
        "lead_auditor": audit.lead_auditor,
        "total_score": audit.total_score,
        "percentage_score": audit.percentage_score,
        "section_scores": audit.section_scores,
        "findings_count": audit.findings_count,
        "major_findings": audit.major_findings,
        "minor_findings": audit.minor_findings,
        "observations": audit.observations,
        "certifications": {
            "iso_9001": audit.iso_9001_verified,
            "iso_14001": audit.iso_14001_verified,
            "iso_45001": audit.iso_45001_verified,
            "iso_27001": audit.iso_27001_verified,
            "ukas_accredited": audit.ukas_accredited,
        },
        "cdm_compliant": audit.cdm_compliant,
        "fors_accredited": audit.fors_accredited,
        "fors_level": audit.fors_level,
        "audit_notes": audit.audit_notes,
    }


@router.put("/audits/{audit_id}", response_model=dict)
async def update_audit(
    audit_id: int,
    audit_data: AuditUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update audit"""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    update_data = audit_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(audit, key, value)

    audit.updated_at = datetime.utcnow()
    await db.flush()

    return {"message": "Audit updated", "id": audit.id}


# ============ Audit Responses ============


@router.post("/audits/{audit_id}/responses", response_model=dict, status_code=201)
async def create_response(
    audit_id: int,
    response_data: ResponseCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Record an audit response"""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    response = UVDBAuditResponse(
        audit_id=audit_id,
        **response_data.model_dump(),
    )
    db.add(response)
    await db.flush()
    await db.refresh(response)

    return {"id": response.id, "message": "Response recorded"}


@router.get("/audits/{audit_id}/responses", response_model=dict)
async def get_audit_responses(
    audit_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get all responses for an audit"""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    result = await db.execute(select(UVDBAuditResponse).where(UVDBAuditResponse.audit_id == audit_id))
    responses = result.scalars().all()

    return {
        "audit_id": audit_id,
        "total_responses": len(responses),
        "responses": [
            {
                "id": r.id,
                "question_id": r.question_id,
                "mse_response": r.mse_response,
                "site_response": r.site_response,
                "finding_type": r.finding_type,
                "finding_description": r.finding_description,
            }
            for r in responses
        ],
    }


# ============ KPI Management ============


@router.post("/audits/{audit_id}/kpis", response_model=dict, status_code=201)
async def add_kpi_record(
    audit_id: int,
    kpi_data: KPICreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Add KPI record for an audit year"""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    ltifr = None
    if kpi_data.total_man_hours and kpi_data.total_man_hours > 0:
        lost_time = kpi_data.lost_time_incidents_1_7_days + kpi_data.riddor_reportable
        ltifr = (lost_time / kpi_data.total_man_hours) * 1000000

    kpi = UVDBKPIRecord(
        audit_id=audit_id,
        ltifr=ltifr,
        **kpi_data.model_dump(),
    )
    db.add(kpi)
    await db.flush()
    await db.refresh(kpi)

    return {"id": kpi.id, "message": "KPI record added", "ltifr": ltifr}


@router.get("/audits/{audit_id}/kpis", response_model=dict)
async def get_audit_kpis(
    audit_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get KPI records for an audit"""
    result = await db.execute(
        select(UVDBKPIRecord).where(UVDBKPIRecord.audit_id == audit_id).order_by(UVDBKPIRecord.year.desc())
    )
    kpis = result.scalars().all()

    return {
        "audit_id": audit_id,
        "kpi_records": [
            {
                "year": k.year,
                "total_man_hours": k.total_man_hours,
                "fatalities": k.fatalities,
                "riddor_reportable": k.riddor_reportable,
                "lost_time_incidents": k.lost_time_incidents_1_7_days,
                "medical_treatment_incidents": k.medical_treatment_incidents,
                "first_aid_incidents": k.first_aid_incidents,
                "dangerous_occurrences": k.dangerous_occurrences,
                "near_misses": k.near_misses,
                "hse_notices": k.hse_improvement_notices + k.hse_prohibition_notices,
                "hse_prosecutions": k.hse_prosecutions,
                "env_incidents": k.env_minor_incidents + k.env_reportable_incidents,
                "ltifr": k.ltifr,
            }
            for k in kpis
        ],
    }


# ============ ISO Cross-Mapping ============


@router.get("/iso-mapping", response_model=dict)
async def get_iso_cross_mapping() -> dict[str, Any]:
    """Get cross-mapping between UVDB sections and ISO standards"""
    mappings = []

    for section in UVDB_B2_SECTIONS:
        for question in section.get("questions", []):
            if "iso_mapping" in question and question["iso_mapping"]:
                mappings.append(
                    {
                        "uvdb_section": section["number"],
                        "uvdb_question": question["number"],
                        "uvdb_text": (
                            question["text"][:100] + "..." if len(question["text"]) > 100 else question["text"]
                        ),
                        "iso_9001": question["iso_mapping"].get("9001", []),
                        "iso_14001": question["iso_mapping"].get("14001", []),
                        "iso_45001": question["iso_mapping"].get("45001", []),
                        "iso_27001": question["iso_mapping"].get("27001", []),
                    }
                )

    return {
        "description": "Cross-mapping between UVDB B2 questions and ISO standard clauses",
        "total_mappings": len(mappings),
        "mappings": mappings,
        "summary": {
            "iso_9001_aligned": "Section 1.1 (QMS), Section 2 (Quality Control), Sections 12-13 (Supplier Management)",
            "iso_14001_aligned": "Section 1.3 (EMS), Sections 8-11 (Environmental), Section 15 (KPIs)",
            "iso_45001_aligned": "Section 1.2 (OH&S), Sections 3-7 (H&S), Section 14 (Equipment), Section 15 (KPIs)",
            "iso_27001_aligned": "Section 2.3 (Information Security)",
        },
    }


# ============ Dashboard ============


@router.get("/dashboard", response_model=dict)
async def get_uvdb_dashboard(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get UVDB audit dashboard summary"""
    total_audits = await db.scalar(select(func.count()).select_from(UVDBAudit)) or 0
    active_audits = (
        await db.scalar(
            select(func.count()).select_from(
                select(UVDBAudit).where(UVDBAudit.status.in_(["scheduled", "in_progress"])).subquery()
            )
        )
        or 0
    )
    completed_audits = (
        await db.scalar(
            select(func.count()).select_from(select(UVDBAudit).where(UVDBAudit.status == "completed").subquery())
        )
        or 0
    )

    result = await db.execute(
        select(UVDBAudit).where(UVDBAudit.status == "completed", UVDBAudit.percentage_score.isnot(None))
    )
    completed = result.scalars().all()

    avg_score = 0
    if completed:
        avg_score = sum(a.percentage_score for a in completed) / len(completed)

    return {
        "summary": {
            "total_audits": total_audits,
            "active_audits": active_audits,
            "completed_audits": completed_audits,
            "average_score": round(avg_score, 1),
        },
        "protocol": {
            "name": "UVDB Verify B2",
            "version": "V11.2",
            "sections": len(UVDB_B2_SECTIONS),
        },
        "certification_alignment": {
            "iso_9001": "Quality Management - Section 1.1, 2.1-2.5",
            "iso_14001": "Environmental Management - Section 1.3, 8-11",
            "iso_45001": "OH&S Management - Section 1.2, 3-7, 14",
            "iso_27001": "Information Security - Section 2.3",
        },
    }
