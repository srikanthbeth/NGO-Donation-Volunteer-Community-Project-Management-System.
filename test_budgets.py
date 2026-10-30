
import os
from uuid import uuid4
from decimal import Decimal

import pytest
from dotenv import load_dotenv

load_dotenv(".env")

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:Srik8499@localhost:5433/ngo_management_system_test",
)

from fastapi.testclient import TestClient
from sqlalchemy import delete

from main import app
from db.base import Base
from db.session import SessionLocal
from models.user import User


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    """Clean tables before and after each test."""
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
    finally:
        db.close()


def create_user(role="NGO_MANAGER"):
    """Register a user, assign the requested role, and log in."""
    suffix = uuid4().hex[:10]
    email = f"{role.lower()}_{suffix}@example.com"
    password = "StrongPassword123!"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Test {role}",
            "email": email,
            "password": password,
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
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]
    return {
        "email": email,
        "password": password,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def create_project(headers):
    """Create a project for budget tests."""
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": f"Budget Project {uuid4().hex[:8]}",
            "description": "Community development project for budget tests.",
            "location": "Hyderabad",
            "start_date": "2027-01-01",
            "end_date": "2027-12-31",
            "budget": 50000,
            "currency": "INR",
            "status": "DRAFT",
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def create_budget(headers, project_id, amount="10000.00"):
    response = client.post(
        "/api/v1/budgets",
        headers=headers,
        json={
            "project_id": project_id,
            "allocated_amount": amount,
            "currency": "INR",
            "description": "Community project operating budget",
        },
    )
    return response


def approve_budget(budget_id, headers):
    return client.patch(
        f"/api/v1/budgets/{budget_id}/review",
        headers=headers,
        json={
            "status": "APPROVED",
            "approval_comments": "Budget approved for project activities.",
        },
    )


# -------------------------------------------------------------------
# Budget creation and validation
# -------------------------------------------------------------------

def test_manager_can_create_project_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = create_budget(manager["headers"], project["id"])

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_id"] == project["id"]
    assert Decimal(str(data["allocated_amount"])) == Decimal("10000.00")
    assert data["currency"] == "INR"
    assert data["status"] == "PENDING"


def test_created_budget_records_creator():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = create_budget(manager["headers"], project["id"])

    assert response.status_code == 201, response.text
    assert response.json()["created_by"] is not None


def test_budget_requires_authentication():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = create_budget({}, project["id"])

    assert response.status_code == 401


@pytest.mark.parametrize("role", ["VOLUNTEER", "DONOR", "VOLUNTEER_COORDINATOR"])
def test_unauthorized_role_cannot_create_budget(role):
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    user = create_user(role)

    response = create_budget(user["headers"], project["id"])

    assert response.status_code == 403


def test_finance_officer_cannot_create_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    finance = create_user("FINANCE_OFFICER")

    response = create_budget(finance["headers"], project["id"])

    assert response.status_code == 403


def test_budget_requires_existing_project():
    manager = create_user("NGO_MANAGER")

    response = create_budget(manager["headers"], 999999)

    assert response.status_code in (404, 422)


def test_budget_requires_exactly_one_parent():
    manager = create_user("NGO_MANAGER")

    response = client.post(
        "/api/v1/budgets",
        headers=manager["headers"],
        json={
            "allocated_amount": "10000.00",
            "currency": "INR",
            "description": "Missing project or campaign",
        },
    )

    assert response.status_code == 422


def test_budget_rejects_both_project_and_campaign():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = client.post(
        "/api/v1/budgets",
        headers=manager["headers"],
        json={
            "project_id": project["id"],
            "campaign_id": 1,
            "allocated_amount": "10000.00",
            "currency": "INR",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("amount", ["0", "-1", "-100.00"])
def test_budget_rejects_nonpositive_amount(amount):
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = create_budget(manager["headers"], project["id"], amount)

    assert response.status_code == 422


def test_budget_rejects_invalid_currency():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = client.post(
        "/api/v1/budgets",
        headers=manager["headers"],
        json={
            "project_id": project["id"],
            "allocated_amount": "10000.00",
            "currency": "INDIA",
        },
    )

    assert response.status_code == 422


# -------------------------------------------------------------------
# Reading and access control
# -------------------------------------------------------------------

def test_creator_can_get_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    response = client.get(
        f"/api/v1/budgets/{created.json()['id']}",
        headers=manager["headers"],
    )

    assert response.status_code == 200
    assert response.json()["id"] == created.json()["id"]


def test_finance_officer_can_get_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    response = client.get(
        f"/api/v1/budgets/{created.json()['id']}",
        headers=finance["headers"],
    )

    assert response.status_code == 200


def test_unrelated_manager_cannot_get_another_managers_budget():
    manager1 = create_user("NGO_MANAGER")
    project = create_project(manager1["headers"])
    created = create_budget(manager1["headers"], project["id"])
    assert created.status_code == 201, created.text

    manager2 = create_user("NGO_MANAGER")
    response = client.get(
        f"/api/v1/budgets/{created.json()['id']}",
        headers=manager2["headers"],
    )

    assert response.status_code == 403


def test_get_nonexistent_budget_returns_not_found():
    manager = create_user("NGO_MANAGER")

    response = client.get(
        "/api/v1/budgets/999999",
        headers=manager["headers"],
    )

    assert response.status_code == 404


def test_creator_can_list_own_budgets():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    response = client.get(
        "/api/v1/budgets",
        headers=manager["headers"],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["id"] == created.json()["id"] for item in data["items"])


def test_finance_officer_can_list_budgets():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    response = client.get(
        "/api/v1/budgets",
        headers=finance["headers"],
    )

    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_budget_list_supports_pagination():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    for _ in range(3):
        response = create_budget(manager["headers"], project["id"])
        assert response.status_code == 201, response.text

    response = client.get(
        "/api/v1/budgets?page=1&page_size=2",
        headers=manager["headers"],
    )

    assert response.status_code == 200
    assert response.json()["page"] == 1
    assert response.json()["page_size"] == 2
    assert len(response.json()["items"]) <= 2


def test_budget_list_rejects_invalid_pagination():
    manager = create_user("NGO_MANAGER")

    response = client.get(
        "/api/v1/budgets?page=0",
        headers=manager["headers"],
    )

    assert response.status_code == 422


# -------------------------------------------------------------------
# Budget approval and rejection
# -------------------------------------------------------------------

def test_finance_officer_can_approve_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    response = approve_budget(created.json()["id"], finance["headers"])

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"
    assert response.json()["approved_by"] is not None


def test_super_admin_can_approve_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    admin = create_user("SUPER_ADMIN")
    response = approve_budget(created.json()["id"], admin["headers"])

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"


def test_manager_cannot_approve_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    response = approve_budget(created.json()["id"], manager["headers"])

    assert response.status_code == 403


def test_volunteer_cannot_approve_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    volunteer = create_user("VOLUNTEER")
    response = approve_budget(created.json()["id"], volunteer["headers"])

    assert response.status_code == 403


def test_finance_officer_can_reject_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    response = client.patch(
        f"/api/v1/budgets/{created.json()['id']}/review",
        headers=finance["headers"],
        json={
            "status": "REJECTED",
            "approval_comments": "Please revise the allocation.",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REJECTED"


def test_cannot_review_budget_twice_after_approval():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    first = approve_budget(created.json()["id"], finance["headers"])
    assert first.status_code == 200, first.text

    second = client.patch(
        f"/api/v1/budgets/{created.json()['id']}/review",
        headers=finance["headers"],
        json={"status": "REJECTED", "approval_comments": "Changed decision"},
    )

    assert second.status_code == 409


def test_review_rejects_invalid_status():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    response = client.patch(
        f"/api/v1/budgets/{created.json()['id']}/review",
        headers=finance["headers"],
        json={"status": "CLOSED"},
    )

    assert response.status_code == 422


# -------------------------------------------------------------------
# Updating and closing budgets
# -------------------------------------------------------------------

def test_creator_can_update_rejected_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text
    budget_id = created.json()["id"]

    finance = create_user("FINANCE_OFFICER")
    rejected = client.patch(
        f"/api/v1/budgets/{budget_id}/review",
        headers=finance["headers"],
        json={
            "status": "REJECTED",
            "approval_comments": "Please adjust the amount.",
        },
    )
    assert rejected.status_code == 200, rejected.text

    response = client.patch(
        f"/api/v1/budgets/{budget_id}",
        headers=manager["headers"],
        json={"allocated_amount": "15000.00"},
    )

    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["allocated_amount"])) == Decimal("15000.00")
    assert response.json()["status"] == "PENDING"


def test_cannot_update_pending_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/budgets/{created.json()['id']}",
        headers=manager["headers"],
        json={"allocated_amount": "15000.00"},
    )

    assert response.status_code == 409


def test_finance_officer_cannot_update_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    response = client.patch(
        f"/api/v1/budgets/{created.json()['id']}",
        headers=finance["headers"],
        json={"allocated_amount": "15000.00"},
    )

    assert response.status_code == 403


def test_approved_budget_can_be_closed_by_finance():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text
    budget_id = created.json()["id"]

    finance = create_user("FINANCE_OFFICER")
    approved = approve_budget(budget_id, finance["headers"])
    assert approved.status_code == 200, approved.text

    response = client.patch(
        f"/api/v1/budgets/{budget_id}/close",
        headers=finance["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CLOSED"


def test_manager_cannot_close_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    approved = approve_budget(created.json()["id"], finance["headers"])
    assert approved.status_code == 200, approved.text

    response = client.patch(
        f"/api/v1/budgets/{created.json()['id']}/close",
        headers=manager["headers"],
    )

    assert response.status_code == 403


def test_cannot_close_pending_budget():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    response = client.patch(
        f"/api/v1/budgets/{created.json()['id']}/close",
        headers=finance["headers"],
    )

    assert response.status_code == 409


# -------------------------------------------------------------------
# Budget utilization summary
# -------------------------------------------------------------------

def test_budget_summary_returns_expected_fields():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"], "10000.00")
    assert created.status_code == 201, created.text

    response = client.get(
        f"/api/v1/budgets/{created.json()['id']}/summary",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["budget_id"] == created.json()["id"]
    assert Decimal(str(data["allocated_amount"])) == Decimal("10000.00")
    assert Decimal(str(data["approved_expenses"])) == Decimal("0")
    assert Decimal(str(data["remaining_budget"])) == Decimal("10000.00")
    assert data["is_over_budget"] is False
    assert data["currency"] == "INR"


def test_finance_officer_can_view_budget_summary():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    created = create_budget(manager["headers"], project["id"])
    assert created.status_code == 201, created.text

    finance = create_user("FINANCE_OFFICER")
    response = client.get(
        f"/api/v1/budgets/{created.json()['id']}/summary",
        headers=finance["headers"],
    )

    assert response.status_code == 200, response.text


def test_unrelated_manager_cannot_view_budget_summary():
    manager1 = create_user("NGO_MANAGER")
    project = create_project(manager1["headers"])
    created = create_budget(manager1["headers"], project["id"])
    assert created.status_code == 201, created.text

    manager2 = create_user("NGO_MANAGER")
    response = client.get(
        f"/api/v1/budgets/{created.json()['id']}/summary",
        headers=manager2["headers"],
    )

    assert response.status_code == 403
