# Google Analytics MCP Server (Experimental)

[![PyPI version](https://img.shields.io/pypi/v/analytics-mcp.svg)](https://pypi.org/project/analytics-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub branch check runs](https://img.shields.io/github/check-runs/googleanalytics/google-analytics-mcp/main)](https://github.com/googleanalytics/google-analytics-mcp/actions?query=branch%3Amain++)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/analytics-mcp)](https://pypi.org/project/analytics-mcp/)
[![GitHub stars](https://img.shields.io/github/stars/googleanalytics/google-analytics-mcp?style=social)](https://github.com/googleanalytics/google-analytics-mcp/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/googleanalytics/google-analytics-mcp?style=social)](https://github.com/googleanalytics/google-analytics-mcp/network/members)
[![YouTube Video Views](https://img.shields.io/youtube/views/PT4wGPxWiRQ)](https://www.youtube.com/watch?v=PT4wGPxWiRQ)

This repo contains the source code for running a local
[MCP](https://modelcontextprotocol.io) server that interacts with APIs for
[Google Analytics](https://support.google.com/analytics).

Join the discussion and ask questions in the
[🤖-analytics-mcp channel](https://discord.com/channels/971845904002871346/1398002598665257060)
on Discord.

## Tools 🛠️

The server uses the
[Google Analytics Admin API](https://developers.google.com/analytics/devguides/config/admin/v1)
and
[Google Analytics Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)
to provide several
[Tools](https://modelcontextprotocol.io/docs/concepts/tools) for use with LLMs.

This fork exposes only the ten tools pinned in `analytics_mcp/policy.py`. The
`get_capabilities` tool reports the effective read-only policy without making a
Google request or starting OAuth. No login, create, update, or delete tool is
registered.

### Retrieve account and property information 🟠

- `get_account_summaries`: Retrieves information about the user's Google
  Analytics accounts and properties.
- `get_property_details`: Returns details about a property.
- `list_google_ads_links`: Returns a list of links to Google Ads accounts for
  a property.
- `list_property_annotations`: Returns annotations for an allowed property.

### Run core reports 📙

- `run_report`: Runs a Google Analytics report using the Data API.
- `run_funnel_report`: Runs a Google Analytics funnel report using the Data API.
- `run_conversions_report`: Runs a conversion-focused report using the Data API.
- `get_custom_dimensions_and_metrics`: Retrieves the custom dimensions and
  metrics for a specific property.

### Run realtime reports ⏳

- `run_realtime_report`: Runs a Google Analytics realtime report using the
  Data API.

## Codex read-only setup 🔧

This branch is intended for a reviewed, checkout-bound local installation. Do
not launch it with an unversioned `pipx run` or `uvx` command: those can execute
a package revision other than the one you audited.

Prerequisites:

- Python 3.10 or newer, managed directly or by
  [uv](https://docs.astral.sh/uv/).
- A Google Cloud project with the two Analytics APIs below enabled.
- A Google OAuth client whose application type is **Desktop app**.
- A Google user who has access only to the Analytics properties the AI should
  read.

### Enable APIs in your project ✅

[Follow the instructions](https://support.google.com/googleapi/answer/6158841)
to enable the following APIs in your Google Cloud project:

- [Google Analytics Admin API](https://console.cloud.google.com/apis/library/analyticsadmin.googleapis.com)
- [Google Analytics Data API](https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com)

### Create the frozen environment

From the reviewed checkout:

```powershell
uv sync --frozen --python 3.11
```

### Create the dedicated OAuth token 🔑

Keep the Desktop client JSON and generated token outside the repository. The
standalone helper uses a system-browser loopback flow with PKCE, requests only
this scope, and atomically writes `token.readonly.json`:

```text
https://www.googleapis.com/auth/analytics.readonly
```

On Windows PowerShell:

```powershell
$oauthDir = "$env:LOCALAPPDATA/google-analytics-mcp"
New-Item -ItemType Directory -Force -Path $oauthDir | Out-Null
$currentAccount = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $oauthDir /inheritance:r /grant:r `
  "${currentAccount}:(OI)(CI)F" `
  "*S-1-5-18:(OI)(CI)F" `
  "*S-1-5-32-544:(OI)(CI)F"
& icacls.exe $oauthDir

$env:ANALYTICS_MCP_OAUTH_CLIENT_SECRETS_FILE = `
  "C:/Users/YOU/AppData/Local/google-analytics-mcp/client_secrets.json"
$env:ANALYTICS_MCP_TOKEN_FILE = `
  "C:/Users/YOU/AppData/Local/google-analytics-mcp/token.readonly.json"
uv run --frozen analytics-mcp-auth login
```

Authentication is deliberately not an MCP tool. A model cannot open the
browser, replace the token, or broaden its scope. Re-run the terminal command
with `--force` only when you intentionally want to replace the current grant.

Do not reuse an ADC file or another server's token. A Desktop OAuth client JSON
may be shared deliberately, but a separate Analytics client is easier to revoke
and audit. The Windows ACL step keeps the current user, Local System, and local
Administrators while removing broader inherited access; review its printed
result before login.

### Configure the property boundary

The server denies every property until the operator sets
`ANALYTICS_MCP_ALLOWED_PROPERTY_IDS` to a comma-separated list such as
`123456789,properties/987654321`. Use `*` only when every property accessible
to the Google account is intentionally in scope.

Copy the numeric **Property ID** from that property's details in Google
Analytics Admin, then place it in the Codex configuration and restart Codex.
Property discovery is intentionally unavailable while the allowlist is empty;
do not temporarily use `*` just to discover IDs.

`ANALYTICS_MCP_MAX_ROWS` defaults to 1,000 and can never exceed 10,000. Smaller
requests and pagination are preferred for model context and Analytics quota.
Serialized tool output is also rejected above 1,000,000 bytes by default so an
oversized response cannot flood the model context.

### Configure Codex

Copy and edit [`config/codex.example.toml`](config/codex.example.toml), then
place its server section in `~/.codex/config.toml`. It binds Codex to this
checkout's virtual environment, uses STDIO only, pins the visible tool names,
and requests approval for every credentialed call.

Restart the local Codex client after changing MCP configuration. Use `/mcp` to
confirm the server is attached, then call `get_capabilities` before making a
small approved read.

## Try it out 🥼

In Codex, type `/mcp`. You should see `google_analytics_readonly` listed in the
results.

Here are some sample prompts to get you started:

- Ask what the server can do:

  ```
  what can the analytics-mcp server do?
  ```

- Ask about a Google Analytics property

  ```
  Give me details about my Google Analytics property with 'xyz' in the name
  ```

- Prompt for analysis:

  ```
  what are the most popular events in my Google Analytics property in the last 180 days?
  ```

- Ask about signed-in users:

  ```
  were most of my users in the last 6 months logged in?
  ```

- Ask about property configuration:

  ```
  what are the custom dimensions and custom metrics in my property?
  ```

## Contributing ✨

Contributions welcome! See the [Contributing Guide](CONTRIBUTING.md).
