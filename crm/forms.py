from django import forms
from django.forms import inlineformset_factory
from django.db.models import Q

from .access import customers_for, employees
from .models import Customer, Inquiry, Task, Appointment, Quote, QuoteItem


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email", "phone", "address", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}


class IntakeForm(forms.Form):
    name = forms.CharField(label="お名前（架空）", max_length=120)
    email = forms.EmailField(label="メールアドレス（架空）", max_length=254)
    phone = forms.CharField(label="電話番号（任意・架空）", max_length=30, required=False)
    service_category = forms.ChoiceField(label="工事種別", choices=Inquiry.Category.choices)
    subject = forms.CharField(label="件名", max_length=200)
    description = forms.CharField(label="お問い合わせ内容", max_length=10000, widget=forms.Textarea(attrs={"rows": 5}))
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("送信内容を確認してください。")
        return ""


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = ["customer", "subject", "service_category", "source", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = customers_for(user).filter(Q(is_active=True) | Q(pk=self.instance.customer_id))
        self.fields["customer"].empty_label = "顧客を選択してください"


class StatusForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = ["status"]


class AssignmentForm(forms.Form):
    owner = forms.ModelChoiceField(label="担当者", queryset=None, required=False, empty_label="未割当")
    needs_review = forms.BooleanField(label="重複候補・要確認", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = employees()


class NoteForm(forms.Form):
    kind = forms.ChoiceField(label="対応種別", choices=[("note", "メモ"), ("call", "電話"), ("visit", "訪問"), ("email", "メールの記録")])
    note = forms.CharField(label="対応内容", max_length=5000, widget=forms.Textarea(attrs={"rows": 3}))


class RelatedForm(forms.ModelForm):
    def __init__(self, *args, inquiry, **kwargs):
        super().__init__(*args, **kwargs)
        # Related staff must also be able to access this inquiry.
        self.fields["assigned_to"].queryset = employees().filter(pk=inquiry.owner_id)
        self.initial["assigned_to"] = self.instance.assigned_to_id or inquiry.owner_id
        self.fields["assigned_to"].empty_label = "担当者を選択してください"


class TaskForm(RelatedForm):
    class Meta:
        model = Task
        fields = ["title", "assigned_to", "due_date", "note"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"}), "note": forms.Textarea(attrs={"rows": 3})}


class AppointmentForm(RelatedForm):
    class Meta:
        model = Appointment
        fields = ["assigned_to", "starts_at", "ends_at", "location", "notes", "status"]
        widgets = {
            "starts_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = ["title", "issued_on", "valid_until", "status", "tax_rate"]
        widgets = {"issued_on": forms.DateInput(attrs={"type": "date"}), "valid_until": forms.DateInput(attrs={"type": "date"})}


QuoteItemFormSet = inlineformset_factory(
    Quote, QuoteItem, fields=["description", "quantity", "unit_price"],
    extra=3, min_num=1, validate_min=True, max_num=20, validate_max=True, can_delete=True,
)


class DateFilterForm(forms.Form):
    start = forms.DateField(label="受付日から", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(label="受付日まで", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError("終了日は開始日以降にしてください。")
        return data
