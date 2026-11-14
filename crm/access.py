from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Customer, Inquiry, Quote, Task, Appointment


def is_manager(user):
    return user.is_authenticated and user.is_active and (user.is_superuser or user.groups.filter(name="Manager").exists())


def is_employee(user):
    return user.is_authenticated and user.is_active and user.groups.filter(name="Employee").exists()


def staff_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not (is_manager(request.user) or is_employee(request.user)):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def employees():
    return User.objects.filter(is_active=True, groups__name="Employee").distinct()


def inquiries_for(user):
    qs = Inquiry.objects.select_related("customer", "owner")
    if is_manager(user):
        return qs
    return qs.filter(owner=user) if is_employee(user) else qs.none()


def customers_for(user):
    qs = Customer.objects.all()
    if is_manager(user):
        return qs
    return qs.filter(Q(created_by=user) | Q(inquiries__owner=user)).distinct() if is_employee(user) else qs.none()


def quotes_for(user):
    return Quote.objects.filter(inquiry__in=inquiries_for(user)).select_related("inquiry__customer")


def tasks_for(user):
    qs = Task.objects.filter(inquiry__in=inquiries_for(user)).select_related("inquiry", "assigned_to")
    return qs if is_manager(user) else qs.filter(assigned_to=user)


def appointments_for(user):
    qs = Appointment.objects.filter(inquiry__in=inquiries_for(user)).select_related("inquiry", "assigned_to")
    return qs if is_manager(user) else qs.filter(assigned_to=user)


def role_context(request):
    return {"manager_role": is_manager(request.user)}
