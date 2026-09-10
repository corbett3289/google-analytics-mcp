# Changelog

## 2026-09-10 - Codex startup resilience and lifecycle verification

- Investigated a project-chat resume failure that coincided with many sibling
  local MCP processes. The direct failure was another required MCP server's
  initialization handshake, not an Analytics MCP functional failure.
- Changed the reviewed Codex example and recommendation to keep Analytics
  enabled with `required = false`, so a transient Analytics startup failure
  cannot abort unrelated Codex task startup or resume.
- Verified that this server does not spawn copies of itself and that idle and
  initialized STDIO processes exit cleanly after standard-input EOF and after
  their parent client disconnects on Windows.
- Added a process-level EOF shutdown regression test. No speculative singleton
  or shutdown mechanism was added because the existing lifecycle passed.
- Documented that multiple sibling STDIO instances may be legitimate—one per
  Codex client or agent host—and that persistent single-process reuse would be
  a separately reviewed HTTP or broker architecture change.

## 2026-09-08 - Codex read-only hardening

- Cloned and reviewed upstream commit
  `a8ca729d4a8fa99bffe87962c17c0539c6aa9da7`.
- Added a standalone Desktop OAuth/PKCE helper using only
  `analytics.readonly`; removed ambient Application Default Credentials from
  the local server path.
- Added separate atomic `token.readonly.json` persistence outside the checkout.
- Validated trusted Google OAuth endpoints and required refresh metadata before
  using persisted credentials.
- Added a non-interactive `get_capabilities` tool and pinned the complete
  model-visible tool allowlist.
- Marked every MCP tool as read-only/open-world and added prompt-injection
  guidance to the server instructions.
- Added a default-deny Analytics property allowlist and filtered account
  discovery.
- Added a default 1,000-row query ceiling with a hard 10,000-row maximum and a
  separate serialized-response ceiling.
- Added safe error reporting, credential ignore rules, Codex configuration, a
  security review, and security-invariant tests.
- Added a frozen uv dependency lock and checkout-bound setup guidance.
- Installed a deny-by-default `google_analytics_readonly` profile in the local
  Codex configuration as a required server; OAuth consent and property selection
  remain separate operator actions.
- Hardened and read back the Windows credential-directory ACL.
- Replaced the Windows OAuth example with a single-line, explicit-interpreter
  command to avoid console-launcher and PowerShell continuation mistakes.
- Added a prominent upstream-versus-fork comparison to the README covering the
  security model, OAuth, property/tool boundaries, limits, Codex deployment,
  dependency freezing, error handling, and verification.
- Verified 26 tests including a real STDIO handshake, package builds, formatting,
  critical lint, Bandit, `pip-audit`, and secret scanning.
