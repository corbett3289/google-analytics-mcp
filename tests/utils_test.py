# Copyright 2025 Google LLC All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test cases for the utils module."""

import unittest
from unittest.mock import patch

from analytics_mcp.tools import utils


class TestUtils(unittest.TestCase):
    """Test cases for the utils module."""

    def test_construct_property_rn(self):
        """Tests construct_property_rn using valid input."""
        with patch.dict(
            "os.environ",
            {"ANALYTICS_MCP_ALLOWED_PROPERTY_IDS": "12345"},
        ):
            self.assertEqual(
                utils.construct_property_rn(12345),
                "properties/12345",
                "Numeric property ID should b considered valid",
            )
            self.assertEqual(
                utils.construct_property_rn("12345"),
                "properties/12345",
                "Numeric property ID as string should be considered valid",
            )
            self.assertEqual(
                utils.construct_property_rn(" 12345  "),
                "properties/12345",
                "Whitespace around property ID should be considered valid",
            )
            self.assertEqual(
                utils.construct_property_rn("properties/12345"),
                "properties/12345",
                "Full resource name should be considered valid",
            )

    def test_construct_property_rn_enforces_allowlist(self):
        with patch.dict(
            "os.environ",
            {"ANALYTICS_MCP_ALLOWED_PROPERTY_IDS": "12345"},
        ):
            with self.assertRaises(PermissionError):
                utils.construct_property_rn(67890)

    def test_construct_property_rn_denies_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(PermissionError):
                utils.construct_property_rn(12345)

    def test_filter_account_summaries(self):
        summaries = [
            {
                "account": "accounts/1",
                "display_name": "Example account",
                "property_summaries": [
                    {"property": "properties/12345", "display_name": "Allowed"},
                    {"property": "properties/67890", "display_name": "Denied"},
                ],
            }
        ]
        with patch.dict(
            "os.environ",
            {"ANALYTICS_MCP_ALLOWED_PROPERTY_IDS": "12345"},
        ):
            filtered = utils.filter_account_summaries(summaries)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(
            filtered[0]["property_summaries"],
            [{"property": "properties/12345", "display_name": "Allowed"}],
        )
        self.assertEqual(len(summaries[0]["property_summaries"]), 2)

    def test_construct_property_rn_invalid_input(self):
        """Tests that construct_property_rn raises a ValueError for invalid input."""
        with self.assertRaises(ValueError, msg="None should fail"):
            utils.construct_property_rn(None)
        with self.assertRaises(ValueError, msg="Empty string should fail"):
            utils.construct_property_rn("")
        with self.assertRaises(
            ValueError, msg="Non-numeric string should fail"
        ):
            utils.construct_property_rn("abc")
        with self.assertRaises(
            ValueError, msg="Resource name without ID should fail"
        ):
            utils.construct_property_rn("properties/")
        with self.assertRaises(
            ValueError, msg="Resource name with non-numeric ID should fail"
        ):
            utils.construct_property_rn("properties/abc")
        with self.assertRaises(
            ValueError,
            msg="Resource name with more than 2 components should fail",
        ):
            utils.construct_property_rn("properties/123/abc")
