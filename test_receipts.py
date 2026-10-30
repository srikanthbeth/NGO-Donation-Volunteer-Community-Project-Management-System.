
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv(".env")

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:Srik8499@localhost:5433/ngo_management_test",
)

from fastapi.testclient import TestClient

from db.base import Base
from db.session import SessionLocal
from main import app
from models.user import User
from models.donor import Donor
from models.campaign import Campaign
from models.donation import Donation
from models.receipt import DonationReceipt


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


def create_user(role="DONOR"):
    email = f"receipt_{uuid4().hex[:10]}@example.com"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Receipt Test User",
            "email": email,
            "password": PASSWORD,
        },
    )
    assert response.status_code in (200, 201), response.text

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.role = role
        db.commit()
        user_id = user.id
    finally:
        db.close()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text

    return auth_headers(response.json()["access_token"]), user_id


def create_donor(user_id):
    db = SessionLocal()
    try:
        donor = Donor(
            user_id=user_id,
            donor_type="INDIVIDUAL",
            phone="9876543210",
            address="Test Address",
            city="Hyderabad",
            state="Telangana",
            country="India",
            postal_code="500001",
            preferred_contact_method="EMAIL",
            anonymous_default=False,
        )
        db.add(donor)
        db.commit()
        db.refresh(donor)
        return donor.id
    finally:
        db.close()


