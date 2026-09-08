# Copyright 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Tests that pin the complete model-visible MCP surface."""

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from analytics_mcp import coordinator, policy
from analytics_mcp.tools.capabilities import get_capabilities


class TestCoordinator(unittest.TestCase):
    def test_list_tools_is_exactly_the_reviewed_allowlist(self):
        tools = asyncio.run(coordinator.list_tools())
        self.assertEqual(
            tuple(tool.name for tool in tools), policy.READ_ONLY_TOOL_NAMES
        )

    def test_all_tools_are_annotated_read_only_and_open_world(self):
        tools = asyncio.run(coordinator.list_tools())
        for tool in tools:
            with self.subTest(tool=tool.name):
                self.assertEqual(
                    tool.annotations.model_dump(exclude_none=True),
                    {"readOnlyHint": True, "openWorldHint": True},
                )

    def test_no_authentication_or_mutation_tool_is_visible(self):
        names = set(policy.READ_ONLY_TOOL_NAMES)
        forbidden_fragments = (
            "auth",
            "login",
            "create",
            "delete",
            "update",
            "patch",
            "write",
        )
        for fragment in forbidden_fragments:
            self.assertFalse(
                any(fragment in name for name in names),
                f"Unexpected model-visible {fragment!r} tool",
            )

    def test_capabilities_is_noninteractive_and_fail_closed(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "ANALYTICS_MCP_CONFIG_DIR": directory,
                    "ANALYTICS_MCP_ALLOWED_PROPERTY_IDS": "",
                    "ANALYTICS_MCP_MAX_ROWS": "250",
                    "ANALYTICS_MCP_MAX_RESPONSE_BYTES": "500000",
                },
                clear=True,
            ),
        ):
            capabilities = asyncio.run(get_capabilities())
        self.assertEqual(capabilities["access_mode"], "read_only")
        self.assertTrue(capabilities["auth_status_is_noninteractive"])
        self.assertEqual(capabilities["auth_status"], "oauth_token_missing")
        self.assertEqual(
            capabilities["property_access"]["mode"],
            "deny_all_until_configured",
        )
        self.assertEqual(capabilities["max_report_rows"], 250)
        self.assertEqual(capabilities["max_response_bytes"], 500000)

    def test_unexpected_error_details_are_not_model_visible(self):
        class UnexpectedFailureTool:
            async def run_async(self, *, args, tool_context):
                del args, tool_context
                raise FileNotFoundError(r"C:\sensitive\account-name.json")

        with patch.dict(
            coordinator.tool_map,
            {"get_capabilities": UnexpectedFailureTool()},
        ):
            result = asyncio.run(
                coordinator.call_mcp_tool("get_capabilities", {})
            )

        self.assertTrue(result.isError)
        response = json.loads(result.content[0].text)
        self.assertEqual(response["error_type"], "FileNotFoundError")
        self.assertNotIn("sensitive", response["error"])
        self.assertNotIn("account-name", response["error"])


if __name__ == "__main__":
    unittest.main()
