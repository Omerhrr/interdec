"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr
from typing import Optional
import base64
import binascii


# --- Lenient email type (no strict validation to match original Firebase behavior) ---
class LooseEmail(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        return str(v).strip().lower() if v else v


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class AppAccess(BaseModel):
    access: bool = False
    role: Optional[str] = None


class UserApps(BaseModel):
    facade: Optional[AppAccess] = None
    importflow: Optional[AppAccess] = None
    catalogues: Optional[AppAccess] = None


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    avatar: str = ""
    platformRole: str = "user"
    apps: dict = {}
    active: bool = True

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    name: str
    email: str
    password: str = ""
    avatar: str = ""
    platformRole: str = "user"
    apps: dict = {}


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    avatar: Optional[str] = None
    platformRole: Optional[str] = None
    apps: Optional[dict] = None
    active: Optional[bool] = None


class VendorBase(BaseModel):
    name: str
    contact: str = ""
    email: str = ""
    phone: str = ""
    country: str = ""
    category: str = ""
    address: str = ""
    notes: str = ""


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class CatalogFile(BaseModel):
    name: str
    size: int = 0
    type: str = ""
    data: str  # base64
    uploaded: int = 0


class ShipperBase(BaseModel):
    name: str
    contact: str = ""
    email: str = ""
    phone: str = ""
    country: str = ""
    category: str = ""
    notes: str = ""


class ShipperCreate(ShipperBase):
    pass


class ShipperUpdate(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    client: str = ""
    description: str = ""
    status: str = "Active"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    client: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class FileData(BaseModel):
    name: str
    size: int = 0
    type: str = ""
    data: str = ""  # base64 (no data: prefix)
    uploaded: int = 0


class ShipmentCreate(BaseModel):
    companyId: str
    projectId: Optional[str] = None
    category: str = ""
    vendorId: Optional[str] = None
    description: str = ""
    productionDays: str = ""
    value: float = 0
    currency: str = "USD"


class ShipmentUpdate(BaseModel):
    shipperId: Optional[str] = None
    paymentTerms: Optional[str] = None
    eta: Optional[str] = None
    shipMethod: Optional[str] = None
    productionDays: Optional[str] = None
    status: Optional[str] = None
    vendorInvoice: Optional[FileData] = None
    packingList: Optional[FileData] = None
    shipperInvoice: Optional[FileData] = None
    goodsConfirmed: Optional[bool] = None


TokenResponse.model_rebuild()
