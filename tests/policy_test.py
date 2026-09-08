# Copyright 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Tests for fail-closed property and output controls."""

import os
import unittest
from unittest.mock import patch

from analytics_mcp import policy


class TestPolicy(unittest.TestCase):
    def test_property_allowlist_defaults_to_deny_all(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(policy.get_allowed_property_ids(), frozenset())
            with self.assertRaises(PermissionError):
                policy.require_property_access(12345)

    def test_property_allowlist_accepts_ids_and_explicit_wildcard(self):
        with patch.dict(
            os.environ,
            {"ANALYTICS_MCP_ALLOWED_PROPERTY_IDS": "123, properties/456"},
            clear=True,
        ):
            self.assertEqual(
                policy.get_allowed_property_ids(), frozenset({123, 456})
            )
            policy.require_property_access(456)
        with patch.dict(
            os.environ,
            {"ANALYTICS_MCP_ALLOWED_PROPERTY_IDS": "*"},
            clear=True,
        ):
            self.assertIsNone(policy.get_allowed_property_ids())
            policy.require_property_access(999)

    def test_property_ids_must_be_positive_integers(self):
        with patch.dict(
            os.environ,
            {"ANALYTICS_MCP_ALLOWED_PROPERTY_IDS": "0"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                policy.get_allowed_property_ids()
        with self.assertRaises(ValueError):
            policy.require_property_access(True)

    def test_report_limit_defaults_and_ceiling(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                policy.validate_report_limit(None),
                policy.DEFAULT_MAX_REPORT_ROWS,
            )
        with patch.dict(
            os.environ,
            {"ANALYTICS_MCP_MAX_ROWS": "500"},
            clear=True,
        ):
            self.assertEqual(policy.validate_report_limit(None), 500)
            self.assertEqual(policy.validate_report_limit(250), 250)
            with self.assertRaises(ValueError):
                policy.validate_report_limit(501)

    def test_offset_must_be_non_negative(self):
        self.assertIsNone(policy.validate_report_offset(None))
        self.assertEqual(policy.validate_report_offset(0), 0)
        with self.assertRaises(ValueError):
            policy.validate_report_offset(-1)

    def test_response_size_ceiling(self):
        with patch.dict(
            os.environ,
            {"ANALYTICS_MCP_MAX_RESPONSE_BYTES": "10"},
            clear=True,
        ):
            policy.validate_response_size("1234567890")
            with self.assertRaises(ValueError):
                policy.validate_response_size("12345678901")


if __name__ == "__main__":
    unittest.main()
