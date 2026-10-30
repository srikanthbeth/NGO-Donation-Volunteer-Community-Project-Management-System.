
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
    """Clean database tables before and after each test."""
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


def create_user(role="NGO_MANAGER"):
    suffix = uuid4().hex[:12]
    email = f"{role.lower()}_{suffix}@example.com"
    password = "TestPassword123!"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Test {role}",
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

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]
    return {
        "Authorization": f"Bearer {token}",
    }


def create_project(headers):
    today = date.today()
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": f"Resource Test Project {uuid4().hex[:8]}",
            "description": "Project created for resource management tests",
            "location": "Hyderabad",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=60)).isoformat(),
            "budget": 50000,
            "currency": "INR",
            "status": "DRAFT",
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def create_resource(headers, **overrides):
    payload = {
        "name": f"Food Package {uuid4().hex[:8]}",
        "category": "FOOD",
        "description": "Resource created for testing",
        "unit": "package",
        "low_stock_threshold": 5,
    }
    payload.update(overrides)

    response = client.post(
        "/api/v1/resources",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def stock_movement(headers, resource_id, transaction_type, quantity):
    return client.post(
        f"/api/v1/resources/{resource_id}/stock-movements",
        headers=headers,
        json={
            "transaction_type": transaction_type,
            "quantity": quantity,
            "reference": f"TEST-{uuid4().hex[:8]}",
            "notes": "Automated integration test",
        },
    )


def test_create_resource_starts_with_zero_stock():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)

    assert resource["id"] > 0
    assert resource["category"] == "FOOD"
    assert resource["quantity_available"] == 0
    assert resource["status"] == "ACTIVE"


def test_list_resources():
    headers = create_user("NGO_MANAGER")
    create_resource(headers, name="Food Supplies")
    create_resource(headers, name="Clothing Supplies", category="CLOTHING")

    response = client.get("/api/v1/resources", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 2


def test_filter_resources_by_category():
    headers = create_user("NGO_MANAGER")
    create_resource(headers, name="Food Item", category="FOOD")
    create_resource(headers, name="Medical Item", category="MEDICAL_SUPPLIES")

    response = client.get(
        "/api/v1/resources",
        headers=headers,
        params={"category": "FOOD"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["category"] == "FOOD"


def test_get_resource_by_id():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)

    response = client.get(
        f"/api/v1/resources/{resource['id']}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == resource["id"]


def test_get_missing_resource_returns_404():
    headers = create_user("NGO_MANAGER")

    response = client.get("/api/v1/resources/999999", headers=headers)

    assert response.status_code == 404


def test_stock_in_increases_inventory():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)

    response = stock_movement(
        headers, resource["id"], "STOCK_IN", 20
    )

    assert response.status_code == 201, response.text

    get_response = client.get(
        f"/api/v1/resources/{resource['id']}",
        headers=headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["quantity_available"] == 20


def test_stock_out_decreases_inventory():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)

    stock_in = stock_movement(
        headers, resource["id"], "STOCK_IN", 20
    )
    assert stock_in.status_code == 201, stock_in.text

    stock_out = stock_movement(
        headers, resource["id"], "STOCK_OUT", 7
    )
    assert stock_out.status_code == 201, stock_out.text

    response = client.get(
        f"/api/v1/resources/{resource['id']}",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["quantity_available"] == 13


def test_stock_out_cannot_make_inventory_negative():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)

    stock_in = stock_movement(
        headers, resource["id"], "STOCK_IN", 3
    )
    assert stock_in.status_code == 201, stock_in.text

    stock_out = stock_movement(
        headers, resource["id"], "STOCK_OUT", 10
    )

    assert stock_out.status_code in (400, 409, 422)

    response = client.get(
        f"/api/v1/resources/{resource['id']}",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["quantity_available"] == 3


def test_low_stock_endpoint_returns_low_stock_resources():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(
        headers,
        name="Low Stock Food",
        low_stock_threshold=5,
    )

    response = client.get(
        "/api/v1/resources/low-stock",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()]
    assert resource["id"] in ids


def test_stock_transaction_history_is_recorded():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)

    movement = stock_movement(
        headers, resource["id"], "STOCK_IN", 12
    )
    assert movement.status_code == 201, movement.text

    response = client.get(
        f"/api/v1/resources/{resource['id']}/transactions",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] >= 1
    assert any(
        item["transaction_type"] == "STOCK_IN"
        for item in response.json()["items"]
    )


def test_allocate_resource_to_project():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)
    project = create_project(headers)

    movement = stock_movement(
        headers, resource["id"], "STOCK_IN", 30
    )
    assert movement.status_code == 201, movement.text

    response = client.post(
        "/api/v1/resources/allocations",
        headers=headers,
        json={
            "resource_id": resource["id"],
            "project_id": project["id"],
            "allocated_quantity": 10,
            "notes": "Allocation test",
        },
    )

    assert response.status_code == 201, response.text
    allocation = response.json()
    assert allocation["resource_id"] == resource["id"]
    assert allocation["project_id"] == project["id"]
    assert allocation["allocated_quantity"] == 10
    assert allocation["distributed_quantity"] == 0

    resource_response = client.get(
        f"/api/v1/resources/{resource['id']}",
        headers=headers,
    )
    assert resource_response.json()["quantity_available"] == 20


def test_allocation_cannot_exceed_available_stock():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)
    project = create_project(headers)

    stock_in = stock_movement(
        headers, resource["id"], "STOCK_IN", 4
    )
    assert stock_in.status_code == 201, stock_in.text

    response = client.post(
        "/api/v1/resources/allocations",
        headers=headers,
        json={
            "resource_id": resource["id"],
            "project_id": project["id"],
            "allocated_quantity": 10,
            "notes": "Insufficient stock test",
        },
    )

    assert response.status_code in (400, 409, 422)


