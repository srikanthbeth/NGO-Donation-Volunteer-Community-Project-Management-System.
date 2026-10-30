
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ResourceCategory = Literal[
    "FOOD",
    "CLOTHING",
    "EDUCATIONAL_MATERIALS",
    "MEDICAL_SUPPLIES",
    "EMERGENCY_KITS",
    "OTHER",
]


class ResourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category: ResourceCategory
    description: str | None = Field(default=None, max_length=5000)
    unit: str = Field(default="unit", min_length=1, max_length=30)
    low_stock_threshold: int = Field(default=10, ge=0)

    @field_validator("name", "unit")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class ResourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    category: ResourceCategory | None = None
    description: str | None = Field(default=None, max_length=5000)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    status: Literal["ACTIVE", "INACTIVE"] | None = None

    @field_validator("name", "unit")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    def validate_not_empty(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied.")


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    description: str | None
    unit: str
    quantity_available: int
    low_stock_threshold: int
    status: str
    created_by: int
    created_at: object
    updated_at: object


class ResourceListResponse(BaseModel):
    items: list[ResourceResponse]
    total: int
    page: int
    page_size: int


class ResourceStockMovementCreate(BaseModel):
    transaction_type: Literal["STOCK_IN", "STOCK_OUT"]
    quantity: int = Field(gt=0)
    reference: str | None = Field(default=None, max_length=150)
    notes: str | None = Field(default=None, max_length=5000)


class ResourceTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    transaction_type: str
    quantity: int
    project_id: int | None
    performed_by: int
    reference: str | None
    notes: str | None
    created_at: object


class ResourceTransactionListResponse(BaseModel):
    items: list[ResourceTransactionResponse]
    total: int
    page: int
    page_size: int


class ResourceAllocationCreate(BaseModel):
    resource_id: int = Field(gt=0)
    project_id: int = Field(gt=0)
    allocated_quantity: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=5000)


class ResourceDistributionCreate(BaseModel):
    quantity: int = Field(gt=0)
    reference: str | None = Field(default=None, max_length=150)
    notes: str | None = Field(default=None, max_length=5000)


class ResourceAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    project_id: int
    allocated_quantity: int
    distributed_quantity: int
    status: str
    allocated_by: int
    notes: str | None
    created_at: object
    updated_at: object


class ResourceAllocationListResponse(BaseModel):
    items: list[ResourceAllocationResponse]
    total: int
    page: int
    page_size: int


class LowStockResource(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    unit: str
    quantity_available: int
    low_stock_threshold: int
