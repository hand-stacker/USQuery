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
    path('member-query/update-senators/<int:congress_id>/', SQviews.update_senators, name='update_senators'),
    path('member-query/update-reps/<int:congress_id>/', SQviews.update_reps, name='update_reps'),
    path('member-query/sen-results/', SQviews.query, name='senateQuery'),
    path('member-query/rep-results/', SQviews.rep_query, name='senateQueryReps'),
    path('member-query/populate-congress', SQviews.populate_congress, name = 'senateQueryPopulateCongress'),
]