def test_distribute_allocated_resource():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)
    project = create_project(headers)

    stock_in = stock_movement(
        headers, resource["id"], "STOCK_IN", 20
    )
    assert stock_in.status_code == 201, stock_in.text

    allocation_response = client.post(
        "/api/v1/resources/allocations",
        headers=headers,
        json={
            "resource_id": resource["id"],
            "project_id": project["id"],
            "allocated_quantity": 10,
            "notes": "Distribution test",
        },
    )
    assert allocation_response.status_code == 201, allocation_response.text
    allocation_id = allocation_response.json()["id"]

    distribution_response = client.post(
        f"/api/v1/resources/allocations/{allocation_id}/distributions",
        headers=headers,
        json={
            "quantity": 4,
            "notes": "Distributed four packages",
        },
    )

    assert distribution_response.status_code == 200, distribution_response.text
    allocation = distribution_response.json()
    assert allocation["distributed_quantity"] == 4
    assert allocation["status"] == "PARTIALLY_DISTRIBUTED"


def test_distribution_cannot_exceed_remaining_allocation():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)
    project = create_project(headers)

    stock_in = stock_movement(
        headers, resource["id"], "STOCK_IN", 20
    )
    assert stock_in.status_code == 201, stock_in.text

    allocation_response = client.post(
        "/api/v1/resources/allocations",
        headers=headers,
        json={
            "resource_id": resource["id"],
            "project_id": project["id"],
            "allocated_quantity": 5,
            "notes": "Distribution limit test",
        },
    )
    assert allocation_response.status_code == 201, allocation_response.text
    allocation_id = allocation_response.json()["id"]

    response = client.post(
        f"/api/v1/resources/allocations/{allocation_id}/distributions",
        headers=headers,
        json={
            "quantity": 6,
            "notes": "Excess distribution attempt",
        },
    )

    assert response.status_code in (400, 409, 422)


def test_customer_cannot_create_resource():
    headers = create_user("DONOR")

    response = client.post(
        "/api/v1/resources",
        headers=headers,
        json={
            "name": "Unauthorized Resource",
            "category": "FOOD",
            "unit": "package",
            "low_stock_threshold": 5,
        },
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_list_resources():
    response = client.get("/api/v1/resources")

    assert response.status_code in (401, 403)


def test_invalid_resource_category_is_rejected():
    headers = create_user("NGO_MANAGER")

    response = client.post(
        "/api/v1/resources",
        headers=headers,
        json={
            "name": "Invalid Category Resource",
            "category": "INVALID_CATEGORY",
            "unit": "unit",
            "low_stock_threshold": 5,
        },
    )

    assert response.status_code == 422


def test_zero_stock_movement_is_rejected():
    headers = create_user("NGO_MANAGER")
    resource = create_resource(headers)

    response = stock_movement(
        headers, resource["id"], "STOCK_IN", 0
    )

    assert response.status_code == 422
