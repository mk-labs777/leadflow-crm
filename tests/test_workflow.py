from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from crm.models import Customer, Inquiry, Activity, Task, Appointment, Quote, QuoteItem
from .conftest import quote_data

pytestmark = pytest.mark.django_db


def test_fr02_customer_create_edit_search_archive(client, users):
    client.force_login(users["alice"])
    response = client.post(reverse("customer_create"), {"name": "架空テスト", "email": "NEW@example.test", "phone": "デモ", "notes": "メモ"})
    assert response.status_code == 302
    customer = Customer.objects.get()
    assert customer.normalized_email == "new@example.test"
    assert customer.created_by == users["alice"]
    assert "架空テスト" in client.get(reverse("customer_list"), {"q": "new@EXAMPLE.test"}).content.decode()
    response = client.post(reverse("customer_edit", args=[customer.pk]), {"name": "架空の編集", "email": "changed@example.test"})
    assert response.status_code == 302
    customer.refresh_from_db()
    assert customer.name == "架空の編集" and customer.normalized_email == "changed@example.test"
    assert client.post(reverse("customer_archive", args=[customer.pk])).status_code == 403
    client.force_login(users["manager"])
    assert client.post(reverse("customer_archive", args=[customer.pk])).status_code == 302
    customer.refresh_from_db()
    assert not customer.is_active
    assert "架空の編集" not in client.get(reverse("customer_list")).content.decode()
    assert client.get(reverse("customer_detail", args=[customer.pk])).status_code == 200


def test_fr04_fr05_status_correction_notes_and_history(client, users, records):
    client.force_login(users["alice"])
    inquiry = records[1]
    url = reverse("inquiry_action", args=[inquiry.pk, "status"])
    for status in ["won", "contacted"]:
        assert client.post(url, {"status": status}).status_code == 302
    assert client.post(url, {"status": "bad"}).status_code == 400
    assert inquiry.activities.filter(event_type="status").count() == 2
    text = '<script>alert("xss")</script>'
    assert client.post(reverse("inquiry_action", args=[inquiry.pk, "note"]), {"kind": "call", "note": text}).status_code == 302
    response = client.get(reverse("inquiry_detail", args=[inquiry.pk]))
    assert text not in response.content.decode()
    assert "&lt;script&gt;" in response.content.decode()
    inquiry.refresh_from_db()
    assert inquiry.status == "contacted"
    activity = inquiry.activities.first()
    with pytest.raises(ValidationError):
        activity.save()
    with pytest.raises(ValidationError):
        activity.delete()


def test_fr06_appointment_create_edit_cancel_and_validation(client, users, records):
    client.force_login(users["alice"])
    inquiry = records[1]
    day = str(timezone.localdate() + timedelta(days=7))
    data = {"assigned_to": users["alice"].pk, "starts_at": f"{day}T10:00", "ends_at": f"{day}T11:00", "location": "架空市", "status": "scheduled"}
    assert client.post(reverse("appointment_create", args=[inquiry.pk]), data).status_code == 302
    appointment = Appointment.objects.get()
    assert timezone.localtime(appointment.starts_at).hour == 10
    assert "架空の台所工事" in client.get(reverse("schedule")).content.decode()
    edit_url = reverse("appointment_edit", args=[inquiry.pk, appointment.pk])
    assert client.post(edit_url, {**data, "ends_at": f"{day}T09:00"}).status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == "scheduled"
    assert client.post(edit_url, {**data, "status": "cancelled"}).status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == "cancelled"
    assert "架空の台所工事" not in client.get(reverse("schedule")).content.decode()
    assert inquiry.activities.filter(event_type="appointment").count() == 2


def test_fr08_task_edit_complete_reopen_and_history(client, users, records):
    client.force_login(users["alice"])
    inquiry = records[1]
    data = {"title": "架空フォロー", "assigned_to": users["alice"].pk, "due_date": str(timezone.localdate() - timedelta(days=1)), "note": "連絡する"}
    assert client.post(reverse("task_create", args=[inquiry.pk]), data).status_code == 302
    task = Task.objects.get()
    assert task.is_overdue
    assert client.post(reverse("task_edit", args=[inquiry.pk, task.pk]), {**data, "title": "架空フォロー更新"}).status_code == 302
    for completed in [True, False]:
        assert client.post(reverse("task_toggle", args=[task.pk])).status_code == 302
        task.refresh_from_db()
        assert bool(task.completed_at) == completed
        assert task.is_overdue != completed
    assert list(inquiry.activities.values_list("event_type", flat=True)) == ["task_reopened", "task_completed", "task_updated", "task_created"]


@pytest.mark.parametrize("target", ["task_create", "appointment_create"])
def test_fr06_fr08_reject_assignee_without_inquiry_access(client, users, records, target):
    client.force_login(users["manager"])
    response = client.post(reverse(target, args=[records[1].pk]), {"title": "不正", "assigned_to": users["bob"].pk, "due_date": "2026-12-20", "starts_at": "2026-12-20T10:00", "status": "scheduled"})
    assert response.status_code == 200
    assert Task.objects.count() == Appointment.objects.count() == 0


