"""FastAPI application for Finance Dashboard"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import models
import schemas
from database import get_db, init_db, SessionLocal
from sync_sheets import GoogleSheetsSync
from config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_PATH = BASE_DIR / "dashboard" / "index.html"

# Initialize sync
syncer = GoogleSheetsSync()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Finance Dashboard API...")
    if not init_db():
        logger.error("Failed to connect to database")
    
    if config.AUTO_SYNC_ON_STARTUP:
        logger.info("Auto-syncing from Google Sheets...")
        db = SessionLocal()
        try:
            if syncer.authenticate():
                syncer.sync_all(db)
            else:
                logger.warning("Google Sheets authentication failed. Proceeding without sync.")
        except Exception as e:
            logger.error(f"Sync failed: {e}")
        finally:
            db.close()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Finance Dashboard API...")

# Create FastAPI app
app = FastAPI(
    title="Finance Dashboard API",
    description="API for financial project management with Google Sheets integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== HEALTH CHECK ====================

@app.get("/", include_in_schema=False)
async def dashboard():
    """Serve the local financial dashboard."""
    if not DASHBOARD_PATH.exists():
        raise HTTPException(status_code=404, detail="Dashboard file not found")
    return FileResponse(DASHBOARD_PATH)

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "Finance Dashboard API"
    }

@app.get("/api/v1/source", tags=["Dashboard"], response_model=dict)
async def source_info():
    """Return configured source metadata for the dashboard."""
    return {
        "google_sheets_url": config.GOOGLE_SHEETS_URL,
    }

# ==================== DASHBOARD DATA ====================

def _empty_months():
    return {month: 0.0 for month in range(1, 13)}

def _month_bucket(rows):
    values = _empty_months()
    for month, amount in rows:
        if month:
            values[int(month)] = float(amount or 0)
    return values

def _period_shape(months):
    return {
        "year1": {
            "jan": months[1],
            "feb": months[2],
            "mar": months[3],
            "apr": months[4],
            "may": months[5],
            "jun": months[6],
            "jul": months[7],
            "aug": months[8],
            "sep": months[9],
            "oct": months[10],
            "nov": months[11],
            "dec": months[12],
            "q1": months[1] + months[2] + months[3],
            "q2": months[4] + months[5] + months[6],
            "q3": months[7] + months[8] + months[9],
            "q4": months[10] + months[11] + months[12],
            "total": sum(months.values()),
        }
    }

def _position_shape(months):
    return {
        "year1": {
            "jan": months[1],
            "feb": months[2],
            "mar": months[3],
            "apr": months[4],
            "may": months[5],
            "jun": months[6],
            "jul": months[7],
            "aug": months[8],
            "sep": months[9],
            "oct": months[10],
            "nov": months[11],
            "dec": months[12],
            "q1": months[3],
            "q2": months[6],
            "q3": months[9],
            "q4": months[12],
            "total": months[12],
        }
    }

def _sum(values):
    return float(sum(value or 0 for value in values))

def _latest_balance(db: Session) -> float:
    latest = db.query(models.BankCashMovement).filter(
        models.BankCashMovement.is_deleted == False,
        models.BankCashMovement.balance_after.isnot(None),
    ).order_by(
        models.BankCashMovement.date.desc(),
        models.BankCashMovement.movement_id.desc(),
    ).first()
    if latest:
        return float(latest.balance_after or 0)
    return float(db.query(func.coalesce(func.sum(models.BankCashMovement.amount), 0)).filter(
        models.BankCashMovement.is_deleted == False
    ).scalar() or 0)

def _latest_balance_until(db: Session, end_date) -> float:
    latest = db.query(models.BankCashMovement).filter(
        models.BankCashMovement.is_deleted == False,
        models.BankCashMovement.balance_after.isnot(None),
        models.BankCashMovement.date <= end_date,
    ).order_by(
        models.BankCashMovement.date.desc(),
        models.BankCashMovement.movement_id.desc(),
    ).first()
    if latest:
        return float(latest.balance_after or 0)
    return float(db.query(func.coalesce(func.sum(models.BankCashMovement.amount), 0)).filter(
        models.BankCashMovement.is_deleted == False,
        models.BankCashMovement.date <= end_date,
    ).scalar() or 0)

def _project_initial(project_name: str) -> str:
    return (project_name or "?").strip()[:1].upper() or "?"

def _available_years(db: Session) -> list[int]:
    years = set()
    date_columns = [
        (models.RevenueTransaction, models.RevenueTransaction.date),
        (models.CogsTransaction, models.CogsTransaction.date),
        (models.OverheadTransaction, models.OverheadTransaction.date),
        (models.BankCashMovement, models.BankCashMovement.date),
        (models.Salary, models.Salary.date),
    ]
    for model, column in date_columns:
        rows = db.query(func.distinct(func.extract("year", column))).filter(
            model.is_deleted == False
        ).all()
        years.update(int(row[0]) for row in rows if row[0])
    return sorted(years, reverse=True)

def _scope_for_period(
    db: Session,
    period: str,
    year: Optional[int],
    quarter: Optional[int],
    month: Optional[int],
    week: Optional[int],
):
    years = _available_years(db)
    selected_year = year or (years[0] if years else datetime.utcnow().year)
    selected_period = period if period in {"year", "quarter", "month", "week"} else "year"

    if selected_period == "quarter":
        selected_quarter = min(max(quarter or 1, 1), 4)
        start_month = (selected_quarter - 1) * 3 + 1
        start_date = datetime(selected_year, start_month, 1).date()
        if selected_quarter == 4:
            end_date = datetime(selected_year, 12, 31).date()
        else:
            end_date = datetime(selected_year, start_month + 3, 1).date() - timedelta(days=1)
        label = f"Q{selected_quarter} {selected_year}"
        bucket = "month"
        quarter = selected_quarter
    elif selected_period == "month":
        selected_month = min(max(month or 1, 1), 12)
        start_date = datetime(selected_year, selected_month, 1).date()
        if selected_month == 12:
            end_date = datetime(selected_year, 12, 31).date()
        else:
            end_date = datetime(selected_year, selected_month + 1, 1).date() - timedelta(days=1)
        label = start_date.strftime("%B %Y")
        bucket = "day"
        month = selected_month
    elif selected_period == "week":
        selected_week = min(max(week or 1, 1), 53)
        start_date = datetime.strptime(f"{selected_year}-W{selected_week:02d}-1", "%G-W%V-%u").date()
        end_date = start_date + timedelta(days=6)
        label = f"Week {selected_week}, {selected_year}"
        bucket = "day"
        week = selected_week
    else:
        start_date = datetime(selected_year, 1, 1).date()
        end_date = datetime(selected_year, 12, 31).date()
        label = str(selected_year)
        bucket = "month"

    return {
        "period": selected_period,
        "year": selected_year,
        "quarter": quarter,
        "month": month,
        "week": week,
        "start_date": start_date,
        "end_date": end_date,
        "label": label,
        "bucket": bucket,
        "available_years": years,
    }

def _previous_scope(scope):
    period = scope["period"]
    year = scope["year"]
    if period == "year":
        previous_year = year - 1
        start_date = datetime(previous_year, 1, 1).date()
        end_date = datetime(previous_year, 12, 31).date()
        label = str(previous_year)
    elif period == "quarter":
        quarter = scope["quarter"] or 1
        if quarter == 1:
            previous_year = year - 1
            previous_quarter = 4
        else:
            previous_year = year
            previous_quarter = quarter - 1
        start_month = (previous_quarter - 1) * 3 + 1
        start_date = datetime(previous_year, start_month, 1).date()
        if previous_quarter == 4:
            end_date = datetime(previous_year, 12, 31).date()
        else:
            end_date = datetime(previous_year, start_month + 3, 1).date() - timedelta(days=1)
        label = f"Q{previous_quarter} {previous_year}"
    elif period == "month":
        month = scope["month"] or 1
        if month == 1:
            previous_year = year - 1
            previous_month = 12
        else:
            previous_year = year
            previous_month = month - 1
        start_date = datetime(previous_year, previous_month, 1).date()
        if previous_month == 12:
            end_date = datetime(previous_year, 12, 31).date()
        else:
            end_date = datetime(previous_year, previous_month + 1, 1).date() - timedelta(days=1)
        label = start_date.strftime("%B %Y")
    elif period == "week":
        start_date = scope["start_date"] - timedelta(days=7)
        end_date = scope["end_date"] - timedelta(days=7)
        previous_year, previous_week, _ = start_date.isocalendar()
        label = f"Week {previous_week}, {previous_year}"
    else:
        end_date = scope["start_date"] - timedelta(days=1)
        start_date = end_date
        label = f"Previous {scope['label']}"
    return {
        **scope,
        "start_date": start_date,
        "end_date": end_date,
        "label": label,
    }

def _filter_date(query, column, scope):
    return query.filter(
        column >= scope["start_date"],
        column <= scope["end_date"],
    )

def _bucket_labels(scope):
    if scope["bucket"] == "day":
        labels = []
        current = scope["start_date"]
        while current <= scope["end_date"]:
            labels.append(current.strftime("%d %b"))
            current += timedelta(days=1)
        return labels

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return month_names[scope["start_date"].month - 1:scope["end_date"].month]

def _series_by_scope(db: Session, model, date_column, amount_column, scope):
    if scope["bucket"] == "day":
        rows = _filter_date(db.query(
            date_column,
            func.coalesce(func.sum(amount_column), 0),
        ).filter(model.is_deleted == False), date_column, scope).group_by(date_column).all()
        values_by_day = {row_date: float(amount or 0) for row_date, amount in rows}
        values = []
        current = scope["start_date"]
        while current <= scope["end_date"]:
            values.append(values_by_day.get(current, 0.0))
            current += timedelta(days=1)
        return values

    rows = _filter_date(db.query(
        func.extract("month", date_column),
        func.coalesce(func.sum(amount_column), 0),
    ).filter(model.is_deleted == False), date_column, scope).group_by(func.extract("month", date_column)).all()
    values_by_month = {int(month): float(amount or 0) for month, amount in rows if month}
    return [
        values_by_month.get(month, 0.0)
        for month in range(scope["start_date"].month, scope["end_date"].month + 1)
    ]

def _period_from_series(values):
    months = _empty_months()
    for index, value in enumerate(values[:12], start=1):
        months[index] = value
    shaped = _period_shape(months)
    shaped["year1"]["total"] = float(sum(values))
    return shaped

def _category_total(db: Session, category: str, scope) -> float:
    return float(_filter_date(db.query(
        func.coalesce(func.sum(models.OverheadTransaction.amount), 0)
    ).filter(
        models.OverheadTransaction.is_deleted == False,
        models.OverheadTransaction.overhead_category == category,
    ), models.OverheadTransaction.date, scope).scalar() or 0)

def _sum_for_scope(db: Session, model, date_column, amount_column, scope) -> float:
    return float(_filter_date(db.query(
        func.coalesce(func.sum(amount_column), 0)
    ).filter(
        model.is_deleted == False
    ), date_column, scope).scalar() or 0)

def _pct_change(current: float, previous: float) -> Optional[float]:
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100

def _period_comparisons(
    db: Session,
    scope,
    gross_cash: float,
    frozen_funds: float,
    net_cash: float,
    revenue_total: float,
    cogs_total: float,
    overhead_total: float,
    gross_profit_total: float,
    ebitda_total: float,
    net_result_total: float,
    gross_margin_pct: float,
    net_profit_margin_pct: float,
    operational_margin_pct: float,
    monthly_burnrate: float,
    runway_months: float,
    taxes_total: float,
    salary_total: float,
    social_costs_total: float,
):
    previous = _previous_scope(scope)
    previous_revenue = _sum_for_scope(
        db,
        models.RevenueTransaction,
        models.RevenueTransaction.date,
        models.RevenueTransaction.amount,
        previous,
    )
    previous_cogs = _sum_for_scope(
        db,
        models.CogsTransaction,
        models.CogsTransaction.date,
        models.CogsTransaction.amount,
        previous,
    )
    previous_overhead = _sum_for_scope(
        db,
        models.OverheadTransaction,
        models.OverheadTransaction.date,
        models.OverheadTransaction.amount,
        previous,
    )
    previous_salary = _sum_for_scope(
        db,
        models.Salary,
        models.Salary.date,
        models.Salary.gross_salary,
        previous,
    )
    previous_taxes = _category_total(db, "Taxes", previous)
    previous_social_costs = _category_total(db, "Social Costs", previous)
    previous_frozen_funds = float(_filter_date(db.query(func.coalesce(func.sum(models.BankCashMovement.amount), 0)).filter(
        models.BankCashMovement.is_deleted == False,
        models.BankCashMovement.is_frozen == True
    ), models.BankCashMovement.date, previous).scalar() or 0)
    previous_gross_cash = _latest_balance_until(db, previous["end_date"])
    previous_net_cash = previous_gross_cash - abs(previous_frozen_funds)
    previous_gross_profit = previous_revenue - previous_cogs
    previous_ebitda = previous_gross_profit - previous_overhead
    previous_net_result = previous_ebitda
    previous_gross_margin_pct = (previous_gross_profit / previous_revenue * 100) if previous_revenue else 0
    previous_net_profit_margin_pct = (previous_net_result / previous_revenue * 100) if previous_revenue else 0
    previous_operational_margin_pct = previous_net_profit_margin_pct
    previous_days = max((previous["end_date"] - previous["start_date"]).days + 1, 1)
    previous_normalized_months = max(previous_days / 30.4375, 1 / 30.4375)
    previous_monthly_burnrate = previous_overhead / previous_normalized_months if previous_overhead else 0
    previous_runway_months = previous_net_cash / previous_monthly_burnrate if previous_monthly_burnrate else 0

    return {
        "scope_label": scope["label"],
        "previous_scope_label": previous["label"],
        "previous_start_date": previous["start_date"],
        "previous_end_date": previous["end_date"],
        "gross_cash_position": _pct_change(gross_cash, previous_gross_cash),
        "net_cash_position": _pct_change(net_cash, previous_net_cash),
        "growth_cash_position": _pct_change(gross_cash, previous_gross_cash),
        "revenue": _pct_change(revenue_total, previous_revenue),
        "total_revenue": _pct_change(revenue_total, previous_revenue),
        "operating_expenses": _pct_change(overhead_total, previous_overhead),
        "frozen_funds": _pct_change(abs(frozen_funds), abs(previous_frozen_funds)),
        "cogs": _pct_change(cogs_total, previous_cogs),
        "gross_profit": _pct_change(gross_profit_total, previous_gross_profit),
        "ebitda": _pct_change(ebitda_total, previous_ebitda),
        "net_profit": _pct_change(net_result_total, previous_net_result),
        "net_profit_margin": _pct_change(net_profit_margin_pct, previous_net_profit_margin_pct),
        "operational_margin": _pct_change(operational_margin_pct, previous_operational_margin_pct),
        "gross_margin": _pct_change(gross_margin_pct, previous_gross_margin_pct),
        "burnrate": _pct_change(monthly_burnrate, previous_monthly_burnrate),
        "short_term_payables": _pct_change(overhead_total, previous_overhead),
        "runway_months": _pct_change(runway_months, previous_runway_months),
        "runway_cash": _pct_change(net_cash, previous_net_cash),
        "forecasted_net_cash": _pct_change(net_cash, previous_net_cash),
        "reserves_solvability": _pct_change(gross_cash, previous_gross_cash),
        "cost_taxes": _pct_change(taxes_total, previous_taxes),
        "cost_salaries": _pct_change(salary_total, previous_salary),
        "cost_social": _pct_change(social_costs_total, previous_social_costs),
        "cost_project": _pct_change(cogs_total, previous_cogs),
    }

@app.get("/api/v1/dashboard-data/available-years", tags=["Dashboard"], response_model=dict)
async def get_available_years(db: Session = Depends(get_db)):
    years = _available_years(db)
    return {
        "available_years": years,
        "default_year": years[0] if years else datetime.utcnow().year,
    }

@app.get("/api/v1/dashboard-data", tags=["Dashboard"], response_model=dict)
async def dashboard_data(
    db: Session = Depends(get_db),
    year: Optional[int] = Query(None),
    period: str = Query("year"),
    quarter: Optional[int] = Query(None, ge=1, le=4),
    month: Optional[int] = Query(None, ge=1, le=12),
    week: Optional[int] = Query(None, ge=1, le=53),
):
    """Return database-backed dashboard data for one explicit time scope."""
    scope = _scope_for_period(db, period, year, quarter, month, week)

    revenue_series = _series_by_scope(
        db,
        models.RevenueTransaction,
        models.RevenueTransaction.date,
        models.RevenueTransaction.amount,
        scope,
    )
    cogs_series = _series_by_scope(
        db,
        models.CogsTransaction,
        models.CogsTransaction.date,
        models.CogsTransaction.amount,
        scope,
    )
    overhead_series = _series_by_scope(
        db,
        models.OverheadTransaction,
        models.OverheadTransaction.date,
        models.OverheadTransaction.amount,
        scope,
    )
    salary_series = _series_by_scope(
        db,
        models.Salary,
        models.Salary.date,
        models.Salary.gross_salary,
        scope,
    )

    profit_series = [
        revenue - cogs - overhead
        for revenue, cogs, overhead in zip(revenue_series, cogs_series, overhead_series)
    ]
    gross_profit_series = [
        revenue - cogs
        for revenue, cogs in zip(revenue_series, cogs_series)
    ]
    cash_series = []
    running_cash = 0.0
    for value in profit_series:
        running_cash += value
        cash_series.append(running_cash)

    gross_cash = _latest_balance(db)
    frozen_funds = float(_filter_date(db.query(func.coalesce(func.sum(models.BankCashMovement.amount), 0)).filter(
        models.BankCashMovement.is_deleted == False,
        models.BankCashMovement.is_frozen == True
    ), models.BankCashMovement.date, scope).scalar() or 0)
    net_cash = gross_cash - abs(frozen_funds)

    revenue_total = sum(revenue_series)
    cogs_total = sum(cogs_series)
    overhead_total = sum(overhead_series)
    gross_profit_total = revenue_total - cogs_total
    ebitda_total = gross_profit_total - overhead_total
    net_result_total = ebitda_total
    gross_margin_pct = (gross_profit_total / revenue_total * 100) if revenue_total else 0
    net_profit_margin_pct = (net_result_total / revenue_total * 100) if revenue_total else 0
    operational_margin_pct = net_profit_margin_pct

    revenue_stream_query = db.query(
        models.RevenueStream.revenue_stream_id,
        models.RevenueStream.stream_name,
        (
            models.RevenueTransaction.date
            if scope["bucket"] == "day"
            else func.extract("month", models.RevenueTransaction.date)
        ).label("bucket"),
        func.coalesce(func.sum(models.RevenueTransaction.amount), 0).label("amount"),
    ).join(
        models.Project,
        models.Project.revenue_stream_id == models.RevenueStream.revenue_stream_id,
    ).join(
        models.RevenueTransaction,
        models.RevenueTransaction.project_id == models.Project.project_id,
    ).filter(
        models.RevenueStream.is_deleted == False,
        models.Project.is_deleted == False,
        models.RevenueTransaction.is_deleted == False,
    )
    revenue_stream_rows = _filter_date(
        revenue_stream_query,
        models.RevenueTransaction.date,
        scope,
    ).group_by(
        models.RevenueStream.revenue_stream_id,
        models.RevenueStream.stream_name,
        (
            models.RevenueTransaction.date
            if scope["bucket"] == "day"
            else func.extract("month", models.RevenueTransaction.date)
        ),
    ).all()

    stream_names = []
    stream_ids = []
    stream_values = {}
    labels = _bucket_labels(scope)
    for stream_id, stream_name, bucket, amount in revenue_stream_rows:
        if stream_id not in stream_values:
            stream_names.append(stream_name)
            stream_ids.append(stream_id)
            stream_values[stream_id] = [0.0 for _ in labels]
        if scope["bucket"] == "day":
            index = (bucket - scope["start_date"]).days
        else:
            index = int(bucket) - scope["start_date"].month
        if 0 <= index < len(labels):
            stream_values[stream_id][index] = float(amount or 0)

    stream_payload = {}
    stream_chart_series = []
    for index, values in enumerate(stream_values.values()):
        if index >= 4:
            break
        stream_payload[f"stream{index + 1}"] = _period_from_series(values)
        stream_chart_series.append(values)
    for index in range(len(stream_payload), 4):
        stream_payload[f"stream{index + 1}"] = _period_from_series([])
        stream_chart_series.append([0.0 for _ in labels])

    overhead_category_query = db.query(
        models.OverheadTransaction.overhead_category,
        func.coalesce(func.sum(models.OverheadTransaction.amount), 0),
    ).filter(
        models.OverheadTransaction.is_deleted == False
    )
    overhead_category_rows = _filter_date(
        overhead_category_query,
        models.OverheadTransaction.date,
        scope,
    ).group_by(
        models.OverheadTransaction.overhead_category
    ).all()

    project_rows = db.query(models.Project).filter(
        models.Project.is_deleted == False
    ).order_by(models.Project.project_id).all()
    project_table = []
    for project in project_rows:
        project_revenue = float(_filter_date(db.query(func.coalesce(func.sum(models.RevenueTransaction.amount), 0)).filter(
            models.RevenueTransaction.is_deleted == False,
            models.RevenueTransaction.project_id == project.project_id
        ), models.RevenueTransaction.date, scope).scalar() or 0)
        project_cogs = float(_filter_date(db.query(func.coalesce(func.sum(models.CogsTransaction.amount), 0)).filter(
            models.CogsTransaction.is_deleted == False,
            models.CogsTransaction.project_id == project.project_id
        ), models.CogsTransaction.date, scope).scalar() or 0)
        project_table.append({
            "project_id": project.project_id,
            "project_name": project.project_name,
            "initial": _project_initial(project.project_name),
            "revenue": project_revenue,
            "cogs": project_cogs,
            "overhead": 0,
            "net_profit": project_revenue - project_cogs,
        })

    forecast_table = []
    for index, label in enumerate(labels):
        income = profit_series[index]
        forecast_table.append({
            "period": label.upper(),
            "revenue": revenue_series[index],
            "cogs": cogs_series[index],
            "overhead": overhead_series[index],
            "income": income,
            "net_cash_position": cash_series[index],
        })

    bank_position_months = {month: gross_cash for month in range(1, 13)}
    net_position_months = {month: net_cash for month in range(1, 13)}
    frozen_position_months = {month: abs(frozen_funds) for month in range(1, 13)}
    taxes_total = _category_total(db, "Taxes", scope)
    social_costs_total = _category_total(db, "Social Costs", scope)
    salary_total = sum(salary_series)
    scope_days = max((scope["end_date"] - scope["start_date"]).days + 1, 1)
    normalized_months = max(scope_days / 30.4375, 1 / 30.4375)
    monthly_burnrate = overhead_total / normalized_months if overhead_total else 0
    runway_months = net_cash / monthly_burnrate if monthly_burnrate else 0
    comparisons = _period_comparisons(
        db,
        scope,
        gross_cash,
        frozen_funds,
        net_cash,
        revenue_total,
        cogs_total,
        overhead_total,
        gross_profit_total,
        ebitda_total,
        net_result_total,
        gross_margin_pct,
        net_profit_margin_pct,
        operational_margin_pct,
        monthly_burnrate,
        runway_months,
        taxes_total,
        salary_total,
        social_costs_total,
    )
    previous_scope = _previous_scope(scope)
    for index, stream_id in enumerate(stream_ids[:4], start=1):
        current_stream_total = float(sum(stream_values.get(stream_id, [])))
        previous_stream_total = float(_filter_date(db.query(
            func.coalesce(func.sum(models.RevenueTransaction.amount), 0)
        ).join(
            models.Project,
            models.Project.project_id == models.RevenueTransaction.project_id,
        ).filter(
            models.Project.revenue_stream_id == stream_id,
            models.Project.is_deleted == False,
            models.RevenueTransaction.is_deleted == False,
        ), models.RevenueTransaction.date, previous_scope).scalar() or 0)
        comparisons[f"revenue_stream_{index}"] = _pct_change(current_stream_total, previous_stream_total)
    for index in range(len(stream_ids[:4]) + 1, 5):
        comparisons[f"revenue_stream_{index}"] = None

    return {
        "summary": {
            "totalRevenue": _period_from_series(revenue_series),
            "cogs": _period_from_series(cogs_series),
            "operatingExpenses": _period_from_series(overhead_series),
            "grossProfit": _period_from_series(gross_profit_series),
            "ebitda": _period_from_series(profit_series),
            "netResult": _period_from_series(profit_series),
            "taxes": _period_from_series([taxes_total]),
            "totals": {
                "revenue": revenue_total,
                "cogs": cogs_total,
                "overhead": overhead_total,
                "gross_profit": gross_profit_total,
                "ebitda": ebitda_total,
                "net_result": net_result_total,
            },
        },
        "liquidityPosition": {
            "bankBalance": _position_shape(bank_position_months),
            "netCashPosition": _position_shape(net_position_months),
            "frozenFunds": _position_shape(frozen_position_months),
            "cashByMonth": _period_from_series(cash_series),
        },
        "revenueStreams": stream_payload,
        "revenueStreamNames": stream_names[:4],
        "operatingExpenses": {
            "salaries": _period_from_series([salary_total]),
            "generalCosts": _period_from_series([social_costs_total]),
        },
        "cogs": {
            "projectCosts": _period_from_series(cogs_series),
        },
        "charts": {
            "labels": labels,
            "forecast": {
                "revenue": revenue_series,
                "cogs": cogs_series,
                "overhead": overhead_series,
                "profit": profit_series,
            },
            "revenueStreams": stream_chart_series[:4],
            "cashPosition": cash_series,
            "costRatio": {
                "labels": ["Taxes", "Salary contracts", "Social Costs", "Project Costs"],
                "values": [taxes_total, salary_total, social_costs_total, cogs_total],
            },
        },
        "metrics": {
            "gross_margin_pct": gross_margin_pct,
            "net_profit_margin_pct": net_profit_margin_pct,
            "operational_margin_pct": operational_margin_pct,
            "monthly_burnrate": monthly_burnrate,
            "runway_months": runway_months,
            "short_term_payables": overhead_total,
        },
        "comparisons": comparisons,
        "tables": {
            "projects": project_table[:12],
            "overheadCategories": [
                {"category": category, "amount": float(amount or 0)}
                for category, amount in overhead_category_rows
            ],
            "forecastCash": forecast_table,
        },
        "scope": {
            "period": scope["period"],
            "year": scope["year"],
            "start_date": scope["start_date"],
            "end_date": scope["end_date"],
            "label": scope["label"],
            "available_years": scope["available_years"],
        },
        "updatedAt": datetime.utcnow(),
    }

# ==================== SYNC ENDPOINTS ====================

@app.post("/api/v1/sync", tags=["Sync"], response_model=dict)
async def sync_from_sheets(db: Session = Depends(get_db)):
    """Manually trigger synchronization from Google Sheets"""
    try:
        if not syncer.sheet:
            if not syncer.authenticate():
                raise HTTPException(
                    status_code=500,
                    detail="Failed to authenticate with Google Sheets"
                )
        
        sync_start = datetime.utcnow()
        results = syncer.sync_all(db)
        sync_end = datetime.utcnow()
        
        # Calculate totals
        total_inserted = sum(r.get("inserted", 0) for r in results.values())
        total_updated = sum(r.get("updated", 0) for r in results.values())
        total_deleted = sum(r.get("deleted", 0) for r in results.values())
        
        return {
            "status": "success",
            "duration_seconds": (sync_end - sync_start).total_seconds(),
            "total_inserted": total_inserted,
            "total_updated": total_updated,
            "total_deleted": total_deleted,
            "details": results,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sync/logs", tags=["Sync"], response_model=list)
async def get_sync_logs(
    limit: int = Query(10, le=100),
    db: Session = Depends(get_db)
):
    """Get recent synchronization logs"""
    logs = db.query(models.SyncLog).order_by(
        models.SyncLog.created_at.desc()
    ).limit(limit).all()
    return [log.to_dict() for log in logs]

# ==================== REVENUE STREAMS ====================

@app.get("/api/v1/revenue-streams", tags=["Revenue Streams"], response_model=list)
async def list_revenue_streams(db: Session = Depends(get_db)):
    """List all revenue streams"""
    streams = db.query(models.RevenueStream).filter(models.RevenueStream.is_deleted == False).all()
    return [s.to_dict() for s in streams]

@app.get("/api/v1/revenue-streams/{stream_id}", tags=["Revenue Streams"], response_model=schemas.RevenueStreamResponse)
async def get_revenue_stream(stream_id: str, db: Session = Depends(get_db)):
    """Get a specific revenue stream"""
    stream = db.query(models.RevenueStream).filter_by(revenue_stream_id=stream_id, is_deleted=False).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Revenue stream not found")
    return stream

# ==================== EMPLOYEES ====================

@app.get("/api/v1/employees", tags=["Employees"], response_model=list)
async def list_employees(
    is_active: bool = Query(None),
    db: Session = Depends(get_db)
):
    """List all employees"""
    query = db.query(models.Employee).filter(models.Employee.is_deleted == False)
    if is_active is not None:
        query = query.filter(models.Employee.is_active == is_active)
    employees = query.all()
    return [e.to_dict() for e in employees]

@app.get("/api/v1/employees/{employee_id}", tags=["Employees"], response_model=schemas.EmployeeResponse)
async def get_employee(employee_id: str, db: Session = Depends(get_db)):
    """Get a specific employee"""
    employee = db.query(models.Employee).filter_by(employee_id=employee_id, is_deleted=False).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@app.post("/api/v1/employees", tags=["Employees"], response_model=schemas.EmployeeResponse)
async def create_employee(employee: schemas.EmployeeCreate, db: Session = Depends(get_db)):
    """Create a new employee"""
    existing = db.query(models.Employee).filter_by(employee_id=employee.employee_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee already exists")
    
    db_employee = models.Employee(**employee.model_dump())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@app.patch("/api/v1/employees/{employee_id}", tags=["Employees"], response_model=schemas.EmployeeResponse)
async def update_employee(
    employee_id: str,
    employee_update: schemas.EmployeeUpdate,
    db: Session = Depends(get_db)
):
    """Update an employee"""
    db_employee = db.query(models.Employee).filter_by(employee_id=employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = employee_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_employee, key, value)
    
    db_employee.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_employee)
    return db_employee

# ==================== PROJECTS ====================

@app.get("/api/v1/projects", tags=["Projects"], response_model=list)
async def list_projects(
    status: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List all projects"""
    query = db.query(models.Project).filter(models.Project.is_deleted == False)
    if status:
        query = query.filter(models.Project.status == status)
    
    projects = query.offset(skip).limit(limit).all()
    return [p.to_dict() for p in projects]

