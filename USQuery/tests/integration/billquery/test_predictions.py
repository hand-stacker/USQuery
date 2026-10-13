"""Vote-prediction endpoints and their tier/credit gates.

siteutils.getPredictionBatch (TensorFlow + Anthropic) is replaced with a fake
that writes a BillPrediction on generation and returns fixed samples.
"""

import datetime
from unittest import mock

import pytest
from django.core.cache import cache
from freezegun import freeze_time

from app import siteutils
from BillQuery.models import BillPrediction, BinaryProbability
from tests.factories import jwt_headers, make_bill, make_congress, make_member, make_membership, make_user

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures('frozen_today')]

TODAY = '2026-06-01'
HOUSE_SAMPLES = [210, 220, 220]
SENATE_SAMPLES = [49, 51]


@pytest.fixture
def frozen_today():
    # _current_congress() derives from date.today(); pin it inside the 119th.
    # Midday UTC so the Eastern credit day (what _pred_today keys on) is also TODAY.
    with freeze_time(f'{TODAY} 16:00:00'):
        yield


@pytest.fixture
def bill():
    return make_bill(119, 4, 1)


@pytest.fixture
def fake_batch():
    def _fake(bill_id, in_house, sample_size, run_sample=True):
        if sample_size == 0:
            BillPrediction.objects.get_or_create(id=bill_id, defaults={'creation_date': datetime.date(2026, 6, 1)})
            return True
        return HOUSE_SAMPLES if in_house else SENATE_SAMPLES
    with mock.patch.object(siteutils, 'getPredictionBatch', side_effect=_fake) as m:
        yield m


@pytest.fixture
def predicted(bill, fake_batch):
    BillPrediction.objects.create(id=bill.id, creation_date=datetime.date(2026, 6, 1))
    return bill


def _gen_url(bill_id, generate=True):
    return f'/bill/prediction/generate/{bill_id}/' + ('' if generate else '?generate=false')


def _mem_url(bill_id, generate=True):
    return f'/bill/prediction/members/{bill_id}/' + ('' if generate else '?generate=false')


def _credits_used(user):
    return cache.get(f'pred_credits_used:{user.id}:{TODAY}', 0)


class TestReadOnly:
    def test_unknown_bill(self, client):
        assert client.post(_gen_url(99, generate=False)).status_code == 404

    def test_no_prediction_yet(self, client, bill):
        assert client.post(_gen_url(bill.id, generate=False)).json() == {'exists': False}

    def test_public_distribution(self, client, predicted):
        data = client.post(_gen_url(predicted.id, generate=False)).json()
        assert data['exists'] is True
        assert data['house_dist'] == {'210': 1, '220': 2}
        assert data['senate_dist'] == {'49': 1, '51': 1}
        assert 'credits_remaining' not in data

    def test_plus_sees_credits(self, client, predicted, plus_user):
        client.force_login(plus_user)
        data = client.post(_gen_url(predicted.id, generate=False)).json()
        assert (data['credits_remaining'], data['member_reveal_unlocked']) == (10, False)

    def test_premium_unlocked(self, client, predicted, premium_user):
        client.force_login(premium_user)
        data = client.post(_gen_url(predicted.id, generate=False)).json()
        assert (data['credits_remaining'], data['member_reveal_unlocked']) == (None, True)

    def test_prediction_data_error(self, client, predicted):
        with mock.patch.object(siteutils, 'getPredictionBatch',
                               side_effect=siteutils.PredictionDataError('no_text', 'Bill text unavailable')):
            resp = client.post(_gen_url(predicted.id, generate=False))
        assert resp.status_code == 422
        assert resp.json()['reason'] == 'no_text'

    def test_sampling_failure(self, client, predicted):
        with mock.patch.object(siteutils, 'getPredictionBatch', return_value=-1):
            assert client.post(_gen_url(predicted.id, generate=False)).json()['error'] == 'data_unavailable'