def test_fr07_decimal_totals_print_and_sent_status_rule(client, users, records):
    client.force_login(users["alice"])
    inquiry = records[1]
    assert client.post(reverse("quote_create", args=[inquiry.pk]), quote_data(status="sent", total="1")).status_code == 302
    quote = Quote.objects.get()
    assert quote.subtotal == Decimal("792.25")
    assert quote.tax_amount == Decimal("79")
    assert quote.total == Decimal("871.25")
    assert list(quote.items.values_list("line_amount", flat=True)) == [Decimal("126.25"), Decimal("666.00")]
    inquiry.refresh_from_db()
    assert inquiry.status == "quotation_sent"
    assert set(inquiry.activities.values_list("event_type", flat=True)) == {"quote_created", "quote_sent", "status"}
    response = client.get(reverse("quote_print", args=[quote.pk]))
    html = response.content.decode()
    assert "SAMPLE / DEMO" in html and "871.25" in html
    assert "<form" not in html and "見積を編集" not in html
    assert client.get(reverse("quote_detail", args=[quote.pk])).status_code == 200


def test_fr07_edit_delete_items_recomputes_totals(client, users, records):
    client.force_login(users["alice"])
    inquiry = records[1]
    client.post(reverse("quote_create", args=[inquiry.pk]), quote_data())
    quote = Quote.objects.get()
    items = list(quote.items.all())
    data = quote_data(**{"items-INITIAL_FORMS": "2", "items-0-id": items[0].pk, "items-1-id": items[1].pk,
                         "items-0-quantity": "1", "items-0-unit_price": "105", "items-1-DELETE": "on"})
    assert client.post(reverse("quote_edit", args=[inquiry.pk, quote.pk]), data).status_code == 302
    quote.refresh_from_db()
    assert quote.subtotal == Decimal("105.00")
    assert quote.tax_amount == Decimal("11")  # 10.5 -> 11, ROUND_HALF_UP
    assert quote.total == Decimal("116.00")
    assert quote.items.count() == 1


@pytest.mark.parametrize("changes", [
    {"items-0-quantity": "0"}, {"items-0-quantity": "-1"}, {"items-0-unit_price": "-1"},
    {"tax_rate": "-0.1"}, {"tax_rate": "1.1"}, {"valid_until": "2026-11-01"},
    {"items-TOTAL_FORMS": "0"}, {"items-0-unit_price": "NaN"}, {"items-0-quantity": "Infinity"},
])
def test_fr07_invalid_values_do_not_persist(client, users, records, changes):
    client.force_login(users["alice"])
    response = client.post(reverse("quote_create", args=[records[1].pk]), quote_data(**changes))
    assert response.status_code == 200
    assert Quote.objects.count() == QuoteItem.objects.count() == 0


def test_fr07_item_ids_cannot_be_stolen_between_quotes(client, users, records):
    client.force_login(users["manager"])
    client.post(reverse("quote_create", args=[records[1].pk]), quote_data())
    own = Quote.objects.get()
    client.post(reverse("quote_create", args=[records[3].pk]), quote_data())
    foreign = Quote.objects.exclude(pk=own.pk).get()
    original = list(foreign.items.values_list("pk", "line_amount"))
    data = quote_data(**{"items-INITIAL_FORMS": "1", "items-0-id": foreign.items.first().pk, "items-0-unit_price": "1"})
    client.force_login(users["alice"])
    response = client.post(reverse("quote_edit", args=[records[1].pk, own.pk]), data)
    assert response.status_code in [200, 302]
    assert list(foreign.items.values_list("pk", "line_amount")) == original


def test_fr10_seed_idempotent_and_no_passwords():
    for _ in range(2):
        call_command("seed_demo", stdout=StringIO())
    from django.contrib.auth.models import User
    assert Customer.objects.count() == Inquiry.objects.count() == 60
    assert User.objects.filter(groups__name="Employee").count() == 5
    assert User.objects.filter(groups__name="Manager").count() == 1
    assert Task.objects.count() == Appointment.objects.count() == 54
    assert Quote.objects.count() == 18
    assert QuoteItem.objects.count() == 36
    assert all(not user.has_usable_password() for user in User.objects.all())
    assert all(email.endswith("@example.test") for email in Customer.objects.values_list("email", flat=True))


@pytest.mark.parametrize("name", ["task_create", "appointment_create"])
def test_fr06_fr08_new_forms_default_to_current_inquiry_owner(client, users, records, name):
    client.force_login(users["alice"])
    response = client.get(reverse(name, args=[records[1].pk]))
    assert response.context["form"]["assigned_to"].value() == users["alice"].pk
    assert f'value="{users["alice"].pk}" selected' in response.content.decode()


def test_fr02_archived_customer_history_remains_editable(client, users, records):
    customer, inquiry, _, _ = records
    customer.is_active = False
    customer.save()
    client.force_login(users["alice"])
    response = client.post(reverse("inquiry_edit", args=[inquiry.pk]), {"customer": customer.pk, "subject": "架空の継続対応", "service_category": "kitchen", "source": "phone", "description": "履歴を保持"})
    assert response.status_code == 302
    inquiry.refresh_from_db()
    assert inquiry.customer == customer and inquiry.subject == "架空の継続対応"
