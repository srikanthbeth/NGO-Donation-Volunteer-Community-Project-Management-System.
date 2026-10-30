import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv

load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL or "ngo_management_system_test" not in TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL must point to ngo_management_system_test."
    )

os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from fastapi.testclient import TestClient
from sqlalchemy import select

from db.base import Base
from db.session import SessionLocal
from main import app
from models.user import User

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    """Clear test tables before and after every test."""
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()

    yield

    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()


def unique_email():
    return f"volunteer_{uuid4().hex[:12]}@example.com"


def register_and_login(role="VOLUNTEER"):
    email = unique_email()
    password = "StrongPassword123!"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Test {role.title()}",
            "email": email,
            "password": password,
        },
    )
    assert response.status_code in (200, 201), response.text

    # Assign the role directly for testing role-based access.
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.role = role
        db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text

    token = response.json()["access_token"]
    return {
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def create_volunteer_profile(headers, **overrides):
    payload = {
        "bio": "I enjoy helping my community.",
        "skills": ["Teaching", "First Aid"],
        "availability": "WEEKENDS",
        "hours_per_week": 8,
        "experience_years": 2,
        "preferred_areas": "Education and community outreach",
        "emergency_contact_name": "Emergency Contact",
        "emergency_contact_phone": "9876543210",
    }
    payload.update(overrides)

    return client.post(
        "/api/v1/volunteers",
        json=payload,
        headers=headers,
    )


def test_volunteer_can_create_own_profile():
    volunteer = register_and_login()

    response = create_volunteer_profile(volunteer["headers"])

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["user_id"] > 0
    assert data["skills"] == ["Teaching", "First Aid"]
    assert data["availability"] == "WEEKENDS"
    assert data["status"] == "PENDING"


def test_creating_profile_requires_authentication():
    response = client.post(
        "/api/v1/volunteers",
        json={"skills": ["Teaching"]},
    )

    assert response.status_code == 401


def test_non_volunteer_cannot_create_volunteer_profile():
    donor = register_and_login("DONOR")

    response = create_volunteer_profile(donor["headers"])

    assert response.status_code == 409
    assert "Only volunteer accounts" in response.json()["detail"]


def test_volunteer_cannot_create_duplicate_profile():
    volunteer = register_and_login()
    first = create_volunteer_profile(volunteer["headers"])
    assert first.status_code == 201, first.text

    second = create_volunteer_profile(volunteer["headers"])

    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


def test_volunteer_can_get_own_profile():
    volunteer = register_and_login()
    created = create_volunteer_profile(volunteer["headers"])
    assert created.status_code == 201, created.text

    response = client.get(
        "/api/v1/volunteers/me",
        headers=volunteer["headers"],
    )

    assert response.status_code == 200
    assert response.json()["id"] == created.json()["id"]


def test_volunteer_without_profile_gets_404():
    volunteer = register_and_login()

    response = client.get(
        "/api/v1/volunteers/me",
        headers=volunteer["headers"],
    )

    assert response.status_code == 404


def test_volunteer_can_update_own_profile():
    volunteer = register_and_login()
    created = create_volunteer_profile(volunteer["headers"])
    volunteer_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/volunteers/{volunteer_id}",
        json={
            "bio": "Updated volunteer biography.",
            "skills": ["Teaching", "First Aid", "Driving"],
            "hours_per_week": 12,
        },
        headers=volunteer["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["bio"] == "Updated volunteer biography."
    assert data["skills"] == ["Teaching", "First Aid", "Driving"]
    assert data["hours_per_week"] == 12


def test_volunteer_cannot_access_another_volunteers_profile():
    volunteer_one = register_and_login()
    created = create_volunteer_profile(volunteer_one["headers"])
    volunteer_id = created.json()["id"]

    volunteer_two = register_and_login()

    response = client.get(
        f"/api/v1/volunteers/{volunteer_id}",
        headers=volunteer_two["headers"],
    )

    assert response.status_code == 403


def test_volunteer_cannot_update_another_volunteers_profile():
    volunteer_one = register_and_login()
    created = create_volunteer_profile(volunteer_one["headers"])
    volunteer_id = created.json()["id"]

    volunteer_two = register_and_login()

    response = client.patch(
        f"/api/v1/volunteers/{volunteer_id}",
        json={"bio": "Unauthorized update"},
        headers=volunteer_two["headers"],
    )

    assert response.status_code == 403


def test_staff_can_list_volunteers():
    volunteer = register_and_login()
    created = create_volunteer_profile(volunteer["headers"])
    assert created.status_code == 201, created.text

    manager = register_and_login("NGO_MANAGER")

    response = client.get(
        "/api/v1/volunteers",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_volunteer_cannot_list_all_volunteers():
    volunteer = register_and_login()

    response = client.get(
        "/api/v1/volunteers",
        headers=volunteer["headers"],
    )

    assert response.status_code == 403


def test_staff_can_activate_volunteer():
    volunteer = register_and_login()
    created = create_volunteer_profile(volunteer["headers"])
    volunteer_id = created.json()["id"]

    manager = register_and_login("VOLUNTEER_COORDINATOR")

    response = client.patch(
        f"/api/v1/volunteers/{volunteer_id}/status",
        json={"status": "ACTIVE"},
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACTIVE"


def test_volunteer_cannot_change_own_status():
    volunteer = register_and_login()
    created = create_volunteer_profile(volunteer["headers"])
    volunteer_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/volunteers/{volunteer_id}/status",
        json={"status": "ACTIVE"},
        headers=volunteer["headers"],
    )

    assert response.status_code == 403


@pytest.mark.parametrize("hours", [-1, 169])
def test_invalid_hours_per_week_are_rejected(hours):
    volunteer = register_and_login()

    response = create_volunteer_profile(
        volunteer["headers"],
        hours_per_week=hours,
    )

    assert response.status_code == 422


@pytest.mark.parametrize("years", [-1, 101])
def test_invalid_experience_years_are_rejected(years):
    volunteer = register_and_login()

    response = create_volunteer_profile(
        volunteer["headers"],
        experience_years=years,
    )

    assert response.status_code == 422


def test_invalid_availability_is_rejected():
    volunteer = register_and_login()

    response = create_volunteer_profile(
        volunteer["headers"],
        availability="SOMEDAY",
    )

    assert response.status_code == 422


def test_blank_skill_is_rejected():
    volunteer = register_and_login()

    response = create_volunteer_profile(
        volunteer["headers"],
        skills=["Teaching", "   "],
    )

    assert response.status_code == 422


def test_duplicate_skills_are_removed():
    volunteer = register_and_login()

    response = create_volunteer_profile(
        volunteer["headers"],
        skills=["Teaching", "Teaching", "First Aid"],
    )

    assert response.status_code == 201, response.text
    assert response.json()["skills"] == ["Teaching", "First Aid"]


def test_staff_can_filter_volunteers_by_status():
    volunteer = register_and_login()
    created = create_volunteer_profile(volunteer["headers"])
    assert created.status_code == 201, created.text

    manager = register_and_login("NGO_MANAGER")

    response = client.get(
        "/api/v1/volunteers?status=PENDING",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["status"] == "PENDING"


def test_staff_can_search_volunteers():
    volunteer = register_and_login()
    created = create_volunteer_profile(
        volunteer["headers"],
        preferred_areas="Special Education",
    )
    assert created.status_code == 201, created.text

    manager = register_and_login("NGO_MANAGER")

    response = client.get(
        "/api/v1/volunteers?search=Special%20Education",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


def test_unknown_volunteer_profile_returns_404():
    manager = register_and_login("NGO_MANAGER")

    response = client.get(
        "/api/v1/volunteers/999999",
        headers=manager["headers"],
    )

    assert response.status_code == 404


def test_staff_can_filter_volunteers_by_availability():
    volunteer = register_and_login()
    created = create_volunteer_profile(
        volunteer["headers"],
        availability="WEEKENDS",
    )
    assert created.status_code == 201, created.text

    manager = register_and_login("NGO_MANAGER")

    response = client.get(
        "/api/v1/volunteers?availability=WEEKENDS",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["availability"] == "WEEKENDS"
