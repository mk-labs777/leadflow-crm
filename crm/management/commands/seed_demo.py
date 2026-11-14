from datetime import timedelta

from django.contrib.auth.models import User, Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm.models import Customer, Inquiry, Task, Appointment, Quote
from crm.forms import QuoteForm, QuoteItemFormSet
from crm.services import log, save_quote


class Command(BaseCommand):
    help = "架空の顧客60件・担当者5名と営業データを作成（再実行可、既存データを変更しません）"

    @transaction.atomic
    def handle(self, *args, **options):
        employee_group, _ = Group.objects.get_or_create(name="Employee")
        manager_group, _ = Group.objects.get_or_create(name="Manager")
        manager, created = User.objects.get_or_create(username="demo-manager", defaults={"first_name": "デモ管理者", "is_staff": True, "email": "manager@example.test"})
        if created:
            manager.set_unusable_password()
            manager.save()
            manager.groups.add(manager_group)
        elif not manager.groups.filter(name="Manager").exists():
            self.stderr.write("demo-manager が既存の別用途アカウントです。名前の競合を解決してください。")
            return
        owners = []
        for i in range(1, 6):
            user, created = User.objects.get_or_create(username=f"demo-employee-{i}", defaults={"first_name": f"架空担当{i}", "email": f"staff{i}@example.test"})
            if created:
                user.set_unusable_password()
                user.save()
                user.groups.add(employee_group)
            elif not user.groups.filter(name="Employee").exists():
                raise ValueError("デモ担当者名が既存アカウントと競合しています。")
            owners.append(user)
        today = timezone.localdate()
        for i in range(1, 61):
            customer, _ = Customer.objects.get_or_create(email=f"demo-customer-{i:03d}@example.test", defaults={
                "name": f"架空のお客様 {i:03d}", "address": "架空市デモ町（実在しない住所）", "notes": "自主制作デモ専用の架空データ", "created_by": manager,
            })
            status = Inquiry.Status.values[(i - 1) % 6]
            owner = owners[(i - 1) % 5] if i % 10 else None
            inquiry, created = Inquiry.objects.get_or_create(customer=customer, subject=f"架空リフォームのご相談 {i:03d}", defaults={
                "description": "架空のお住まいのリフォームについて相談するデモデータです。", "service_category": Inquiry.Category.values[i % 5],
                "source": "web" if i % 2 else "phone", "status": status, "owner": owner,
            })
            if not created:
                continue
            Inquiry.objects.filter(pk=inquiry.pk).update(created_at=timezone.now() - timedelta(days=i * 3))
            log(inquiry, None, "intake", "架空データ：お問い合わせを受け付けました。")
            if owner:
                log(inquiry, manager, "assignment", f"担当者：未割当 → {owner.username}")
                Task.objects.create(inquiry=inquiry, assigned_to=owner, title="架空のお客様へのフォロー", due_date=today + timedelta(days=i % 7 - 3))
                Appointment.objects.create(inquiry=inquiry, assigned_to=owner, starts_at=timezone.now() + timedelta(days=i % 14 + 1), location="架空市デモ町", notes="デモ現地調査")
                if i % 3 == 0:
                    form = QuoteForm({"title": "架空工事のお見積り", "issued_on": str(today), "status": "draft", "tax_rate": "0.10"})
                    formset = QuoteItemFormSet({"items-TOTAL_FORMS": "2", "items-INITIAL_FORMS": "0",
                        "items-0-description": "架空の設備工事", "items-0-quantity": "1", "items-0-unit_price": "120000",
                        "items-1-description": "架空の内装工事", "items-1-quantity": "2.50", "items-1-unit_price": "8000"}, instance=form.instance)
                    if not (form.is_valid() and formset.is_valid()):
                        raise ValueError("デモ見積の検証に失敗しました。")
                    quote = save_quote(form, formset, inquiry, manager)
                    if status in [Inquiry.Status.QUOTATION, Inquiry.Status.WON]:
                        Quote.objects.filter(pk=quote.pk).update(status="sent" if status == Inquiry.Status.QUOTATION else "accepted")
        self.stdout.write(self.style.SUCCESS("架空データを準備しました。パスワードは changepassword で個別設定してください。"))
