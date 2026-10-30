
import os
from datetime import date, timedelta
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import text

load_dotenv(".env")

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:Srik8499@localhost:5433/ngo_management_test",
)

from db.base import Base
from db.session import SessionLocal
from main import app
from models.user import User

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    def clean():
        db = SessionLocal()
        try:
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(text(f'DELETE FROM "{table.name}"'))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    clean()
    yield
    clean()


def unique_email():
    return f"user_{uuid4().hex[:10]}@example.com"


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_user(role="NGO_MANAGER"):
    email = unique_email()

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Test {role}",
            "email": email,
            "password": "TestPassword123!",
        },
    )
    assert register_response.status_code == 201, register_response.text

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
        json={
            "email": email,
            "password": "TestPassword123!",
        },
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]
    return auth_headers(token)


def create_project(headers):
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": f"Beneficiary Project {uuid4().hex[:8]}",
            "description": "Project for beneficiary management tests",
            "location": "Hyderabad",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=60)).isoformat(),
            "budget": 50000,
            "currency": "INR",
            "status": "DRAFT",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_resource(headers):
    response = client.post(
        "/api/v1/resources",
        headers=headers,
        json={
            "name": f"Food Supplies {uuid4().hex[:8]}",
            "description": "Food packages for beneficiaries",
            "category": "FOOD",
            "unit": "package",
            "low_stock_threshold": 5,
        },
    )
    assert response.status_code == 201, response.text
    resource = response.json()

    stock_response = client.post(
        f"/api/v1/resources/{resource['id']}/stock-movements",
        headers=headers,
        json={
            "transaction_type": "STOCK_IN",
            "quantity": 100,
            "reference": "BENEFICIARY-TEST-INITIAL-STOCK",
            "notes": "Initial stock for beneficiary tests",
        },
    )
    assert stock_response.status_code == 201, stock_response.text

    detail_response = client.get(
        f"/api/v1/resources/{resource['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text

    return detail_response.json()


def beneficiary_payload(**overrides):
    payload = {
        "full_name": f"Beneficiary {uuid4().hex[:8]}",
        "category": "CHILDREN",
        "date_of_birth": "2015-05-10",
        "gender": "OTHER",
        "phone": "9876543210",
        "email": unique_email(),
        "address": "Test Street",
        "city": "Hyderabad",
        "notes": "Created during automated testing",
    }
    payload.update(overrides)
    return payload


def create_beneficiary(headers, **overrides):
    response = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json=beneficiary_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def assistance_payload(beneficiary_id, **overrides):
    payload = {
        "beneficiary_id": beneficiary_id,
        "project_id": None,
        "resource_id": None,
        "assistance_type": "FOOD_PACKAGE",
        "description": "Food package distribution",
        "quantity": 1,
        "distribution_date": date.today().isoformat(),
        "notes": "Test assistance record",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------
# Beneficiary profile tests
# ---------------------------------------------------------


def test_create_beneficiary_success():
    headers = create_user("NGO_MANAGER")

    response = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json=beneficiary_payload(),
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["id"] > 0
    assert data["category"] == "CHILDREN"
    assert data["status"] == "ACTIVE"
    assert data["city"] == "Hyderabad"
    assert data["full_name"].startswith("Beneficiary")


def test_super_admin_can_create_beneficiary():
    headers = create_user("SUPER_ADMIN")

    response = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json=beneficiary_payload(category="FAMILIES"),
    )

    assert response.status_code == 201, response.text
    assert response.json()["category"] == "FAMILIES"


def test_volunteer_coordinator_can_create_beneficiary():
    headers = create_user("VOLUNTEER_COORDINATOR")

    response = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json=beneficiary_payload(),
    )

    assert response.status_code == 201, response.text


def test_donor_cannot_create_beneficiary():
    headers = create_user("DONOR")

    response = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json=beneficiary_payload(),
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_create_beneficiary():
    response = client.post(
        "/api/v1/beneficiaries",
        json=beneficiary_payload(),
    )

    assert response.status_code in (401, 403)


def test_create_beneficiary_rejects_invalid_category():
    headers = create_user("NGO_MANAGER")

    response = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json=beneficiary_payload(category="INVALID_CATEGORY"),
    )

    assert response.status_code == 422


def test_create_beneficiary_rejects_future_birth_date():
    headers = create_user("NGO_MANAGER")
    future_date = (date.today() + timedelta(days=30)).isoformat()

    response = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json=beneficiary_payload(date_of_birth=future_date),
    )

    assert response.status_code == 422


