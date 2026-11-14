import pytest
from django.urls import reverse
from django.utils import timezone
from crm.models import Task, Appointment, Quote, Inquiry, Activity

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("name", ["dashboard", "customer_list", "inquiry_list", "quote_list", "schedule"])
def test_fr01_anonymous_redirect(client, name):
    response = client.get(reverse(name))
    assert response.status_code == 302 and "/accounts/login/" in response.url


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("target", ["customer_detail", "customer_edit", "customer_archive", "inquiry_detail", "inquiry_edit", "assign", "status", "note", "quote_create", "task_create", "appointment_create"])
def test_fr01_cross_employee_denied(client, users, records, method, target):
    client.force_login(users["bob"])
    if target in ["assign", "status", "note"]:
        url = reverse("inquiry_action", args=[records[1].pk, target])
    elif target.startswith("customer"):
        url = reverse(target, args=[records[0].pk])
    else:
        url = reverse(target, args=[records[1].pk])
    response = getattr(client, method)(url, {"status": "won", "owner": users["bob"].pk, "title": "forged"})
    assert response.status_code in [403, 404, 405]
    records[1].refresh_from_db()
    assert records[1].status == "new" and records[1].owner == users["alice"]


def test_fr01_related_record_direct_urls_scoped(client, users, records):
    inquiry = records[1]
    task = Task.objects.create(inquiry=inquiry, assigned_to=users["alice"], title="秘密タスク", due_date=timezone.localdate())
    appointment = Appointment.objects.create(inquiry=inquiry, assigned_to=users["alice"], starts_at=timezone.now())
    quote = Quote.objects.create(inquiry=inquiry, quote_number="LF-PRIVATE", title="秘密見積")
    urls = [reverse("task_edit", args=[inquiry.pk, task.pk]), reverse("task_toggle", args=[task.pk]),
            reverse("appointment_edit", args=[inquiry.pk, appointment.pk]), reverse("quote_edit", args=[inquiry.pk, quote.pk]),
            reverse("quote_detail", args=[quote.pk]), reverse("quote_print", args=[quote.pk])]
    client.force_login(users["bob"])
    for url in urls:
        assert client.get(url).status_code in [404, 405]
        assert client.post(url, {}).status_code == 404
    assert Activity.objects.count() == 0


def test_fr01_lists_do_not_leak(client, users, records):
    client.force_login(users["alice"])
    for name in ["dashboard", "customer_list", "inquiry_list", "quote_list", "schedule"]:
        response = client.get(reverse(name))
        assert response.status_code == 200
        assert "非公開" not in response.content.decode()


def test_fr01_staff_flag_is_not_manager(client, users, records):
    employee = users["alice"]
    employee.is_staff = True
    employee.save()
    client.force_login(employee)
    assert client.get("/admin/").status_code == 302
    response = client.post(reverse("inquiry_action", args=[records[1].pk, "assign"]), {"owner": users["bob"].pk})
    assert response.status_code == 403
    client.force_login(users["outsider"])
    assert client.get(reverse("dashboard")).status_code == 403


def test_fr01_manager_admin_and_assignment(client, users, records):
    manager = users["manager"]
    manager.is_staff = True
    manager.save()
    client.force_login(manager)
    assert client.get("/admin/").status_code == 200
    inquiry = records[1]
    inquiry.owner = None
    inquiry.save()
    response = client.post(reverse("inquiry_action", args=[inquiry.pk, "assign"]), {"owner": users["bob"].pk})
    assert response.status_code == 302
    inquiry.refresh_from_db()
    assert inquiry.owner == users["bob"]
    assert inquiry.activities.get().event_type == "assignment"
    client.force_login(users["alice"])
    assert client.get(reverse("inquiry_detail", args=[inquiry.pk])).status_code == 404
    client.force_login(users["bob"])
    assert client.get(reverse("inquiry_detail", args=[inquiry.pk])).status_code == 200


@pytest.mark.parametrize("assignee", ["outsider", "manager"])
def test_fr04_assignment_rejects_nonemployee(client, users, records, assignee):
    client.force_login(users["manager"])
    response = client.post(reverse("inquiry_action", args=[records[1].pk, "assign"]), {"owner": users[assignee].pk})
    assert response.status_code == 400


def test_fr01_state_changes_require_post(client, users, records):
    client.force_login(users["manager"])
    assert client.get(reverse("inquiry_action", args=[records[1].pk, "status"])).status_code == 405
    assert client.get(reverse("customer_archive", args=[records[0].pk])).status_code == 405
    assert client.get(reverse("logout")).status_code == 405


def test_fr01_unassigned_denied_and_employee_cannot_forge_owner(client, users, records):
    inquiry = records[1]
    Inquiry.objects.filter(pk=inquiry.pk).update(owner=None)
    client.force_login(users["alice"])
    assert client.get(reverse("inquiry_detail", args=[inquiry.pk])).status_code == 404
    response = client.post(reverse("inquiry_create"), {"customer": records[0].pk, "subject": "電話のご相談", "description": "架空", "source": "phone", "service_category": "other", "owner": users["bob"].pk})
    assert response.status_code == 302
    assert Inquiry.objects.get(subject="電話のご相談").owner == users["alice"]


def test_fr01_manager_can_manage_accounts_without_superuser(client, users):
    manager = users["manager"]
    assert not manager.is_superuser
    manager.is_staff = True
    manager.save()
    client.force_login(manager)
    for url in ["/admin/auth/user/", "/admin/auth/user/add/", f"/admin/auth/user/{users['alice'].pk}/change/"]:
        assert client.get(url).status_code == 200
    client.force_login(users["alice"])
    assert client.get("/admin/auth/user/").status_code == 302
