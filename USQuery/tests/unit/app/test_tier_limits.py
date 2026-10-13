"""UserProfile limit getters, on unsaved profiles (no DB).

Expected values are written out literally so an accidental edit to the tier
tables in app/models.py fails here instead of shipping.
"""

import pytest

from app.models import UserProfile

FREE, PLUS, PREMIUM, SPECIAL, PLUS_PRO = 0, 1, 2, 3, 4
INF = float('inf')

#                 name        dev   bills  mems  daily_pred chat   chat_tok  out_tok  cost  budget     web
TABLE = {
    FREE:     ('Free',      5,    10,    3,    0,       0,       0,        0,       0.0,  0,         0),
    PLUS:     ('Plus',      5,    50,    10,   10,      10,      10_000,   5_000,   INF,  0,         30),
    PREMIUM:  ('Premium',   5,    1000,  100,  10_000,  10_000,  100_000,  50_000,  INF,  5_000_000, 200),
    SPECIAL:  ('Special',   1000, 10000, 1000, 10_000,  1_000_000, 1_000_000, 500_000, INF, 0,       1_000_000),
    PLUS_PRO: ('Plus Pro',  5,    100,   25,   30,      30,      30_000,   15_000,  INF,  0,         60),
}


@pytest.mark.parametrize('tier', list(TABLE))
def test_limits(tier):
    (name, devices, bills, mems, daily_pred, chats, chat_tokens, out_tokens,
     cost, budget, web) = TABLE[tier]
    p = UserProfile(user_type=tier)
    assert p.get_subscription_type() == name
    assert p.get_device_limit() == devices
    assert p.get_starred_bills_limit() == bills
    assert p.get_starred_memberships_limit() == mems
    assert p.get_daily_prediction_credits() == daily_pred
    assert p.get_chat_limit() == chats
    assert p.get_chat_token_limit() == chat_tokens
    assert p.get_chat_output_limit() == out_tokens
    assert p.get_monthly_cost_limit() == cost
    assert p.get_monthly_token_budget() == budget
    assert p.get_monthly_web_search_limit() == web


def test_plus_pro_sits_between_plus_and_premium():
    plus, pro, premium = (UserProfile(user_type=t) for t in (PLUS, PLUS_PRO, PREMIUM))
    for getter in ('get_starred_bills_limit', 'get_starred_memberships_limit',
                   'get_chat_limit', 'get_monthly_web_search_limit'):
        assert getattr(plus, getter)() < getattr(pro, getter)() < getattr(premium, getter)(), getter


def test_free_has_no_ai_access():
    p = UserProfile(user_type=FREE)
    assert p.get_chat_limit() == 0
    assert p.get_daily_prediction_credits() == 0
    assert p.get_monthly_web_search_limit() == 0


def test_unknown_tier_raises():
    with pytest.raises(KeyError):
        UserProfile(user_type=99).get_device_limit()
