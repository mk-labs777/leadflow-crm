from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, MaxLengthValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Customer(models.Model):
    name = models.CharField("氏名・会社名", max_length=120)
    email = models.EmailField("メールアドレス")
    normalized_email = models.CharField("正規化メール", max_length=254, db_index=True, editable=False)
    phone = models.CharField("電話番号", max_length=30, blank=True)
    address = models.CharField("住所", max_length=255, blank=True)
    notes = models.TextField("顧客メモ", blank=True, validators=[MaxLengthValidator(5000)])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="登録者", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_customers")
    is_active = models.BooleanField("有効", default=True)
    created_at = models.DateTimeField("登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "顧客"
        verbose_name_plural = "顧客"

    def save(self, *args, **kwargs):
        self.normalized_email = self.email.strip().casefold()
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"normalized_email"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Inquiry(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "新規受付"
        CONTACTED = "contacted", "初回対応済"
        INSPECTION = "inspection_scheduled", "現地調査予定"
        QUOTATION = "quotation_sent", "見積提出済"
        WON = "won", "成約"
        LOST = "lost", "失注"

    class Category(models.TextChoices):
        KITCHEN = "kitchen", "キッチン"
        BATHROOM = "bathroom", "浴室"
        EXTERIOR = "exterior", "外壁・屋根"
        INTERIORS = "interiors", "内装"
        OTHER = "other", "その他"

    class Source(models.TextChoices):
        WEB = "web", "Webフォーム"
        PHONE = "phone", "電話"
        INTERNAL = "internal", "社内登録"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="inquiries", verbose_name="顧客")
    subject = models.CharField("件名", max_length=200)
    description = models.TextField("お問い合わせ内容", validators=[MaxLengthValidator(10000)])
    service_category = models.CharField("工事種別", max_length=20, choices=Category.choices)
    source = models.CharField("受付経路", max_length=20, choices=Source.choices, default=Source.INTERNAL)
    status = models.CharField("対応状況", max_length=30, choices=Status.choices, default=Status.NEW, db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="inquiries", verbose_name="担当者")
    needs_review = models.BooleanField("重複候補・要確認", default=False)
    created_at = models.DateTimeField("受付日時", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "案件"
        verbose_name_plural = "案件"

    def __str__(self):
        return self.subject


class Activity(models.Model):
    inquiry = models.ForeignKey(Inquiry, verbose_name="案件", on_delete=models.PROTECT, related_name="activities")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="操作担当", null=True, on_delete=models.SET_NULL)
    event_type = models.CharField("履歴種別", max_length=40, choices=[
        ("intake", "受付"), ("assignment", "担当者変更"), ("review", "重複候補確認"), ("status", "状況変更"),
        ("note", "メモ"), ("call", "電話"), ("visit", "訪問"), ("email", "メール記録"),
        ("inquiry_updated", "案件更新"), ("appointment", "現地調査"),
        ("task_created", "タスク作成"), ("task_updated", "タスク更新"), ("task_completed", "タスク完了"),
        ("task_reopened", "タスク再開"), ("quote_created", "見積作成"), ("quote_updated", "見積更新"), ("quote_sent", "見積提出"),
    ])
    note = models.TextField("内容", validators=[MaxLengthValidator(10000)])
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "対応履歴"
        verbose_name_plural = "対応履歴"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("対応履歴は変更できません。訂正は新しいメモに記録してください。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("対応履歴は削除できません。")


class Appointment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "予定"
        COMPLETED = "completed", "実施済"
        CANCELLED = "cancelled", "キャンセル"

    inquiry = models.ForeignKey(Inquiry, verbose_name="案件", on_delete=models.PROTECT, related_name="appointments")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="担当者")
    starts_at = models.DateTimeField("開始日時")
    ends_at = models.DateTimeField("終了日時", null=True, blank=True)
    location = models.CharField("場所", max_length=255, blank=True)
    notes = models.TextField("メモ", blank=True, validators=[MaxLengthValidator(5000)])
    status = models.CharField("予定の状況", max_length=20, choices=Status.choices, default=Status.SCHEDULED)

    class Meta:
        verbose_name = "現地調査"
        verbose_name_plural = "現地調査"
        ordering = ["starts_at"]
        constraints = [models.CheckConstraint(condition=Q(ends_at__isnull=True) | Q(ends_at__gte=models.F("starts_at")), name="appointment_end_after_start")]

    def clean(self):
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise ValidationError({"ends_at": "終了日時は開始日時以降にしてください。"})


class Task(models.Model):
    inquiry = models.ForeignKey(Inquiry, verbose_name="案件", on_delete=models.PROTECT, related_name="tasks")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="担当者")
    title = models.CharField("タスク名", max_length=200)
    note = models.TextField("メモ", blank=True, validators=[MaxLengthValidator(5000)])
    due_date = models.DateField("期限", db_index=True)
    completed_at = models.DateTimeField("完了日時", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "フォローアップタスク"
        verbose_name_plural = "フォローアップタスク"
        ordering = ["due_date", "pk"]

    @property
    def is_overdue(self):
        return self.completed_at is None and self.due_date < timezone.localdate()


class Quote(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "下書き"
        SENT = "sent", "提出済"
        ACCEPTED = "accepted", "承認"
        REJECTED = "rejected", "否認"

    inquiry = models.ForeignKey(Inquiry, verbose_name="案件", on_delete=models.PROTECT, related_name="quotes")
    quote_number = models.CharField("見積番号", max_length=40, unique=True, editable=False)
    title = models.CharField("見積件名", max_length=200)
    issued_on = models.DateField("発行日", default=timezone.localdate)
    valid_until = models.DateField("有効期限", null=True, blank=True)
    status = models.CharField("見積状況", max_length=20, choices=Status.choices, default=Status.DRAFT)
    tax_rate = models.DecimalField("消費税率（0.10 = 10%）", max_digits=4, decimal_places=3, default=Decimal("0.10"), validators=[MinValueValidator(0), MaxValueValidator(1)])
    subtotal = models.DecimalField("小計（円）", max_digits=24, decimal_places=2, default=0, editable=False)
    tax_amount = models.DecimalField("消費税額（円）", max_digits=24, decimal_places=0, default=0, editable=False)
    total = models.DecimalField("合計（円）", max_digits=24, decimal_places=2, default=0, editable=False)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "見積書"
        verbose_name_plural = "見積書"
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(tax_rate__gte=0) & Q(tax_rate__lte=1), name="quote_tax_range")]

    def clean(self):
        if self.valid_until and self.issued_on and self.valid_until < self.issued_on:
            raise ValidationError({"valid_until": "有効期限は発行日以降にしてください。"})


class QuoteItem(models.Model):
    quote = models.ForeignKey(Quote, verbose_name="見積書", on_delete=models.CASCADE, related_name="items")
    description = models.CharField("品目・工事内容", max_length=200)
    quantity = models.DecimalField("数量", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField("単価（円）", max_digits=12, decimal_places=0, validators=[MinValueValidator(0)])
    position = models.PositiveIntegerField("表示順", default=0)
    line_amount = models.DecimalField("明細金額（円）", max_digits=22, decimal_places=2, editable=False)

    class Meta:
        verbose_name = "見積明細"
        verbose_name_plural = "見積明細"
        ordering = ["position", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="item_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="item_price_nonnegative"),
        ]
