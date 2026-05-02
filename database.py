"""Database connection and session management"""
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker, Session
from config import config

# Create database engine
engine = create_engine(
    config.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True  # Verify connections before using them
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db() -> Session:
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database"""
    try:
        import models

        models.Base.metadata.create_all(bind=engine)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("""
                ALTER TABLE revenue_streams
                ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP
            """))
            conn.execute(text("""
                ALTER TABLE employees
                ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP
            """))
            conn.execute(text("""
                ALTER TABLE overhead_transactions
                DROP CONSTRAINT IF EXISTS overhead_transactions_overhead_category_check
            """))
            conn.execute(text("""
                ALTER TABLE overhead_transactions
                ADD CONSTRAINT overhead_transactions_overhead_category_check
                CHECK (
                    overhead_category IN (
                        'Taxes',
                        'Social Costs',
                        'Car Lease',
                        'Office Costs',
                        'Sell Costs',
                        'Financial Burdens',
                        'Other',
                        'Other Costs'
                    )
                )
            """))
            conn.commit()
        print("✓ Database connection successful")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False
