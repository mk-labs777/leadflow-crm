import pytest
from django.urls import reverse
from crm.models import Inquiry, Activity, Quote
from .conftest import quote_data

pytestmark = pytest.mark.django_db


def test_fr01_login_logout_password_hash_and_open_redirect(client, users):
    alice = users["alice"]
    alice.set_password("test-only-random-phrase-29")
    alice.save()
    assert alice.password != "test-only-random-phrase-29"
    assert client.post(reverse("login"), {"username": "alice", "password": "wrong"}).status_code == 200
    response = client.post(reverse("login"), {"username": "alice", "password": "test-only-random-phrase-29", "next": "https://example.test/"})
    assert response.status_code == 302 and response.url == reverse("dashboard")
    assert client.post(reverse("logout")).status_code == 302
    assert client.get(reverse("dashboard")).status_code == 302


def test_fr01_inactive_employee_cannot_be_assigned(client, users, records):
    users["bob"].is_active = False
    users["bob"].save()
    client.force_login(users["manager"])
    assert client.post(reverse("inquiry_action", args=[records[1].pk, "assign"]), {"owner": users["bob"].pk}).status_code == 400


def test_fr02_customer_can_be_seen_if_linked_but_hidden_history_cannot(client, users, records):
    # Shared customer must not expose another owner's inquiries/activities.
    Inquiry.objects.filter(pk=records[3].pk).update(customer=records[0])
    Activity.objects.create(inquiry=records[3], actor=users["bob"], event_type="note", note="秘密の履歴")
    client.force_login(users["alice"])
    response = client.get(reverse("customer_detail", args=[records[0].pk]))
    assert response.status_code == 200
    assert "秘密の履歴" not in response.content.decode()
    assert "非公開の案件" not in response.content.decode()


def test_fr07_zero_price_valid_and_huge_legal_inputs_fit_database(client, users, records):
    client.force_login(users["alice"])
    data = quote_data(**{"items-0-quantity": "99999999.99", "items-0-unit_price": "999999999999", "items-1-unit_price": "0"})
    assert client.post(reverse("quote_create", args=[records[1].pk]), data).status_code == 302
    quote = Quote.objects.get()
    assert quote.total > 0


def test_fr07_formset_delete_all_invalid_and_status_reversal_explicit(client, users, records):
    client.force_login(users["alice"])
    inquiry = records[1]
    url = reverse("quote_create", args=[inquiry.pk])
    assert client.post(url, quote_data(**{"items-0-DELETE": "on", "items-1-DELETE": "on"})).status_code == 200
    assert Quote.objects.count() == 0
    client.post(url, quote_data(status="sent"))
    quote = Quote.objects.get()
    items = list(quote.items.all())
    data = quote_data(**{"status": "draft", "items-INITIAL_FORMS": "2", "items-0-id": items[0].pk, "items-1-id": items[1].pk})
    client.post(reverse("quote_edit", args=[inquiry.pk, quote.pk]), data)
    inquiry.refresh_from_db()
    quote.refresh_from_db()
    assert quote.status == "draft"
    assert inquiry.status == "quotation_sent"  # Documented independent fields on reversal.


def test_nfr08_no_real_email_backend(settings):
    from config import settings as project_settings
    assert project_settings.MAILERS["default"]["BACKEND"] == "django.core.mail.backends.dummy.EmailBackend"
