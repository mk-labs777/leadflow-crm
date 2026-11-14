import hashlib
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, RequestDataTooBig
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .access import (staff_required, is_manager, customers_for, inquiries_for,
                     quotes_for, tasks_for, appointments_for, employees)
from .forms import (CustomerForm, IntakeForm, InquiryForm, StatusForm, AssignmentForm,
                    NoteForm, TaskForm, AppointmentForm, QuoteForm, QuoteItemFormSet, DateFilterForm)
from .models import Inquiry, Customer, Activity, Quote, Task, Appointment
from .services import intake, log, change_assignment, change_status, save_quote, toggle_task


def page(request, queryset):
    return Paginator(queryset, 20).get_page(request.GET.get("page"))


def home(request):
    return render(request, "crm/home.html")


@require_http_methods(["GET", "POST"])
def public_intake(request):
    if request.method == "POST":
        try:
            data = request.POST
        except RequestDataTooBig:
            return render(request, "crm/error.html", {"message": "送信データが大きすぎます。"}, status=413)
        key = "intake:" + hashlib.sha256(request.META.get("REMOTE_ADDR", "unknown").encode()).hexdigest()
        if cache.add(key, 1, timeout=settings.INTAKE_RATE_WINDOW):
            count = 1
        else:
            count = cache.incr(key)
        if count > settings.INTAKE_RATE_LIMIT:
            response = render(request, "crm/error.html", {"message": "送信回数が多すぎます。10分後にお試しください。"}, status=429)
            response["Retry-After"] = str(settings.INTAKE_RATE_WINDOW)
            return response
        form = IntakeForm(data)
        if form.is_valid():
            intake(form.cleaned_data)
            return redirect("thank_you")
    else:
        form = IntakeForm()
    return render(request, "crm/form.html", {"form": form, "title": "リフォームのご相談", "public": True})


def thank_you(request):
    return render(request, "crm/thank_you.html")


@staff_required
def dashboard(request):
    form = DateFilterForm(request.GET)
    inquiries = inquiries_for(request.user)
    if form.is_valid():
        if form.cleaned_data["start"]:
            inquiries = inquiries.filter(created_at__date__gte=form.cleaned_data["start"])
        if form.cleaned_data["end"]:
            inquiries = inquiries.filter(created_at__date__lte=form.cleaned_data["end"])
    else:
        inquiries = inquiries.none()
    counts = inquiries.aggregate(
        new=Count("pk", filter=Q(status=Inquiry.Status.NEW)),
        unassigned=Count("pk", filter=Q(owner=None)),
        active=Count("pk", filter=~Q(status__in=[Inquiry.Status.WON, Inquiry.Status.LOST])),
        won=Count("pk", filter=Q(status=Inquiry.Status.WON)),
        lost=Count("pk", filter=Q(status=Inquiry.Status.LOST)),
    )
    closed = counts["won"] + counts["lost"]
    rate = (Decimal(counts["won"]) / closed * 100).quantize(Decimal("0.1")) if closed else None
    tasks = tasks_for(request.user).filter(inquiry__in=inquiries, completed_at__isnull=True, due_date__lt=timezone.localdate())
    metrics = [
        ("有効顧客", customers_for(request.user).filter(is_active=True).count()),
        ("新規受付", counts["new"]), ("対応中", counts["active"]), ("期限超過タスク", tasks.count()),
        ("提出済見積", quotes_for(request.user).filter(inquiry__in=inquiries, status=Quote.Status.SENT).count()),
        ("成約", counts["won"]), ("成約率", f"{rate}%" if rate is not None else "N/A"),
    ]
    if is_manager(request.user):
        metrics.insert(2, ("未割当", counts["unassigned"]))
    trend = list(inquiries.order_by().annotate(month=TruncMonth("created_at")).values("month").annotate(count=Count("pk")).order_by("month"))
    chart = {"labels": [row["month"].strftime("%Y年%m月") for row in trend], "counts": [row["count"] for row in trend]}
    return render(request, "crm/dashboard.html", {"form": form, "metrics": metrics, "counts": counts, "rate": rate,
                  "chart": chart, "trend": trend, "overdue_tasks": tasks[:5], "queue": inquiries.filter(owner=None)[:5] if is_manager(request.user) else []})