@app.get("/api/v1/projects/{project_id}", tags=["Projects"], response_model=schemas.ProjectResponse)
async def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get a specific project"""
    project = db.query(models.Project).filter_by(project_id=project_id, is_deleted=False).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@app.post("/api/v1/projects", tags=["Projects"], response_model=schemas.ProjectResponse)
async def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project"""
    existing = db.query(models.Project).filter_by(project_id=project.project_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project already exists")
    
    db_project = models.Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@app.patch("/api/v1/projects/{project_id}", tags=["Projects"], response_model=schemas.ProjectResponse)
async def update_project(
    project_id: str,
    project_update: schemas.ProjectUpdate,
    db: Session = Depends(get_db)
):
    """Update a project"""
    db_project = db.query(models.Project).filter_by(project_id=project_id, is_deleted=False).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = project_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)
    
    db_project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_project)
    return db_project

@app.delete("/api/v1/projects/{project_id}", tags=["Projects"])
async def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Soft delete a project"""
    db_project = db.query(models.Project).filter_by(project_id=project_id, is_deleted=False).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db_project.is_deleted = True
    db_project.deleted_at = datetime.utcnow()
    db.commit()
    return {"status": "deleted", "project_id": project_id}

# ==================== REVENUE TRANSACTIONS ====================

@app.get("/api/v1/revenue-transactions", tags=["Revenue"], response_model=list)
async def list_revenue_transactions(
    project_id: str = Query(None),
    payment_status: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List revenue transactions"""
    query = db.query(models.RevenueTransaction).filter(models.RevenueTransaction.is_deleted == False)
    
    if project_id:
        query = query.filter(models.RevenueTransaction.project_id == project_id)
    if payment_status:
        query = query.filter(models.RevenueTransaction.payment_status == payment_status)
    
    transactions = query.offset(skip).limit(limit).all()
    return [t.to_dict() for t in transactions]

