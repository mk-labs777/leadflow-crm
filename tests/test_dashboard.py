from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from crm.models import Inquiry, Task, Quote

pytestmark = pytest.mark.django_db


def test_fr09_scoped_counts_and_conversion_updates(client, users, records):
    Inquiry.objects.filter(pk=records[1].pk).update(status="won")
    Inquiry.objects.filter(pk=records[3].pk).update(status="lost")
    Task.objects.create(inquiry=records[1], assigned_to=users["alice"], title="期限超過", due_date=timezone.localdate() - timedelta(days=1))
    Quote.objects.create(inquiry=records[1], quote_number="LF-1", title="見積", status="sent")
    client.force_login(users["manager"])
    response = client.get(reverse("dashboard"))
    assert response.context["rate"] == Decimal("50.0")
    assert dict(response.context["metrics"])["有効顧客"] == 2
    assert dict(response.context["metrics"])["期限超過タスク"] == 1
    assert dict(response.context["metrics"])["提出済見積"] == 1
    Inquiry.objects.filter(pk=records[3].pk).update(status="won")
    assert client.get(reverse("dashboard")).context["rate"] == Decimal("100.0")
    client.force_login(users["alice"])
    response = client.get(reverse("dashboard"))
    assert response.context["counts"]["won"] == 1
    assert dict(response.context["metrics"])["有効顧客"] == 1
    assert "未割当" not in dict(response.context["metrics"])


def test_fr09_empty_and_open_outcomes_are_na(client, users, records):
    client.force_login(users["alice"])
    response = client.get(reverse("dashboard"))
    assert response.context["rate"] is None
    response = client.get(reverse("dashboard"), {"start": "2000-01-01", "end": "2000-02-01"})
    assert response.context["rate"] is None
    assert response.context["trend"] == []
    assert "この期間のお問い合わせはありません" in response.content.decode()


def test_fr09_tokyo_date_boundary_and_month_grouping(client, users, records):
    # 15:00 UTC is midnight on Dec 1 in Tokyo.
    Inquiry.objects.filter(pk=records[1].pk).update(created_at=datetime(2026, 11, 30, 15, 0, tzinfo=dt_timezone.utc))
    Inquiry.objects.filter(pk=records[3].pk).update(created_at=datetime(2026, 11, 30, 14, 59, tzinfo=dt_timezone.utc))
    client.force_login(users["manager"])
    response = client.get(reverse("dashboard"), {"start": "2026-12-01", "end": "2026-12-01"})
    assert response.context["counts"]["new"] == 1
    assert response.context["chart"] == {"labels": ["2026年12月"], "counts": [1]}
    response = client.get(reverse("dashboard"), {"start": "2026-12-02", "end": "2026-12-01"})
    assert response.context["form"].errors
    assert response.context["trend"] == []


def test_fr08_overdue_tokyo_day_and_completed_exclusion(client, users, records):
    now = datetime(2026, 11, 14, 15, 1, tzinfo=dt_timezone.utc)  # Nov 15 Tokyo
    with patch("django.utils.timezone.now", return_value=now):
        task = Task.objects.create(inquiry=records[1], assigned_to=users["alice"], title="前日の期限", due_date=timezone.localdate() - timedelta(days=1))
        today_task = Task.objects.create(inquiry=records[1], assigned_to=users["alice"], title="本日の期限", due_date=timezone.localdate())
        assert task.is_overdue and not today_task.is_overdue
        client.force_login(users["alice"])
        assert dict(client.get(reverse("dashboard")).context["metrics"])["期限超過タスク"] == 1
        client.post(reverse("task_toggle", args=[task.pk]))
        assert dict(client.get(reverse("dashboard")).context["metrics"])["期限超過タスク"] == 0