@staff_required
def customer_list(request):
    qs = customers_for(request.user).filter(is_active=True)
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query))
    return render(request, "crm/customers.html", {"page_obj": page(request, qs), "query": query})


@staff_required
def customer_detail(request, pk):
    customer = get_object_or_404(customers_for(request.user), pk=pk)
    inquiries = inquiries_for(request.user).filter(customer=customer)
    return render(request, "crm/customer_detail.html", {"customer": customer, "inquiries": inquiries,
                  "activities": Activity.objects.filter(inquiry__in=inquiries).select_related("actor", "inquiry")[:50]})


@staff_required
@require_http_methods(["GET", "POST"])
def customer_edit(request, pk=None):
    customer = get_object_or_404(customers_for(request.user), pk=pk) if pk else Customer(created_by=request.user)
    form = CustomerForm(request.POST if request.method == "POST" else None, instance=customer)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        messages.success(request, "顧客を保存しました。")
        return redirect("customer_detail", pk=customer.pk)
    return render(request, "crm/form.html", {"form": form, "title": "顧客の編集" if pk else "顧客の登録"})


@staff_required
@require_POST
def customer_archive(request, pk):
    if not is_manager(request.user):
        raise PermissionDenied
    customer = get_object_or_404(customers_for(request.user), pk=pk)
    customer.is_active = False
    customer.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "顧客をアーカイブしました。履歴は保持されます。")
    return redirect("customer_list")


@staff_required
def inquiry_list(request):
    qs = inquiries_for(request.user)
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(Q(subject__icontains=query) | Q(customer__name__icontains=query) | Q(customer__email__icontains=query))
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])
    if request.GET.get("owner") == "unassigned":
        qs = qs.filter(owner=None)
    elif request.GET.get("owner", "").isdigit():
        qs = qs.filter(owner_id=request.GET["owner"])
    if request.GET.get("customer", "").isdigit():
        qs = qs.filter(customer_id=request.GET["customer"])
    return render(request, "crm/inquiries.html", {"page_obj": page(request, qs), "query": query,
                  "statuses": Inquiry.Status.choices, "employees": employees() if is_manager(request.user) else [],
                  "customers": customers_for(request.user)})


