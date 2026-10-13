"""Routing guard for USQuery/urls.py (one module, no per-app urls), legacy
301 redirects, mobile aliases, staff-only routes and simple pages."""

import pytest
from django.urls import resolve, reverse

from app import views as app_views
from BillQuery import views as BQviews
from SenateQuery import views as SQviews
from tests.factories import make_congress, make_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('name, kwargs, view', [
    ('home', {}, app_views.home),
    ('billQueryHome', {}, BQviews.home),
    ('billQueryAR', {}, BQviews.bill_query),
    ('billQueryKeyword', {}, BQviews.bill_keyword_query),
    ('voteQueryHome', {}, BQviews.vote_home),
    ('voteSearch', {}, BQviews.vote_query),
    ('voteQueryKeyword', {}, BQviews.vote_keyword_query),
    ('billQueryBill', {'congress_num': 119, 'bill_type': 'hr', 'bill_num': 1}, BQviews.bill),
    ('voteDetail', {'vote_id': 1191100001}, BQviews.vote),
    ('prediction_generate', {'bill_id': 11940001}, BQviews.generate_prediction_ajax),
    ('prediction_members', {'bill_id': 11940001}, BQviews.get_member_predictions),
    ('prediction_usage', {}, BQviews.prediction_usage),
    ('bill_web_chat', {}, BQviews.web_chat),
    ('bill_chat_usage', {}, BQviews.chat_usage),
    ('senateQueryHome', {}, SQviews.home),
    ('senateQuery', {}, SQviews.query),
])
def test_named_routes(name, kwargs, view):
    assert resolve(reverse(name, kwargs=kwargs)).func is view


def test_bill_detail_route_does_not_shadow_bill_subroutes():
    assert resolve('/bill/search/').func is BQviews.bill_query
    assert resolve('/bill/chat/usage/').func is BQviews.chat_usage
    assert resolve('/bill/119/hr/1').func is BQviews.bill


@pytest.mark.parametrize('path, view', [
    ('/bill-query/prediction/generate/11940001/', BQviews.generate_prediction_ajax),
    ('/bill-query/prediction/members/11940001/', BQviews.get_member_predictions),
    ('/bill-query/prediction/usage/', BQviews.prediction_usage),
    ('/bill-query/chat/usage/', BQviews.chat_usage),
])
def test_mobile_aliases_are_not_redirects(path, view):
    # Shipped mobile builds POST here with a Bearer token; a 301 would break them.
    assert resolve(path).func is view


@pytest.mark.parametrize('old, new', [
    ('/bill-query/bill-query/?congress=119&page=2', '/bill/search/?congress=119&page=2'),
    ('/bill-query/vote-query/?q=x', '/vote/search/?q=x'),
    ('/bill-query/bill/119/hr/1', '/bill/119/hr/1'),
    ('/bill-query/vote/1191100001', '/vote/1191100001'),
    ('/bill-query/fix/119/2025/5/', '/vote/fix/119/2025/5/'),
    ('/bill-query/', '/bill/'),
    ('/bill-query/search-failed/', '/bill/search-failed/'),
    ('/member-query/', '/member/'),
    ('/member-query/results/?congress=119&member=S000001&chamber=Senate',
     '/member/results/?congress=119&member=S000001&chamber=Senate'),
])
def test_legacy_redirects(client, old, new):
    resp = client.get(old)
    assert resp.status_code == 301
    assert resp['Location'] == new


@pytest.mark.parametrize('path', [
    '/bill/populate-bills/119/hr/10/0',
    '/bill/update-bill/119/hr/1',
    '/bill/update/119/2026-01-01/',
    '/vote/fix/119/2025/5/',
    '/member/populate-congress/119/',
    '/member/create/119/S000001/CA/1/D/',
    '/member/swap/119/S000001/2026-01-01/1/',
    '/member/arrival/119/S000001/2026-01-01/1/',
    '/admin/dashboard/',
])
def test_maintenance_routes_are_staff_only(client, path):
    client.force_login(make_user())
    resp = client.get(path)
    assert resp.status_code == 302
    assert resp['Location'].startswith('/admin/login/')


class TestSimplePages:
    @pytest.mark.parametrize('path', [
        '/about/', '/privacy-policy/', '/terms-of-service/', '/login/', '/register/', '/plans/',
        '/bill/', '/vote/',
    ])
    def test_renders(self, client, path):
        assert client.get(path).status_code == 200

    @pytest.mark.parametrize('path', ['/updateJSON/119/', '/updateSTATES/'])
    def test_removed_map_maintenance_routes(self, client, path):
        assert client.get(path).status_code == 404

    def test_robots(self, client):
        resp = client.get('/robots.txt')
        assert resp.status_code == 200
        assert resp['Content-Type'].startswith('text/plain')

    def test_home_without_congress_redirects(self, client):
        resp = client.get('/')
        assert resp.status_code == 302 and resp['Location'] == '/member/'

    def test_home_with_congress(self, client):
        make_congress(119)
        assert client.get('/').status_code == 200

    def test_member_home(self, client):
        make_congress(119)
        assert client.get('/member/').status_code == 200

    def test_dead_member_search_route_removed(self, client):
        # SenateQuery.views.search is reached through /member/results/ only.
        assert client.get('/member/search/').status_code == 404
