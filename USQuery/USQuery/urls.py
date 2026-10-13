"""
Definition of urls for USQuery.
"""
from rest_framework.views import csrf_exempt
from USQuery import settings
from django.urls import re_path
from django.views.static import serve
from datetime import datetime
from django.urls import path, include
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView,PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.views.generic import RedirectView

from app import forms, views
from app import subscription_views
from app import iap_views
from app import dashboard_views
from django.conf.urls.static import static
from SenateQuery import views as SQviews
from BillQuery import views as BQviews
from strawberry.django.views import AsyncGraphQLView
from strawberryAPI.graphql.schema import schema
from notifications import views as Nviews
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)
admin.autodiscover()


urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('plans/', subscription_views.plans, name='plans'),
    path('subscription/checkout/create/', subscription_views.create_checkout_session, name='create_checkout_session'),
    path('subscription/confirm/', subscription_views.confirm_subscription_change, name='confirm_subscription_change'),
    path('subscription/success/', subscription_views.checkout_success, name='checkout_success'),
    path('subscription/manage/', subscription_views.manage_subscription, name='manage_subscription'),
    path('subscription/portal/', subscription_views.billing_portal, name='billing_portal'),
    path('subscription/return-to-app/', subscription_views.return_to_app, name='return_to_app'),
    path('api/stripe/webhook/', subscription_views.stripe_webhook, name='stripe_webhook'),
    path('api/subscription/apple/verify/', iap_views.api_apple_verify, name='api_apple_verify'),
    path('api/subscription/apple/notifications/', iap_views.apple_notifications, name='apple_notifications'),
    path('api/subscription/plans/', subscription_views.api_plans, name='api_plans'),
    path('api/subscription/status/', subscription_views.api_subscription_status, name='api_subscription_status'),
    path('api/subscription/create-checkout/', subscription_views.api_create_checkout_session, name='api_create_checkout_session'),
    path('api/subscription/preview-change/', subscription_views.api_preview_subscription_change, name='api_preview_subscription_change'),
    path('api/subscription/cancel/', subscription_views.api_cancel_subscription, name='api_cancel_subscription'),
    path('api/subscription/reactivate/', subscription_views.api_reactivate_subscription, name='api_reactivate_subscription'),
    path('api/subscription/portal/', subscription_views.api_billing_portal, name='api_billing_portal'),
    # Registered before 'admin/' so these match ahead of the admin catch-all
    path('admin/dashboard/', dashboard_views.dashboard, name='dashboard'),
    path('admin/dashboard/data/', dashboard_views.dashboard_data, name='dashboard_data'),
    path('starred/', views.starred, name='starred'),
    path('star-item/', Nviews.StarItemInternal.as_view(), name='star_item_internal'),
    path('unstar-item/', Nviews.UnstarItemInternal.as_view(), name='unstar_item_internal'),
    path('login/',
         views.CustomLoginView.as_view
         (
             template_name='app/login.html',
             authentication_form=forms.BootstrapAuthenticationForm,
             extra_context=
             {
                 'title': 'Log in',
                 'year' : datetime.now().year,
                 'google_client_id': views._get_google_web_client_id(),
                 'apple_client_id': getattr(settings, 'APPLE_CLIENT_ID', None),
             }
         ),
         name='login'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('register/', views.register, name='register'),
    path('oauth/google/', views.oauth_google_web, name='oauth-google-web'),
    path('oauth/apple/', views.oauth_apple_web, name='oauth-apple-web'),
    path('verify-email/<str:email>/', views.verify_email, name='verify-email'),
    path('verify-email/<str:email>/resend/', views.resend_verification, name="resend-verification"),
    path("robots.txt", views.robots_txt),
    path('privacy-policy/', views.my_congress_privacy_policy, name='MCPrivPolicy'),
    path('terms-of-service/', views.terms_of_service, name='MCTerms'),
    path('admin/', admin.site.urls),
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    # ---- Member (SenateQuery) ----
    path('member/', SQviews.home, name='senateQueryHome'),
    path('member/search-failed/', SQviews.search_failed, name='senateQuerySearchFailed'),
    path('member/update-mems/<int:congress_num>/<str:chamber>/<str:state>/', SQviews.update_members, name='update_members'),
    path('member/get-filtered/<int:congress_num>/<str:chamber>/<str:state>/', SQviews.get_filtered_memberships, name='get_filtered_memberships'),
    path('member/arrival/<int:congress_num>/<str:arriving_id>/<str:arriving_date>/<int:in_house>/', SQviews.update_arrival, name='update_arrival'),
    path('member/swap/<int:congress_num>/<str:leaving_id>/<str:leaving_date>/<int:in_house>/', SQviews.swap_membership, name='swap_membership'),
    path('member/swap/<int:congress_num>/<str:leaving_id>/<str:leaving_date>/<int:in_house>/<str:arriving_id>/<str:arriving_date>/<str:party>/', SQviews.swap_membership, name='swap_membership'),
    path('member/create/<int:congress_num>/<str:bioguide_id>/<str:state>/<int:in_house>/<str:party>/', SQviews.create_membership, name='create_membership'),
    path('member/create/<int:congress_num>/<str:bioguide_id>/<str:state>/<int:in_house>/<str:party>/<str:arrival_date>/<str:departure_date>/', SQviews.create_membership, name='create_membership'),
    path('member/create/<int:congress_num>/<str:bioguide_id>/<str:state>/<int:in_house>/<str:party>/<str:arrival_date>/<str:departure_date>/<int:district_num>/', SQviews.create_membership, name='create_membership'),
    path('member/results/', SQviews.query, name='senateQuery'),
    path('member/populate-congress/<int:congress_num>/', SQviews.populate_congress, name = 'senateQueryPopulateCongress'),

    # ---- Bill (BillQuery) ----
    path('bill/', BQviews.home, name = "billQueryHome"),
    path('bill/search/', BQviews.bill_query, name='billQueryAR'),
    path('bill/keyword-search/', BQviews.bill_keyword_query, name='billQueryKeyword'),
    path('bill/search-failed/', BQviews.search_failed, name='billQuerySearchFailed'),
    path('bill/chat/', BQviews.web_chat, name='bill_web_chat'),
    path('bill/chat/usage/', BQviews.chat_usage, name='bill_chat_usage'),
    path('bill/chat/history/', BQviews.chat_history, name='bill_chat_history'),
    path('bill/generate-summary/<int:congress_num>/<str:bill_type>/<int:bill_num>/', BQviews.generate_summary, name='generate_summary'),
    path('bill/prediction-request/<int:congress_num>/<str:bill_type>/<int:bill_num>', BQviews.requestPrediction, name = 'billQueryrequestPrediction'),
    path('bill/prediction/generate/<int:bill_id>/', BQviews.generate_prediction_ajax, name='prediction_generate'),
    path('bill/prediction/members/<int:bill_id>/', BQviews.get_member_predictions, name='prediction_members'),
    path('bill/prediction/usage/', BQviews.prediction_usage, name='prediction_usage'),
    path('bill/populate-bills/<int:congress_num>/<str:bill_type>/<int:limit>/<int:offset>', BQviews.populate_bills, name = 'billQueryPopulateBills'),
    path('bill/update-bill/<int:congress_num>/<str:bill_type>/<int:bill_num>', BQviews.update_bill, name = 'billQueryUpdateBill'),
    path('bill/update/<int:congress_num>/<str:date>/', BQviews.update_bills, name = 'billQueryUpdateRecentBills'),
    # Keep LAST in the bill block - the only pattern here starting with a bare converter.
    path('bill/<int:congress_num>/<str:bill_type>/<int:bill_num>', BQviews.bill, name = 'billQueryBill'),

    # ---- Vote ----
    path('vote/', BQviews.vote_home, name='voteQueryHome'),
    path('vote/search/', BQviews.vote_query, name='voteSearch'),
    path('vote/keyword-search/', BQviews.vote_keyword_query, name='voteQueryKeyword'),
    path('vote/fix/<int:congress_num>/<int:year>/<int:nums>/', BQviews.fix_votes, name = 'voteFix'),
    path('vote/<int:vote_id>', BQviews.vote, name = "voteDetail"),

    # ---- Mobile compatibility aliases ----
    # Called by already-shipped mobile builds. These are ALIASES, not redirects:
    # two are @api_view(['POST']) and three require IsAuthenticated. A 301 risks
    # clients downgrading POST->GET (DRF then answers 405) or dropping the
    # Authorization header (401). Declared here so they resolve BEFORE the legacy
    # redirect block at the bottom of this file. Deliberately unnamed - the new
    # /bill/ routes above own the names.
    path('bill-query/prediction/generate/<int:bill_id>/', BQviews.generate_prediction_ajax),
    path('bill-query/prediction/members/<int:bill_id>/', BQviews.get_member_predictions),
    path('bill-query/prediction/usage/', BQviews.prediction_usage),
    path('bill-query/chat/usage/', BQviews.chat_usage),

    # API ROUTES (too lazy to make graphql queries for these two routes)
    path('api/v1.0/membership/<int:congress_num>/<str:bioguide_id>/<int:in_house>/', csrf_exempt(SQviews.get_membership)),
    path('api/v1.0/membership-by-id/<int:membership_id>', csrf_exempt(SQviews.get_membership_by_id)),
    path('api/v1.0/membership-set/<int:congress_num>/<str:chamber>/<str:state>/', csrf_exempt(SQviews.get_memberships_set)),
    path('api/v1.0/memberships/', csrf_exempt(SQviews.get_starred_memberships)),
    path("api/v1.0/graphql/", csrf_exempt(AsyncGraphQLView.as_view(schema=schema))),
    re_path(r'^static/(?P<path>.*)$', serve,{'document_root': settings.STATIC_ROOT})
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


#Notif api
urlpatterns += [
    path("api/notif/register-device/", Nviews.RegisterDevice.as_view()),
    path("api/notif/unregister-device/", Nviews.UnregisterDevice.as_view()),
    path("api/notif/star-bill/", Nviews.StarBill.as_view()),
    path("api/notif/unstar-bill/", Nviews.UnstarBill.as_view()),
    path("api/notif/star-membership/", Nviews.StarMembership.as_view()),
    path("api/notif/unstar-membership/", Nviews.UnstarMembership.as_view()),
    path("api/notif/update-favorites/", Nviews.UpdateFavoriteSubjects.as_view()),
    path("api/notif/update-preferences/", Nviews.UpdateNotifPreferences.as_view()),
    path("api/notif/update-floor-preferences/", Nviews.UpdateFloorNotifPreferences.as_view()),
    path("api/notif/get-preferences/", Nviews.getUserPreferences),
    # Admin-only test endpoint to trigger a mock push notification
    path("api/notif/send-test/", Nviews.send_test_bill_notification),
    path("api/notif/send-test-null/", Nviews.send_test_bill_notification_exclusion_test),
    path("api/notif/mass-unstar/<int:congress_num>", Nviews.MassUnstar)
]

#Auth api
urlpatterns += [
    path('api/auth/', include('app.api.urls')),
    path('api/auth/view-details/', views.view_details, name='account-details'),
    path('api/auth/delete/', views.manage_account_deletion, name='account-delete'),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path(
    "api/auth/password-reset/",
    PasswordResetView.as_view(
        template_name="app/password_reset.html",
        email_template_name="app/password_reset_email.txt",
        subject_template_name="app/password_reset_subject.txt",
        success_url="done/",
    ),
    name="password_reset",
),

path(
    "api/auth/password-reset/done/",
    PasswordResetDoneView.as_view(
        template_name="app/password_reset_done.html"
    ),
    name="password_reset_done",
),

path(
    "api/auth/reset/<uidb64>/<token>/",
    PasswordResetConfirmView.as_view(
        template_name="app/password_reset_confirm.html",
        success_url="/api/auth/reset/done/",
    ),
    name="password_reset_confirm",
),

path(
    "api/auth/reset/done/",
    PasswordResetCompleteView.as_view(
        template_name="app/password_reset_complete.html"
    ),
    name="password_reset_complete",
),
    
]


# ---------------------------------------------------------------------------
# Legacy URL redirects (old /member-query/ and /bill-query/ prefixes).
# Declared LAST so the mobile aliases above win. query_string=True is required:
# /member-query/results/?congress=..&member=..&chamber=.. carries its params in
# the query string and RedirectView drops them by default.
# ---------------------------------------------------------------------------
urlpatterns += [
    # Paths whose shape changed, not just the prefix.
    path('bill-query/bill-query/', RedirectView.as_view(url='/bill/search/', permanent=True, query_string=True)),
    path('bill-query/vote-query/', RedirectView.as_view(url='/vote/search/', permanent=True, query_string=True)),
    re_path(r'^bill-query/bill/(?P<rest>.*)$', RedirectView.as_view(url='/bill/%(rest)s', permanent=True, query_string=True)),
    re_path(r'^bill-query/vote/(?P<rest>.*)$', RedirectView.as_view(url='/vote/%(rest)s', permanent=True, query_string=True)),
    re_path(r'^bill-query/fix/(?P<rest>.*)$', RedirectView.as_view(url='/vote/fix/%(rest)s', permanent=True, query_string=True)),
    # Generic prefix fallbacks.
    re_path(r'^bill-query/(?P<rest>.*)$', RedirectView.as_view(url='/bill/%(rest)s', permanent=True, query_string=True)),
    re_path(r'^member-query/(?P<rest>.*)$', RedirectView.as_view(url='/member/%(rest)s', permanent=True, query_string=True)),
]
