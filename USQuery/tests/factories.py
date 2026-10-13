"""Plain-function builders for test data.

Bill and Vote primary keys are encoded integers; the builders compute them the
same way production does so fixtures can't drift from the real encoding.
"""

import datetime
import itertools

from django.utils import timezone

from BillQuery.bill_reference import encode_bill_id

_seq = itertools.count(1)


def _n():
    return next(_seq)


def make_congress(num=119, start_year=None, end_year=None):
    from SenateQuery.models import Congress
    start_year = start_year if start_year is not None else 1789 + 2 * (num - 1)
    congress, _ = Congress.objects.get_or_create(
        congress_num=num,
        defaults={'start_year': start_year, 'end_year': end_year},
    )
    return congress


def make_member(member_id=None, first='Test', last=None, **kw):
    from SenateQuery.models import Member
    n = _n()
    last = last or f'Member{n}'
    return Member.objects.create(
        id=member_id or f'T{n:06d}',
        first_name=first,
        last_name=last,
        full_name=f'{first} {last}',
        **kw,
    )


def make_membership(congress=None, member=None, house=True, state='CA',
                    party='Democratic', district_num=1, **kw):
    from SenateQuery.models import Membership
    congress = congress or make_congress()
    member = member or make_member()
    return Membership.objects.create(
        congress=congress,
        member=member,
        house=house,
        state=state,
        geoid=kw.pop('geoid', '0601'),
        party=party,
        district_num=district_num if house else None,
        **kw,
    )


def bill_id(congress=119, type_code=4, num=1):
    return encode_bill_id(congress, type_code, num)


def make_bill(congress=119, type_code=4, num=None, sponsor=None,
              title=None, origin_date=None, latest_action=None, **kw):
    from BillQuery.models import Bill
    num = num if num is not None else _n()
    make_congress(congress)
    sponsor = sponsor or make_membership(congress=make_congress(congress))
    today = datetime.date(2026, 1, 15)
    return Bill.objects.create(
        id=bill_id(congress, type_code, num),
        sponsor=sponsor,
        title=title or f'Test Bill {num}',
        origin_date=origin_date or today,
        latest_action=latest_action or origin_date or today,
        **kw,
    )


def vote_id(congress=119, house=True, session=1, num=1):
    """CCC_H_S_XXXXX, see BillQuery.models.Vote."""
    return congress * 10_000_000 + int(house) * 1_000_000 + session * 100_000 + num


def make_vote(bill=None, congress=119, house=True, session=1, num=None,
              when=None, question='On Passage', result='Passed', **kw):
    from BillQuery.models import Vote
    num = num if num is not None else _n()
    return Vote.objects.create(
        id=vote_id(congress, house, session, num),
        congress=make_congress(congress),
        house=house,
        bill=bill,
        dateTime=when or timezone.make_aware(datetime.datetime(2026, 1, 15, 12, 0)),
        question=question,
        result=result,
        **kw,
    )


def make_user(tier=0, active=True, email=None, password='pass-1234-word', **profile_kw):
    from django.contrib.auth.models import User
    from app.models import UserProfile
    email = email or f'user{_n()}@example.com'
    user = User.objects.create_user(
        username=email, email=email, password=password, is_active=active)
    UserProfile.objects.create(user=user, user_type=tier, **profile_kw)
    return user


def make_apple_identity_token(key, kid='kid-1', aud='com.usquery.test', expires_in=300, **claims):
    """RS256 Sign in with Apple identity token signed with `key` (a throwaway
    cryptography RSA private key)."""
    import jwt
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {'iss': 'https://appleid.apple.com', 'aud': aud, 'sub': 'a-1',
               'iat': now, 'exp': now + datetime.timedelta(seconds=expires_in), **claims}
    return jwt.encode(payload, key, algorithm='RS256', headers={'kid': kid})


def jwt_headers(user):
    """Bearer header for DRF endpoints that declare JWTAuthentication
    explicitly (a session login is not enough for those)."""
    from rest_framework_simplejwt.tokens import RefreshToken
    return {'HTTP_AUTHORIZATION': f'Bearer {RefreshToken.for_user(user).access_token}'}
