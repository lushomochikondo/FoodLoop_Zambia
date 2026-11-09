from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from core.authentication import UsernameOrEmailAuthenticationForm
from core import views
from core import public_pages
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse
from django.views.generic import TemplateView
from django.views.decorators.cache import never_cache

urlpatterns = [path('requests/<int:pk>/notes/', views.collection_notes, name='collection_notes'), path('admin/', admin.site.urls), path('login/', auth.LoginView.as_view(template_name='login.html', authentication_form=UsernameOrEmailAuthenticationForm), name='login'), path('logout/', auth.LogoutView.as_view(), name='logout'), path('password-reset/', auth.PasswordResetView.as_view(template_name='registration/password_reset_form.html', email_template_name='registration/password_reset_email.html', subject_template_name='registration/password_reset_subject.txt', success_url='/password-reset/done/'), name='password_reset'), path('password-reset/done/', auth.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'), path('reset/<uidb64>/<token>/', auth.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html', success_url='/reset/complete/'), name='password_reset_confirm'), path('reset/complete/', auth.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'), path('', views.home, name='home'), path('listings/new/', views.create_listing, name='create_listing'), path('listings/<int:pk>/', views.detail, name='detail'), path('requests/<int:pk>/<str:action>/', views.transition, name='transition')]
urlpatterns += [
    path('company/<slug:slug>/',public_pages.company_page,name='company_page'),
    path('drop-off-locations/',public_pages.drop_off_locations,name='drop_off_locations'),
    path('faq/',public_pages.faq,name='faq'),
    path('news/',public_pages.news,name='news'),
    path('internal/run-jobs/', views.scheduled_jobs, name='scheduled_jobs'),
    path('news/submit-success-story/', views.submit_success_story, name='submit_success_story'),
    path('news/<slug:slug>/',public_pages.news_detail,name='news_detail'),
    path('contact/',public_pages.contact,name='contact'),
    path('welcome/', views.landing_page, name='landing_page'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('listings/nearby/', views.nearby_listings, name='nearby_listings'),
    path('requests/', views.collections, name='collections'),
    path('beneficiary/eligibility/', views.beneficiary_eligibility, name='beneficiary_eligibility'),
    path('signup/', views.signup, name='signup'),
    path('beneficiary/application/', views.beneficiary_application, name='beneficiary_application'),
    path('beneficiary/application/<int:pk>/document/<str:kind>/', views.beneficiary_document, name='beneficiary_document'),
    path('listings/<int:pk>/edit/', views.edit_listing, name='edit_listing'),
    path('listings/<int:pk>/withdraw/', views.withdraw_listing, name='withdraw_listing'),
    path('listings/<int:pk>/delete/', views.delete_listing, name='delete_listing'),
    path('listings/<int:pk>/report/', views.report_listing, name='report_listing'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/push/subscribe/', views.save_push_subscription, name='push_subscribe'),
    path('notifications/push/unsubscribe/', views.remove_push_subscription, name='push_unsubscribe'),
    path('administration/', views.moderation, name='moderation'),
    path('impact/', views.impact, name='impact'),
    path('impact/statement/', views.impact_statement, name='impact_statement'),
    path('profile/', views.profile, name='profile'),
    path('listings/<int:pk>/photo/', views.listing_photo, name='listing_photo'),
    path('about/terms/', TemplateView.as_view(template_name='terms.html'), name='terms'),
    path('about/privacy/', TemplateView.as_view(template_name='privacy.html'), name='privacy'),
    path('service-worker.js', never_cache(lambda request: FileResponse(open(settings.BASE_DIR / 'static' / 'service-worker.js', 'rb'), content_type='application/javascript')), name='service_worker'),
]
handler403 = 'core.errors.forbidden'
handler404 = 'core.errors.not_found'
handler500 = 'core.errors.server_error'
