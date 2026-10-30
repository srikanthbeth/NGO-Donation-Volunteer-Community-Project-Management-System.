
import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect

# Load settings before importing application modules.
load_dotenv(dotenv_path=".env", override=False)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is missing from .env")

# Prevent accidentally running tests against the development database.
database_name = TEST_DATABASE_URL.split("?", 1)[0].rsplit("/", 1)[-1]
if not database_name.endswith("_test"):
    raise RuntimeError(
        "Safety check failed: TEST_DATABASE_URL must end with a database "
        "name ending in '_test'."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "development"

from db.base import Base
from db.session import SessionLocal, engine, get_db
from main import app
from models.user import User, RefreshToken, PasswordResetToken
from models.donor import Donor


BASE_URL = "/api/v1"
PASSWORD = "DonorTest@12345"

# Ensure these tables are registered in SQLAlchemy metadata.
_ = (User, RefreshToken, PasswordResetToken, Donor)

# Confirm that the test database has already been migrated.
existing_tables = set(inspect(engine).get_table_names())
missing_tables = set(Base.metadata.tables) - existing_tables
if missing_tables:
    raise RuntimeError(
        f"Test database is missing tables: {sorted(missing_tables)}. "
        "Apply Alembic migrations to TEST_DATABASE_URL first."
    )


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_test_data():
    # This fixture only deletes data from the database ending in '_test'.
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
    yield


def unique_email():
    return f"donor_{uuid4().hex[:12]}@example.com"




def register_and_login(client, email=None):
    email = email or unique_email()

    register_response = client.post(
        f"{BASE_URL}/auth/register",
        json={
            "full_name": "Test Donor",
            "email": email,
            "password": PASSWORD,
        },
    )

    assert register_response.status_code in (200, 201), (
        f"Registration failed: {register_response.status_code} "
        f"{register_response.text}"
    )

    login_response = client.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": email,
            "password": PASSWORD,
        },
    )

    assert login_response.status_code == 200, (
        f"Login failed: {login_response.status_code} "
        f"{login_response.text}"
    )

    login_data = login_response.json()
    token = login_data.get("access_token")

    assert token, f"Login response has no access_token: {login_data}"

    headers = {"Authorization": f"Bearer {token}"}

    me_response = client.get(
        f"{BASE_URL}/auth/me",
        headers=headers,
    )

    assert me_response.status_code == 200, (
        f"Could not get current user: {me_response.status_code} "
        f"{me_response.text}"
    )

    user = me_response.json()

    return {
        "email": email,
        "token": token,
        "headers": headers,
        "user": user,
    }



def create_individual_profile(client, headers):
    return client.post(
        f"{BASE_URL}/donors",
        headers=headers,
        json={
            "donor_type": "INDIVIDUAL",
            "phone": "9876543210",
            "city": "Hyderabad",
            "country": "India",
            "preferred_contact_method": "EMAIL",
            "anonymous_default": False,
        },
    )


def test_create_donor_profile(client):
    account = register_and_login(client)

    response = create_individual_profile(client, account["headers"])

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["user_id"] == account["user"]["id"]
    assert data["donor_type"] == "INDIVIDUAL"
    assert data["city"] == "Hyderabad"


