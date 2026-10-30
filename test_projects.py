
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv(".env")

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL must be configured in .env.")

if "ngo_management_system_test" not in TEST_DATABASE_URL:
    raise RuntimeError("Tests must use the dedicated test database.")

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from db.base import Base
from db.session import SessionLocal
from main import app
from models.user import User

BASE_URL = "/api/v1"
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    clear_database()
    yield
    clear_database()


def clear_database():
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def register_account(role="DONOR"):
    email = f"{uuid4().hex}@example.com"
    password = "StrongTestPassword123!"

    response = client.post(
        f"{BASE_URL}/auth/register",
        json={
            "full_name": f"Project Test {role}",
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

    response = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text

    return {
        "email": email,
        "headers": {
            "Authorization": f"Bearer {response.json()['access_token']}"
        },
    }


def project_payload(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "title": f"Community Project {uuid4().hex[:8]}",
        "description": "A community development initiative.",
        "location": "Hyderabad",
        "start_date": (now + timedelta(days=7)).isoformat(),
        "end_date": (now + timedelta(days=90)).isoformat(),
        "budget": "50000.00",
        "currency": "INR",
        "status": "DRAFT",
    }
    payload.update(overrides)
    return payload


def create_project(headers, **overrides):
    return client.post(
        f"{BASE_URL}/projects",
        json=project_payload(**overrides),
        headers=headers,
    )


def test_manager_can_create_project():
    manager = register_account("NGO_MANAGER")

    response = create_project(manager["headers"])

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["title"].startswith("Community Project")
    assert data["status"] == "DRAFT"
    assert data["currency"] == "INR"
    assert data["created_by"] > 0


def test_super_admin_can_create_project():
    admin = register_account("SUPER_ADMIN")

    response = create_project(admin["headers"])

    assert response.status_code == 201, response.text


def test_project_creation_requires_authentication():
    response = client.post(
        f"{BASE_URL}/projects",
        json=project_payload(),
    )

    assert response.status_code == 401


@pytest.mark.parametrize("role", ["DONOR", "VOLUNTEER", "FINANCE_OFFICER"])
def test_unauthorized_roles_cannot_create_project(role):
    account = register_account(role)

    response = create_project(account["headers"])

    assert response.status_code == 403, response.text


def test_authenticated_user_can_list_projects():
    manager = register_account("NGO_MANAGER")
    created = create_project(manager["headers"])
    assert created.status_code == 201, created.text

    donor = register_account("DONOR")
    response = client.get(
        f"{BASE_URL}/projects",
        headers=donor["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert len(response.json()["items"]) == 1


def test_project_list_requires_authentication():
    response = client.get(f"{BASE_URL}/projects")

    assert response.status_code == 401


def test_authenticated_user_can_get_project():
    manager = register_account("NGO_MANAGER")
    created = create_project(manager["headers"])
    assert created.status_code == 201, created.text

    donor = register_account("DONOR")
    project_id = created.json()["id"]

    response = client.get(
        f"{BASE_URL}/projects/{project_id}",
        headers=donor["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == project_id


def test_unknown_project_returns_404():
    donor = register_account("DONOR")

    response = client.get(
        f"{BASE_URL}/projects/999999",
        headers=donor["headers"],
    )

    assert response.status_code == 404


def test_manager_can_update_project():
    manager = register_account("NGO_MANAGER")
    created = create_project(manager["headers"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"{BASE_URL}/projects/{created.json()['id']}",
        json={
            "title": "Updated Community Project",
            "budget": "75000.00",
        },
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated Community Project"
    assert response.json()["budget"] == "75000.00"


def test_super_admin_can_update_project():
    admin = register_account("SUPER_ADMIN")
    created = create_project(admin["headers"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"{BASE_URL}/projects/{created.json()['id']}",
        json={"status": "PLANNED"},
        headers=admin["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PLANNED"


def test_donor_cannot_update_project():
    manager = register_account("NGO_MANAGER")
    created = create_project(manager["headers"])
    assert created.status_code == 201, created.text

    donor = register_account("DONOR")
    response = client.patch(
        f"{BASE_URL}/projects/{created.json()['id']}",
        json={"title": "Unauthorized Update"},
        headers=donor["headers"],
    )

    assert response.status_code == 403


def test_update_unknown_project_returns_404():
    manager = register_account("NGO_MANAGER")

    response = client.patch(
        f"{BASE_URL}/projects/999999",
        json={"title": "Missing Project"},
        headers=manager["headers"],
    )

    assert response.status_code == 404


def test_search_projects_by_title():
    manager = register_account("NGO_MANAGER")
    created = create_project(
        manager["headers"],
        title="Community Library Initiative",
    )
    assert created.status_code == 201, created.text

    response = client.get(
        f"{BASE_URL}/projects?search=Library",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == (
        "Community Library Initiative"
    )


def test_filter_projects_by_status():
    manager = register_account("NGO_MANAGER")

    draft = create_project(manager["headers"], status="DRAFT")
    planned = create_project(manager["headers"], status="PLANNED")
    assert draft.status_code == 201, draft.text
    assert planned.status_code == 201, planned.text

    response = client.get(
        f"{BASE_URL}/projects?status=PLANNED",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["status"] == "PLANNED"


def test_project_pagination():
    manager = register_account("NGO_MANAGER")

    for _ in range(3):
        response = create_project(manager["headers"])
        assert response.status_code == 201, response.text

    response = client.get(
        f"{BASE_URL}/projects?page=1&page_size=2",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 3
    assert len(response.json()["items"]) == 2
    assert response.json()["page"] == 1
    assert response.json()["page_size"] == 2


def test_project_rejects_blank_title():
    manager = register_account("NGO_MANAGER")

    response = create_project(manager["headers"], title="   ")

    assert response.status_code == 422


def test_project_rejects_blank_description():
    manager = register_account("NGO_MANAGER")

    response = create_project(manager["headers"], description="   ")

    assert response.status_code == 422


def test_project_rejects_negative_budget():
    manager = register_account("NGO_MANAGER")

    response = create_project(manager["headers"], budget="-100.00")

    assert response.status_code == 422


def test_project_rejects_invalid_status():
    manager = register_account("NGO_MANAGER")

    response = create_project(manager["headers"], status="INVALID")

    assert response.status_code == 422


def test_project_rejects_invalid_date_range():
    manager = register_account("NGO_MANAGER")
    now = datetime.now(timezone.utc)

    response = create_project(
        manager["headers"],
        start_date=(now + timedelta(days=30)).isoformat(),
        end_date=(now + timedelta(days=10)).isoformat(),
    )

    assert response.status_code == 422


def test_project_rejects_invalid_currency():
    manager = register_account("NGO_MANAGER")

    response = create_project(manager["headers"], currency="USDD")

    assert response.status_code == 422


def test_project_normalizes_currency():
    manager = register_account("NGO_MANAGER")

    response = create_project(manager["headers"], currency="inr")

    assert response.status_code == 201, response.text
    assert response.json()["currency"] == "INR"


def test_project_rejects_invalid_page():
    manager = register_account("NGO_MANAGER")

    response = client.get(
        f"{BASE_URL}/projects?page=0",
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_project_rejects_page_size_above_limit():
    manager = register_account("NGO_MANAGER")

    response = client.get(
        f"{BASE_URL}/projects?page_size=101",
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_project_update_rejects_invalid_date_range():
    manager = register_account("NGO_MANAGER")
    created = create_project(manager["headers"])
    assert created.status_code == 201, created.text

    now = datetime.now(timezone.utc)
    response = client.patch(
        f"{BASE_URL}/projects/{created.json()['id']}",
        json={
            "start_date": (now + timedelta(days=120)).isoformat(),
        },
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_project_update_rejects_null_title():
    manager = register_account("NGO_MANAGER")
    created = create_project(manager["headers"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"{BASE_URL}/projects/{created.json()['id']}",
        json={"title": None},
        headers=manager["headers"],
    )

    assert response.status_code == 422