class TestGenerate:
    def test_anonymous(self, client, bill, fake_batch):
        assert client.post(_gen_url(bill.id)).status_code == 401
        fake_batch.assert_not_called()

    def test_free_must_upgrade(self, client, bill, free_user, fake_batch):
        client.force_login(free_user)
        resp = client.post(_gen_url(bill.id))
        assert (resp.status_code, resp.json()['error']) == (403, 'upgrade_required')
        fake_batch.assert_not_called()

    def test_plus_spends_a_credit_and_unlocks_members(self, client, bill, plus_user, fake_batch):
        client.force_login(plus_user)
        data = client.post(_gen_url(bill.id)).json()
        assert data['success'] is True
        assert data['credits_remaining'] == 9
        assert BillPrediction.objects.filter(id=bill.id).exists()
        assert cache.get(f'pred_member_reveal:{plus_user.id}:{bill.id}') is True

    def test_plus_daily_limit(self, client, bill, plus_user, fake_batch):
        cache.set(f'pred_credits_used:{plus_user.id}:{TODAY}', 10)
        client.force_login(plus_user)
        data = client.post(_gen_url(bill.id)).json()
        assert data == {'error': 'daily_limit', 'credits_remaining': 0}
        fake_batch.assert_not_called()

    def test_premium_not_metered(self, client, bill, premium_user, fake_batch):
        client.force_login(premium_user)
        data = client.post(_gen_url(bill.id)).json()
        assert data['success'] is True and data['credits_remaining'] is None
        assert _credits_used(premium_user) == 0

    def test_plus_pro_is_metered(self, client, bill, plus_pro_user, fake_batch):
        # Tier ids don't sort by plan level (Plus Pro is 4, Premium 2); Plus Pro
        # must spend its own 30 daily credits, not be treated as Premium.
        client.force_login(plus_pro_user)
        data = client.post(_gen_url(bill.id)).json()
        assert data['credits_remaining'] == 29
        assert _credits_used(plus_pro_user) == 1

    def test_plus_pro_daily_limit_is_thirty(self, client, bill, plus_pro_user, fake_batch):
        cache.set(f'pred_credits_used:{plus_pro_user.id}:{TODAY}', 29)
        client.force_login(plus_pro_user)
        assert client.post(_gen_url(bill.id)).json()['credits_remaining'] == 0
        assert client.post(_gen_url(make_bill(119, 4, 5).id)).json()['error'] == 'daily_limit'

    def test_user_without_profile(self, client, bill, fake_batch):
        from django.contrib.auth.models import User
        client.force_login(User.objects.create_user('np@example.com', 'np@example.com', 'x'))
        assert client.post(_gen_url(bill.id)).json()['error'] == 'upgrade_required'

    def test_jwt_works_for_mobile(self, api_client, bill, plus_user, fake_batch):
        api_client.credentials(**jwt_headers(plus_user))
        assert api_client.post(_gen_url(bill.id)).json()['success'] is True

    def test_legacy_mobile_alias(self, api_client, bill, plus_user, fake_batch):
        api_client.credentials(**jwt_headers(plus_user))
        resp = api_client.post(f'/bill-query/prediction/generate/{bill.id}/')
        assert resp.status_code == 200 and resp.json()['success'] is True

    def test_enacted_bill(self, client, plus_user, fake_batch):
        enacted = make_bill(119, 4, 2, status=True)
        client.force_login(plus_user)
        assert client.post(_gen_url(enacted.id)).json()['error'] == 'bill_passed'

    def test_previous_congress(self, client, plus_user, fake_batch):
        old = make_bill(118, 4, 1)
        client.force_login(plus_user)
        assert client.post(_gen_url(old.id)).json()['error'] == 'not_eligible'

    def test_wide_bill_id_congress_decoding(self, client, plus_user, fake_batch):
        wide = make_bill(119, 4, 10001)
        client.force_login(plus_user)
        assert client.post(_gen_url(wide.id)).json()['success'] is True

    def test_generation_wrote_nothing(self, client, bill, plus_user):
        client.force_login(plus_user)
        with mock.patch.object(siteutils, 'getPredictionBatch', return_value=None):
            resp = client.post(_gen_url(bill.id))
        assert (resp.status_code, resp.json()['error']) == (422, 'generation_failed')
        assert _credits_used(plus_user) == 0


