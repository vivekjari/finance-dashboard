"""SQLAlchemy ORM Models"""
from sqlalchemy import Column, String, Integer, Float, Boolean, Date, DateTime, Text, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

# ==================== LOOKUP TABLES ====================

class RevenueStream(Base):
    """Revenue stream reference table"""
    __tablename__ = "revenue_streams"
    
    revenue_stream_id = Column(String(50), primary_key=True)
    stream_name = Column(String(255), nullable=False)
    stream_type = Column(String(50), nullable=False)
    pricing_model = Column(String(50), nullable=False)
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    projects = relationship("Project", back_populates="revenue_stream")
    
    def to_dict(self):
        return {
            "revenue_stream_id": self.revenue_stream_id,
            "stream_name": self.stream_name,
            "stream_type": self.stream_type,
            "pricing_model": self.pricing_model,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class Employee(Base):
    """Employee reference table"""
    __tablename__ = "employees"
    
    employee_id = Column(String(50), primary_key=True)
    full_name = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    employment_type = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    currency = Column(String(3), default="EUR")
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    projects = relationship("Project", back_populates="responsible_employee")
    overhead_transactions = relationship("OverheadTransaction", back_populates="employee")
    salaries = relationship("Salary", back_populates="employee")
    
    def to_dict(self):
        return {
            "employee_id": self.employee_id,
            "full_name": self.full_name,
            "role": self.role,
            "department": self.department,
            "employment_type": self.employment_type,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "currency": self.currency,
            "is_active": self.is_active,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

# ==================== MAIN TRANSACTIONAL TABLES ====================

class Project(Base):
    """Projects table"""
    __tablename__ = "projects"
    
    project_id = Column(String(50), primary_key=True)
    project_name = Column(String(255), nullable=False)
    client_name = Column(String(255), nullable=False)
    project_type = Column(String(50), nullable=False)
    status = Column(String(50), default="active")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    contracted_budget = Column(Float, nullable=False)
    revenue_stream_id = Column(String(50), ForeignKey("revenue_streams.revenue_stream_id"), nullable=False)
    currency = Column(String(3), default="EUR")
    responsible_employee_id = Column(String(50), ForeignKey("employees.employee_id"))
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    revenue_stream = relationship("RevenueStream", back_populates="projects")
    responsible_employee = relationship("Employee", back_populates="projects")
    revenue_transactions = relationship("RevenueTransaction", back_populates="project", cascade="all, delete-orphan")
    cogs_transactions = relationship("CogsTransaction", back_populates="project", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "client_name": self.client_name,
            "project_type": self.project_type,
            "status": self.status,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "contracted_budget": float(self.contracted_budget),
            "revenue_stream_id": self.revenue_stream_id,
            "currency": self.currency,
            "responsible_employee_id": self.responsible_employee_id,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class RevenueTransaction(Base):
    """Revenue transactions table"""
    __tablename__ = "revenue_transactions"
    
    transaction_id = Column(String(50), primary_key=True)
    invoice_number = Column(String(100), unique=True, nullable=False)
    date = Column(Date, nullable=False)
    project_id = Column(String(50), ForeignKey("projects.project_id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_status = Column(String(50), default="invoiced")
    payment_date = Column(Date)
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="revenue_transactions")
    
    def to_dict(self):
        return {
            "transaction_id": self.transaction_id,
            "invoice_number": self.invoice_number,
            "date": self.date,
            "project_id": self.project_id,
            "amount": float(self.amount),
            "payment_status": self.payment_status,
            "payment_date": self.payment_date,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class CogsTransaction(Base):
    """Cost of Goods Sold transactions table"""
    __tablename__ = "cogs_transactions"
    
    transaction_id = Column(String(50), primary_key=True)
    invoice_number = Column(String(100), unique=True, nullable=False)
    date = Column(Date, nullable=False)
    vendor_name = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    cost_category = Column(String(100), nullable=False)
    payment_status = Column(String(50), default="pending")
    payment_date = Column(Date)
    project_id = Column(String(50), ForeignKey("projects.project_id"), nullable=False)
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="cogs_transactions")
    
    def to_dict(self):
        return {
            "transaction_id": self.transaction_id,
            "invoice_number": self.invoice_number,
            "date": self.date,
            "vendor_name": self.vendor_name,
            "amount": float(self.amount),
            "cost_category": self.cost_category,
            "payment_status": self.payment_status,
            "payment_date": self.payment_date,
            "project_id": self.project_id,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class OverheadTransaction(Base):
    """Overhead transactions table"""
    __tablename__ = "overhead_transactions"
    
    transaction_id = Column(String(50), primary_key=True)
    date = Column(Date, nullable=False)
    overhead_category = Column(String(100), nullable=False)
    sub_category = Column(String(100))
    vendor_name = Column(String(255), nullable=False)
    invoice_number = Column(String(100))
    amount = Column(Float, nullable=False)
    payment_status = Column(String(50), default="pending")
    payment_date = Column(Date)
    employee_id = Column(String(50), ForeignKey("employees.employee_id"))
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", back_populates="overhead_transactions")
    
    def to_dict(self):
        return {
            "transaction_id": self.transaction_id,
            "date": self.date,
            "overhead_category": self.overhead_category,
            "sub_category": self.sub_category,
            "vendor_name": self.vendor_name,
            "invoice_number": self.invoice_number,
            "amount": float(self.amount),
            "payment_status": self.payment_status,
            "payment_date": self.payment_date,
            "employee_id": self.employee_id,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class BankCashMovement(Base):
    """Bank cash movements table"""
    __tablename__ = "bank_cash_movements"
    
    movement_id = Column(String(50), primary_key=True)
    date = Column(Date, nullable=False)
    bank_account = Column(String(100), nullable=False)
    movement_type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    counterparty = Column(String(255))
    description = Column(String(500))
    reference_transaction_id = Column(String(50))
    is_frozen = Column(Boolean, default=False)
    frozen_reason = Column(String(255))
    balance_after = Column(Float)
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "movement_id": self.movement_id,
            "date": self.date,
            "bank_account": self.bank_account,
            "movement_type": self.movement_type,
            "amount": float(self.amount),
            "counterparty": self.counterparty,
            "description": self.description,
            "reference_transaction_id": self.reference_transaction_id,
            "is_frozen": self.is_frozen,
            "frozen_reason": self.frozen_reason,
            "balance_after": float(self.balance_after) if self.balance_after else None,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class Salary(Base):
    """Salaries table"""
    __tablename__ = "salaries"
    
    salary_id = Column(String(50), primary_key=True)
    date = Column(Date, nullable=False)
    gross_salary = Column(Float, nullable=False)
    currency = Column(String(3), default="EUR")
    cadence = Column(String(50), nullable=False)
    employee_id = Column(String(50), ForeignKey("employees.employee_id"), nullable=False)
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", back_populates="salaries")
    
    def to_dict(self):
        return {
            "salary_id": self.salary_id,
            "date": self.date,
            "gross_salary": float(self.gross_salary),
            "currency": self.currency,
            "cadence": self.cadence,
            "employee_id": self.employee_id,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class SyncLog(Base):
    """Sync logs for tracking data synchronization"""
    __tablename__ = "sync_logs"
    
    sync_id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(100), nullable=False)
    sync_type = Column(String(50), nullable=False)
    rows_processed = Column(Integer)
    rows_inserted = Column(Integer)
    rows_updated = Column(Integer)
    rows_deleted = Column(Integer)
    status = Column(String(50), nullable=False)
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "sync_id": self.sync_id,
            "table_name": self.table_name,
            "sync_type": self.sync_type,
            "rows_processed": self.rows_processed,
            "rows_inserted": self.rows_inserted,
            "rows_updated": self.rows_updated,
            "rows_deleted": self.rows_deleted,
            "status": self.status,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at
        }
