
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

from db.base import Base
from db.session import SessionLocal, engine
from main import app
from models.user import User


BASE_URL = "/api/v1"
PASSWORD = "DonationTest@12345"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_test_database():
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    yield

    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def unique_email():
    return f"donation_{uuid4().hex[:12]}@example.com"


def register_account(client, role="DONOR"):
    email = unique_email()

    response = client.post(
        f"{BASE_URL}/auth/register",
        json={
            "full_name": "Donation Test User",
            "email": email,
            "password": PASSWORD,
        },
    )
    assert response.status_code in (200, 201), response.text

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        user.role = role
        db.commit()

    login_response = client.post(
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


def create_donor_profile(client, account):
    response = client.post(
        f"{BASE_URL}/donors",
        headers=account["headers"],
        json={
            "donor_type": "INDIVIDUAL",
            "preferred_contact_method": "EMAIL",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_campaign(client, manager, **overrides):
    payload = {
        "title": "Community Food Support",
        "description": (
            "Provide food supplies and essential groceries to families."
        ),
        "goal_amount": "10000.00",
        "currency": "INR",
        "start_date": "2026-11-01T00:00:00+00:00",
        "end_date": "2027-01-31T23:59:59+00:00",
        "status": "ACTIVE",
    }
    payload.update(overrides)

    response = client.post(
        f"{BASE_URL}/campaigns",
        headers=manager["headers"],
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_donation(client, donor, campaign_id, **overrides):
    payload = {
        "campaign_id": campaign_id,
        "amount": "100.00",
        "currency": "INR",
        "payment_method": "UPI",
        "notes": "Donation test",
    }
    payload.update(overrides)

    return client.post(
        f"{BASE_URL}/donations",
        headers=donor["headers"],
        json=payload,
    )


def test_donor_can_create_donation(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)

    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    response = create_donation(client, donor, campaign["id"])

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["campaign_id"] == campaign["id"]
    assert data["amount"] == "100.00"
    assert data["payment_status"] == "PENDING"


def test_donation_requires_authentication(client):
    response = client.get(f"{BASE_URL}/donations")
    assert response.status_code in (401, 403)


def test_donor_must_have_profile_before_donating(client):
    donor = register_account(client, "DONOR")
    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    response = create_donation(client, donor, campaign["id"])

    assert response.status_code == 404


def test_donor_cannot_create_donation_for_another_donor(client):
    donor_one = register_account(client, "DONOR")
    create_donor_profile(client, donor_one)

    donor_two = register_account(client, "DONOR")
    donor_two_profile = create_donor_profile(client, donor_two)

    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    response = create_donation(
        client,
        donor_one,
        campaign["id"],
        donor_id=donor_two_profile["id"],
    )

    assert response.status_code == 403


def test_donation_amount_must_be_positive(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)
    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    response = create_donation(
        client, donor, campaign["id"], amount="0"
    )

    assert response.status_code == 422


def test_donation_must_use_matching_currency(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)
    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    response = create_donation(
        client,
        donor,
        campaign["id"],
        currency="USD",
    )

    assert response.status_code == 422


def test_donation_requires_active_campaign(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)
    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager, status="DRAFT")

    response = create_donation(client, donor, campaign["id"])

    assert response.status_code == 422


def test_donation_to_missing_campaign_returns_404(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)

    response = create_donation(client, donor, 999999)

    assert response.status_code == 404


def test_donor_can_list_own_donations(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)
    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    created = create_donation(client, donor, campaign["id"])
    assert created.status_code == 201, created.text

    response = client.get(
        f"{BASE_URL}/donations",
        headers=donor["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


def test_donor_cannot_view_another_donors_donation(client):
    donor_one = register_account(client, "DONOR")
    create_donor_profile(client, donor_one)

    donor_two = register_account(client, "DONOR")
    create_donor_profile(client, donor_two)

    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    created = create_donation(client, donor_two, campaign["id"])
    donation_id = created.json()["id"]

    response = client.get(
        f"{BASE_URL}/donations/{donation_id}",
        headers=donor_one["headers"],
    )

    assert response.status_code == 403


def test_finance_officer_can_mark_donation_successful(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)

    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    created = create_donation(client, donor, campaign["id"])
    donation_id = created.json()["id"]

    finance = register_account(client, "FINANCE_OFFICER")
    response = client.patch(
        f"{BASE_URL}/donations/{donation_id}/status",
        headers=finance["headers"],
        json={
            "payment_status": "SUCCESSFUL",
            "transaction_reference": f"TX-{uuid4().hex[:12]}",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["payment_status"] == "SUCCESSFUL"


def test_successful_donation_updates_campaign_total(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)

    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    donation = create_donation(client, donor, campaign["id"])
    donation_id = donation.json()["id"]

    finance = register_account(client, "FINANCE_OFFICER")
    response = client.patch(
        f"{BASE_URL}/donations/{donation_id}/status",
        headers=finance["headers"],
        json={"payment_status": "SUCCESSFUL"},
    )
    assert response.status_code == 200, response.text

    campaign_response = client.get(
        f"{BASE_URL}/campaigns/{campaign['id']}",
        headers=manager["headers"],
    )

    assert campaign_response.status_code == 200
    assert campaign_response.json()["raised_amount"] == "100.00"


def test_pending_donation_does_not_update_campaign_total(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)
    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    response = create_donation(client, donor, campaign["id"])
    assert response.status_code == 201, response.text

    campaign_response = client.get(
        f"{BASE_URL}/campaigns/{campaign['id']}",
        headers=manager["headers"],
    )

    assert campaign_response.status_code == 200
    assert campaign_response.json()["raised_amount"] == "0.00"


def test_donor_cannot_update_payment_status(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)
    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(client, manager)

    donation = create_donation(client, donor, campaign["id"])
    donation_id = donation.json()["id"]

    response = client.patch(
        f"{BASE_URL}/donations/{donation_id}/status",
        headers=donor["headers"],
        json={"payment_status": "SUCCESSFUL"},
    )

    assert response.status_code == 403


def test_successful_donations_cannot_exceed_campaign_goal(client):
    donor = register_account(client, "DONOR")
    create_donor_profile(client, donor)

    manager = register_account(client, "NGO_MANAGER")
    campaign = create_campaign(
        client,
        manager,
        goal_amount="100.00",
    )

    donation = create_donation(
        client,
        donor,
        campaign["id"],
        amount="101.00",
    )
    assert donation.status_code == 201, donation.text

    finance = register_account(client, "FINANCE_OFFICER")
    response = client.patch(
        f"{BASE_URL}/donations/{donation.json()['id']}/status",
        headers=finance["headers"],
        json={"payment_status": "SUCCESSFUL"},
    )

    assert response.status_code == 422


def test_invalid_payment_status_rejected(client):
    finance = register_account(client, "FINANCE_OFFICER")

    response = client.patch(
        f"{BASE_URL}/donations/1/status",
        headers=finance["headers"],
        json={"payment_status": "INVALID"},
    )

    assert response.status_code == 422