class TestMemberPredictions:
    @pytest.fixture
    def members(self, predicted):
        congress = make_congress(119)
        make_membership(congress=congress, member=make_member(first='Dem'), house=True, state='CA', party='Democratic')
        make_membership(congress=congress, member=make_member(first='Rep'), house=True, state='TX', party='Republican')
        make_membership(congress=congress, member=make_member(first='Sen'), house=False, state='CA', party='Democratic')
        BinaryProbability.objects.create(bill_pred_id=predicted.id, state='CA', in_house=True,
                                         party='Democratic', counts=1, p='0.91000')
        return predicted

    def test_anonymous(self, client, members):
        assert client.post(_mem_url(members.id)).status_code == 403

    def test_free(self, client, members, free_user):
        client.force_login(free_user)
        assert client.post(_mem_url(members.id)).status_code == 403

    def test_premium_gets_members(self, client, members, premium_user):
        client.force_login(premium_user)
        data = client.post(_mem_url(members.id)).json()
        house = data['members_house']
        probs = [m['prob'] for m in house]
        assert probs == sorted(probs, reverse=True)
        for m in house:
            # CA House Democrats get the stored probability; everyone else the 0.5 default.
            assert m['prob'] == (0.91 if (m['state'], m['party']) == ('CA', 'D') else 0.5)
        assert [m['prob'] for m in data['members_senate']] == [0.5]  # in_house=False row absent

    def test_plus_pays_once_per_bill(self, client, members, plus_user):
        client.force_login(plus_user)
        first = client.post(_mem_url(members.id)).json()
        second = client.post(_mem_url(members.id)).json()
        assert first['credits_remaining'] == 9
        assert second['credits_remaining'] == 9
        assert _credits_used(plus_user) == 1

    def test_plus_out_of_credits(self, client, members, plus_user):
        cache.set(f'pred_credits_used:{plus_user.id}:{TODAY}', 10)
        client.force_login(plus_user)
        assert client.post(_mem_url(members.id)).json()['error'] == 'daily_limit'

    def test_no_prediction(self, client, bill, premium_user):
        client.force_login(premium_user)
        assert client.post(_mem_url(bill.id)).status_code == 404

    def test_read_only_locked_for_plus(self, client, members, plus_user):
        client.force_login(plus_user)
        data = client.post(_mem_url(members.id, generate=False)).json()
        assert data == {'exists': True, 'credits_remaining': 10}

    def test_plus_pro_pays_for_reveal(self, client, members, plus_pro_user):
        client.force_login(plus_pro_user)
        assert client.post(_mem_url(members.id)).json()['credits_remaining'] == 29

    def test_read_only_unlocked_for_plus(self, client, members, plus_user):
        cache.set(f'pred_member_reveal:{plus_user.id}:{members.id}', True)
        client.force_login(plus_user)
        assert 'members_house' in client.post(_mem_url(members.id, generate=False)).json()


class TestCreditDay:
    def test_resets_at_midnight_eastern_not_utc(self, client, plus_user):
        client.force_login(plus_user)
        # 03:00 UTC on Jun 2 is still 11 PM on Jun 1 in Washington.
        with freeze_time('2026-06-02 03:00:00'):
            cache.set(f'pred_credits_used:{plus_user.id}:2026-06-01', 4)
            assert client.get('/bill/prediction/usage/').json()['val'] == 6
        with freeze_time('2026-06-02 05:00:00'):  # 1 AM Eastern, Jun 2: fresh day
            assert client.get('/bill/prediction/usage/').json()['val'] == 10


class TestUsage:
    def test_plus(self, client, plus_user):
        cache.set(f'pred_credits_used:{plus_user.id}:{TODAY}', 3)
        client.force_login(plus_user)
        assert client.get('/bill/prediction/usage/').json() == {'display': 'count', 'val': 7, 'limit': 10}

    def test_plus_pro(self, client, plus_pro_user):
        cache.set(f'pred_credits_used:{plus_pro_user.id}:{TODAY}', 5)
        client.force_login(plus_pro_user)
        assert client.get('/bill/prediction/usage/').json() == {'display': 'count', 'val': 25, 'limit': 30}

    @pytest.mark.parametrize('fixture', ['free_user', 'premium_user'])
    def test_others(self, client, request, fixture):
        client.force_login(request.getfixturevalue(fixture))
        assert client.get('/bill/prediction/usage/').json() == {'display': 'none', 'val': None}

    def test_anonymous(self, client):
        assert client.get('/bill/prediction/usage/').status_code == 403
