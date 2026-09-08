# Copyright 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Fail-closed policy controls for AI-mediated Analytics access."""

from __future__ import annotations

import os

READ_ONLY_TOOL_NAMES = (
    "get_capabilities",
    "get_account_summaries",
    "list_google_ads_links",
    "get_property_details",
    "list_property_annotations",
    "get_custom_dimensions_and_metrics",
    "run_report",
    "run_realtime_report",
    "run_funnel_report",
    "run_conversions_report",
)

_ALLOWED_PROPERTIES_ENV = "ANALYTICS_MCP_ALLOWED_PROPERTY_IDS"
_MAX_ROWS_ENV = "ANALYTICS_MCP_MAX_ROWS"
_MAX_RESPONSE_BYTES_ENV = "ANALYTICS_MCP_MAX_RESPONSE_BYTES"
DEFAULT_MAX_REPORT_ROWS = 1_000
HARD_MAX_REPORT_ROWS = 10_000
DEFAULT_MAX_RESPONSE_BYTES = 1_000_000
HARD_MAX_RESPONSE_BYTES = 4_000_000


class SafePolicyError(Exception):
    """Marker for policy errors that are safe to return to the MCP client."""


class PolicyConfigurationError(SafePolicyError, ValueError):
    """Raised when an operator-managed environment setting is invalid."""


class ToolInputError(SafePolicyError, ValueError):
    """Raised when an MCP argument violates a local safety constraint."""


class PropertyAccessDenied(SafePolicyError, PermissionError):
    """Raised when an Analytics property is outside the local allowlist."""


class ResponseLimitExceeded(SafePolicyError, ValueError):
    """Raised before oversized serialized output is returned to the model."""


def get_allowed_property_ids() -> frozenset[int] | None:
    """Return allowed IDs, None for explicit wildcard, or empty for deny-all."""
    raw_value = os.environ.get(_ALLOWED_PROPERTIES_ENV, "").strip()
    if raw_value == "*":
        return None
    if not raw_value:
        return frozenset()

    property_ids: set[int] = set()
    for value in raw_value.split(","):
        normalized = value.strip()
        if normalized.startswith("properties/"):
            normalized = normalized.removeprefix("properties/")
        if not normalized.isdigit():
            raise PolicyConfigurationError(
                f"{_ALLOWED_PROPERTIES_ENV} must contain comma-separated "
                "numeric IDs, 'properties/ID' values, or '*'."
            )
        property_id = int(normalized)
        if property_id < 1:
            raise PolicyConfigurationError(
                f"{_ALLOWED_PROPERTIES_ENV} property IDs must be positive integers."
            )
        property_ids.add(property_id)
    return frozenset(property_ids)


def require_property_access(property_id: int) -> None:
    """Raise before an API call when a property is outside operator policy."""
    if isinstance(property_id, bool) or not isinstance(property_id, int):
        raise ToolInputError("Google Analytics property IDs must be integers.")
    if property_id < 1:
        raise ToolInputError(
            "Google Analytics property IDs must be positive integers."
        )
    allowed = get_allowed_property_ids()
    if allowed is not None and property_id not in allowed:
        raise PropertyAccessDenied(
            "That Google Analytics property is not in the operator-managed "
            f"{_ALLOWED_PROPERTIES_ENV} allowlist."
        )


def property_access_summary() -> dict[str, int | str]:
    """Describe policy without disclosing property identifiers."""
    allowed = get_allowed_property_ids()
    if allowed is None:
        return {"mode": "all_properties_explicitly_allowed"}
    if not allowed:
        return {"mode": "deny_all_until_configured", "count": 0}
    return {"mode": "allowlist", "count": len(allowed)}


def get_max_report_rows() -> int:
    """Return the configured row ceiling, capped by a hard safety maximum."""
    raw_value = os.environ.get(_MAX_ROWS_ENV, str(DEFAULT_MAX_REPORT_ROWS))
    try:
        configured = int(raw_value)
    except ValueError as exc:
        raise PolicyConfigurationError(
            f"{_MAX_ROWS_ENV} must be an integer."
        ) from exc
    if configured < 1 or configured > HARD_MAX_REPORT_ROWS:
        raise PolicyConfigurationError(
            f"{_MAX_ROWS_ENV} must be between 1 and "
            f"{HARD_MAX_REPORT_ROWS:,}."
        )
    return configured


def validate_report_limit(limit: int | None) -> int:
    """Return an explicit bounded limit for every row-producing request."""
    ceiling = get_max_report_rows()
    if limit is None:
        return ceiling
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ToolInputError("limit must be an integer.")
    if limit < 1 or limit > ceiling:
        raise ToolInputError(
            f"limit must be between 1 and the configured ceiling of {ceiling:,}."
        )
    return limit


def validate_report_offset(offset: int | None) -> int | None:
    if offset is None:
        return None
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ToolInputError("offset must be a non-negative integer.")
    return offset


def get_max_response_bytes() -> int:
    """Return the serialized response ceiling for model-visible output."""
    raw_value = os.environ.get(
        _MAX_RESPONSE_BYTES_ENV, str(DEFAULT_MAX_RESPONSE_BYTES)
    )
    try:
        configured = int(raw_value)
    except ValueError as exc:
        raise PolicyConfigurationError(
            f"{_MAX_RESPONSE_BYTES_ENV} must be an integer."
        ) from exc
    if configured < 1 or configured > HARD_MAX_RESPONSE_BYTES:
        raise PolicyConfigurationError(
            f"{_MAX_RESPONSE_BYTES_ENV} must be between 1 and "
            f"{HARD_MAX_RESPONSE_BYTES:,}."
        )
    return configured


def validate_response_size(response_text: str) -> None:
    """Reject oversized output as a unit instead of returning invalid partial JSON."""
    response_bytes = len(response_text.encode("utf-8"))
    ceiling = get_max_response_bytes()
    if response_bytes > ceiling:
        raise ResponseLimitExceeded(
            f"The serialized response is {response_bytes:,} bytes, above the "
            f"configured {ceiling:,}-byte ceiling. Narrow the date range, "
            "dimensions, filters, or row limit and retry."
        )
