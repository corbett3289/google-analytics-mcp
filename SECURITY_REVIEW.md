# Security review: Codex read-only profile

Review date: 2026-09-10

Upstream reviewed commit: `a8ca729d4a8fa99bffe87962c17c0539c6aa9da7`

Threat model: a local AI client can select tool inputs and can encounter hostile
strings inside Analytics dimensions, campaign labels, URLs, and annotations.
The local Windows user and the Google account owner remain trusted operators.

## Outcome

The upstream server had no registered create, update, or delete tools and ran
over local STDIO. It was not sufficient as a least-privilege user-OAuth profile,
because the documented ADC flow included `cloud-platform` and the scope passed
to `google.auth.default()` does not down-scope an existing user credential.

This branch closes that gap with a dedicated installed-app OAuth flow that
persists only an exact `analytics.readonly` grant. Authentication is a separate
human-run command and is not exposed to MCP.

## Findings and disposition

| Severity | Finding | Disposition |
| --- | --- | --- |
| High | The documented user ADC contained both `analytics.readonly` and `cloud-platform`; runtime scope arguments do not reliably down-scope user ADC. | Replaced for this profile. The server loads only a dedicated token whose persisted scope is exactly `analytics.readonly`. |
| Medium | Any Analytics property reachable by the credential was model-queryable. | Mitigated with a central, default-deny `ANALYTICS_MCP_ALLOWED_PROPERTY_IDS` policy. Account summaries are filtered and property requests fail before credential/API use. |
| Medium | Report tools accepted up to 250,000 rows and returned whole responses. | Mitigated with a default 1,000-row ceiling, a hard 10,000-row maximum, a default 1 MB serialized-response ceiling, and Codex output-token limits. |
| Medium | `pipx run analytics-mcp` could execute a revision other than the audited checkout; runtime dependency ranges were not locked. | Mitigated with a committed uv lockfile and checkout-bound `uv sync --frozen`/virtual-environment configuration. |
| Low | Raw unexpected exceptions and fatal tracebacks could disclose request or account details to the model/client logs. | Mitigated by returning controlled policy/input errors and only the unexpected exception type otherwise. |
| Low | OAuth/token filename patterns were not comprehensively ignored. | Mitigated in `.gitignore`; the supported paths are outside the repository. |
| Low | Schema compatibility rewriting permits arbitrary nested dictionary keys for complex Google filter objects. | Accepted residual risk. Google protobuf constructors validate those objects, and no value is used for command, path, or code execution. |

## Security invariants

- Exact OAuth scope: `https://www.googleapis.com/auth/analytics.readonly`.
- Dedicated `token.readonly.json`; ADC and other MCP tokens are never loaded.
- Persisted tokens and Desktop client files must use Google's expected OAuth
  endpoints and contain the refresh fields required for non-interactive use.
- OAuth login is a standalone system-browser loopback/PKCE command.
- OAuth replacement is atomic and rejects symbolic-link token targets.
- Model-visible tools are pinned by name and annotated read-only/open-world.
- Property access is deny-all until configured by the operator.
- Local server transport is STDIO only.
- The Codex profile is enabled but optional (`required = false`) so this
  integration cannot make unrelated task startup depend on Analytics.
- Analytics response text is untrusted data, never agent instruction.
- Codex config adds its own enabled-tool allowlist and prompt approvals.

## Residual risks

- Read-only Analytics data may still be commercially sensitive. Grant the OAuth
  user access only to necessary properties and keep the property allowlist
  narrow.
- Google access tokens are bearer credentials. Protect the Windows user account,
  the LocalAppData credential directory, and backups; revoke the Google grant if
  the host is compromised.
- Analytics queries consume API quota and can expose granular data even without
  modifying Google state. Keep prompt approval enabled and use small limits.
- Alpha API report methods can change independently of this fork. Re-audit when
  updating Google client libraries or adding tools.
- Dependency audits identify published known vulnerabilities, not malicious or
  previously unknown package behavior. Review lockfile changes before syncing.
- Codex may run one STDIO server per client or agent host. Multiple sibling
  processes can be legitimate; persistent single-process reuse would require a
  separately reviewed HTTP or broker deployment.
- Google API calls currently use synchronous client methods in worker threads.
  An MCP disconnect during an in-flight RPC can delay interpreter exit until
  that underlying request returns; keeping the server optional limits the host
  impact. Explicit RPC deadlines or async Google clients require separate live
  API validation before adoption.

## Verification

- All 27 unit/integration tests pass on Python 3.11.16, including an offline
  assertion that the real OAuth library generates an S256 PKCE request with the
  exact read-only scope.
- The integration suite completes real STDIO `initialize`, `tools/list`,
  `get_capabilities`, and denied-property calls, proving the exact ten-tool set,
  annotations, and fail-closed behavior without OAuth.
- A process-level regression test closes the server's standard input and
  requires a clean, timely exit, covering the disconnect signal used by local
  STDIO clients. A separate Windows parent-disconnect probe also exited cleanly.
- Bytecode compilation, the modified Python file's Black check, critical Ruff
  checks, and `git diff --check` pass. The earlier full-tree Bandit scan remains
  unchanged because this update does not modify runtime code.
- The source distribution and wheel build successfully.
- `uv lock --check` passes, and `pip-audit` reports no known vulnerabilities in
  the 76-package frozen virtual environment as checked on 2026-09-08.
- A full-tree `detect-secrets` scan found no credential material. Its only hits
  were the OAuth environment-variable name, explicit test placeholders, and
  pre-existing skill integrity hashes; each was inspected manually.
- Codex parses the installed local configuration and reports
  `google_analytics_readonly` enabled and optional with the checkout-bound
  interpreter.
- The deployed Windows credential directory has protected inheritance and only
  the current user, Local System, and local Administrators retain access. The
  README includes the same create/apply/read-back procedure for fresh installs.
- The existing GSC Desktop OAuth client configuration passes the Analytics
  helper's offline type, field, and Google-endpoint validation, so its client
  registration can be reused without reusing the GSC token.
- Live Google acceptance remains intentionally pending: the standalone OAuth
  flow requires operator consent, and property access remains deny-all until
  the operator chooses the allowed Analytics property IDs.
