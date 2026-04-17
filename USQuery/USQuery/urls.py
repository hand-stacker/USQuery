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

from app import forms, views
from django.conf.urls.static import static
from SenateQuery import views as SQviews
from BillQuery import views as BQviews
from strawberry.django.views import AsyncGraphQLView
from strawberryAPI.graphql.schema import schema
from notifications import views as NViews
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)
admin.autodiscover()


urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
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
    path('admin/', admin.site.urls),
    path('updateJSON/<int:congress_id>/', views.updateJSON, name='updateJSON'),
    path('updateSTATES/', views.updateSTATES, name='updateSTATES'),
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('member-query/', SQviews.home, name='senateQueryHome'),
    path('member-query/search/', SQviews.search, name='senateQuerySearch'),
    path('member-query/search-failed/', SQviews.search_failed, name='senateQuerySearchFailed'),
    path('member-query/update-mems/<int:congress_num>/<str:chamber>/<str:state>/', SQviews.update_members, name='update_members'),
    path('member-query/arrival/<int:congress_num>/<str:arriving_id>/<str:arriving_date>/<int:in_house>/', SQviews.update_arrival, name='update_arrival'),
    path('member-query/swap/<int:congress_num>/<str:leaving_id>/<str:leaving_date>/<int:in_house>/', SQviews.swap_membership, name='swap_membership'),
    path('member-query/swap/<int:congress_num>/<str:leaving_id>/<str:leaving_date>/<int:in_house>/<str:arriving_id>/<str:arriving_date>/<str:party>/', SQviews.swap_membership, name='swap_membership'),
    path('member-query/create/<int:congress_num>/<str:bioguide_id>/<str:state>/<int:in_house>/<str:party>/', SQviews.create_membership, name='create_membership'),
    path('member-query/create/<int:congress_num>/<str:bioguide_id>/<str:state>/<int:in_house>/<str:party>/<str:arrival_date>/<str:departure_date>/', SQviews.create_membership, name='create_membership'),
    path('member-query/create/<int:congress_num>/<str:bioguide_id>/<str:state>/<int:in_house>/<str:party>/<str:arrival_date>/<str:departure_date>/<int:district_num>/', SQviews.create_membership, name='create_membership'),
    path('member-query/results/', SQviews.query, name='senateQuery'),
    path('member-query/populate-congress/<int:congress_num>/', SQviews.populate_congress, name = 'senateQueryPopulateCongress'),
    path('bill-query/', BQviews.home, name = "billQueryHome"),
    path('bill-query/search-failed/', BQviews.search_failed, name='billQuerySearchFailed'),
    path('bill-query/bill-query/', BQviews.bill_query, name='billQueryAR'),
    path('bill-query/vote-query/', BQviews.vote_query, name='billQueryVR'),
    path('bill-query/bill/<int:congress_num>/<str:bill_type>/<int:bill_num>', BQviews.bill, name = 'billQueryBill'),
    path('bill-query/generate-summary/<int:congress_num>/<str:bill_type>/<int:bill_num>/', BQviews.generate_summary, name='generate_summary'),
    path('bill-query/prediction-request/<int:congress_num>/<str:bill_type>/<int:bill_num>', BQviews.requestPrediction, name = 'billQueryrequestPrediction'),
    path('bill-query/vote/<int:vote_id>', BQviews.vote, name = "billQueryVote"),
    path('bill-query/fix/<int:congress_num>/<int:year>/<int:nums>/', BQviews.fix_votes, name = 'billQueryFixVotes'),
    path('bill-query/populate-bills/<int:congress_num>/<str:bill_type>/<int:limit>/<int:offset>', BQviews.populate_bills, name = 'billQueryPopulateBills'),
    path('bill-query/update-bill/<int:congress_num>/<str:bill_type>/<int:bill_num>', BQviews.update_bill, name = 'billQueryUpdateBill'),
    path('bill-query/update/<int:congress_num>/<str:date>/', BQviews.update_votes, name = 'billQueryUpdateBill'),
    path("tasks/daily-task/", BQviews.daily_task, name="daily-task"),
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
    path("api/notif/register-device/", NViews.RegisterDevice.as_view()),
    path("api/notif/unregister-device/", NViews.UnregisterDevice.as_view()),
    path("api/notif/star-bill/", NViews.StarBill.as_view()),
    path("api/notif/unstar-bill/", NViews.UnstarBill.as_view()),
    path("api/notif/star-membership/", NViews.StarMembership.as_view()),
    path("api/notif/unstar-membership/", NViews.UnstarMembership.as_view()),
    path("api/notif/update-favorites/", NViews.UpdateFavoriteSubjects.as_view()),
    path("api/notif/update-preferences/", NViews.UpdateNotifPreferences.as_view()),
    path("api/notif/get-preferences/", NViews.getUserPreferences),
    # Admin-only test endpoint to trigger a mock push notification
    path("api/notif/send-test/", NViews.send_test_bill_notification),
    path("api/notif/send-test-null/", NViews.send_test_bill_notification_exclusion_test),
    path("api/notif/mass-unstar/<int:congress_num>", NViews.MassUnstar)
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
