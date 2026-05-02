"""Pydantic request/response schemas"""
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, List

# ==================== REVENUE STREAMS ====================

class RevenueStreamBase(BaseModel):
    stream_name: str
    stream_type: str
    pricing_model: str
    notes: Optional[str] = None

class RevenueStreamCreate(RevenueStreamBase):
    revenue_stream_id: str

class RevenueStreamResponse(RevenueStreamBase):
    revenue_stream_id: str
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== EMPLOYEES ====================

class EmployeeBase(BaseModel):
    full_name: str
    role: str
    department: str
    employment_type: str
    start_date: date
    end_date: Optional[date] = None
    currency: str = "EUR"
    is_active: bool = True
    notes: Optional[str] = None

class EmployeeCreate(EmployeeBase):
    employee_id: str

class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class EmployeeResponse(EmployeeBase):
    employee_id: str
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== PROJECTS ====================

class ProjectBase(BaseModel):
    project_name: str
    client_name: str
    project_type: str
    status: str = "active"
    start_date: date
    end_date: Optional[date] = None
    contracted_budget: float
    revenue_stream_id: str
    currency: str = "EUR"
    responsible_employee_id: Optional[str] = None
    notes: Optional[str] = None

class ProjectCreate(ProjectBase):
    project_id: str

class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    status: Optional[str] = None
    end_date: Optional[date] = None
    contracted_budget: Optional[float] = None
    responsible_employee_id: Optional[str] = None
    notes: Optional[str] = None

class ProjectResponse(ProjectBase):
    project_id: str
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== REVENUE TRANSACTIONS ====================

class RevenueTransactionBase(BaseModel):
    invoice_number: str
    date: date
    project_id: str
    amount: float = Field(gt=0)
    payment_status: str = "invoiced"
    payment_date: Optional[date] = None
    notes: Optional[str] = None

class RevenueTransactionCreate(RevenueTransactionBase):
    transaction_id: str

class RevenueTransactionUpdate(BaseModel):
    payment_status: Optional[str] = None
    payment_date: Optional[date] = None
    notes: Optional[str] = None

class RevenueTransactionResponse(RevenueTransactionBase):
    transaction_id: str
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== COGS TRANSACTIONS ====================

class CogsTransactionBase(BaseModel):
    invoice_number: str
    date: date
    vendor_name: str
    amount: float = Field(gt=0)
    cost_category: str
    payment_status: str = "pending"
    payment_date: Optional[date] = None
    project_id: str
    notes: Optional[str] = None

class CogsTransactionCreate(CogsTransactionBase):
    transaction_id: str

class CogsTransactionUpdate(BaseModel):
    payment_status: Optional[str] = None
    payment_date: Optional[date] = None
    notes: Optional[str] = None

class CogsTransactionResponse(CogsTransactionBase):
    transaction_id: str
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== OVERHEAD TRANSACTIONS ====================

class OverheadTransactionBase(BaseModel):
    date: date
    overhead_category: str
    sub_category: Optional[str] = None
    vendor_name: str
    invoice_number: Optional[str] = None
    amount: float = Field(gt=0)
    payment_status: str = "pending"
    payment_date: Optional[date] = None
    employee_id: Optional[str] = None
    notes: Optional[str] = None

class OverheadTransactionCreate(OverheadTransactionBase):
    transaction_id: str

class OverheadTransactionUpdate(BaseModel):
    payment_status: Optional[str] = None
    payment_date: Optional[date] = None
    notes: Optional[str] = None

class OverheadTransactionResponse(OverheadTransactionBase):
    transaction_id: str
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== BANK CASH MOVEMENTS ====================

class BankCashMovementBase(BaseModel):
    date: date
    bank_account: str
    movement_type: str
    amount: float
    counterparty: Optional[str] = None
    description: Optional[str] = None
    reference_transaction_id: Optional[str] = None
    is_frozen: bool = False
    frozen_reason: Optional[str] = None
    balance_after: Optional[float] = None
    notes: Optional[str] = None

class BankCashMovementCreate(BankCashMovementBase):
    movement_id: str

class BankCashMovementUpdate(BaseModel):
    is_frozen: Optional[bool] = None
    frozen_reason: Optional[str] = None
    notes: Optional[str] = None

class BankCashMovementResponse(BankCashMovementBase):
    movement_id: str
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== SALARIES ====================

class SalaryBase(BaseModel):
    date: date
    gross_salary: float = Field(gt=0)
    currency: str = "EUR"
    cadence: str
    employee_id: str
    notes: Optional[str] = None

class SalaryCreate(SalaryBase):
    salary_id: str

class SalaryUpdate(BaseModel):
    gross_salary: Optional[float] = None
    cadence: Optional[str] = None
    notes: Optional[str] = None

class SalaryResponse(SalaryBase):
    salary_id: str
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== SYNC LOGS ====================

class SyncLogResponse(BaseModel):
    sync_id: int
    table_name: str
    sync_type: str
    rows_processed: Optional[int] = None
    rows_inserted: Optional[int] = None
    rows_updated: Optional[int] = None
    rows_deleted: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== SUMMARY RESPONSES ====================

class SyncSummary(BaseModel):
    status: str
    total_tables_synced: int
    total_rows_processed: int
    total_rows_inserted: int
    total_rows_updated: int
    total_rows_deleted: int
    errors: Optional[List[str]] = None
    started_at: datetime
    completed_at: datetime
