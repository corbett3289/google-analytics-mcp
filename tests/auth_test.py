# Copyright 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Security invariants for the dedicated read-only OAuth helper."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock, patch

from google.oauth2.credentials import Credentials

from analytics_mcp import auth


def _credentials() -> Credentials:
    return Credentials(
        token="access-token-for-test-only",
        refresh_token="refresh-token-for-test-only",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client-id-for-test-only",
        client_secret="client-secret-for-test-only",
        scopes=list(auth.READ_ONLY_ANALYTICS_SCOPES),
    )


def _token_info() -> dict:
    return json.loads(_credentials().to_json())


def _desktop_client_info() -> dict:
    return {
        "installed": {
            "client_id": "client-id-for-test-only",
            "client_secret": "client-secret-for-test-only",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


class TestReadOnlyOAuth(unittest.TestCase):
    def test_exact_scope_is_required(self):
        token_info = _token_info()
        auth.validate_read_only_token_info(token_info)
        with self.assertRaises(auth.CredentialConfigurationError):
            broader_token = token_info.copy()
            broader_token["scopes"] = [
                auth.READ_ONLY_ANALYTICS_SCOPE,
                "https://www.googleapis.com/auth/cloud-platform",
            ]
            auth.validate_read_only_token_info(broader_token)
        with self.assertRaises(auth.CredentialConfigurationError):
            auth.validate_read_only_token_info({})

    def test_untrusted_oauth_endpoints_are_rejected(self):
        token_info = _token_info()
        token_info["token_uri"] = "https://example.invalid/token"
        with self.assertRaises(auth.CredentialConfigurationError):
            auth.validate_read_only_token_info(token_info)

        client_info = _desktop_client_info()
        client_info["installed"]["token_uri"] = "https://example.invalid/token"
        with self.assertRaises(auth.CredentialConfigurationError):
            auth.validate_desktop_client_info(client_info)

    def test_real_oauth_library_builds_exact_scope_pkce_request(self):
        flow = auth.InstalledAppFlow.from_client_config(
            _desktop_client_info(),
            scopes=list(auth.READ_ONLY_ANALYTICS_SCOPES),
            autogenerate_code_verifier=True,
        )
        authorization_url, _ = flow.authorization_url(
            prompt="consent",
            include_granted_scopes="false",
        )
        query = parse_qs(urlparse(authorization_url).query)

        self.assertEqual(
            query["scope"],
            [auth.READ_ONLY_ANALYTICS_SCOPE],
        )
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertTrue(query["code_challenge"][0])
        self.assertEqual(query["include_granted_scopes"], ["false"])

    def test_atomic_write_replaces_token(self):
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "token.readonly.json"
            token_path.write_text('{"old": true}', encoding="utf-8")
            auth._write_token_atomically(_credentials(), token_path)
            token_info = json.loads(token_path.read_text(encoding="utf-8"))
            self.assertEqual(
                token_info["scopes"], list(auth.READ_ONLY_ANALYTICS_SCOPES)
            )
            self.assertFalse(any(Path(directory).glob(".token-readonly-*.tmp")))

    def test_failed_serialization_preserves_existing_token(self):
        broken_credentials = MagicMock()
        broken_credentials.to_json.side_effect = RuntimeError("test failure")
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "token.readonly.json"
            token_path.write_text('{"old": true}', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                auth._write_token_atomically(broken_credentials, token_path)
            self.assertEqual(
                token_path.read_text(encoding="utf-8"), '{"old": true}'
            )

    def test_missing_token_fails_without_starting_oauth(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.dict(
                    os.environ,
                    {"ANALYTICS_MCP_CONFIG_DIR": directory},
                    clear=True,
                ),
                patch.object(
                    auth.InstalledAppFlow, "from_client_secrets_file"
                ) as flow,
            ):
                with self.assertRaises(auth.CredentialConfigurationError):
                    auth.load_read_only_credentials()
                flow.assert_not_called()

    def test_oauth_material_inside_checkout_is_rejected(self):
        checkout_root = Path(auth.__file__).resolve().parent.parent
        with self.assertRaises(auth.CredentialConfigurationError):
            auth._require_external_oauth_path(
                checkout_root / "token.readonly.json", "OAuth token"
            )

    def test_login_uses_desktop_loopback_and_exact_scope(self):
        credentials = _credentials()
        flow = MagicMock()
        flow.run_local_server.return_value = credentials
        with tempfile.TemporaryDirectory() as directory:
            client_path = Path(directory) / "client_secrets.json"
            client_info = _desktop_client_info()
            client_path.write_text(json.dumps(client_info), encoding="utf-8")
            token_path = Path(directory) / "token.readonly.json"
            with patch.object(
                auth.InstalledAppFlow,
                "from_client_config",
                return_value=flow,
            ) as from_config:
                result = auth.authenticate_read_only(
                    client_secrets=str(client_path),
                    token_file=str(token_path),
                )
            self.assertEqual(result, token_path.resolve())
            from_config.assert_called_once_with(
                client_info,
                scopes=list(auth.READ_ONLY_ANALYTICS_SCOPES),
                autogenerate_code_verifier=True,
            )
            flow.run_local_server.assert_called_once_with(
                host="127.0.0.1",
                port=0,
                timeout_seconds=300,
                open_browser=True,
                prompt="consent",
                include_granted_scopes="false",
            )


if __name__ == "__main__":
    unittest.main()
