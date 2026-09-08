# Copyright 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0

"""Least-privilege OAuth for the local read-only Analytics MCP profile."""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

READ_ONLY_ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
READ_ONLY_ANALYTICS_SCOPES = (READ_ONLY_ANALYTICS_SCOPE,)
_GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
_GOOGLE_AUTH_URIS = frozenset(
    {
        "https://accounts.google.com/o/oauth2/auth",
        "https://accounts.google.com/o/oauth2/v2/auth",
    }
)

_CLIENT_SECRETS_ENV = "ANALYTICS_MCP_OAUTH_CLIENT_SECRETS_FILE"
_CONFIG_DIR_ENV = "ANALYTICS_MCP_CONFIG_DIR"
_TOKEN_FILE_ENV = "ANALYTICS_MCP_TOKEN_FILE"


class CredentialConfigurationError(RuntimeError):
    """Raised when the local OAuth material violates the read-only policy."""


def _expanded_path(value: str | None) -> Path | None:
    if not value or not value.strip():
        return None
    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    # absolute() does not dereference a symbolic link, so later link checks keep
    # guarding the operator-selected credential path.
    return Path(os.path.abspath(expanded))


def get_config_dir() -> Path:
    """Return the credential directory without creating it."""
    configured = _expanded_path(os.environ.get(_CONFIG_DIR_ENV))
    if configured:
        return configured

    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "google-analytics-mcp"

    xdg_config_home = _expanded_path(os.environ.get("XDG_CONFIG_HOME"))
    if xdg_config_home:
        return xdg_config_home / "google-analytics-mcp"
    return Path.home() / ".config" / "google-analytics-mcp"


def get_token_path(explicit_path: str | None = None) -> Path:
    """Return the dedicated read-only token cache path."""
    configured = _expanded_path(
        explicit_path or os.environ.get(_TOKEN_FILE_ENV)
    )
    return configured or (get_config_dir() / "token.readonly.json")


def get_client_secrets_path(explicit_path: str | None = None) -> Path | None:
    """Return the operator-supplied desktop OAuth client path, if configured."""
    return _expanded_path(explicit_path or os.environ.get(_CLIENT_SECRETS_ENV))


def _require_external_oauth_path(path: Path, label: str) -> None:
    """Reject OAuth material stored inside this package's source checkout."""
    checkout_root = Path(__file__).resolve().parent.parent
    resolved_path = path.resolve(strict=False)
    if resolved_path == checkout_root or checkout_root in resolved_path.parents:
        raise CredentialConfigurationError(
            f"The {label} must be stored outside the Analytics MCP checkout."
        )


