"""Small pure helpers: RAG chunking, GraphQL truncation, floor-notification
timezones, end-of-congress expiry map."""

import pytest

from app.management.commands.send_floor_notifications import _local_to_utc_hour
from strawberryAPI.graphql.utils import _truncate




class TestTruncate:
    def test_short_unchanged(self):
        assert _truncate('hello', 10) == 'hello'

    def test_exact_length_unchanged(self):
        assert _truncate('a' * 10, 10) == 'a' * 10

    def test_word_boundary(self):
        assert _truncate('the quick brown fox jumps', 15) == 'the quick...'

    def test_no_space_hard_cut(self):
        assert _truncate('a' * 20, 10) == 'aaaaaaa...'

    def test_none_and_non_string(self):
        assert _truncate(None) == ''
        assert _truncate(12345, 10) == '12345'

    def test_default_length(self):
        assert len(_truncate('word ' * 100)) <= 240


class TestLocalToUtcHour:
    @pytest.mark.parametrize('hour, tz, expected', [
        (9, 'EST', 14),
        (9, 'EDT', 13),
        (20, 'PST', 4),     # wraps past midnight
        (23, 'HST', 9),
        (0, 'UTC', 0),
        (9, 'est', 14),     # case-insensitive
        (9, None, 9),       # missing -> UTC
        (9, 'XYZ', 9),      # unknown -> UTC
    ])
    def test_conversion(self, hour, tz, expected):
        assert _local_to_utc_hour(hour, tz) == expected

    def test_fixed_offsets_ignore_dst(self):
        # Documented limitation: 'PST' is UTC-8 year-round.
        assert _local_to_utc_hour(12, 'PST') == 20