@staff_required
@require_http_methods(["GET", "POST"])
def inquiry_edit(request, pk=None):
    inquiry = get_object_or_404(inquiries_for(request.user), pk=pk) if pk else Inquiry()
    form = InquiryForm(request.POST if request.method == "POST" else None, instance=inquiry, user=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            inquiry = form.save(commit=False)
            if pk is None and not is_manager(request.user):
                inquiry.owner = request.user
            inquiry.save()
            log(inquiry, request.user, "inquiry_updated" if pk else "intake", "案件を編集しました。" if pk else "社内で案件を登録しました。")
        return redirect("inquiry_detail", pk=inquiry.pk)
    return render(request, "crm/form.html", {"form": form, "title": "案件の編集" if pk else "案件の登録"})


@staff_required
def inquiry_detail(request, pk):
    inquiry = get_object_or_404(inquiries_for(request.user), pk=pk)
    return render(request, "crm/inquiry_detail.html", {
        "inquiry": inquiry, "status_form": StatusForm(instance=inquiry),
        "assignment_form": AssignmentForm(initial={"owner": inquiry.owner_id, "needs_review": inquiry.needs_review}) if is_manager(request.user) else None,
        "note_form": NoteForm(), "activities": inquiry.activities.select_related("actor"),
        "tasks": tasks_for(request.user).filter(inquiry=inquiry),
        "appointments": appointments_for(request.user).filter(inquiry=inquiry), "quotes": inquiry.quotes.all(),
    })


@staff_required
@require_POST
def inquiry_action(request, pk, action):
    inquiry = get_object_or_404(inquiries_for(request.user), pk=pk)
    if action == "assign":
        if not is_manager(request.user):
            raise PermissionDenied
        form = AssignmentForm(request.POST)
        if form.is_valid():
            change_assignment(inquiry, request.user, **form.cleaned_data)
    elif action == "status":
        form = StatusForm(request.POST, instance=inquiry)
        if form.is_valid():
            change_status(inquiry, request.user, form.cleaned_data["status"])
    elif action == "note":
        form = NoteForm(request.POST)
        if form.is_valid():
            log(inquiry, request.user, form.cleaned_data["kind"], form.cleaned_data["note"])
    else:
        raise PermissionDenied
    if form.errors:
        return render(request, "crm/form.html", {"form": form, "title": "入力内容の確認"}, status=400)
    messages.success(request, "対応履歴を更新しました。")
    return redirect("inquiry_detail", pk=pk)


@staff_required
def schedule(request):
    return render(request, "crm/schedule.html", {
        "tasks": tasks_for(request.user),
        "appointments": appointments_for(request.user).filter(status=Appointment.Status.SCHEDULED, starts_at__gte=timezone.now()),
    })


@staff_required
@require_http_methods(["GET", "POST"])
def task_edit(request, inquiry_pk, pk=None):
    inquiry = get_object_or_404(inquiries_for(request.user), pk=inquiry_pk)
    task = get_object_or_404(tasks_for(request.user), pk=pk, inquiry=inquiry) if pk else Task(inquiry=inquiry)
    form = TaskForm(request.POST if request.method == "POST" else None, instance=task, inquiry=inquiry)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            log(inquiry, request.user, "task_updated" if pk else "task_created", f"タスク{'更新' if pk else '作成'}：{task.title}")
        return redirect("inquiry_detail", pk=inquiry.pk)
    return render(request, "crm/form.html", {"form": form, "title": "フォローアップタスク", "hint": "先に案件の担当者を割り当ててください。タスク担当者は案件の担当者です。"})


@staff_required
@require_POST
def task_toggle(request, pk):
    task = get_object_or_404(tasks_for(request.user), pk=pk)
    toggle_task(task, request.user)
    return redirect("inquiry_detail", pk=task.inquiry_id)


@staff_required
@require_http_methods(["GET", "POST"])
def appointment_edit(request, inquiry_pk, pk=None):
    inquiry = get_object_or_404(inquiries_for(request.user), pk=inquiry_pk)
    appointment = get_object_or_404(appointments_for(request.user), pk=pk, inquiry=inquiry) if pk else Appointment(inquiry=inquiry)
    form = AppointmentForm(request.POST if request.method == "POST" else None, instance=appointment, inquiry=inquiry)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            log(inquiry, request.user, "appointment", f"現地調査を{'更新' if pk else '登録'}：{appointment.get_status_display()} / {timezone.localtime(appointment.starts_at):%Y-%m-%d %H:%M}")
        return redirect("inquiry_detail", pk=inquiry.pk)
    return render(request, "crm/form.html", {"form": form, "title": "現地調査の予定", "hint": "日時は日本時間です。担当者は案件の担当者です。"})


@staff_required
def quote_list(request):
    return render(request, "crm/quotes.html", {"page_obj": page(request, quotes_for(request.user))})


@staff_required
@require_http_methods(["GET", "POST"])
def quote_edit(request, inquiry_pk, pk=None):
    inquiry = get_object_or_404(inquiries_for(request.user), pk=inquiry_pk)
    quote = get_object_or_404(quotes_for(request.user), pk=pk, inquiry=inquiry) if pk else Quote(inquiry=inquiry)
    data = request.POST if request.method == "POST" else None
    form = QuoteForm(data, instance=quote)
    formset = QuoteItemFormSet(data, instance=quote)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        quote = save_quote(form, formset, inquiry, request.user)
        return redirect("quote_detail", pk=quote.pk)
    return render(request, "crm/quote_form.html", {"form": form, "formset": formset, "inquiry": inquiry, "quote": quote})


@staff_required
def quote_detail(request, pk):
    quote = get_object_or_404(quotes_for(request.user).prefetch_related("items"), pk=pk)
    return render(request, "crm/quote_detail.html", {"quote": quote, "tax_percent": quote.tax_rate * 100})


@staff_required
def quote_print(request, pk):
    quote = get_object_or_404(quotes_for(request.user).prefetch_related("items"), pk=pk)
    return render(request, "crm/quote_print.html", {"quote": quote, "tax_percent": quote.tax_rate * 100})
