
import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv

load_dotenv(".env")

test_database_url = os.getenv("TEST_DATABASE_URL")
if not test_database_url:
    raise RuntimeError("TEST_DATABASE_URL must be configured in .env")

if "ngo_management_system_test" not in test_database_url:
    raise RuntimeError("Refusing to run tests against a non-test database")

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = test_database_url

from fastapi.testclient import TestClient
from sqlalchemy import text

from db.base import Base
from db.session import SessionLocal, engine
from main import app
from models.campaign import Campaign
from models.user import User


BASE_URL = "/api/v1"
PASSWORD = "CampaignTest@12345"

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_database():
    # Delete rows in reverse dependency order.
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    yield

    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture
def test_client():
    with TestClient(app) as test_client:
        yield test_client


def unique_email():
    return f"campaign_{uuid4().hex[:12]}@example.com"


def register_account(test_client, role="DONOR"):
    email = unique_email()

    response = test_client.post(
        f"{BASE_URL}/auth/register",
        json={
            "full_name": "Campaign Test User",
            "email": email,
            "password": PASSWORD,
        },
    )
    assert response.status_code in (200, 201), response.text

    # Public registration creates a normal account. Assign the required
    # role directly in the isolated test database.
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        user.role = role
        db.commit()

    login_response = test_client.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]

    return {
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def campaign_payload(**overrides):
    payload = {
        "title": "Clean Water for Communities",
        "description": (
            "Fund clean drinking water systems for underserved communities."
        ),
        "goal_amount": "50000.00",
        "currency": "INR",
        "start_date": "2026-11-01T00:00:00+00:00",
        "end_date": "2027-01-31T23:59:59+00:00",
        "status": "DRAFT",
    }
    payload.update(overrides)
    return payload


def create_campaign(test_client, headers, **overrides):
    return test_client.post(
        f"{BASE_URL}/campaigns",
        headers=headers,
        json=campaign_payload(**overrides),
    )


def test_manager_can_create_campaign(test_client):
    manager = register_account(test_client, "NGO_MANAGER")

    response = create_campaign(test_client, manager["headers"])

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["title"] == "Clean Water for Communities"
    assert data["goal_amount"] == "50000.00"
    assert data["raised_amount"] == "0.00"
    assert data["currency"] == "INR"
    assert data["status"] == "DRAFT"


def test_super_admin_can_create_campaign(test_client):
    admin = register_account(test_client, "SUPER_ADMIN")

    response = create_campaign(test_client, admin["headers"])

    assert response.status_code == 201, response.text


def test_donor_cannot_create_campaign(test_client):
    donor = register_account(test_client, "DONOR")

    response = create_campaign(test_client, donor["headers"])

    assert response.status_code == 403


def test_volunteer_cannot_create_campaign(test_client):
    volunteer = register_account(test_client, "VOLUNTEER")

    response = create_campaign(test_client, volunteer["headers"])

    assert response.status_code == 403


def test_campaign_requires_authentication(test_client):
    response = test_client.get(f"{BASE_URL}/campaigns")

    assert response.status_code in (401, 403)


def test_get_campaign_by_id(test_client):
    manager = register_account(test_client, "NGO_MANAGER")
    created = create_campaign(test_client, manager["headers"])
    campaign_id = created.json()["id"]

    response = test_client.get(
        f"{BASE_URL}/campaigns/{campaign_id}",
        headers=manager["headers"],
    )

    assert response.status_code == 200
    assert response.json()["id"] == campaign_id


def test_nonexistent_campaign_returns_404(test_client):
    manager = register_account(test_client, "NGO_MANAGER")

    response = test_client.get(
        f"{BASE_URL}/campaigns/999999",
        headers=manager["headers"],
    )

    assert response.status_code == 404


def test_list_campaigns(test_client):
    manager = register_account(test_client, "NGO_MANAGER")
    create_campaign(test_client, manager["headers"])
    create_campaign(
        test_client,
        manager["headers"],
        title="School Supplies Drive",
    )

    response = test_client.get(
        f"{BASE_URL}/campaigns",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_search_campaigns(test_client):
    manager = register_account(test_client, "NGO_MANAGER")
    create_campaign(test_client, manager["headers"])
    create_campaign(
        test_client,
        manager["headers"],
        title="School Supplies Drive",
    )

    response = test_client.get(
        f"{BASE_URL}/campaigns",
        params={"search": "School Supplies"},
        headers=manager["headers"],
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "School Supplies Drive"


def test_filter_campaigns_by_status(test_client):
    manager = register_account(test_client, "NGO_MANAGER")
    create_campaign(test_client, manager["headers"], status="DRAFT")
    create_campaign(
        test_client,
        manager["headers"],
        title="Active Campaign",
        status="ACTIVE",
    )

    response = test_client.get(
        f"{BASE_URL}/campaigns",
        params={"status": "ACTIVE"},
        headers=manager["headers"],
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["status"] == "ACTIVE"


def test_manager_can_update_campaign(test_client):
    manager = register_account(test_client, "NGO_MANAGER")
    created = create_campaign(test_client, manager["headers"])
    campaign_id = created.json()["id"]

    response = test_client.patch(
        f"{BASE_URL}/campaigns/{campaign_id}",
        headers=manager["headers"],
        json={"title": "Updated Water Campaign", "status": "ACTIVE"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated Water Campaign"
    assert response.json()["status"] == "ACTIVE"


def test_donor_cannot_update_campaign(test_client):
    manager = register_account(test_client, "NGO_MANAGER")
    created = create_campaign(test_client, manager["headers"])

    donor = register_account(test_client, "DONOR")
    response = test_client.patch(
        f"{BASE_URL}/campaigns/{created.json()['id']}",
        headers=donor["headers"],
        json={"title": "Unauthorized Update"},
    )

    assert response.status_code == 403


def test_invalid_goal_amount_rejected(test_client):
    manager = register_account(test_client, "NGO_MANAGER")

    response = create_campaign(
        test_client,
        manager["headers"],
        goal_amount="0",
    )

    assert response.status_code == 422


def test_end_date_before_start_date_rejected(test_client):
    manager = register_account(test_client, "NGO_MANAGER")

    response = create_campaign(
        test_client,
        manager["headers"],
        start_date="2027-02-01T00:00:00+00:00",
        end_date="2027-01-01T00:00:00+00:00",
    )

    assert response.status_code == 422


def test_invalid_campaign_status_rejected(test_client):
    manager = register_account(test_client, "NGO_MANAGER")

    response = create_campaign(
        test_client,
        manager["headers"],
        status="UNKNOWN",
    )

    assert response.status_code == 422


def test_invalid_page_rejected(test_client):
    manager = register_account(test_client, "NGO_MANAGER")

    response = test_client.get(
        f"{BASE_URL}/campaigns",
        params={"page": 0},
        headers=manager["headers"],
    )

    assert response.status_code == 422


def test_invalid_page_size_rejected(test_client):
    manager = register_account(test_client, "NGO_MANAGER")

    response = test_client.get(
        f"{BASE_URL}/campaigns",
        params={"page_size": 101},
        headers=manager["headers"],
    )

    assert response.status_code == 422
