"""
Definition of urls for USQuery.
"""
from USQuery import settings
from django.urls import re_path
from django.views.static import serve
from datetime import datetime
from django.urls import path, include
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from app import forms, views
from django.conf.urls.static import static
from SenateQuery import views as SQviews
from BillQuery import views as BQviews
from strawberry.django.views import AsyncGraphQLView
from strawberryAPI.graphql.schema import schema
admin.autodiscover()


urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('login/',
         LoginView.as_view
         (
             template_name='app/login.html',
             authentication_form=forms.BootstrapAuthenticationForm,
             extra_context=
             {
                 'title': 'Log in',
                 'year' : datetime.now().year,
             }
         ),
         name='login'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('admin/', admin.site.urls),
    path('updateJSON/<int:congress_id>/', views.updateJSON, name='updateJSON'),
    path('updateSTATES/', views.updateSTATES, name='updateSTATES'),
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('member-query/', SQviews.home, name='senateQueryHome'),
    path('member-query/search/', SQviews.search, name='senateQuerySearch'),
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
    path('bill-query/action-range/', BQviews.query, name='billQueryAR'),
    path('bill-query/vote-range/', BQviews.vote_query, name='billQueryVR'),
    path('bill-query/bill-search/', BQviews.bill_search, name='billQueryBS'),
    path('bill-query/update-bills/<int:congress_num>', BQviews.update_bills, name='update_bills'),
    path('bill-query/bill/<int:congress_num>/<str:bill_type>/<int:bill_num>', BQviews.bill, name = 'billQueryBill'),
    path('bill-query/prediction-request/<int:congress_num>/<str:bill_type>/<int:bill_num>', BQviews.requestPrediction, name = 'billQueryrequestPrediction'),
    path('bill-query/vote/<int:vote_id>', BQviews.vote, name = "billQueryVote"),
    path('bill-query/fix/<int:congress_num>/<int:year>/<int:nums>/', BQviews.fix_votes, name = 'billQueryFixVotes'),
    path('bill-query/populate-bills/<int:congress_num>/<str:bill_type>/<int:limit>/<int:offset>', BQviews.populate_bills, name = 'billQueryPopulateBills'),
    path('bill-query/update-bill/<int:congress_num>/<str:bill_type>/<int:bill_num>', BQviews.update_bill, name = 'billQueryUpdateBill'),
    path('bill-query/update/<int:congress_num>/<str:date>/', BQviews.update_votes, name = 'billQueryUpdateBill'),
    path("tasks/daily-task/", BQviews.daily_task, name="daily-task"),
    # API ROUTES
    path('api/v1.0/membership/<int:congress_num>/<str:bioguide_id>/<int:in_house>/', SQviews.get_membership, name='get_membership'),
    path('api/v1.0/membership-set/<int:congress_num>/<str:chamber>/<str:state>/', SQviews.get_memberships_set, name='get_memberships_set'),
    path('api/v1.0/vote/<int:vote_id>/', BQviews.get_vote, name='get_vote'),
    path('api/v1.0/congress-set/', SQviews.get_congress_set, name='get_congress_set'),
    path("api/v1.0/graphql/", AsyncGraphQLView.as_view(schema=schema)),
    re_path(r'^static/(?P<path>.*)$', serve,{'document_root': settings.STATIC_ROOT})
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
