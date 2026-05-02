-- PostgreSQL Schema for Finance Dashboard
-- This schema creates a normalized database for financial project tracking

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==================== LOOKUP TABLES ====================

-- Revenue Streams (Lookup Table)
CREATE TABLE IF NOT EXISTS revenue_streams (
    revenue_stream_id VARCHAR(50) PRIMARY KEY,
    stream_name VARCHAR(255) NOT NULL,
    stream_type VARCHAR(50) NOT NULL CHECK (stream_type IN ('service', 'product', 'license', 'other')),
    pricing_model VARCHAR(50) NOT NULL CHECK (pricing_model IN ('hourly', 'fixed', 'monthly', 'per-unit', 'other')),
    notes TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Employees (Reference Table)
CREATE TABLE IF NOT EXISTS employees (
    employee_id VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    employment_type VARCHAR(50) NOT NULL CHECK (employment_type IN ('full-time', 'part-time', 'contractor')),
    start_date DATE NOT NULL,
    end_date DATE,
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR' CHECK (currency IN ('EUR', 'USD', 'GBP')),
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== MAIN TRANSACTIONAL TABLES ====================

-- Projects (Main Table)
CREATE TABLE IF NOT EXISTS projects (
    project_id VARCHAR(50) PRIMARY KEY,
    project_name VARCHAR(255) NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    project_type VARCHAR(50) NOT NULL CHECK (project_type IN ('Fixed Price', 'T&M', 'Retainer')),
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'on-hold')),
    start_date DATE NOT NULL,
    end_date DATE,
    contracted_budget NUMERIC(15, 2) NOT NULL,
    revenue_stream_id VARCHAR(50) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR' CHECK (currency IN ('EUR', 'USD', 'GBP')),
    responsible_employee_id VARCHAR(50),
    notes TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (revenue_stream_id) REFERENCES revenue_streams(revenue_stream_id),
    FOREIGN KEY (responsible_employee_id) REFERENCES employees(employee_id)
);

-- Revenue Transactions
CREATE TABLE IF NOT EXISTS revenue_transactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    invoice_number VARCHAR(100) NOT NULL UNIQUE,
    date DATE NOT NULL,
    project_id VARCHAR(50) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    payment_status VARCHAR(50) NOT NULL DEFAULT 'invoiced' CHECK (payment_status IN ('invoiced', 'received', 'overdue')),
    payment_date DATE,
    notes TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- COGS (Cost of Goods Sold) Transactions
CREATE TABLE IF NOT EXISTS cogs_transactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    invoice_number VARCHAR(100) NOT NULL UNIQUE,
    date DATE NOT NULL,
    vendor_name VARCHAR(255) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    cost_category VARCHAR(100) NOT NULL CHECK (cost_category IN ('Materials', 'Subcontractors', 'Licenses', 'Cloud', 'Other')),
    payment_status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (payment_status IN ('pending', 'paid', 'accrued')),
    payment_date DATE,
    project_id VARCHAR(50) NOT NULL,
    notes TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Overhead Transactions
CREATE TABLE IF NOT EXISTS overhead_transactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    date DATE NOT NULL,
    overhead_category VARCHAR(100) NOT NULL CHECK (overhead_category IN ('Taxes', 'Social Costs', 'Car Lease', 'Office Costs', 'Sell Costs', 'Financial Burdens', 'Other', 'Other Costs')),
    sub_category VARCHAR(100),
    vendor_name VARCHAR(255) NOT NULL,
    invoice_number VARCHAR(100),
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    payment_status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (payment_status IN ('pending', 'paid')),
    payment_date DATE,
    employee_id VARCHAR(50),
    notes TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

-- Bank Cash Movements
CREATE TABLE IF NOT EXISTS bank_cash_movements (
    movement_id VARCHAR(50) PRIMARY KEY,
    date DATE NOT NULL,
    bank_account VARCHAR(100) NOT NULL,
    movement_type VARCHAR(50) NOT NULL CHECK (movement_type IN ('credit', 'debit', 'transfer')),
    amount NUMERIC(15, 2) NOT NULL,
    counterparty VARCHAR(255),
    description VARCHAR(500),
    reference_transaction_id VARCHAR(50),
    is_frozen BOOLEAN DEFAULT FALSE,
    frozen_reason VARCHAR(255),
    balance_after NUMERIC(15, 2),
    notes TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Salaries
CREATE TABLE IF NOT EXISTS salaries (
    salary_id VARCHAR(50) PRIMARY KEY,
    date DATE NOT NULL,
    gross_salary NUMERIC(12, 2) NOT NULL CHECK (gross_salary > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR' CHECK (currency IN ('EUR', 'USD', 'GBP')),
    cadence VARCHAR(50) NOT NULL CHECK (cadence IN ('weekly', 'bi-weekly', 'monthly', 'quarterly', 'annual')),
    employee_id VARCHAR(50) NOT NULL,
    notes TEXT,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

-- ==================== AUDIT/TRACKING TABLE ====================

-- Sync Log (for tracking Google Sheets syncs)
CREATE TABLE IF NOT EXISTS sync_logs (
    sync_id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    sync_type VARCHAR(50) NOT NULL CHECK (sync_type IN ('full', 'incremental', 'delete')),
    rows_processed INTEGER,
    rows_inserted INTEGER,
    rows_updated INTEGER,
    rows_deleted INTEGER,
    status VARCHAR(50) NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== INDEXES ====================

-- Performance indexes
CREATE INDEX idx_projects_status ON projects(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_revenue_streams_active ON revenue_streams(revenue_stream_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_employees_active ON employees(employee_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_projects_revenue_stream ON projects(revenue_stream_id);
CREATE INDEX idx_projects_employee ON projects(responsible_employee_id);
CREATE INDEX idx_revenue_transactions_project ON revenue_transactions(project_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_revenue_transactions_payment_status ON revenue_transactions(payment_status) WHERE is_deleted = FALSE;
CREATE INDEX idx_revenue_transactions_date ON revenue_transactions(date) WHERE is_deleted = FALSE;
CREATE INDEX idx_cogs_transactions_project ON cogs_transactions(project_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_cogs_transactions_date ON cogs_transactions(date) WHERE is_deleted = FALSE;
CREATE INDEX idx_overhead_transactions_date ON overhead_transactions(date) WHERE is_deleted = FALSE;
CREATE INDEX idx_overhead_transactions_employee ON overhead_transactions(employee_id);
CREATE INDEX idx_bank_movements_date ON bank_cash_movements(date) WHERE is_deleted = FALSE;
CREATE INDEX idx_bank_movements_account ON bank_cash_movements(bank_account);
CREATE INDEX idx_salaries_employee ON salaries(employee_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_salaries_date ON salaries(date) WHERE is_deleted = FALSE;

-- ==================== GRANTS ====================

-- Grant permissions to Loek user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO Loek;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO Loek;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO Loek;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO Loek;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO Loek;
