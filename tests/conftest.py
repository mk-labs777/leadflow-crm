import pytest
from django.contrib.auth.models import User, Group
from django.core.cache import cache
from crm.models import Customer, Inquiry


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def users(db):
    result = {}
    for name, role in [("manager", "Manager"), ("alice", "Employee"), ("bob", "Employee"), ("outsider", None)]:
        user = User.objects.create_user(username=name)
        if role:
            user.groups.add(Group.objects.get(name=role))
        result[name] = user
    return result


@pytest.fixture
def records(users):
    customer = Customer.objects.create(name="架空のお客様", email="customer@example.test", created_by=users["alice"])
    inquiry = Inquiry.objects.create(customer=customer, subject="架空の台所工事", description="架空のご相談", service_category="kitchen", owner=users["alice"])
    other = Customer.objects.create(name="非公開の顧客", email="private@example.test", created_by=users["bob"])
    hidden = Inquiry.objects.create(customer=other, subject="非公開の案件", description="非公開", service_category="other", owner=users["bob"])
    return customer, inquiry, other, hidden


@pytest.fixture
def intake_data():
    return {"name": "架空のお客様", "email": "demo@example.test", "phone": "", "service_category": "kitchen", "subject": "架空工事", "description": "架空のお問い合わせ"}


def quote_data(**changes):
    data = {"title": "架空の工事見積", "issued_on": "2026-11-14", "valid_until": "2026-12-14", "status": "draft", "tax_rate": "0.10",
        "items-TOTAL_FORMS": "2", "items-INITIAL_FORMS": "0", "items-MIN_NUM_FORMS": "1", "items-MAX_NUM_FORMS": "20",
        "items-0-description": "工事A", "items-0-quantity": "1.25", "items-0-unit_price": "101",
        "items-1-description": "工事B", "items-1-quantity": "2.00", "items-1-unit_price": "333"}
    data.update(changes)
    return data
