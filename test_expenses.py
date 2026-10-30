
import os
from uuid import uuid4

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

from db.base import Base
from db.session import SessionLocal
from main import app
from models.user import User


client = TestClient(app)
PASSWORD = "TestPassword123!"


def unique_email():
    return f"expense_{uuid4().hex[:12]}@example.com"


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_user(role="NGO_MANAGER"):
    email = unique_email()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Expense Test {role}",
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
        user_id = user.id
    finally:
        db.close()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]

    return {
        "id": user_id,
        "email": email,
        "password": PASSWORD,
        "role": role,
        "headers": auth_headers(token),
    }


@pytest.fixture(autouse=True)
def clean_database():
    """Clear application tables before each test."""
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
    finally:
        db.close()

    yield


def create_project(headers):
    payload = {
        "title": f"Expense Project {uuid4().hex[:8]}",
        "description": "Community development project for expense tests.",
        "location": "Hyderabad",
        "start_date": "2027-01-01",
        "end_date": "2027-12-31",
        "budget": 50000,
        "currency": "INR",
        "status": "DRAFT",
    }

    response = client.post(
        "/api/v1/projects",
        json=payload,
        headers=headers,
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def expense_payload(project_id, **overrides):
    payload = {
        "project_id": project_id,
        "category": "TRAVEL",
        "amount": "1250.50",
        "currency": "INR",
        "expense_date": "2026-10-20",
        "receipt_reference": f"RECEIPT-{uuid4().hex[:8]}",
        "description": "Travel costs for project activities.",
    }
    payload.update(overrides)
    return payload


def submit_expense(headers, project_id, **overrides):
    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(project_id, **overrides),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_manager_can_submit_expense():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(project["id"]),
        headers=manager["headers"],
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_id"] == project["id"]
    assert data["submitted_by"] == manager["id"]
    assert data["category"] == "TRAVEL"
    assert data["amount"] == "1250.50"
    assert data["status"] == "SUBMITTED"
    assert data["reviewed_by"] is None
    assert data["reviewed_at"] is None



def test_finance_officer_can_submit_expense():
    manager = create_user("NGO_MANAGER")
    finance = create_user("FINANCE_OFFICER")

    # NGO_MANAGER creates the project because the Projects API
    # does not grant project-management permission to FINANCE_OFFICER.
    project = create_project(manager["headers"])

    # FINANCE_OFFICER submits an expense for that project.
    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(project["id"]),
        headers=finance["headers"],
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_id"] == project["id"]
    assert data["submitted_by"] == finance["id"]
    assert data["status"] == "SUBMITTED"


def test_super_admin_can_submit_expense():
    admin = create_user("SUPER_ADMIN")
    project = create_project(admin["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(project["id"]),
        headers=admin["headers"],
    )

    assert response.status_code == 201, response.text


def test_volunteer_cannot_submit_expense():
    volunteer = create_user("VOLUNTEER")
    project = create_project(create_user("NGO_MANAGER")["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(project["id"]),
        headers=volunteer["headers"],
    )

    assert response.status_code == 403


def test_donor_cannot_submit_expense():
    donor = create_user("DONOR")
    project = create_project(create_user("NGO_MANAGER")["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(project["id"]),
        headers=donor["headers"],
    )

    assert response.status_code == 403


def test_expense_submission_requires_authentication():
    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(1),
    )

    assert response.status_code == 401


def test_submission_rejects_nonexistent_project():
    manager = create_user("NGO_MANAGER")

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(999999),
        headers=manager["headers"],
    )

    assert response.status_code == 404


@pytest.mark.parametrize("amount", ["0", "-1", "-25.50"])
def test_expense_rejects_nonpositive_amount(amount):
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(project["id"], amount=amount),
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_expense_requires_receipt_reference_or_attachment():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(
            project["id"],
            receipt_reference=None,
            attachment_url=None,
        ),
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_expense_accepts_attachment_url_without_receipt_reference():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(
            project["id"],
            receipt_reference=None,
            attachment_url="https://example.com/receipts/travel.pdf",
        ),
        headers=manager["headers"],
    )

    assert response.status_code == 201, response.text
    assert response.json()["attachment_url"].startswith("https://")


def test_expense_rejects_invalid_attachment_url():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(
            project["id"],
            attachment_url="not-a-valid-url",
        ),
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_expense_rejects_invalid_category():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(project["id"], category="INVALID_CATEGORY"),
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_expense_rejects_invalid_currency():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = client.post(
        "/api/v1/expenses",
        json=expense_payload(project["id"], currency="INR1"),
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_finance_officer_can_approve_expense():
    manager = create_user("NGO_MANAGER")
    finance = create_user("FINANCE_OFFICER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={
            "status": "APPROVED",
            "review_comments": "Receipt checked and approved.",
        },
        headers=finance["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["reviewed_by"] == finance["id"]
    assert data["review_comments"] == "Receipt checked and approved."
    assert data["reviewed_at"] is not None


def test_super_admin_can_approve_expense():
    manager = create_user("NGO_MANAGER")
    admin = create_user("SUPER_ADMIN")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={"status": "APPROVED"},
        headers=admin["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"


def test_finance_officer_can_reject_expense():
    manager = create_user("NGO_MANAGER")
    finance = create_user("FINANCE_OFFICER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={
            "status": "REJECTED",
            "review_comments": "Receipt details need correction.",
        },
        headers=finance["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REJECTED"


def test_manager_cannot_approve_expense():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={"status": "APPROVED"},
        headers=manager["headers"],
    )

    assert response.status_code == 403


def test_volunteer_cannot_approve_expense():
    manager = create_user("NGO_MANAGER")
    volunteer = create_user("VOLUNTEER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={"status": "APPROVED"},
        headers=volunteer["headers"],
    )

    assert response.status_code == 403


def test_cannot_review_expense_twice():
    manager = create_user("NGO_MANAGER")
    finance = create_user("FINANCE_OFFICER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    first = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={"status": "APPROVED"},
        headers=finance["headers"],
    )
    assert first.status_code == 200, first.text

    second = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={"status": "REJECTED"},
        headers=finance["headers"],
    )

    assert second.status_code == 409


def test_cannot_reimburse_unapproved_expense():
    manager = create_user("NGO_MANAGER")
    finance = create_user("FINANCE_OFFICER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}/reimburse",
        json={},
        headers=finance["headers"],
    )

    assert response.status_code == 409


def test_finance_officer_can_reimburse_approved_expense():
    manager = create_user("NGO_MANAGER")
    finance = create_user("FINANCE_OFFICER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    approve_response = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={"status": "APPROVED"},
        headers=finance["headers"],
    )
    assert approve_response.status_code == 200, approve_response.text

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}/reimburse",
        json={"review_comments": "Payment completed."},
        headers=finance["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REIMBURSED"
    assert response.json()["reimbursed_at"] is not None


def test_manager_cannot_reimburse_expense():
    manager = create_user("NGO_MANAGER")
    finance = create_user("FINANCE_OFFICER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    approve_response = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={"status": "APPROVED"},
        headers=finance["headers"],
    )
    assert approve_response.status_code == 200, approve_response.text

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}/reimburse",
        json={},
        headers=manager["headers"],
    )

    assert response.status_code == 403


def test_manager_can_list_own_expenses():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])
    submit_expense(manager["headers"], project["id"])

    response = client.get(
        "/api/v1/expenses",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["submitted_by"] == manager["id"]


def test_manager_cannot_view_another_users_expense():
    manager1 = create_user("NGO_MANAGER")
    manager2 = create_user("NGO_MANAGER")
    project = create_project(manager1["headers"])
    expense = submit_expense(manager1["headers"], project["id"])

    response = client.get(
        f"/api/v1/expenses/{expense['id']}",
        headers=manager2["headers"],
    )

    assert response.status_code == 403


def test_manager_list_is_restricted_to_own_expenses():
    manager1 = create_user("NGO_MANAGER")
    manager2 = create_user("NGO_MANAGER")
    project1 = create_project(manager1["headers"])
    project2 = create_project(manager2["headers"])

    submit_expense(manager1["headers"], project1["id"])
    submit_expense(manager2["headers"], project2["id"])

    response = client.get(
        "/api/v1/expenses",
        headers=manager1["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert all(item["submitted_by"] == manager1["id"] for item in data["items"])


def test_finance_can_filter_expenses_by_status():
    manager = create_user("NGO_MANAGER")
    finance = create_user("FINANCE_OFFICER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    review = client.patch(
        f"/api/v1/expenses/{expense['id']}/review",
        json={"status": "APPROVED"},
        headers=finance["headers"],
    )
    assert review.status_code == 200, review.text

    response = client.get(
        "/api/v1/expenses",
        params={"status": "APPROVED"},
        headers=finance["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "APPROVED"


def test_expense_list_supports_pagination():
    manager = create_user("NGO_MANAGER")
    project = create_project(manager["headers"])

    for _ in range(3):
        submit_expense(manager["headers"], project["id"])

    response = client.get(
        "/api/v1/expenses",
        params={"page": 1, "page_size": 2},
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_expense_list_rejects_invalid_pagination():
    manager = create_user("NGO_MANAGER")

    response = client.get(
        "/api/v1/expenses",
        params={"page": 0},
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_finance_can_get_expense_details():
    manager = create_user("NGO_MANAGER")
    finance = create_user("FINANCE_OFFICER")
    project = create_project(manager["headers"])
    expense = submit_expense(manager["headers"], project["id"])

    response = client.get(
        f"/api/v1/expenses/{expense['id']}",
        headers=finance["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == expense["id"]


def test_get_nonexistent_expense_returns_404():
    finance = create_user("FINANCE_OFFICER")

    response = client.get(
        "/api/v1/expenses/999999",
        headers=finance["headers"],
    )

    assert response.status_code == 404
