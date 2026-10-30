
import os
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

test_database_url = os.getenv("TEST_DATABASE_URL")
if not test_database_url:
    raise RuntimeError(
        "TEST_DATABASE_URL is missing from .env. "
        "Tests must use a separate PostgreSQL test database."
    )

if not test_database_url.split("/")[-1].split("?")[0].endswith("_test"):
    raise RuntimeError(
        "Safety check failed: TEST_DATABASE_URL must end with '_test'."
    )

os.environ["DATABASE_URL"] = test_database_url
os.environ["ENVIRONMENT"] = "development"

from fastapi.testclient import TestClient
from sqlalchemy import text

from core.security import hash_password, verify_password
from db.base import Base
from db.session import SessionLocal, engine
from main import app
from models.user import User


client = TestClient(app)


def unique_email():
    return f"user_{uuid4().hex[:10]}@example.com"


def cleanup_database():
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    password_reset_tokens,
                    refresh_tokens,
                    users
                RESTART IDENTITY CASCADE
                """
            )
        )


def setup_module():
    Base.metadata.create_all(bind=engine)
    cleanup_database()


def teardown_module():
    cleanup_database()


def register_user(email=None, password="StrongPassword123!"):
    if email is None:
        email = unique_email()

    return client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Donor",
            "email": email,
            "password": password,
        },
    )


def login_user(email, password="StrongPassword123!"):
    return client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )


def create_admin():
    email = unique_email()
    db = SessionLocal()

    try:
        admin = User(
            full_name="Test Super Admin",
            email=email,
            hashed_password=hash_password("AdminPassword123!"),
            role="SUPER_ADMIN",
            is_active=True,
            is_verified=True,
        )

        db.add(admin)
        db.commit()
    finally:
        db.close()

    response = login_user(email, "AdminPassword123!")
    assert response.status_code == 200, response.text

    return response.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------
# Registration tests
# ---------------------------------------------------------


def test_register_user():
    response = register_user()

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["full_name"] == "Test Donor"
    assert data["email"].endswith("@example.com")
    assert data["role"] == "DONOR"
    assert data["is_active"] is True
    assert "hashed_password" not in data
    assert "password" not in data


def test_public_registration_cannot_select_admin_role():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Attempted Admin",
            "email": unique_email(),
            "password": "StrongPassword123!",
            "role": "SUPER_ADMIN",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "DONOR"


def test_duplicate_email():
    email = unique_email()

    first = register_user(email)
    assert first.status_code == 201, first.text

    second = register_user(email)

    assert second.status_code == 409
    assert second.json()["detail"] == (
        "An account with this email already exists."
    )


def test_email_is_normalized():
    email = unique_email()
    response = register_user(email.upper())

    assert response.status_code == 201, response.text
    assert response.json()["email"] == email.lower()


def test_password_is_hashed():
    email = unique_email()

    response = register_user(email)
    assert response.status_code == 201, response.text

    db = SessionLocal()

    try:
        user = db.query(User).filter(User.email == email).first()

        assert user is not None
        assert user.hashed_password != "StrongPassword123!"
        assert verify_password(
            "StrongPassword123!",
            user.hashed_password,
        )
    finally:
        db.close()


def test_registration_rejects_short_password():
    response = register_user(password="Short1!")

    assert response.status_code == 422


def test_registration_rejects_password_without_uppercase():
    response = register_user(password="strongpassword123!")

    assert response.status_code == 422


def test_registration_rejects_password_without_lowercase():
    response = register_user(password="STRONGPASSWORD123!")

    assert response.status_code == 422


def test_registration_rejects_password_without_number():
    response = register_user(password="StrongPassword!")

    assert response.status_code == 422


def test_registration_rejects_password_without_special_character():
    response = register_user(password="StrongPassword123")

    assert response.status_code == 422


def test_registration_rejects_invalid_email():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Donor",
            "email": "not-an-email",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 422


def test_registration_rejects_short_full_name():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "A",
            "email": unique_email(),
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 422


# ---------------------------------------------------------
# Login tests
# ---------------------------------------------------------


def test_login_success():
    email = unique_email()

    register_response = register_user(email)
    assert register_response.status_code == 201, register_response.text

    response = login_user(email)

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_login_with_invalid_password():
    email = unique_email()
    register_user(email)

    response = login_user(email, "WrongPassword123!")

    assert response.status_code == 401


def test_login_with_unknown_email():
    response = login_user(unique_email())

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_inactive_user_cannot_login():
    email = unique_email()

    register_response = register_user(email)
    assert register_response.status_code == 201, register_response.text

    user_id = register_response.json()["id"]

    db = SessionLocal()

    try:
        user = db.get(User, user_id)
        assert user is not None

        user.is_active = False
        db.commit()
    finally:
        db.close()

    response = login_user(email)

    assert response.status_code == 403
    assert response.json()["detail"] == "This account is inactive."


# ---------------------------------------------------------
# Current-user authentication tests
# ---------------------------------------------------------


def test_current_user():
    email = unique_email()
    register_response = register_user(email)

    assert register_response.status_code == 201, register_response.text

    login_response = login_user(email)
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers(token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["email"] == email
    assert response.json()["role"] == "DONOR"


def test_missing_authentication():
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_invalid_access_token():
    response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers("invalid-token"),
    )

    assert response.status_code == 401


def test_inactive_user_cannot_access_current_user_endpoint():
    email = unique_email()
    register_response = register_user(email)

    assert register_response.status_code == 201

    login_response = login_user(email)
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    user_id = register_response.json()["id"]

    db = SessionLocal()

    try:
        user = db.get(User, user_id)
        assert user is not None

        user.is_active = False
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers(token),
    )

    assert response.status_code == 401


# ---------------------------------------------------------
# Refresh-token tests
# ---------------------------------------------------------


def test_refresh_token():
    email = unique_email()
    register_user(email)

    login_response = login_user(email)
    assert login_response.status_code == 200, login_response.text

    old_refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["access_token"]
    assert data["refresh_token"]
    assert data["refresh_token"] != old_refresh_token


def test_old_refresh_token_cannot_be_reused():
    email = unique_email()
    register_user(email)

    login_response = login_user(email)
    assert login_response.status_code == 200, login_response.text

    old_refresh_token = login_response.json()["refresh_token"]

    first_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert first_refresh.status_code == 200, first_refresh.text

    second_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert second_refresh.status_code == 401


def test_invalid_refresh_token():
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-refresh-token-123456789"},
    )

    assert response.status_code == 401


def test_logout():
    email = unique_email()
    register_user(email)

    login_response = login_user(email)
    assert login_response.status_code == 200, login_response.text

    data = login_response.json()

    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": data["refresh_token"]},
        headers=auth_headers(data["access_token"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Logged out successfully."

    # Logout revokes the refresh token; it does not currently revoke
    # an already-issued access token.
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )

    assert refresh_response.status_code == 401


def test_logout_with_unknown_refresh_token():
    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "unknown-refresh-token-123456789"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully."


# ---------------------------------------------------------
# Password-reset tests
# ---------------------------------------------------------


def test_password_reset_request():
    email = unique_email()
    register_user(email)

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "message" in data
    assert data.get("development_reset_token")


def test_password_reset_unknown_email():
    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": unique_email()},
    )

    assert response.status_code == 200
    assert "message" in response.json()
    assert "development_reset_token" not in response.json()


def test_password_reset_changes_password():
    email = unique_email()
    register_user(email)

    reset_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
    )

    assert reset_response.status_code == 200, reset_response.text

    reset_token = reset_response.json().get("development_reset_token")
    assert reset_token

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": reset_token,
            "new_password": "NewStrongPassword456!",
        },
    )

    assert response.status_code == 200, response.text

    old_login = login_user(email, "StrongPassword123!")
    assert old_login.status_code == 401

    new_login = login_user(email, "NewStrongPassword456!")
    assert new_login.status_code == 200, new_login.text


def test_password_reset_token_cannot_be_reused():
    email = unique_email()
    register_user(email)

    reset_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
    )

    assert reset_response.status_code == 200, reset_response.text
    reset_token = reset_response.json()["development_reset_token"]

    first_reset = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": reset_token,
            "new_password": "NewStrongPassword456!",
        },
    )

    assert first_reset.status_code == 200, first_reset.text

    second_reset = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": reset_token,
            "new_password": "AnotherStrongPassword789!",
        },
    )

    assert second_reset.status_code == 400


def test_invalid_password_reset_token():
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": "invalid-reset-token-123456789",
            "new_password": "NewStrongPassword456!",
        },
    )

    assert response.status_code == 400


def test_password_reset_revokes_refresh_tokens():
    email = unique_email()
    register_user(email)

    login_response = login_user(email)
    assert login_response.status_code == 200

    old_refresh_token = login_response.json()["refresh_token"]

    reset_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
    )

    assert reset_response.status_code == 200
    reset_token = reset_response.json()["development_reset_token"]

    confirm_response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": reset_token,
            "new_password": "NewStrongPassword456!",
        },
    )

    assert confirm_response.status_code == 200, confirm_response.text

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert refresh_response.status_code == 401


# ---------------------------------------------------------
# Role-based access tests
# ---------------------------------------------------------


def test_donor_cannot_list_users():
    email = unique_email()
    register_user(email)

    login_response = login_user(email)
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/users",
        headers=auth_headers(token),
    )

    assert response.status_code == 403


def test_donor_cannot_update_user_status():
    donor_email = unique_email()
    register_user(donor_email)

    login_response = login_user(donor_email)
    assert login_response.status_code == 200

    target_response = register_user()
    assert target_response.status_code == 201

    target_id = target_response.json()["id"]

    response = client.patch(
        f"/api/v1/users/{target_id}/status",
        json={"is_active": False},
        headers=auth_headers(login_response.json()["access_token"]),
    )

    assert response.status_code == 403


def test_super_admin_can_list_users():
    token = create_admin()

    response = client.get(
        "/api/v1/users",
        headers=auth_headers(token),
    )

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_super_admin_can_update_user_status():
    token = create_admin()

    target_response = register_user()
    assert target_response.status_code == 201, target_response.text

    target_id = target_response.json()["id"]

    response = client.patch(
        f"/api/v1/users/{target_id}/status",
        json={"is_active": False},
        headers=auth_headers(token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False


def test_super_admin_can_activate_user():
    token = create_admin()

    target_response = register_user()
    assert target_response.status_code == 201

    target_id = target_response.json()["id"]

    deactivate_response = client.patch(
        f"/api/v1/users/{target_id}/status",
        json={"is_active": False},
        headers=auth_headers(token),
    )

    assert deactivate_response.status_code == 200

    activate_response = client.patch(
        f"/api/v1/users/{target_id}/status",
        json={"is_active": True},
        headers=auth_headers(token),
    )

    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True


def test_super_admin_can_update_user_role():
    token = create_admin()

    target_response = register_user()
    assert target_response.status_code == 201, target_response.text

    target_id = target_response.json()["id"]

    response = client.patch(
        f"/api/v1/users/{target_id}/role",
        json={"role": "NGO_MANAGER"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "NGO_MANAGER"


def test_super_admin_role_cannot_be_changed_by_role_endpoint():
    token = create_admin()

    db = SessionLocal()

    try:
        admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
        assert admin is not None
        admin_id = admin.id
    finally:
        db.close()

    response = client.patch(
        f"/api/v1/users/{admin_id}/role",
        json={"role": "NGO_MANAGER"},
        headers=auth_headers(token),
    )

    assert response.status_code == 403


def test_user_cannot_deactivate_own_account():
    token = create_admin()

    db = SessionLocal()

    try:
        admin = db.query(User).filter(User.role == "SUPER_ADMIN").first()
        assert admin is not None
        admin_id = admin.id
    finally:
        db.close()

    response = client.patch(
        f"/api/v1/users/{admin_id}/status",
        json={"is_active": False},
        headers=auth_headers(token),
    )

    # The current service protects all SUPER_ADMIN accounts.
    assert response.status_code == 403


def test_update_nonexistent_user_returns_404():
    token = create_admin()

    response = client.patch(
        "/api/v1/users/999999/status",
        json={"is_active": False},
        headers=auth_headers(token),
    )

    assert response.status_code == 404