def test_create_beneficiary_rejects_invalid_email():
    headers = create_user("NGO_MANAGER")

    response = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json=beneficiary_payload(email="not-an-email"),
    )

    assert response.status_code == 422


def test_create_beneficiary_rejects_short_name():
    headers = create_user("NGO_MANAGER")

    response = client.post(
        "/api/v1/beneficiaries",
        headers=headers,
        json=beneficiary_payload(full_name="A"),
    )

    assert response.status_code == 422


def test_list_beneficiaries_success():
    headers = create_user("NGO_MANAGER")
    create_beneficiary(headers)
    create_beneficiary(headers, category="FAMILIES")

    response = client.get(
        "/api/v1/beneficiaries",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_beneficiaries_filter_by_category():
    headers = create_user("NGO_MANAGER")
    create_beneficiary(headers, category="CHILDREN")
    create_beneficiary(headers, category="FAMILIES")

    response = client.get(
        "/api/v1/beneficiaries",
        headers=headers,
        params={"category": "CHILDREN"},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["category"] == "CHILDREN"


def test_list_beneficiaries_search_by_name():
    headers = create_user("NGO_MANAGER")
    name = f"Searchable {uuid4().hex[:8]}"
    create_beneficiary(headers, full_name=name)
    create_beneficiary(headers)

    response = client.get(
        "/api/v1/beneficiaries",
        headers=headers,
        params={"search": name},
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["full_name"] == name


def test_list_beneficiaries_filter_by_city():
    headers = create_user("NGO_MANAGER")
    create_beneficiary(headers, city="Hyderabad")
    create_beneficiary(headers, city="Warangal")

    response = client.get(
        "/api/v1/beneficiaries",
        headers=headers,
        params={"city": "Hyderabad"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


def test_donor_cannot_list_beneficiaries():
    headers = create_user("DONOR")

    response = client.get(
        "/api/v1/beneficiaries",
        headers=headers,
    )

    assert response.status_code == 403


def test_get_beneficiary_success():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)

    response = client.get(
        f"/api/v1/beneficiaries/{beneficiary['id']}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == beneficiary["id"]


def test_get_missing_beneficiary_returns_404():
    headers = create_user("NGO_MANAGER")

    response = client.get(
        "/api/v1/beneficiaries/999999",
        headers=headers,
    )

    assert response.status_code == 404


def test_update_beneficiary_success():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)

    response = client.patch(
        f"/api/v1/beneficiaries/{beneficiary['id']}",
        headers=headers,
        json={
            "city": "Warangal",
            "notes": "Updated beneficiary notes",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["city"] == "Warangal"
    assert response.json()["notes"] == "Updated beneficiary notes"


def test_volunteer_cannot_update_beneficiary():
    headers = create_user("VOLUNTEER")
    manager_headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(manager_headers)

    response = client.patch(
        f"/api/v1/beneficiaries/{beneficiary['id']}",
        headers=headers,
        json={"city": "Warangal"},
    )

    assert response.status_code == 403


def test_update_beneficiary_rejects_empty_patch():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)

    response = client.patch(
        f"/api/v1/beneficiaries/{beneficiary['id']}",
        headers=headers,
        json={},
    )

    assert response.status_code == 422


# ---------------------------------------------------------
# Beneficiary-project link tests
# ---------------------------------------------------------


def test_link_beneficiary_to_project_success():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)
    project = create_project(headers)

    response = client.post(
        f"/api/v1/beneficiaries/{beneficiary['id']}/projects",
        headers=headers,
        json={
            "project_id": project["id"],
            "notes": "Beneficiary enrolled in project",
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["beneficiary_id"] == beneficiary["id"]
    assert data["project_id"] == project["id"]


def test_duplicate_beneficiary_project_link_returns_conflict():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)
    project = create_project(headers)

    payload = {
        "project_id": project["id"],
        "notes": "Project enrollment",
    }

    first = client.post(
        f"/api/v1/beneficiaries/{beneficiary['id']}/projects",
        headers=headers,
        json=payload,
    )
    assert first.status_code == 201, first.text

    second = client.post(
        f"/api/v1/beneficiaries/{beneficiary['id']}/projects",
        headers=headers,
        json=payload,
    )

    assert second.status_code == 409


def test_link_beneficiary_to_missing_project_returns_404():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)

    response = client.post(
        f"/api/v1/beneficiaries/{beneficiary['id']}/projects",
        headers=headers,
        json={"project_id": 999999, "notes": "Invalid project"},
    )

    assert response.status_code == 404


def test_list_beneficiary_projects():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)
    project = create_project(headers)

    link_response = client.post(
        f"/api/v1/beneficiaries/{beneficiary['id']}/projects",
        headers=headers,
        json={"project_id": project["id"], "notes": "Enrollment"},
    )
    assert link_response.status_code == 201, link_response.text

    response = client.get(
        f"/api/v1/beneficiaries/{beneficiary['id']}/projects",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["project_id"] == project["id"]


# ---------------------------------------------------------
# Assistance history tests
# ---------------------------------------------------------


def test_record_assistance_success():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)

    response = client.post(
        "/api/v1/beneficiaries/assistance",
        headers=headers,
        json=assistance_payload(beneficiary["id"]),
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["beneficiary_id"] == beneficiary["id"]
    assert data["assistance_type"] == "FOOD_PACKAGE"
    assert data["quantity"] == 1


def test_record_assistance_with_project():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)
    project = create_project(headers)

    link_response = client.post(
        f"/api/v1/beneficiaries/{beneficiary['id']}/projects",
        headers=headers,
        json={"project_id": project["id"], "notes": "Enrollment"},
    )
    assert link_response.status_code == 201, link_response.text

    response = client.post(
        "/api/v1/beneficiaries/assistance",
        headers=headers,
        json=assistance_payload(
            beneficiary["id"],
            project_id=project["id"],
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["project_id"] == project["id"]


def test_record_assistance_with_unlinked_project_returns_conflict():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)
    project = create_project(headers)

    response = client.post(
        "/api/v1/beneficiaries/assistance",
        headers=headers,
        json=assistance_payload(
            beneficiary["id"],
            project_id=project["id"],
        ),
    )

    assert response.status_code == 409



def test_record_assistance_decreases_resource_stock():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)
    resource = create_resource(headers)

    initial_quantity = resource["quantity_available"]
    distribution_quantity = 3

    response = client.post(
        "/api/v1/beneficiaries/assistance",
        headers=headers,
        json=assistance_payload(
            beneficiary["id"],
            resource_id=resource["id"],
            quantity=distribution_quantity,
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["quantity"] == distribution_quantity

    resource_response = client.get(
        f"/api/v1/resources/{resource['id']}",
        headers=headers,
    )
    assert resource_response.status_code == 200, resource_response.text

    assert (
        resource_response.json()["quantity_available"]
        == initial_quantity - distribution_quantity
    )


def test_record_assistance_for_inactive_beneficiary_returns_conflict():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)

    update_response = client.patch(
        f"/api/v1/beneficiaries/{beneficiary['id']}",
        headers=headers,
        json={"status": "INACTIVE"},
    )
    assert update_response.status_code == 200, update_response.text

    response = client.post(
        "/api/v1/beneficiaries/assistance",
        headers=headers,
        json=assistance_payload(beneficiary["id"]),
    )

    assert response.status_code == 409


def test_record_assistance_rejects_zero_quantity():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)

    response = client.post(
        "/api/v1/beneficiaries/assistance",
        headers=headers,
        json=assistance_payload(
            beneficiary["id"],
            quantity=0,
        ),
    )

    assert response.status_code == 422


def test_volunteer_can_record_assistance():
    manager_headers = create_user("NGO_MANAGER")
    volunteer_headers = create_user("VOLUNTEER")
    beneficiary = create_beneficiary(manager_headers)

    response = client.post(
        "/api/v1/beneficiaries/assistance",
        headers=volunteer_headers,
        json=assistance_payload(beneficiary["id"]),
    )

    assert response.status_code == 201, response.text


def test_donor_cannot_record_assistance():
    manager_headers = create_user("NGO_MANAGER")
    donor_headers = create_user("DONOR")
    beneficiary = create_beneficiary(manager_headers)

    response = client.post(
        "/api/v1/beneficiaries/assistance",
        headers=donor_headers,
        json=assistance_payload(beneficiary["id"]),
    )

    assert response.status_code == 403


def test_list_beneficiary_assistance():
    headers = create_user("NGO_MANAGER")
    beneficiary = create_beneficiary(headers)

    create_response = client.post(
        "/api/v1/beneficiaries/assistance",
        headers=headers,
        json=assistance_payload(beneficiary["id"]),
    )
    assert create_response.status_code == 201, create_response.text

    response = client.get(
        f"/api/v1/beneficiaries/{beneficiary['id']}/assistance",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["beneficiary_id"] == beneficiary["id"]
