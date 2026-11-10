from django.contrib import admin
from django import forms
from django.db import transaction
from .models import AuditLog, FlagReport, FoodRequest, Listing, Membership, Notification, Organisation, RequestEvent
from .models import ContactMessage, DropOffLocation, NewsArticle, PlatformSetting, HandoverCode, ListingReoffer, StorySubmission
from django.utils import timezone
from django.utils.text import slugify

class OrganisationAdminForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = '__all__'
    def clean(self):
        data = super().clean()
        if data.get('status') not in ('pending', 'draft') and not data.get('verification_reason', '').strip():
            self.add_error('verification_reason', 'Record a reason for the verification decision.')
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

@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'description', 'updated']
    search_fields = ['key', 'description']
    def has_delete_permission(self, request, obj=None): return False
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from .services import _platform_settings
        _platform_settings.cache_clear()

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

@admin.register(HandoverCode)
class HandoverCodeAdmin(ReadOnlyAdmin):
    list_display = ['request', 'expires_at', 'attempts', 'verified_at']

@admin.register(ListingReoffer)
class ListingReofferAdmin(ReadOnlyAdmin):
    list_display = ['listing', 'organisation', 'wave', 'created']

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
    list_display = ['title','category','published','published_at']
    list_filter = ['category','published']
    prepopulated_fields = {'slug':('title',)}
    fields = ['category','title','slug','summary','body','image','published','published_at']
    def save_model(self,request,obj,form,change):
        if obj.published and not obj.published_at: obj.published_at = timezone.now()
        super().save_model(request,obj,form,change)

@admin.register(StorySubmission)
class StorySubmissionAdmin(admin.ModelAdmin):
    change_form_template = 'admin/core/storysubmission/change_form.html'
    list_display = ['title', 'organisation', 'submitted_by', 'submitted_at', 'status']
    list_filter = ['status', 'submitted_at']
    search_fields = ['title', 'summary', 'body', 'organisation__name', 'submitted_by__username']
    actions = ['publish_as_success_story', 'decline_submissions']
    readonly_fields = ['organisation', 'submitted_by', 'title', 'summary', 'body', 'image', 'consent_confirmed', 'submitted_at', 'status', 'reviewed_at', 'news_article']
    fields = ['organisation', 'submitted_by', 'title', 'summary', 'body', 'image', 'consent_confirmed', 'submitted_at', 'status', 'review_note', 'reviewed_at', 'news_article']

    def response_change(self, request, obj):
        queryset = StorySubmission.objects.filter(pk=obj.pk)
        if '_publish_story' in request.POST:
            self.publish_as_success_story(request, queryset)
        elif '_decline_story' in request.POST:
            self.decline_submissions(request, queryset)
        return super().response_change(request, obj)

    @admin.action(description='Publish selected submissions as success stories')
    @transaction.atomic
    def publish_as_success_story(self, request, queryset):
        published = 0
        for submission in queryset.select_for_update().select_related('organisation', 'submitted_by'):
            if submission.status != 'pending':
                continue
            slug = f"{slugify(submission.title)[:200].strip('-') or 'success-story'}-{submission.pk}"
            article = NewsArticle.objects.create(
                category='success_story', title=submission.title, slug=slug,
                summary=submission.summary, body=submission.body, image=submission.image.name if submission.image else '',
                published=True, published_at=timezone.now(),
            )
            submission.status = 'published'
            submission.reviewed_at = timezone.now()
            submission.news_article = article
            submission.save(update_fields=['status', 'reviewed_at', 'news_article'])
            Notification.objects.create(user=submission.submitted_by, message=f'Your success story “{submission.title}” has been published.')
            published += 1
        self.message_user(request, f'{published} story submission(s) published.')

    @admin.action(description='Decline selected submissions')
    def decline_submissions(self, request, queryset):
        pending = list(queryset.filter(status='pending').select_related('submitted_by'))
        for submission in pending:
            submission.status = 'declined'
            submission.reviewed_at = timezone.now()
            submission.save(update_fields=['status', 'reviewed_at'])
            detail = f' Feedback: {submission.review_note}' if submission.review_note else ' Please contact the FoodLoop team if you would like feedback.'
            Notification.objects.create(user=submission.submitted_by, message=f'FoodLoop reviewed your story “{submission.title}”.{detail}'[:240])
        self.message_user(request, f'{len(pending)} pending submission(s) declined.')

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['subject','name','email','created','reviewed']
    list_filter = ['reviewed','created']
    search_fields = ['subject','name','email','message']
    readonly_fields = ['name','email','subject','message','created']
    fields = ['name','email','subject','message','created','reviewed']
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
