# Copyright 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""End-to-end local STDIO handshake without Google credentials."""

import json
import os
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from analytics_mcp.policy import READ_ONLY_TOOL_NAMES


class TestStdioServer(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_and_list_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment.update(
                {
                    "ANALYTICS_MCP_CONFIG_DIR": directory,
                    "ANALYTICS_MCP_ALLOWED_PROPERTY_IDS": "",
                    "ANALYTICS_MCP_MAX_ROWS": "1000",
                    "PYTHONNOUSERSITE": "1",
                }
            )
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "analytics_mcp.server"],
                cwd=os.getcwd(),
                env=environment,
            )
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    initialize_result = await session.initialize()
                    tools_result = await session.list_tools()
                    capabilities_result = await session.call_tool(
                        "get_capabilities", {}
                    )
                    denied_result = await session.call_tool(
                        "get_property_details", {"property_id": 123456789}
                    )

        self.assertIn("read-only profile", initialize_result.serverInfo.name)
        self.assertEqual(
            tuple(tool.name for tool in tools_result.tools),
            READ_ONLY_TOOL_NAMES,
        )
        for tool in tools_result.tools:
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertTrue(tool.annotations.openWorldHint)

        capabilities = json.loads(capabilities_result.content[0].text)
        self.assertEqual(capabilities["auth_status"], "oauth_token_missing")
        self.assertEqual(
            capabilities["property_access"]["mode"],
            "deny_all_until_configured",
        )

        denied = json.loads(denied_result.content[0].text)
        self.assertTrue(denied_result.isError)
        self.assertEqual(denied["error_type"], "PropertyAccessDenied")


if __name__ == "__main__":
    unittest.main()
