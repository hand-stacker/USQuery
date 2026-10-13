"""Bill id encoding, plus free-text bill-reference resolution ("H.R 8364").

The reference resolver is not included in this public snapshot; the stubs
below make search behave as if no keyword were a bill reference.
"""


def encode_bill_id(congress_num, type_code, num):
    """Bill id for a (congress, type, number) triple: CCC_T_XXXX, or CCC_T_XXXXX
    once the bill number passes 9999 (see models.Bill)."""
    if num > 9999:
        return congress_num * 1_000_000 + type_code * 100_000 + num
    return congress_num * 100_000 + type_code * 10_000 + num


def parse_bill_reference(keyword, bill_type='!'):
    return None


def bill_reference_candidate_ids(keyword, congress_num, bill_type='!', limit=200):
    return []