@app.get("/api/v1/revenue-transactions/{transaction_id}", tags=["Revenue"], response_model=schemas.RevenueTransactionResponse)
async def get_revenue_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Get a specific revenue transaction"""
    transaction = db.query(models.RevenueTransaction).filter_by(
        transaction_id=transaction_id,
        is_deleted=False
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction

@app.post("/api/v1/revenue-transactions", tags=["Revenue"], response_model=schemas.RevenueTransactionResponse)
async def create_revenue_transaction(
    transaction: schemas.RevenueTransactionCreate,
    db: Session = Depends(get_db)
):
    """Create a new revenue transaction"""
    db_transaction = models.RevenueTransaction(**transaction.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.patch("/api/v1/revenue-transactions/{transaction_id}", tags=["Revenue"])
async def update_revenue_transaction(
    transaction_id: str,
    transaction_update: schemas.RevenueTransactionUpdate,
    db: Session = Depends(get_db)
):
    """Update a revenue transaction"""
    db_transaction = db.query(models.RevenueTransaction).filter_by(
        transaction_id=transaction_id,
        is_deleted=False
    ).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    update_data = transaction_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_transaction, key, value)
    
    db_transaction.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.delete("/api/v1/revenue-transactions/{transaction_id}", tags=["Revenue"])
async def delete_revenue_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Soft delete a revenue transaction"""
    db_transaction = db.query(models.RevenueTransaction).filter_by(
        transaction_id=transaction_id,
        is_deleted=False
    ).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    db_transaction.is_deleted = True
    db_transaction.deleted_at = datetime.utcnow()
    db.commit()
    return {"status": "deleted", "transaction_id": transaction_id}