def create_campaign(headers):
    response = client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={
            "title": f"Receipt Campaign {uuid4().hex[:8]}",
            "description": "Campaign created for receipt tests",
            "goal_amount": "100000.00",
            "currency": "INR",
            "start_date": "2026-01-01",
            "end_date": "2027-12-31",
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_donation(
    donor_id,
    campaign_id,
    payment_status="SUCCESSFUL",
):
    db = SessionLocal()
    try:
        donation = Donation(
            donor_id=donor_id,
            campaign_id=campaign_id,
            amount=Decimal("1500.00"),
            currency="INR",
            payment_method="UPI",
            payment_status=payment_status,
            transaction_reference=f"TXN-{uuid4().hex[:12].upper()}",
            notes="Receipt test donation",
        )
        db.add(donation)
        db.commit()
        db.refresh(donation)
        return donation.id
    finally:
        db.close()


def create_confirmed_donation(donor_user_id, campaign_id):
    donor_id = create_donor(donor_user_id)
    donation_id = create_donation(donor_id, campaign_id)
    return donor_id, donation_id


def create_campaign_for_test():
    manager_headers, _ = create_user("NGO_MANAGER")
    campaign = create_campaign(manager_headers)
    return manager_headers, campaign


def issue_receipt(headers, donation_id):
    return client.post(
        f"/api/v1/receipts/donations/{donation_id}",
        headers=headers,
    )


def test_donor_can_create_receipt_for_successful_donation():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()

    donor_id, donation_id = create_confirmed_donation(
        donor_user_id, campaign["id"]
    )

    response = issue_receipt(donor_headers, donation_id)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["donation_id"] == donation_id
    assert data["donor_id"] == donor_id
    assert data["receipt_number"]
    assert data["amount"] == "1500.00"
    assert data["currency"] == "INR"
    assert data["status"] == "ISSUED"
    assert data["issued_at"] is not None


def test_receipt_number_is_unique():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()

    donor_id = create_donor(donor_user_id)
    first_id = create_donation(donor_id, campaign["id"])
    second_id = create_donation(donor_id, campaign["id"])

    first = issue_receipt(donor_headers, first_id)
    second = issue_receipt(donor_headers, second_id)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert (
        first.json()["receipt_number"]
        != second.json()["receipt_number"]
    )


def test_duplicate_receipt_is_rejected():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()
    _, donation_id = create_confirmed_donation(
        donor_user_id, campaign["id"]
    )

    first = issue_receipt(donor_headers, donation_id)
    second = issue_receipt(donor_headers, donation_id)

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text


@pytest.mark.parametrize("payment_status", ["PENDING", "FAILED"])
def test_receipt_rejected_for_unconfirmed_donation(payment_status):
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()
    donor_id = create_donor(donor_user_id)

    donation_id = create_donation(
        donor_id,
        campaign["id"],
        payment_status=payment_status,
    )

    response = issue_receipt(donor_headers, donation_id)

    assert response.status_code == 409, response.text


def test_receipt_rejected_for_refunded_donation():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()
    donor_id = create_donor(donor_user_id)

    donation_id = create_donation(
        donor_id,
        campaign["id"],
        payment_status="REFUNDED",
    )

    response = issue_receipt(donor_headers, donation_id)

    assert response.status_code == 409, response.text


def test_receipt_for_missing_donation_returns_404():
    donor_headers, _ = create_user("DONOR")

    response = issue_receipt(donor_headers, 999999)

    assert response.status_code == 404, response.text


def test_unauthenticated_user_cannot_create_receipt():
    response = client.post("/api/v1/receipts/donations/1")

    assert response.status_code == 401



def test_donor_cannot_create_receipt_for_another_donor():
    owner_headers, owner_user_id = create_user("DONOR")
    other_headers, other_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()

    # Both users must have donor profiles.
    create_donor(other_user_id)

    _, donation_id = create_confirmed_donation(
        owner_user_id, campaign["id"]
    )

    response = issue_receipt(other_headers, donation_id)

    assert response.status_code == 403, response.text


def test_donor_cannot_retrieve_another_donors_receipt():
    owner_headers, owner_user_id = create_user("DONOR")
    other_headers, other_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()

    # Both users must have donor profiles.
    create_donor(other_user_id)

    _, donation_id = create_confirmed_donation(
        owner_user_id, campaign["id"]
    )

    created = issue_receipt(owner_headers, donation_id)
    assert created.status_code == 201, created.text

    response = client.get(
        f"/api/v1/receipts/{created.json()['id']}",
        headers=other_headers,
    )

    assert response.status_code == 403, response.text


def test_donor_can_retrieve_own_receipt():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()
    _, donation_id = create_confirmed_donation(
        donor_user_id, campaign["id"]
    )

    created = issue_receipt(donor_headers, donation_id)
    assert created.status_code == 201, created.text

    response = client.get(
        f"/api/v1/receipts/{created.json()['id']}",
        headers=donor_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["donation_id"] == donation_id


def test_donor_cannot_retrieve_another_donors_receipt():
    owner_headers, owner_user_id = create_user("DONOR")
    other_headers, other_user_id = create_user("DONOR")

    _, campaign = create_campaign_for_test()

    # Create exactly one donor profile for each user.
    owner_donor_id = create_donor(owner_user_id)
    create_donor(other_user_id)

    # Create a donation belonging to the receipt owner.
    donation_id = create_donation(
        owner_donor_id,
        campaign["id"],
    )

    # The owner creates the receipt.
    created = issue_receipt(owner_headers, donation_id)
    assert created.status_code == 201, created.text

    # Another donor attempts to retrieve the receipt.
    response = client.get(
        f"/api/v1/receipts/{created.json()['id']}",
        headers=other_headers,
    )

    assert response.status_code == 403, response.text

def test_missing_receipt_returns_404():
    donor_headers, _ = create_user("DONOR")

    response = client.get(
        "/api/v1/receipts/999999",
        headers=donor_headers,
    )

    assert response.status_code == 404, response.text


def test_donor_can_list_own_receipts():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()
    donor_id = create_donor(donor_user_id)

    first_id = create_donation(donor_id, campaign["id"])
    second_id = create_donation(donor_id, campaign["id"])

    first = issue_receipt(donor_headers, first_id)
    second = issue_receipt(donor_headers, second_id)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    response = client.get(
        "/api/v1/receipts/me",
        headers=donor_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_receipt_list_supports_pagination():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()
    donor_id = create_donor(donor_user_id)

    donation_ids = [
        create_donation(donor_id, campaign["id"])
        for _ in range(3)
    ]

    for donation_id in donation_ids:
        response = issue_receipt(donor_headers, donation_id)
        assert response.status_code == 201, response.text

    response = client.get(
        "/api/v1/receipts/me",
        headers=donor_headers,
        params={"page": 1, "page_size": 2},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


def test_receipt_metadata_is_persisted():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()
    _, donation_id = create_confirmed_donation(
        donor_user_id, campaign["id"]
    )

    response = issue_receipt(donor_headers, donation_id)
    assert response.status_code == 201, response.text

    db = SessionLocal()
    try:
        receipt = db.scalar(
            select(DonationReceipt).where(
                DonationReceipt.donation_id == donation_id
            )
        )
        assert receipt is not None
        assert receipt.receipt_number == response.json()["receipt_number"]
        assert receipt.amount == Decimal("1500.00")
        assert receipt.currency == "INR"
        assert receipt.status == "ISSUED"
    finally:
        db.close()


def test_staff_can_retrieve_receipt():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()
    _, donation_id = create_confirmed_donation(
        donor_user_id, campaign["id"]
    )

    created = issue_receipt(donor_headers, donation_id)
    assert created.status_code == 201, created.text

    staff_headers, _ = create_user("NGO_MANAGER")

    response = client.get(
        f"/api/v1/receipts/{created.json()['id']}",
        headers=staff_headers,
    )

    assert response.status_code == 200, response.text



def test_receipt_cannot_be_created_by_inactive_user():
    donor_headers, donor_user_id = create_user("DONOR")
    _, campaign = create_campaign_for_test()

    _, donation_id = create_confirmed_donation(
        donor_user_id, campaign["id"]
    )

    db = SessionLocal()
    try:
        user = db.get(User, donor_user_id)
        assert user is not None
        user.is_active = False
        db.commit()
    finally:
        db.close()

    response = issue_receipt(donor_headers, donation_id)

    assert response.status_code == 401
    assert response.json()["detail"] == "Account is unavailable."
