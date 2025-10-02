import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db, Base
from app.models import Advertiser, Campaign, Insertion, Creator, ConvUpload, Conversion
from datetime import date
from sqlalchemy.dialects.postgresql import DATERANGE

# Test database URL (use in-memory SQLite for testing)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop tables after each test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_data(db_session):
    """Create test data for conversions tests."""
    # Create advertiser
    advertiser = Advertiser(
        advertiser_id=1,
        name="Test Advertiser",
        category="Test Category"
    )
    db_session.add(advertiser)
    
    # Create campaign
    campaign = Campaign(
        campaign_id=1,
        advertiser_id=1,
        name="Test Campaign",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        notes="Test campaign"
    )
    db_session.add(campaign)
    
    # Create insertion
    insertion = Insertion(
        insertion_id=1,
        campaign_id=1,
        month_start=date(2025, 9, 1),
        month_end=date(2025, 9, 30),
        cpc=0.50
    )
    db_session.add(insertion)
    
    # Create creator
    creator = Creator(
        creator_id=1,
        name="Test Creator",
        acct_id="TEST123",
        owner_email="creator@example.com",
        topic="Test Topic",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z"
    )
    db_session.add(creator)
    
    db_session.commit()
    
    return {
        "advertiser": advertiser,
        "campaign": campaign,
        "insertion": insertion,
        "creator": creator
    }