# ==================== COGS TRANSACTIONS ====================

@app.get("/api/v1/cogs-transactions", tags=["COGS"], response_model=list)
async def list_cogs_transactions(
    project_id: str = Query(None),
    cost_category: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List COGS transactions"""
    query = db.query(models.CogsTransaction).filter(models.CogsTransaction.is_deleted == False)
    
    if project_id:
        query = query.filter(models.CogsTransaction.project_id == project_id)
    if cost_category:
        query = query.filter(models.CogsTransaction.cost_category == cost_category)
    
    transactions = query.offset(skip).limit(limit).all()
    return [t.to_dict() for t in transactions]

@app.get("/api/v1/cogs-transactions/{transaction_id}", tags=["COGS"], response_model=schemas.CogsTransactionResponse)
async def get_cogs_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Get a specific COGS transaction"""
    transaction = db.query(models.CogsTransaction).filter_by(
        transaction_id=transaction_id,
        is_deleted=False
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction

@app.post("/api/v1/cogs-transactions", tags=["COGS"], response_model=schemas.CogsTransactionResponse)
async def create_cogs_transaction(
    transaction: schemas.CogsTransactionCreate,
    db: Session = Depends(get_db)
):
    """Create a new COGS transaction"""
    db_transaction = models.CogsTransaction(**transaction.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.delete("/api/v1/cogs-transactions/{transaction_id}", tags=["COGS"])
async def delete_cogs_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Soft delete a COGS transaction"""
    db_transaction = db.query(models.CogsTransaction).filter_by(
        transaction_id=transaction_id,
        is_deleted=False
    ).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    db_transaction.is_deleted = True
    db_transaction.deleted_at = datetime.utcnow()
    db.commit()
    return {"status": "deleted", "transaction_id": transaction_id}

# ==================== OVERHEAD TRANSACTIONS ====================

@app.get("/api/v1/overhead-transactions", tags=["Overhead"], response_model=list)
async def list_overhead_transactions(
    overhead_category: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List overhead transactions"""
    query = db.query(models.OverheadTransaction).filter(models.OverheadTransaction.is_deleted == False)
    
    if overhead_category:
        query = query.filter(models.OverheadTransaction.overhead_category == overhead_category)
    
    transactions = query.offset(skip).limit(limit).all()
    return [t.to_dict() for t in transactions]

@app.get("/api/v1/overhead-transactions/{transaction_id}", tags=["Overhead"])
async def get_overhead_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Get a specific overhead transaction"""
    transaction = db.query(models.OverheadTransaction).filter_by(
        transaction_id=transaction_id,
        is_deleted=False
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction

@app.post("/api/v1/overhead-transactions", tags=["Overhead"])
async def create_overhead_transaction(
    transaction: schemas.OverheadTransactionCreate,
    db: Session = Depends(get_db)
):
    """Create a new overhead transaction"""
    db_transaction = models.OverheadTransaction(**transaction.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.delete("/api/v1/overhead-transactions/{transaction_id}", tags=["Overhead"])
async def delete_overhead_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Soft delete an overhead transaction"""
    db_transaction = db.query(models.OverheadTransaction).filter_by(
        transaction_id=transaction_id,
        is_deleted=False
    ).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    db_transaction.is_deleted = True
    db_transaction.deleted_at = datetime.utcnow()
    db.commit()
    return {"status": "deleted", "transaction_id": transaction_id}

# ==================== BANK CASH MOVEMENTS ====================

@app.get("/api/v1/bank-movements", tags=["Banking"], response_model=list)
async def list_bank_movements(
    bank_account: str = Query(None),
    movement_type: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List bank cash movements"""
    query = db.query(models.BankCashMovement).filter(models.BankCashMovement.is_deleted == False)
    
    if bank_account:
        query = query.filter(models.BankCashMovement.bank_account == bank_account)
    if movement_type:
        query = query.filter(models.BankCashMovement.movement_type == movement_type)
    
    movements = query.offset(skip).limit(limit).all()
    return [m.to_dict() for m in movements]

@app.get("/api/v1/bank-movements/{movement_id}", tags=["Banking"])
async def get_bank_movement(movement_id: str, db: Session = Depends(get_db)):
    """Get a specific bank movement"""
    movement = db.query(models.BankCashMovement).filter_by(
        movement_id=movement_id,
        is_deleted=False
    ).first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    return movement

# ==================== SALARIES ====================

@app.get("/api/v1/salaries", tags=["Payroll"], response_model=list)
async def list_salaries(
    employee_id: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List salaries"""
    query = db.query(models.Salary).filter(models.Salary.is_deleted == False)
    
    if employee_id:
        query = query.filter(models.Salary.employee_id == employee_id)
    
    salaries = query.offset(skip).limit(limit).all()
    return [s.to_dict() for s in salaries]

@app.get("/api/v1/salaries/{salary_id}", tags=["Payroll"])
async def get_salary(salary_id: str, db: Session = Depends(get_db)):
    """Get a specific salary"""
    salary = db.query(models.Salary).filter_by(
        salary_id=salary_id,
        is_deleted=False
    ).first()
    if not salary:
        raise HTTPException(status_code=404, detail="Salary not found")
    return salary

@app.post("/api/v1/salaries", tags=["Payroll"])
async def create_salary(salary: schemas.SalaryCreate, db: Session = Depends(get_db)):
    """Create a new salary record"""
    db_salary = models.Salary(**salary.model_dump())
    db.add(db_salary)
    db.commit()
    db.refresh(db_salary)
    return db_salary

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_RELOAD
    )
