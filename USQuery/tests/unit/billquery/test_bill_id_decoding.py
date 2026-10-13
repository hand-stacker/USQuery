"""Bill's id decoders, on unsaved instances (no DB).

Ids are CCC_T_XXXX, or CCC_T_XXXXX once the bill number passes 9999; every
decoder branches on id >= 1e8.
"""

import pytest

from BillQuery.bill_reference import encode_bill_id
from BillQuery.models import Bill

TYPES = [
    (0, 'S', 's', 'Senate', 'S'),
    (1, 'S.RES', 'sres', 'Senate', 'S'),
    (2, 'S.J.RES', 'sjres', 'Senate', 'S'),
    (3, 'S.CON.RES', 'sconres', 'Senate', 'S'),
    (4, 'HR', 'hr', 'House', 'H'),
    (5, 'H.RES', 'hres', 'House', 'H'),
    (6, 'H.J.RES', 'hjres', 'House', 'H'),
    (7, 'H.CON.RES', 'hconres', 'House', 'H'),
]
NUMS = [1, 42, 9999, 10000, 12345, 99999]


@pytest.mark.parametrize('num', NUMS)
@pytest.mark.parametrize('code, type_str, type_url, origin, origin_code', TYPES)
def test_decoders_round_trip(code, type_str, type_url, origin, origin_code, num):
    bill = Bill(id=encode_bill_id(119, code, num))
    assert bill.getCongress() == 119
    assert bill.getNum() == num
    assert bill.getNumStr() == str(num)
    assert bill.getType() == type_str
    assert bill.getTypeURL() == type_url
    assert bill.getOrigin() == origin
    assert bill.getOriginCode() == origin_code
    assert bill.getURL() == f'119/{type_url}/{num}'
    assert str(bill) == f'{type_str} {num}'


@pytest.mark.parametrize('congress', [110, 115, 118, 119, 120])
def test_congress_decoding_across_congresses(congress):
    assert Bill(id=encode_bill_id(congress, 4, 1)).getCongress() == congress
    assert Bill(id=encode_bill_id(congress, 4, 10001)).getCongress() == congress


def test_status_text():
    assert Bill(id=1, status=True).getStatus() == 'Became Public Law'
    assert Bill(id=1, status=False).getStatus() == 'Still Just A Bill'
