from django.conf import settings
from django.contrib.auth import views as auth
from django.urls import path, re_path
from django.views.static import serve

from crm import views
from crm.admin import site

urlpatterns = [
    path("", views.home, name="home"),
    path("inquiry/", views.public_intake, name="public_intake"),
    path("inquiry/thanks/", views.thank_you, name="thank_you"),
    path("accounts/login/", auth.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth.LogoutView.as_view(), name="logout"),
    path("admin/", site.urls),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/new/", views.customer_edit, name="customer_create"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<int:pk>/archive/", views.customer_archive, name="customer_archive"),
    path("inquiries/", views.inquiry_list, name="inquiry_list"),
    path("inquiries/new/", views.inquiry_edit, name="inquiry_create"),
    path("inquiries/<int:pk>/", views.inquiry_detail, name="inquiry_detail"),
    path("inquiries/<int:pk>/edit/", views.inquiry_edit, name="inquiry_edit"),
    path("inquiries/<int:pk>/<str:action>/", views.inquiry_action, name="inquiry_action"),
    path("schedule/", views.schedule, name="schedule"),
    path("inquiries/<int:inquiry_pk>/tasks/new/", views.task_edit, name="task_create"),
    path("inquiries/<int:inquiry_pk>/tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/toggle/", views.task_toggle, name="task_toggle"),
    path("inquiries/<int:inquiry_pk>/appointments/new/", views.appointment_edit, name="appointment_create"),
    path("inquiries/<int:inquiry_pk>/appointments/<int:pk>/edit/", views.appointment_edit, name="appointment_edit"),
    path("quotations/", views.quote_list, name="quote_list"),
    path("inquiries/<int:inquiry_pk>/quotes/new/", views.quote_edit, name="quote_create"),
    path("inquiries/<int:inquiry_pk>/quotes/<int:pk>/edit/", views.quote_edit, name="quote_edit"),
    path("quotations/<int:pk>/", views.quote_detail, name="quote_detail"),
    path("quotations/<int:pk>/print/", views.quote_print, name="quote_print"),
]
if settings.DEBUG:
    # Local demo Gunicorn only. Public deployment must use a static-file server.
    urlpatterns += [re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT})]
