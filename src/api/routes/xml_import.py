"""XML Template Import API Routes.

Endpoints for importing Android XML layout files as audit templates.
"""

import logging
import os
import tempfile
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.audit import AuditTemplateResponse
from src.domain.exceptions import ValidationError
from src.domain.services.audit_service import AuditService
from src.domain.services.xml_importer_service import (
    batch_parse_directory,
    parse_xml_to_template,
    sections_from_template,
    template_structure_to_audit_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_IMPORT_DIR = os.environ.get("XML_IMPORT_DIR", os.path.join(tempfile.gettempdir(), "xml-imports"))


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------


class BatchImportRequest(BaseModel):
    """Request body for batch import from server directory."""

    directory_path: str = Field(
        ...,
        description="Absolute or relative path to directory containing XML layout files",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/parse")
async def parse_xml_file(
    file: UploadFile = File(...),
    user: CurrentUser = None,
) -> dict[str, Any]:
    """Upload a single XML file and return parsed template structure (preview).

    Does not create anything in the database. Use /import to create the template.
    """
    if not file.filename or not file.filename.lower().endswith(".xml"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an XML file (.xml extension)",
        )
    try:
        content = await file.read()
        template = parse_xml_to_template(content, source_filename=file.filename)
        return template
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/import", response_model=AuditTemplateResponse, status_code=status.HTTP_201_CREATED)
async def import_xml_file(
    file: UploadFile = File(...),
    db: DbSession = None,
    user: CurrentUser = None,
) -> Any:
    """Upload XML file and create the audit template in the database."""
    if not file.filename or not file.filename.lower().endswith(".xml"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an XML file (.xml extension)",
        )
    try:
        content = await file.read()
        template_data = parse_xml_to_template(content, source_filename=file.filename)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    audit_service = AuditService(db)
    template_payload = template_structure_to_audit_payload(template_data)

    template = await audit_service.create_template(
        data=template_payload,
        standard_ids=None,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    sections = sections_from_template(template_data)
    for sec in sections:
        sec_payload = {"title": sec["name"], "sort_order": sec.get("order", 0)}
        section = await audit_service.create_section(
            template_id=template.id,
            data=sec_payload,
            tenant_id=user.tenant_id,
        )
        for q in sec.get("questions", []):
            q_payload = {
                "question_text": q["text"],
                "question_type": q.get("question_type", "text"),
                "guidance": q.get("guidance"),
                "sort_order": q.get("order", 0),
                "options_json": q.get("options"),
                "section_id": section.id,
            }
            await audit_service.create_question(
                template_id=template.id,
                data=q_payload,
                tenant_id=user.tenant_id,
            )

    return AuditTemplateResponse.model_validate(template)


@router.post("/batch")
async def batch_parse(
    request: BatchImportRequest,
    user: CurrentUser = None,
) -> list[dict[str, Any]]:
    """Parse all XML layout files from a directory on the server.

    Accepts a directory path and returns a list of parsed template structures.
    Does not create templates in the database.
    Path must be within the allowed import directory (XML_IMPORT_DIR env, default /tmp/xml-imports).
    """
    resolved = os.path.realpath(request.directory_path)
    allowed_base = os.path.realpath(ALLOWED_IMPORT_DIR)
    if not resolved.startswith(allowed_base):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Directory not in allowed import path",
        )
    if not os.path.isdir(resolved):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path is not a valid directory",
        )
    try:
        templates = batch_parse_directory(resolved)
        return templates
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