def _read_json_object(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise CredentialConfigurationError(
            "Refusing to read OAuth material through a symbolic link."
        )
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise CredentialConfigurationError(
            "The dedicated Analytics read-only OAuth token is missing. Run "
            "'analytics-mcp-auth login' in a terminal outside Codex."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CredentialConfigurationError(
            "The dedicated Analytics read-only OAuth token cannot be read. "
            "Run 'analytics-mcp-auth login --force' outside Codex."
        ) from exc

    if not isinstance(value, dict):
        raise CredentialConfigurationError(
            "The Analytics OAuth token must contain a JSON object."
        )
    return value


def _normalized_scopes(raw_scopes: Any) -> set[str]:
    if isinstance(raw_scopes, str):
        return {scope for scope in raw_scopes.split() if scope}
    if isinstance(raw_scopes, list):
        return {scope for scope in raw_scopes if isinstance(scope, str)}
    return set()


def validate_read_only_token_info(token_info: dict[str, Any]) -> None:
    """Reject tokens whose persisted scope is missing, broader, or ambiguous."""
    scopes = _normalized_scopes(
        token_info.get("scopes", token_info.get("scope"))
    )
    expected = set(READ_ONLY_ANALYTICS_SCOPES)
    if scopes != expected:
        raise CredentialConfigurationError(
            "The OAuth token is not an exact Analytics read-only grant. "
            "Do not reuse ADC or a token from another MCP server; run "
            "'analytics-mcp-auth login --force' outside Codex."
        )

    if token_info.get("token_uri") != _GOOGLE_TOKEN_URI:
        raise CredentialConfigurationError(
            "The OAuth token does not use Google's expected token endpoint."
        )
    for field_name in ("refresh_token", "client_id", "client_secret"):
        value = token_info.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise CredentialConfigurationError(
                "The OAuth token is missing required refresh metadata."
            )


def validate_desktop_client_info(client_info: Any) -> None:
    """Accept only a well-formed Google Desktop OAuth client configuration."""
    if not isinstance(client_info, dict):
        raise CredentialConfigurationError(
            "Use a Google OAuth client whose application type is Desktop app."
        )
    installed = client_info.get("installed")
    if not isinstance(installed, dict):
        raise CredentialConfigurationError(
            "Use a Google OAuth client whose application type is Desktop app."
        )
    if installed.get("auth_uri") not in _GOOGLE_AUTH_URIS:
        raise CredentialConfigurationError(
            "The Desktop OAuth client does not use Google's expected auth endpoint."
        )
    if installed.get("token_uri") != _GOOGLE_TOKEN_URI:
        raise CredentialConfigurationError(
            "The Desktop OAuth client does not use Google's expected token endpoint."
        )
    for field_name in ("client_id", "client_secret"):
        value = installed.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise CredentialConfigurationError(
                "The Desktop OAuth client is missing required client metadata."
            )


def _credentials_scopes(credentials: Credentials) -> set[str]:
    granted = credentials.granted_scopes or credentials.scopes
    return _normalized_scopes(granted)


def _write_token_atomically(credentials: Credentials, token_path: Path) -> None:
    """Persist a token without truncating a working credential on failure."""
    _require_external_oauth_path(token_path, "OAuth token")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        token_path.parent.chmod(stat.S_IRWXU)
    if token_path.is_symlink():
        raise CredentialConfigurationError(
            "Refusing to replace an OAuth token through a symbolic link."
        )

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".token-readonly-",
        suffix=".tmp",
        dir=token_path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(
            file_descriptor, "w", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(credentials.to_json())
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            temporary_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary_path, token_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def load_read_only_credentials() -> Credentials:
    """Load and, when possible, refresh the dedicated non-interactive token."""
    token_path = get_token_path()
    _require_external_oauth_path(token_path, "OAuth token")
    token_info = _read_json_object(token_path)
    validate_read_only_token_info(token_info)

    try:
        credentials = Credentials.from_authorized_user_info(
            token_info,
            scopes=list(READ_ONLY_ANALYTICS_SCOPES),
        )
    except (ValueError, TypeError) as exc:
        raise CredentialConfigurationError(
            "The Analytics read-only OAuth token is invalid. Run "
            "'analytics-mcp-auth login --force' outside Codex."
        ) from exc

    if credentials.valid:
        return credentials

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception as exc:
            raise CredentialConfigurationError(
                "The Analytics read-only OAuth token could not be refreshed. "
                "Run 'analytics-mcp-auth login --force' outside Codex."
            ) from exc
        if _credentials_scopes(credentials) != set(READ_ONLY_ANALYTICS_SCOPES):
            raise CredentialConfigurationError(
                "Google returned an OAuth grant outside the exact Analytics "
                "read-only scope; the token was not saved."
            )
        _write_token_atomically(credentials, token_path)
        return credentials

    raise CredentialConfigurationError(
        "The Analytics read-only OAuth token is invalid or expired. Run "
        "'analytics-mcp-auth login --force' outside Codex."
    )


def get_noninteractive_auth_status() -> str:
    """Inspect local configuration without refreshing or contacting Google."""
    token_path = get_token_path()
    try:
        _require_external_oauth_path(token_path, "OAuth token")
        if not token_path.exists():
            return "oauth_token_missing"
        token_info = _read_json_object(token_path)
        validate_read_only_token_info(token_info)
    except CredentialConfigurationError:
        return "oauth_token_invalid_or_not_read_only"
    return "oauth_token_present_not_network_validated"


def authenticate_read_only(
    *,
    client_secrets: str | None = None,
    token_file: str | None = None,
    force: bool = False,
    timeout_seconds: int = 300,
) -> Path:
    """Run the human-visible desktop OAuth flow and atomically save its token."""
    client_path = get_client_secrets_path(client_secrets)
    if client_path is None:
        raise CredentialConfigurationError(
            f"Set {_CLIENT_SECRETS_ENV} or pass --client-secrets."
        )
    _require_external_oauth_path(client_path, "OAuth client configuration")
    if client_path.is_symlink() or not client_path.is_file():
        raise CredentialConfigurationError(
            "The OAuth client configuration must be a regular local file."
        )

    try:
        with client_path.open("r", encoding="utf-8") as handle:
            client_info = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise CredentialConfigurationError(
            "The OAuth client configuration could not be read."
        ) from exc
    validate_desktop_client_info(client_info)

    target = get_token_path(token_file)
    _require_external_oauth_path(target, "OAuth token")
    if target.exists() and not force:
        raise CredentialConfigurationError(
            "A read-only Analytics token already exists. Pass --force only "
            "when you intentionally want to replace it."
        )

    flow = InstalledAppFlow.from_client_config(
        client_info,
        scopes=list(READ_ONLY_ANALYTICS_SCOPES),
        autogenerate_code_verifier=True,
    )
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        timeout_seconds=timeout_seconds,
        open_browser=True,
        prompt="consent",
        include_granted_scopes="false",
    )
    if _credentials_scopes(credentials) != set(READ_ONLY_ANALYTICS_SCOPES):
        raise CredentialConfigurationError(
            "Google returned an OAuth grant outside the exact Analytics "
            "read-only scope; the token was not saved."
        )
    _write_token_atomically(credentials, target)
    return target


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create or inspect the dedicated Google Analytics read-only OAuth "
            "token used by the local MCP server."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser(
        "login", help="Open the system browser for a read-only Google login."
    )
    login.add_argument("--client-secrets")
    login.add_argument("--token-file")
    login.add_argument("--force", action="store_true")
    login.add_argument("--timeout-seconds", type=int, default=300)

    subparsers.add_parser(
        "status", help="Inspect the token cache without contacting Google."
    )
    return parser


def main() -> None:
    """Run the standalone credential helper; this is never an MCP tool."""
    arguments = _build_argument_parser().parse_args()
    try:
        if arguments.command == "status":
            print(get_noninteractive_auth_status())
            return
        token_path = authenticate_read_only(
            client_secrets=arguments.client_secrets,
            token_file=arguments.token_file,
            force=arguments.force,
            timeout_seconds=arguments.timeout_seconds,
        )
        print(f"Saved a dedicated Analytics read-only token to {token_path}")
    except CredentialConfigurationError as exc:
        raise SystemExit(f"Authentication setup failed: {exc}") from exc


if __name__ == "__main__":
    main()
