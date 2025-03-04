"""
Definition of urls for USQuery.
"""

from django.urls import re_path
from django.views.static import serve
from datetime import datetime
from django.urls import path, include
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from app import forms, views
from USQuery import settings
from django.conf.urls.static import static
from SenateQuery import views as SQviews
from BillQuery import views as BQviews
admin.autodiscover()


urlpatterns = [
    path('', views.home, name='home'),
    path('contact/', views.contact, name='contact'),
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
    path('member-query/update-mems/<int:congress_id>/<str:chamber>/<str:state>/', SQviews.update_members, name='update_members'),
    path('member-query/arrival/<int:congress_id>/<str:arriving_id>/<str:arriving_date>/', SQviews.update_arrival, name='update_arrival'),
    path('member-query/swap/<int:congress_id>/<str:leaving_id>/<str:leaving_date>/', SQviews.swap_membership, name='swap_membership'),
    path('member-query/swap/<int:congress_id>/<str:leaving_id>/<str:leaving_date>/<str:arriving_id>/<str:arriving_date>/<str:party>/', SQviews.swap_membership, name='swap_membership'),
    path('member-query/create/<int:congress_id>/<str:member_id>/<str:state>/<int:in_house>/<str:party>/', SQviews.create_membership, name='create_membership'),
    path('member-query/create/<int:congress_id>/<str:member_id>/<str:state>/<int:in_house>/<str:party>/<str:arrival_date>/<str:departure_date>/', SQviews.create_membership, name='create_membership'),
    path('member-query/create/<int:congress_id>/<str:member_id>/<str:state>/<int:in_house>/<str:party>/<str:arrival_date>/<str:departure_date>/<int:district_num>/', SQviews.create_membership, name='create_membership'),
    path('member-query/results/', SQviews.query, name='senateQuery'),
    path('member-query/populate-congress', SQviews.populate_congress, name = 'senateQueryPopulateCongress'),
    path('member-query/populate-congress/<int:congress_id>/', SQviews.populate_congress, name = 'senateQueryPopulateCongress'),
    path('bill-query/', BQviews.home, name = "billQueryHome"),
    path('bill-query/search/', BQviews.search, name = "billQuerySearch"),
    path('bill-query/results/', BQviews.query, name='billQuery'),
    path('bill-query/results/bill/<int:congress_id>/<str:type>/<int:num>', BQviews.bill, name = 'billQueryBill'),
    path('bill-query/populate-bills', BQviews.populate_bills, name = 'billQueryPopulateBills'),
    path('bill-query/populate-bills/<int:congress>/<str:_type>/<int:limit>/<int:offset>', BQviews.populate_bills, name = 'billQueryPopulateBills'),
    path('bill-query/update-bill/<int:congress>/<str:_type>/<int:_num>', BQviews.update_bill, name = 'billQueryUpdateBill'),
    path('bill-query/vote/<int:vote_id>', BQviews.vote, name = "billQueryVote"),
    re_path(r'^static/(?P<path>.*)$', serve,{'document_root': settings.STATIC_ROOT})
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
