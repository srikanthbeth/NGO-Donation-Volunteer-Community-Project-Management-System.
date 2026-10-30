
import os
from datetime import date, timedelta
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
    """Clear tables before and after each test."""
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
    return f"assignment_{uuid4().hex[:12]}@example.com"


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


def create_active_volunteer():
    account = register_and_login("VOLUNTEER")

    response = client.post(
        "/api/v1/volunteers",
        headers=account["headers"],
        json={
            "bio": "Experienced community volunteer",
            "skills": ["Teaching", "First Aid"],
            "availability": "WEEKENDS",
            "hours_per_week": 20,
            "experience_years": 3,
            "preferred_areas": "Education",
        },
    )
    assert response.status_code == 201, response.text

    volunteer_id = response.json()["id"]

    manager = register_and_login("NGO_MANAGER")

    response = client.patch(
        f"/api/v1/volunteers/{volunteer_id}/status",
        headers=manager["headers"],
        json={"status": "ACTIVE"},
    )
    assert response.status_code == 200, response.text

    return account, response.json(), manager


def assignment_payload(volunteer_id, **overrides):
    payload = {
        "volunteer_id": volunteer_id,
        "project_id": None,
        "title": "Community Teaching",
        "description": "Support community education activities.",
        "responsibilities": "Prepare materials and help learners.",
        "start_date": (date.today() + timedelta(days=1)).isoformat(),
        "end_date": (date.today() + timedelta(days=14)).isoformat(),
        "hours_per_week": 8,
    }
    payload.update(overrides)
    return payload


def create_assignment(manager, volunteer_id, **overrides):
    return client.post(
        "/api/v1/volunteer-assignments",
        headers=manager["headers"],
        json=assignment_payload(volunteer_id, **overrides),
    )


def test_staff_can_create_assignment():
    _, volunteer, manager = create_active_volunteer()

    response = create_assignment(manager, volunteer["id"])

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["volunteer_id"] == volunteer["id"]
    assert data["title"] == "Community Teaching"
    assert data["status"] == "ASSIGNED"
    assert data["assigned_by"] > 0


def test_assignment_creation_requires_authentication():
    response = client.post(
        "/api/v1/volunteer-assignments",
        json=assignment_payload(1),
    )

    assert response.status_code == 401


def test_volunteer_cannot_create_assignment():
    _, volunteer, _ = create_active_volunteer()
    volunteer_account = register_and_login("VOLUNTEER")

    response = create_assignment(
        volunteer_account,
        volunteer["id"],
    )

    assert response.status_code == 403


def test_assignment_requires_existing_volunteer():
    manager = register_and_login("NGO_MANAGER")

    response = create_assignment(manager, 999999)

    assert response.status_code == 404


def test_assignment_rejects_pending_volunteer():
    volunteer_account = register_and_login("VOLUNTEER")

    response = client.post(
        "/api/v1/volunteers",
        headers=volunteer_account["headers"],
        json={
            "skills": ["Teaching"],
            "availability": "WEEKENDS",
            "hours_per_week": 10,
            "experience_years": 1,
        },
    )
    assert response.status_code == 201, response.text

    manager = register_and_login("NGO_MANAGER")

    response = create_assignment(manager, response.json()["id"])

    assert response.status_code == 422
    assert "active volunteers" in response.json()["detail"]


def test_assignment_rejects_hours_above_volunteer_availability():
    _, volunteer, manager = create_active_volunteer()

    response = create_assignment(
        manager,
        volunteer["id"],
        hours_per_week=21,
    )

    assert response.status_code == 422
    assert "available hours" in response.json()["detail"]


