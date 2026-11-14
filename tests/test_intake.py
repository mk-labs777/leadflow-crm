from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from crm.models import Customer, Inquiry, Activity
from crm.services import intake

pytestmark = pytest.mark.django_db


def test_fr03_persists_matches_and_never_overwrites_identity(client, intake_data):
    for email in ["Demo@example.test", "DEMO@example.test"]:
        response = client.post(reverse("public_intake"), {**intake_data, "email": email})
        assert response.status_code == 302
        assert response.url == reverse("thank_you")
    assert Customer.objects.count() == 1
    assert Inquiry.objects.count() == Activity.objects.count() == 2
    customer = Customer.objects.get()
    client.post(reverse("public_intake"), {**intake_data, "name": "上書き禁止", "phone": "架空の電話"})
    customer.refresh_from_db()
    assert customer.name == "架空のお客様"
    assert customer.phone == ""
    assert all(i.owner is None and i.status == "new" and i.source == "web" for i in Inquiry.objects.all())


def test_fr03_ambiguous_email_flags_review(client, intake_data):
    for name in ["架空A", "架空B"]:
        Customer.objects.create(name=name, email="DEMO@example.test")
    client.post(reverse("public_intake"), intake_data)
    inquiry = Inquiry.objects.get()
    assert inquiry.needs_review
    assert Customer.objects.count() == 3
    assert inquiry.customer.name == intake_data["name"]


@pytest.mark.parametrize("changes", [{"email": "invalid"}, {"subject": ""}, {"service_category": "invalid"}, {"website": "spam"}, {"description": "x" * 10001}])
def test_fr03_invalid_no_partial_records(client, intake_data, changes):
    assert client.post(reverse("public_intake"), {**intake_data, **changes}).status_code == 200
    assert Customer.objects.count() == Inquiry.objects.count() == Activity.objects.count() == 0


def test_fr03_transaction_rolls_back_on_history_failure(intake_data):
    with patch("crm.services.log", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            intake(intake_data)
    assert Customer.objects.count() == Inquiry.objects.count() == 0


@override_settings(INTAKE_RATE_LIMIT=2)
def test_fr03_rate_limit(client, intake_data):
    for _ in range(2):
        assert client.post(reverse("public_intake"), intake_data).status_code == 302
    response = client.post(reverse("public_intake"), intake_data)
    assert response.status_code == 429
    assert response["Retry-After"] == "600"
    assert Inquiry.objects.count() == 2


def test_fr01_csrf_on_public_and_internal(users, records, intake_data):
    client = Client(enforce_csrf_checks=True)
    assert client.post(reverse("public_intake"), intake_data).status_code == 403
    client.force_login(users["alice"])
    assert client.post(reverse("inquiry_action", args=[records[1].pk, "status"]), {"status": "won"}).status_code == 403


def test_fr03_confirmation_contains_no_customer_details(client, intake_data):
    inquiry = intake(intake_data)
    response = client.get(reverse("thank_you"))
    assert response.status_code == 200
    assert inquiry.customer.email not in response.content.decode()
    assert inquiry.subject not in response.content.decode()


def test_fr03_manager_queue_and_detail_render_unassigned_system_activity(client, users, intake_data):
    client.post(reverse("public_intake"), intake_data)
    inquiry = Inquiry.objects.get()
    client.force_login(users["manager"])
    for name, args in [("dashboard", []), ("inquiry_list", []), ("inquiry_detail", [inquiry.pk]), ("customer_detail", [inquiry.customer_id])]:
        response = client.get(reverse(name, args=args))
        assert response.status_code == 200
        assert "架空" in response.content.decode()
    assert "システム" in client.get(reverse("inquiry_detail", args=[inquiry.pk])).content.decode()
    assert "未割当" in client.get(reverse("inquiry_list"), {"owner": "unassigned"}).content.decode()
    client.force_login(users["alice"])
    assert client.get(reverse("inquiry_detail", args=[inquiry.pk])).status_code == 404
