from django.contrib import admin
from django import forms
from django.db import transaction
from .models import AuditLog, FlagReport, FoodRequest, Listing, Membership, Notification, Organisation, RequestEvent
from .models import DropOffLocation, NewsArticle
from django.utils import timezone

class OrganisationAdminForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = '__all__'
    def clean(self):
        data = super().clean()
        if data.get('status') != 'pending' and not data.get('verification_reason', '').strip():
            self.add_error('verification_reason', 'Record a reason for the verification decision.')
        if data.get('role') == 'recipient' and data.get('pathway') != 'human':
            self.add_error('pathway', 'Recipients for people must use Human Consumption.')
        if data.get('role') == 'recovery' and data.get('pathway') == 'human':
            self.add_error('pathway', 'Recovery partners must use Animal Feed or Composting.')
        return data

@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    form = OrganisationAdminForm
    list_display = ['name', 'role', 'pathway', 'area', 'status']
    list_filter = ['status', 'role', 'pathway']
    search_fields = ['name', 'contact_name', 'registration_reference']
    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditLog.objects.create(actor=request.user, action=f'Organisation {obj.pk}: {obj.status}; reason: {obj.verification_reason}')
        if 'status' in form.changed_data:
            from .services import notify
            notify(obj, f'Organisation verification updated: {obj.status}. {obj.verification_reason}')

admin.site.register(Membership)

@admin.register(AuditLog)
class AuditAdmin(admin.ModelAdmin):
    list_display = ['actor', 'action', 'created']
    readonly_fields = ['actor', 'action', 'created']
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

admin.site.site_header = 'FoodLoop Zambia administration'

class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(FoodRequest)
class RequestAdmin(ReadOnlyAdmin):
    list_display = ['id', 'listing', 'recipient', 'quantity', 'status', 'updated']
    list_filter = ['status']

@admin.register(Listing)
class ListingAdmin(ReadOnlyAdmin):
    list_display = ['name', 'provider', 'quantity', 'allocated', 'pathway', 'status', 'deadline']
    list_filter = ['pathway', 'status']

@admin.register(FlagReport)
class FlagAdmin(ReadOnlyAdmin):
    list_display = ['listing', 'reporter', 'status', 'created']
    list_filter = ['status']

@admin.register(RequestEvent)
class EventAdmin(ReadOnlyAdmin):
    list_display = ['request', 'actor', 'status', 'created']

@admin.register(DropOffLocation)
class DropOffAdmin(admin.ModelAdmin):
    list_display = ['name','area','published']
    list_filter = ['published','area']
    search_fields = ['name','area','address']

@admin.register(NewsArticle)
class NewsAdmin(admin.ModelAdmin):
    list_display = ['title','published','published_at']
    list_filter = ['published']
    prepopulated_fields = {'slug':('title',)}
    def save_model(self,request,obj,form,change):
        if obj.published and not obj.published_at: obj.published_at = timezone.now()
        super().save_model(request,obj,form,change)
