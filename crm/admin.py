from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group

from .access import is_manager
from .models import Customer, Inquiry, Activity, Appointment, Task, Quote, QuoteItem


class ManagerAdminSite(admin.AdminSite):
    site_header = "LeadFlow 管理 — 自主制作デモ / 架空データ"
    site_title = "LeadFlow 管理"
    index_title = "アカウント管理・記録の参照"

    def has_permission(self, request):
        return request.user.is_staff and is_manager(request.user)


site = ManagerAdminSite(name="manager_admin")
class ManagerUserAdmin(UserAdmin):
    # Manager is a domain role, independent of Django's generic staff flag.
    def has_module_permission(self, request):
        return is_manager(request.user)

    def has_view_permission(self, request, obj=None):
        return is_manager(request.user)

    def has_add_permission(self, request):
        return is_manager(request.user)

    def has_change_permission(self, request, obj=None):
        return is_manager(request.user)

    def has_delete_permission(self, request, obj=None):
        return False  # Deactivate accounts to retain history.


site.register(User, ManagerUserAdmin)


class RecordAdmin(admin.ModelAdmin):
    # Domain edits go through the CRM so history/totals cannot be bypassed.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return is_manager(request.user)


for model in [Customer, Inquiry, Activity, Appointment, Task, Quote, QuoteItem]:
    site.register(model, RecordAdmin)

site.register(Group, RecordAdmin)
