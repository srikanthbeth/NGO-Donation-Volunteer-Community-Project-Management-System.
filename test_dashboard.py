import os
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv(".env")

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:Srik8499@localhost:5433/ngo_management_test",
)

import pytest
from fastapi.testclient import TestClient

from db.base import Base
from db.session import SessionLocal
from main import app
from models.user import User


client = TestClient(app)
PASSWORD = "TestPassword123!"


@pytest.fixture(autouse=True)
def clean_database():
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_user(role="NGO_MANAGER"):
    email = f"dashboard_{uuid4().hex[:10]}@example.com"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Dashboard Test User",
            "email": email,
            "password": PASSWORD,
        },
    )
    assert response.status_code in (200, 201), response.text

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        user.role = role
        db.commit()
    finally:
        db.close()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login_response.status_code == 200, login_response.text

    return auth_headers(login_response.json()["access_token"])


def test_unauthenticated_user_cannot_view_dashboard():
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 401


def test_ngo_manager_can_view_dashboard():
    headers = create_user("NGO_MANAGER")

    response = client.get(
        "/api/v1/dashboard/summary",
        headers=headers,
    )

    assert response.status_code == 200, response.text


def test_super_admin_can_view_dashboard():
    headers = create_user("SUPER_ADMIN")

    response = client.get(
        "/api/v1/dashboard/summary",
        headers=headers,
    )

    assert response.status_code == 200, response.text


def test_donor_cannot_view_dashboard():
    headers = create_user("DONOR")

    response = client.get(
        "/api/v1/dashboard/summary",
        headers=headers,
    )

    assert response.status_code == 403


def test_dashboard_empty_database_returns_zero_metrics():
    headers = create_user("NGO_MANAGER")

    response = client.get(
        "/api/v1/dashboard/summary",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total_donations"] == 0
    assert data["confirmed_donations"] == 0
    assert data["active_fundraising_campaigns"] == 0
    assert data["total_volunteers"] == 0
    assert data["active_community_projects"] == 0
    assert data["pending_project_approvals"] == 0
    assert data["pending_expense_approvals"] == 0
    assert data["total_beneficiaries_served"] == 0
    assert data["total_volunteer_hours"] == "0.00"

    assert data["campaign_goal_achievement"]["active_campaigns"] == 0
    assert data["campaign_goal_achievement"]["achievement_percentage"] == 0.0

    assert data["resource_stock_levels"]["active_resources"] == 0
    assert data["resource_stock_levels"]["total_quantity_available"] == 0
    assert data["resource_stock_levels"]["low_stock_resources"] == 0

    assert data["project_budget_utilization"]["utilization_percentage"] == 0.0