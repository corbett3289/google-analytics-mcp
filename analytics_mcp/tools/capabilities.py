# Copyright 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Non-interactive discovery for the hardened local profile."""

from analytics_mcp.auth import (
    READ_ONLY_ANALYTICS_SCOPES,
    get_noninteractive_auth_status,
)
from analytics_mcp.policy import (
    READ_ONLY_TOOL_NAMES,
    get_max_report_rows,
    get_max_response_bytes,
    property_access_summary,
)


async def get_capabilities() -> dict:
    """Return the read-only policy and local auth status without network I/O."""
    auth_status = get_noninteractive_auth_status()
    return {
        "server": "Google Analytics MCP Server (Codex read-only profile)",
        "access_mode": "read_only",
        "oauth_scopes": list(READ_ONLY_ANALYTICS_SCOPES),
        "auth_status": auth_status,
        "auth_status_is_noninteractive": True,
        "transport": "stdio",
        "property_access": property_access_summary(),
        "max_report_rows": get_max_report_rows(),
        "max_response_bytes": get_max_response_bytes(),
        "tools": list(READ_ONLY_TOOL_NAMES),
        "next_step": (
            "Run analytics-mcp-auth login in a local terminal outside Codex."
            if auth_status != "oauth_token_present_not_network_validated"
            else "The token exists; make a small approved read call to validate it."
        ),
    }
