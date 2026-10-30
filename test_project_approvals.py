
import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv

load_dotenv()

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:Srik8499@localhost:5433/ngo_management_system_test",
)

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from db.base import Base
from db.session import SessionLocal
from main import app
from models.user import User

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    """Clear application tables before each test."""
    db: Session = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def unique_email():
    return f"approval_{uuid4().hex}@example.com"


def register_account(role="NGO_MANAGER"):
    """Register a user, assign a test role, and obtain an access token."""
    email = unique_email()
    password = "TestPassword123!"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Approval Tester {role}",
            "email": email,
            "password": password,
        },
    )
    assert response.status_code in (200, 201), response.text

    db: Session = SessionLocal()
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
        "id": user.id,
        "email": email,
        "password": password,
        "role": role,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def project_payload(**overrides):
    payload = {
        "title": f"Approval Project {uuid4().hex[:8]}",
        "description": "Community development project for approval tests.",
        "location": "Hyderabad",
        "start_date": "2027-01-01",
        "end_date": "2027-12-31",
        "budget": 50000,
        "currency": "INR",
        "status": "DRAFT",
    }
    payload.update(overrides)
    return payload


def create_project(headers, **overrides):
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json=project_payload(**overrides),
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def submit_approval(headers, project_id, comments=None):
    return client.post(
        "/api/v1/project-approvals",
        headers=headers,
        json={
            "project_id": project_id,
            "request_comments": comments,
        },
    )


def create_pending_approval():
    manager = register_account("NGO_MANAGER")
    project = create_project(manager["headers"])
    response = submit_approval(
        manager["headers"],
        project["id"],
        "Please review this project.",
    )
    assert response.status_code == 201, response.text
    return manager, project, response.json()


# ---------------------------------------------------------------------
# Submission tests
# ---------------------------------------------------------------------


