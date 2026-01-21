"""Schemas for form configuration API."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

# ==================== Form Field Schemas ====================


class FormFieldBase(BaseModel):
    """Base schema for form fields."""

    name: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    field_type: str = Field(..., min_length=1, max_length=50)
    order: int = 0
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    is_required: bool = False
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    pattern: Optional[str] = None
    default_value: Optional[str] = None
    options: Optional[List[dict]] = None
    show_condition: Optional[dict] = None
    width: str = "full"


class FormFieldCreate(FormFieldBase):
    """Schema for creating a form field."""

    pass


class FormFieldUpdate(BaseModel):
    """Schema for updating a form field."""

    name: Optional[str] = None
    label: Optional[str] = None
    field_type: Optional[str] = None
    order: Optional[int] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    is_required: Optional[bool] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    pattern: Optional[str] = None
    default_value: Optional[str] = None
    options: Optional[List[dict]] = None
    show_condition: Optional[dict] = None
    width: Optional[str] = None


class FormFieldResponse(FormFieldBase):
    """Schema for form field response."""

    id: int
    step_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Form Step Schemas ====================


class FormStepBase(BaseModel):
    """Base schema for form steps."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    order: int = 0
    icon: Optional[str] = None
    show_condition: Optional[dict] = None


class FormStepCreate(FormStepBase):
    """Schema for creating a form step."""

    fields: Optional[List[FormFieldCreate]] = None


class FormStepUpdate(BaseModel):
    """Schema for updating a form step."""

    name: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    icon: Optional[str] = None
    show_condition: Optional[dict] = None


class FormStepResponse(FormStepBase):
    """Schema for form step response."""

    id: int
    template_id: int
    fields: List[FormFieldResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Form Template Schemas ====================


class FormTemplateBase(BaseModel):
    """Base schema for form templates."""

    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    form_type: str = "custom"
    icon: Optional[str] = None
    color: Optional[str] = None
    allow_drafts: bool = True
    allow_attachments: bool = True
    require_signature: bool = False
    auto_assign_reference: bool = True
    reference_prefix: Optional[str] = None
    notify_on_submit: bool = True
    notification_emails: Optional[str] = None
    workflow_id: Optional[int] = None


class FormTemplateCreate(FormTemplateBase):
    """Schema for creating a form template."""

    steps: Optional[List[FormStepCreate]] = None


class FormTemplateUpdate(BaseModel):
    """Schema for updating a form template."""

    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    form_type: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    allow_drafts: Optional[bool] = None
    allow_attachments: Optional[bool] = None
    require_signature: Optional[bool] = None
    auto_assign_reference: Optional[bool] = None
    reference_prefix: Optional[str] = None
    notify_on_submit: Optional[bool] = None
    notification_emails: Optional[str] = None
    workflow_id: Optional[int] = None
    is_active: Optional[bool] = None


class FormTemplateResponse(FormTemplateBase):
    """Schema for form template response."""

    id: int
    version: int
    is_active: bool
    is_published: bool
    published_at: Optional[datetime] = None
    steps: List[FormStepResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FormTemplateListResponse(BaseModel):
    """Schema for list of form templates."""

    items: List[FormTemplateResponse]
    total: int
    page: int
    page_size: int


# ==================== Contract Schemas ====================


class ContractBase(BaseModel):
    """Base schema for contracts."""

    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    client_email: Optional[str] = None
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    display_order: int = 0


class ContractCreate(ContractBase):
    """Schema for creating a contract."""

    pass


class ContractUpdate(BaseModel):
    """Schema for updating a contract."""

    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    client_email: Optional[str] = None
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    display_order: Optional[int] = None


class ContractResponse(ContractBase):
    """Schema for contract response."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContractListResponse(BaseModel):
    """Schema for list of contracts."""

    items: List[ContractResponse]
    total: int


# ==================== System Setting Schemas ====================


class SystemSettingBase(BaseModel):
    """Base schema for system settings."""

    key: str = Field(..., min_length=1, max_length=100)
    value: str
    category: str = "general"
    description: Optional[str] = None
    value_type: str = "string"
    is_public: bool = False
    is_editable: bool = True


class SystemSettingCreate(SystemSettingBase):
    """Schema for creating a system setting."""

    pass


class SystemSettingUpdate(BaseModel):
    """Schema for updating a system setting."""

    value: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class SystemSettingResponse(SystemSettingBase):
    """Schema for system setting response."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemSettingListResponse(BaseModel):
    """Schema for list of system settings."""

    items: List[SystemSettingResponse]
    total: int


# ==================== Lookup Option Schemas ====================


class LookupOptionBase(BaseModel):
    """Base schema for lookup options."""

    category: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: bool = True
    display_order: int = 0
    parent_id: Optional[int] = None


class LookupOptionCreate(LookupOptionBase):
    """Schema for creating a lookup option."""

    pass


class LookupOptionUpdate(BaseModel):
    """Schema for updating a lookup option."""

    code: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None
    parent_id: Optional[int] = None


class LookupOptionResponse(LookupOptionBase):
    """Schema for lookup option response."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LookupOptionListResponse(BaseModel):
    """Schema for list of lookup options."""

    items: List[LookupOptionResponse]
    total: int
