from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .access import is_manager, inquiries_for, employees
from .models import Customer, Inquiry, Activity, Quote


def log(inquiry, actor, event_type, note):
    return Activity.objects.create(inquiry=inquiry, actor=actor, event_type=event_type, note=note)


@transaction.atomic
def intake(data):
    matches = list(Customer.objects.filter(normalized_email=data["email"].strip().casefold())[:2])
    if len(matches) == 1:
        customer = matches[0]
    else:
        customer = Customer.objects.create(name=data["name"], email=data["email"], phone=data.get("phone", ""))
    inquiry = Inquiry.objects.create(
        customer=customer, subject=data["subject"], description=data["description"],
        service_category=data["service_category"], source=Inquiry.Source.WEB, needs_review=len(matches) > 1,
    )
    # Preserve what the public visitor actually submitted without overwriting customer identity.
    log(inquiry, None, "intake", f"Web受付：{data['name']} / {data['email']} / {data.get('phone', '')}")
    return inquiry


@transaction.atomic
def change_assignment(inquiry, actor, owner, needs_review):
    if not is_manager(actor):
        raise PermissionDenied
    if owner and not employees().filter(pk=owner.pk).exists():
        raise PermissionDenied
    current = Inquiry.objects.select_for_update().get(pk=inquiry.pk)
    old = str(current.owner or "未割当")
    changed = current.owner_id != (owner.pk if owner else None)
    review_changed = current.needs_review != needs_review
    current.owner = owner
    current.needs_review = needs_review
    current.save(update_fields=["owner", "needs_review", "updated_at"])
    if changed:
        log(current, actor, "assignment", f"担当者：{old} → {owner or '未割当'}")
    if review_changed:
        log(current, actor, "review", f"重複候補・要確認：{'あり' if needs_review else '確認済'}")
    return current


@transaction.atomic
def change_status(inquiry, actor, status):
    current = inquiries_for(actor).select_for_update(of=("self",)).get(pk=inquiry.pk)
    if status not in Inquiry.Status.values:
        raise ValueError("Invalid status")
    if current.status != status:
        old = current.get_status_display()
        current.status = status
        current.save(update_fields=["status", "updated_at"])
        log(current, actor, "status", f"対応状況：{old} → {current.get_status_display()}")
    return current


@transaction.atomic
def save_quote(form, formset, inquiry, actor):
    # Recheck ownership under a row lock, never accept a browser inquiry ID.
    inquiry = inquiries_for(actor).select_for_update(of=("self",)).get(pk=inquiry.pk)
    quote = form.save(commit=False)
    created = quote.pk is None
    previous = Quote.objects.select_for_update().get(pk=quote.pk).status if not created else None
    quote.inquiry = inquiry
    if created:
        quote.quote_number = f"LF-{uuid4().hex[:16].upper()}"
    quote.save()
    formset.instance = quote
    items = formset.save(commit=False)
    for item in formset.deleted_objects:
        item.delete()
    for item in items:
        item.line_amount = item.quantity * item.unit_price
        item.save()
    subtotal = sum((item.line_amount for item in quote.items.all()), Decimal("0.00"))
    quote.subtotal = subtotal
    quote.tax_amount = (subtotal * quote.tax_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    quote.total = subtotal + quote.tax_amount
    quote.save(update_fields=["subtotal", "tax_amount", "total"])
    log(inquiry, actor, "quote_created" if created else "quote_updated", f"見積{'作成' if created else '更新'}：{quote.quote_number}（{quote.get_status_display()}）")
    if quote.status == Quote.Status.SENT and previous != Quote.Status.SENT:
        log(inquiry, actor, "quote_sent", f"見積提出：{quote.quote_number}")
        change_status(inquiry, actor, Inquiry.Status.QUOTATION)
    return quote


@transaction.atomic
def toggle_task(task, actor):
    from .access import tasks_for
    task = tasks_for(actor).select_for_update().get(pk=task.pk)
    task.completed_at = None if task.completed_at else timezone.now()
    task.save(update_fields=["completed_at", "updated_at"])
    log(task.inquiry, actor, "task_reopened" if task.completed_at is None else "task_completed", f"タスク{'再開' if task.completed_at is None else '完了'}：{task.title}")
