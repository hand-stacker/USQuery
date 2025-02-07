"""
Definition of urls for USQuery.
"""

from datetime import datetime
from django.urls import path, include
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from app import forms, views
from USQuery import settings
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
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('member-query/', SQviews.home, name='senateQueryHome'),
    path('member-query/about', SQviews.about, name='senateQueryAbout'),
    path('member-query/search/', SQviews.search, name='senateQuerySearch'),
    path('member-query/update-mems/<int:congress_id>/<str:chamber>/<str:state>/', SQviews.update_members, name='update_members'),
    path('member-query/results/', SQviews.query, name='senateQuery'),
    path('member-query/populate-congress', SQviews.populate_congress, name = 'senateQueryPopulateCongress'),
    path('member-query/populate-congress/<int:congress_id>/', SQviews.populate_congress, name = 'senateQueryPopulateCongress'),
    path('bill-query/', BQviews.home, name = "billQueryHome"),
    path('bill-query/about', BQviews.about, name = "billQueryAbout"),
    path('bill-query/search/', BQviews.search, name = "billQuerySearch"),
    path('bill-query/results/', BQviews.query, name='billQuery'),
    path('bill-query/results/bill/<int:congress_id>/<str:type>/<int:num>', BQviews.bill, name = 'billQueryBill'),
    path('bill-query/populate-bills', BQviews.populate_bills, name = 'billQueryPopulateBills'),
    path('bill-query/populate-bills/<int:congress>/<str:_type>/<int:limit>/<int:offset>', BQviews.populate_bills, name = 'billQueryPopulateBills'),
    path('bill-query/vote/<int:vote_id>', BQviews.vote, name = "billQueryVote"),
]