def test_manager_can_submit_project_for_approval():
    manager = register_account("NGO_MANAGER")
    project = create_project(manager["headers"])

    response = submit_approval(
        manager["headers"],
        project["id"],
        "Ready for review.",
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_id"] == project["id"]
    assert data["requested_by"] == manager["id"]
    assert data["status"] == "PENDING"
    assert data["request_comments"] == "Ready for review."
    assert data["reviewed_by"] is None
    assert data["reviewed_at"] is None


def test_super_admin_can_submit_project_for_approval():
    admin = register_account("SUPER_ADMIN")
    project = create_project(admin["headers"])

    response = submit_approval(admin["headers"], project["id"])

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "PENDING"


def test_volunteer_cannot_submit_approval_request():
    volunteer = register_account("VOLUNTEER")
    project = create_project(register_account("NGO_MANAGER")["headers"])

    response = submit_approval(volunteer["headers"], project["id"])

    assert response.status_code == 403


def test_unauthenticated_user_cannot_submit_approval():
    response = client.post(
        "/api/v1/project-approvals",
        json={"project_id": 1, "request_comments": "Review"},
    )

    assert response.status_code == 401


def test_nonexistent_project_cannot_be_submitted():
    manager = register_account("NGO_MANAGER")

    response = submit_approval(manager["headers"], 999999)

    assert response.status_code == 404


def test_duplicate_pending_approval_is_rejected():
    manager = register_account("NGO_MANAGER")
    project = create_project(manager["headers"])

    first = submit_approval(manager["headers"], project["id"])
    second = submit_approval(manager["headers"], project["id"])

    assert first.status_code == 201, first.text
    assert second.status_code == 409


def test_invalid_project_id_is_rejected():
    manager = register_account("NGO_MANAGER")

    response = client.post(
        "/api/v1/project-approvals",
        headers=manager["headers"],
        json={"project_id": -1, "request_comments": "Review"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------
# Review tests
# ---------------------------------------------------------------------


@pytest.mark.parametrize("decision", ["APPROVED", "REJECTED"])
def test_super_admin_can_review_pending_request(decision):
    _, _, approval = create_pending_approval()
    admin = register_account("SUPER_ADMIN")

    response = client.patch(
        f"/api/v1/project-approvals/{approval['id']}/review",
        headers=admin["headers"],
        json={
            "status": decision,
            "review_comments": "Review completed.",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == decision
    assert data["reviewed_by"] == admin["id"]
    assert data["review_comments"] == "Review completed."
    assert data["reviewed_at"] is not None


def test_manager_cannot_review_approval_request():
    _, _, approval = create_pending_approval()
    manager = register_account("NGO_MANAGER")

    response = client.patch(
        f"/api/v1/project-approvals/{approval['id']}/review",
        headers=manager["headers"],
        json={"status": "APPROVED"},
    )

    assert response.status_code == 403


def test_reviewing_nonexistent_approval_returns_404():
    admin = register_account("SUPER_ADMIN")

    response = client.patch(
        "/api/v1/project-approvals/999999/review",
        headers=admin["headers"],
        json={"status": "APPROVED"},
    )

    assert response.status_code == 404


def test_already_reviewed_request_cannot_be_reviewed_again():
    _, _, approval = create_pending_approval()
    admin = register_account("SUPER_ADMIN")

    first = client.patch(
        f"/api/v1/project-approvals/{approval['id']}/review",
        headers=admin["headers"],
        json={"status": "APPROVED"},
    )
    second = client.patch(
        f"/api/v1/project-approvals/{approval['id']}/review",
        headers=admin["headers"],
        json={"status": "REJECTED"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 409


def test_invalid_review_status_is_rejected():
    _, _, approval = create_pending_approval()
    admin = register_account("SUPER_ADMIN")

    response = client.patch(
        f"/api/v1/project-approvals/{approval['id']}/review",
        headers=admin["headers"],
        json={"status": "PENDING"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------
# Retrieval, authorization, filtering, and pagination tests
# ---------------------------------------------------------------------


def test_super_admin_can_get_approval_request():
    _, _, approval = create_pending_approval()
    admin = register_account("SUPER_ADMIN")

    response = client.get(
        f"/api/v1/project-approvals/{approval['id']}",
        headers=admin["headers"],
    )

    assert response.status_code == 200
    assert response.json()["id"] == approval["id"]


def test_requester_can_get_own_approval_request():
    manager, _, approval = create_pending_approval()

    response = client.get(
        f"/api/v1/project-approvals/{approval['id']}",
        headers=manager["headers"],
    )

    assert response.status_code == 200
    assert response.json()["requested_by"] == manager["id"]


def test_user_cannot_get_another_users_approval_request():
    _, _, approval = create_pending_approval()
    other_manager = register_account("NGO_MANAGER")

    response = client.get(
        f"/api/v1/project-approvals/{approval['id']}",
        headers=other_manager["headers"],
    )

    assert response.status_code == 403


def test_get_nonexistent_approval_returns_404():
    admin = register_account("SUPER_ADMIN")

    response = client.get(
        "/api/v1/project-approvals/999999",
        headers=admin["headers"],
    )

    assert response.status_code == 404


def test_manager_lists_only_own_approval_requests():
    manager_one, project_one, approval_one = create_pending_approval()

    manager_two = register_account("NGO_MANAGER")
    project_two = create_project(manager_two["headers"])
    response_two = submit_approval(manager_two["headers"], project_two["id"])
    assert response_two.status_code == 201, response_two.text

    response = client.get(
        "/api/v1/project-approvals",
        headers=manager_one["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == approval_one["id"]


def test_super_admin_can_filter_approvals_by_status():
    _, _, approval = create_pending_approval()
    admin = register_account("SUPER_ADMIN")

    response = client.get(
        "/api/v1/project-approvals",
        headers=admin["headers"],
        params={"approval_status": "PENDING"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == approval["id"]
    assert data["items"][0]["status"] == "PENDING"


def test_super_admin_can_filter_approvals_by_project():
    _, project, approval = create_pending_approval()
    admin = register_account("SUPER_ADMIN")

    response = client.get(
        "/api/v1/project-approvals",
        headers=admin["headers"],
        params={"project_id": project["id"]},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == approval["id"]


def test_approval_list_pagination():
    manager = register_account("NGO_MANAGER")

    for _ in range(3):
        project = create_project(manager["headers"])
        response = submit_approval(manager["headers"], project["id"])
        assert response.status_code == 201, response.text

    admin = register_account("SUPER_ADMIN")
    response = client.get(
        "/api/v1/project-approvals",
        headers=admin["headers"],
        params={"page": 1, "page_size": 2},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_invalid_pagination_is_rejected():
    admin = register_account("SUPER_ADMIN")

    response = client.get(
        "/api/v1/project-approvals",
        headers=admin["headers"],
        params={"page": 0},
    )

    assert response.status_code == 422


def test_approval_list_requires_authentication():
    response = client.get("/api/v1/project-approvals")

    assert response.status_code == 401