def test_get_my_donor_profile(client):
    account = register_and_login(client)
    created = create_individual_profile(client, account["headers"])
    assert created.status_code == 201, created.text

    response = client.get(
        f"{BASE_URL}/donors/me",
        headers=account["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == created.json()["id"]


def test_donor_can_update_own_profile(client):
    account = register_and_login(client)
    created = create_individual_profile(client, account["headers"])
    assert created.status_code == 201, created.text

    response = client.patch(
        f"{BASE_URL}/donors/{created.json()['id']}",
        headers=account["headers"],
        json={"city": "Vijayawada", "phone": "9123456789"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["city"] == "Vijayawada"
    assert response.json()["phone"] == "9123456789"


def test_duplicate_donor_profile_is_rejected(client):
    account = register_and_login(client)

    first = create_individual_profile(client, account["headers"])
    second = create_individual_profile(client, account["headers"])

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text


def test_create_organization_donor(client):
    account = register_and_login(client)

    response = client.post(
        f"{BASE_URL}/donors",
        headers=account["headers"],
        json={
            "donor_type": "ORGANIZATION",
            "organization_name": "Community Support Foundation",
            "city": "Hyderabad",
            "country": "India",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["donor_type"] == "ORGANIZATION"
    assert response.json()["organization_name"] == (
        "Community Support Foundation"
    )


def test_organization_requires_name(client):
    account = register_and_login(client)

    response = client.post(
        f"{BASE_URL}/donors",
        headers=account["headers"],
        json={"donor_type": "ORGANIZATION"},
    )

    assert response.status_code == 422


def test_individual_rejects_organization_name(client):
    account = register_and_login(client)

    response = client.post(
        f"{BASE_URL}/donors",
        headers=account["headers"],
        json={
            "donor_type": "INDIVIDUAL",
            "organization_name": "Unexpected Organization",
        },
    )

    assert response.status_code == 422


def test_invalid_donor_type_rejected(client):
    account = register_and_login(client)

    response = client.post(
        f"{BASE_URL}/donors",
        headers=account["headers"],
        json={"donor_type": "GOVERNMENT"},
    )

    assert response.status_code == 422


def test_invalid_contact_method_rejected(client):
    account = register_and_login(client)

    response = client.post(
        f"{BASE_URL}/donors",
        headers=account["headers"],
        json={"preferred_contact_method": "POSTAL_MAIL"},
    )

    assert response.status_code == 422


def test_donor_cannot_list_all_donors(client):
    account = register_and_login(client)

    response = client.get(
        f"{BASE_URL}/donors",
        headers=account["headers"],
    )

    assert response.status_code == 403


def test_donor_cannot_access_another_profile(client):
    first_account = register_and_login(client)
    second_account = register_and_login(client)

    created = create_individual_profile(
        client, first_account["headers"]
    )
    assert created.status_code == 201, created.text

    response = client.get(
        f"{BASE_URL}/donors/{created.json()['id']}",
        headers=second_account["headers"],
    )

    assert response.status_code == 403


def test_donor_cannot_update_another_profile(client):
    first_account = register_and_login(client)
    second_account = register_and_login(client)

    created = create_individual_profile(
        client, first_account["headers"]
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        f"{BASE_URL}/donors/{created.json()['id']}",
        headers=second_account["headers"],
        json={"city": "Unauthorized City"},
    )

    assert response.status_code == 403


def test_missing_own_profile_returns_404(client):
    account = register_and_login(client)

    response = client.get(
        f"{BASE_URL}/donors/me",
        headers=account["headers"],
    )

    assert response.status_code == 404


def test_nonexistent_donor_returns_404(client):
    account = register_and_login(client)

    response = client.get(
        f"{BASE_URL}/donors/99999999",
        headers=account["headers"],
    )

    assert response.status_code == 404


def test_donor_endpoint_requires_authentication(client):
    response = client.get(f"{BASE_URL}/donors/me")

    assert response.status_code == 401


def test_donor_cannot_create_profile_for_another_user(client):
    first_account = register_and_login(client)
    second_account = register_and_login(client)

    response = client.post(
        f"{BASE_URL}/donors",
        headers=first_account["headers"],
        json={"user_id": second_account["user"]["id"]},
    )

    assert response.status_code == 201, response.text
    assert response.json()["user_id"] == first_account["user"]["id"]


@pytest.mark.parametrize("page", [0, -1])
def test_invalid_page_rejected(client, page):
    account = register_and_login(client)

    response = client.get(
        f"{BASE_URL}/donors",
        headers=account["headers"],
        params={"page": page},
    )

    assert response.status_code in (403, 422)


def test_invalid_page_size_rejected(client):
    account = register_and_login(client)

    response = client.get(
        f"{BASE_URL}/donors",
        headers=account["headers"],
        params={"page_size": 101},
    )

    assert response.status_code in (403, 422)
