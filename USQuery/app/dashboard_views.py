"""Internal cost & revenue dashboard. Not included in this public snapshot."""

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse

_NOT_INCLUDED = 'The dashboard is not included in the public snapshot.'


@staff_member_required
def dashboard(request):
    return HttpResponse(_NOT_INCLUDED, content_type='text/plain', status=404)


@staff_member_required
def dashboard_data(request):
    return HttpResponse(_NOT_INCLUDED, content_type='text/plain', status=404)