def test_assignment_rejects_invalid_date_range():
    _, volunteer, manager = create_active_volunteer()
    start = date.today() + timedelta(days=10)
    end = date.today() + timedelta(days=2)

    response = create_assignment(
        manager,
        volunteer["id"],
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("hours", [-1, 169])
def test_assignment_rejects_invalid_weekly_hours(hours):
    _, volunteer, manager = create_active_volunteer()

    response = create_assignment(
        manager,
        volunteer["id"],
        hours_per_week=hours,
    )

    assert response.status_code == 422


def test_volunteer_can_view_own_assignment():
    volunteer_account, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.get(
        f"/api/v1/volunteer-assignments/{created.json()['id']}",
        headers=volunteer_account["headers"],
    )

    assert response.status_code == 200
    assert response.json()["id"] == created.json()["id"]


def test_volunteer_cannot_view_another_volunteers_assignment():
    _, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    # Create a second volunteer account with an actual profile.
    another_volunteer, _, _ = create_active_volunteer()

    response = client.get(
        f"/api/v1/volunteer-assignments/{created.json()['id']}",
        headers=another_volunteer["headers"],
    )

    assert response.status_code == 403



def test_staff_can_list_assignments():
    _, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.get(
        "/api/v1/volunteer-assignments",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


def test_volunteer_can_list_only_own_assignments():
    volunteer_account, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.get(
        "/api/v1/volunteer-assignments",
        headers=volunteer_account["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["volunteer_id"] == volunteer["id"]




def test_volunteer_cannot_filter_another_volunteers_assignments():
    _, volunteer, _ = create_active_volunteer()

    # The requesting user must also have a volunteer profile.
    another_volunteer, _, _ = create_active_volunteer()

    response = client.get(
        f"/api/v1/volunteer-assignments?volunteer_id={volunteer['id']}",
        headers=another_volunteer["headers"],
    )

    assert response.status_code == 403


def test_staff_can_update_assignment_details():
    _, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/volunteer-assignments/{created.json()['id']}",
        headers=manager["headers"],
        json={
            "title": "Updated Teaching Assignment",
            "hours_per_week": 12,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated Teaching Assignment"
    assert response.json()["hours_per_week"] == 12


def test_volunteer_cannot_edit_assignment_details():
    volunteer_account, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/volunteer-assignments/{created.json()['id']}",
        headers=volunteer_account["headers"],
        json={"title": "Unauthorized edit"},
    )

    assert response.status_code == 403


def test_volunteer_can_accept_assignment():
    volunteer_account, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/volunteer-assignments/{created.json()['id']}/status",
        headers=volunteer_account["headers"],
        json={"status": "ACCEPTED"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACCEPTED"


def test_volunteer_can_start_accepted_assignment():
    volunteer_account, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    accepted = client.patch(
        f"/api/v1/volunteer-assignments/{assignment_id}/status",
        headers=volunteer_account["headers"],
        json={"status": "ACCEPTED"},
    )
    assert accepted.status_code == 200, accepted.text

    response = client.patch(
        f"/api/v1/volunteer-assignments/{assignment_id}/status",
        headers=volunteer_account["headers"],
        json={"status": "IN_PROGRESS"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "IN_PROGRESS"


def test_staff_can_complete_in_progress_assignment():
    volunteer_account, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    accepted = client.patch(
        f"/api/v1/volunteer-assignments/{assignment_id}/status",
        headers=volunteer_account["headers"],
        json={"status": "ACCEPTED"},
    )
    assert accepted.status_code == 200, accepted.text

    started = client.patch(
        f"/api/v1/volunteer-assignments/{assignment_id}/status",
        headers=volunteer_account["headers"],
        json={"status": "IN_PROGRESS"},
    )
    assert started.status_code == 200, started.text

    response = client.patch(
        f"/api/v1/volunteer-assignments/{assignment_id}/status",
        headers=manager["headers"],
        json={"status": "COMPLETED"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "COMPLETED"


def test_invalid_status_transition_is_rejected():
    _, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/volunteer-assignments/{created.json()['id']}/status",
        headers=manager["headers"],
        json={"status": "COMPLETED"},
    )

    assert response.status_code == 422


def test_volunteer_cannot_complete_assignment_directly():
    volunteer_account, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"/api/v1/volunteer-assignments/{created.json()['id']}/status",
        headers=volunteer_account["headers"],
        json={"status": "COMPLETED"},
    )

    assert response.status_code == 403


def test_unknown_assignment_returns_404():
    manager = register_and_login("NGO_MANAGER")

    response = client.get(
        "/api/v1/volunteer-assignments/999999",
        headers=manager["headers"],
    )

    assert response.status_code == 404


def test_staff_can_filter_assignments_by_status():
    _, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.get(
        "/api/v1/volunteer-assignments?status=ASSIGNED",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


def test_staff_can_search_assignments_by_title():
    _, volunteer, manager = create_active_volunteer()
    created = create_assignment(
        manager,
        volunteer["id"],
        title="Community Reading Program",
    )
    assert created.status_code == 201, created.text

    response = client.get(
        "/api/v1/volunteer-assignments?search=Reading",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


def test_staff_can_filter_assignments_by_volunteer():
    _, volunteer, manager = create_active_volunteer()
    created = create_assignment(manager, volunteer["id"])
    assert created.status_code == 201, created.text

    response = client.get(
        f"/api/v1/volunteer-assignments?volunteer_id={volunteer['id']}",
        headers=manager["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


def test_assignment_title_must_not_be_blank():
    _, volunteer, manager = create_active_volunteer()

    response = create_assignment(
        manager,
        volunteer["id"],
        title="   ",
    )

    assert response.status_code == 422
