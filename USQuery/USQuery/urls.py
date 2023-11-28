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
    path('senate-query/', SQviews.home, name='senateQueryHome'),
    path('senate-query/about', SQviews.about, name='senateQueryAbout'),
    path('senate-query/search/', SQviews.search, name='senateQuerySearch'),
    path('senate-query/query/', SQviews.query, name='senateQuery'),
    path('senate-query/populate-senators', SQviews.populate, name='senateQueryPopulate'),
    path("select2/", include("django_select2.urls")),
    #path(settings.ABSOLUTE_URL_OVERRIDES['senatequery.models.senator'](), SQviews.senator, name='senateQuerySearchResult'),
]
