from __future__ import annotations

import unittest

from owner_ids import parse_owner_ids


class OwnerIdsTest(unittest.TestCase):
    def test_missing_value_fails_closed(self) -> None:
        self.assertEqual(parse_owner_ids(None), frozenset())
        self.assertEqual(parse_owner_ids(""), frozenset())

    def test_comma_and_whitespace_separators_and_duplicates(self) -> None:
        self.assertEqual(parse_owner_ids("123, 456\n123"), frozenset({123, 456}))

    def test_invalid_values_do_not_grant_owner_access(self) -> None:
        self.assertEqual(
            parse_owner_ids("invalid,-7,0,123456789012345678901"),
            frozenset(),
        )


if __name__ == "__main__":
    unittest.main()
