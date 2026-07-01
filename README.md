# AI Multi-Cloud Log Analyzer

A command-line tool that fetches logs from your AWS, GCP, or Azure account and asks an AI model to
analyze them for you -- anomalies, security issues, cost/performance problems, or just plain
questions in English. Nothing gets installed in your cloud account; it's a local script that
reads logs through each cloud's normal read-only APIs and sends the text to an AI API (OpenAI by
default, or Anthropic).

## What it can do

- **Summarize & spot anomalies** -- "what happened in this time window, and what looks off?"
- **Security review** -- suspicious activity, who-did-what, and what to do about it
- **Cost & performance review** -- errors, slowness, and spend-driving patterns
- **Chat** -- ask questions in plain English; the AI figures out which logs to pull and answers
  based on what it finds

---

## Quick start

Follow these steps once, then skip straight to [Usage](#usage) every time after.

### 1. Install

```bash
git clone https://github.com/Hardikrepo/ai-aws-log-analyzer.git
cd ai-aws-log-analyzer
pip install -r requirements.txt
```

Requires Python 3.10 or newer.

### 2. Give it an AI API key

This is what powers the actual analysis (every mode needs this, regardless of cloud). By default
the tool uses OpenAI; Anthropic is available as an alternative via `--ai-provider anthropic`.

```bash
cp .env.example .env
```

Open `.env` and set:
```
OPENAI_API_KEY=sk-...
```
Get a key at [platform.openai.com](https://platform.openai.com) (you'll need billing set up
there -- this is separate from a ChatGPT/Codex CLI login). If you'd rather use Anthropic instead,
set `ANTHROPIC_API_KEY=sk-ant-...` and pass `--ai-provider anthropic` on every command (see
[Choosing the AI backend](#choosing-the-ai-backend)).

### 3. Log in to the cloud you want to analyze

Pick whichever of these you actually use -- you don't need all three.

| Cloud | One-time login command | What it needs |
|---|---|---|
| **AWS** | `aws configure` | The AWS CLI installed once, to save credentials |
| **GCP** | `gcloud auth application-default login` | The `gcloud` CLI installed |
| **Azure** | `az login` | The Azure CLI installed |

That's it -- the tool automatically picks up whatever credentials you just logged in with. (Full
details, including non-interactive/service-account setups, are in
[Detailed cloud setup](#detailed-cloud-setup) below.)

### 4. Run it

```bash
python main.py chat
```

Then just type a question:

```
you> anything weird in my logs in the last few hours?
```

If that works, you're set up correctly. See [Usage](#usage) for more ways to run it.

---

## Usage

### Chat (recommended starting point)

Ask questions in plain English. The AI decides which cloud/log source to pull from:

```bash
python main.py chat
```

```
you> anything weird in my GCP logs in the last few hours?
  [calling gcp_get_cloud_logging_entries({'hours': 4})]

gpt> ...
```

If you've only logged in to one cloud, you can restrict chat to it (avoids noisy errors from the
others):

```bash
python main.py chat --provider gcp
```

### Choosing the AI backend

Every `analyze` and `chat` command supports `--ai-provider {openai,anthropic}` (default:
`openai`). Both need their own API key/billing (see [OpenAI](#openai) / [Anthropic](#anthropic)
setup below) -- they're independent of each other, so you can use whichever one has credits
available:

```bash
python main.py analyze aws cloudtrail --hours 12 --mode security --ai-provider anthropic
python main.py chat --ai-provider anthropic --model claude-opus-4-8
```

`--model` lets you pick a specific model for whichever provider you chose (defaults to `gpt-5`
for OpenAI, `claude-opus-4-8` for Anthropic).

### One-shot analysis of a specific log source

Useful when you already know exactly what you want checked, or want to script it.

```bash
# AWS
python main.py analyze aws cloudwatch --log-group /aws/lambda/my-fn --hours 24 --mode all
python main.py analyze aws cloudtrail --hours 12 --mode security
python main.py analyze aws vpc-flow-logs --log-group my-flow-log-group --hours 6 --mode anomaly
python main.py analyze aws s3-access-logs --bucket my-logging-bucket --prefix logs/ --hours 24 --mode cost

# GCP
python main.py analyze gcp cloud-logging --project my-gcp-project --hours 24 \
  --filter 'resource.type="cloud_run_revision" AND severity>=ERROR' --mode all

# Azure
python main.py analyze azure activity-log --subscription-id 0000-... --resource-group my-rg \
  --hours 24 --mode security
```

`--mode` controls what kind of report you get: `anomaly`, `security`, `cost`, or `all` (default is
`all`, which runs every kind of analysis in one report).

### Discovery helpers

Don't know the exact log group/bucket name? These list what's available (AWS only for now):

```bash
python main.py list aws log-groups [--prefix /aws/lambda/]
python main.py list aws flow-logs
```

### Log sources covered today

| Cloud | Sources |
|---|---|
| AWS | CloudWatch Logs, CloudTrail (account activity), VPC Flow Logs, S3 server access logs |
| GCP | Cloud Logging |
| Azure | Activity Log (subscription-level account activity) |

AWS has full coverage; GCP and Azure currently cover one log source each, with more planned.

### All flags

| Flag | Applies to | Default | Meaning |
|---|---|---|---|
| `--ai-provider` | everything | `openai` | `openai` or `anthropic` -- which AI backend to use |
| `--model` | everything | `gpt-5` / `claude-opus-4-8` | Model ID for the selected `--ai-provider` |
| `--effort` | everything | `high` | `low`/`medium`/`high`/`xhigh`/`max` -- more effort = deeper analysis, higher cost (OpenAI clamps `xhigh`/`max` to `high`) |
| `--mode` | `analyze` commands | `all` | `anomaly` / `security` / `cost` / `all` |
| `--profile`, `--region` | AWS commands | your default AWS profile/region | Which AWS credentials/region to use |
| `--project` | GCP commands | your default GCP project | Which GCP project to query |
| `--subscription-id` | Azure commands | your default Azure subscription | Which Azure subscription to query |

---

## Detailed cloud setup

Skip this if step 3 of the Quick Start already worked for you -- this is here for less common
setups (service accounts, CI, no CLI installed, etc.).

### AWS

Credentials are read through boto3's standard lookup chain, so any of these work:
- `aws configure` (writes `~/.aws/credentials`; the AWS CLI is only needed once, to write this file)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` environment variables
- An EC2 instance profile / ECS task role / Lambda execution role, if run from inside AWS
- An AWS SSO profile (`aws sso login --profile ...`, then pass `--profile`)

A default region comes from `AWS_REGION`, `~/.aws/config`, or the `--region` flag.

**Permissions needed:** this tool is read-only. The exact policy is in
[`iam-policy.json`](./iam-policy.json) -- attach it with:
```bash
aws iam put-user-policy --user-name <your-user> --policy-name log-analyzer-readonly \
  --policy-document file://iam-policy.json
```
It uses `Resource: "*"` because bucket/log-group names are only known at runtime; tighten to
specific ARNs later if you want stricter least-privilege.

### GCP

Credentials come from Application Default Credentials -- either:
- `gcloud auth application-default login` (interactive, your own identity), or
- A service account key file, pointed to via `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`

A default project comes from `GOOGLE_CLOUD_PROJECT` / `GCLOUD_PROJECT`, or the `--project` flag.

**Permissions needed:** grant `roles/logging.viewer` (Logs Viewer) on the project to whichever
identity runs the tool.

### Azure

Credentials come from `DefaultAzureCredential`'s standard chain -- either:
- `az login` (interactive, requires the Azure CLI), or
- Environment variables for a service principal (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
  `AZURE_CLIENT_SECRET`), or a managed identity if run from inside Azure

A default subscription comes from `AZURE_SUBSCRIPTION_ID`, or the `--subscription-id` flag.

**Permissions needed:** grant `Reader` or `Monitoring Reader` at subscription scope to whichever
identity runs the tool.

### OpenAI

Used when `--ai-provider openai` (the default). Needs `OPENAI_API_KEY` set (env var or `.env` file).

Note: this is *separate* from ChatGPT/Codex CLI login -- a ChatGPT Plus/Pro subscription alone
does not grant API access. You need an API key with billing/credits set up at
[platform.openai.com](https://platform.openai.com).

Defaults to `gpt-5`; pass `--model` for a different OpenAI model. Reasoning-capable models
(`gpt-5*`, `o1`/`o3`/`o4` families) get `--effort` passed through as `reasoning_effort`
(`xhigh`/`max` clamp to `high`, since that's the ceiling OpenAI's API accepts); other models
ignore `--effort`.

### Anthropic

Used when `--ai-provider anthropic`. Any of these gives the tool access, checked in this order:
- A real `ANTHROPIC_API_KEY` environment variable, or an equivalent CLI auth session -- always wins
- `ANTHROPIC_API_KEY` set in your `.env` file

Pass `--model` to use something other than the default `claude-opus-4-8` -- e.g.
`--model claude-sonnet-5` or `--model claude-haiku-4-5` for lower cost per call.

Note: this is a *separate* product/billing from any consumer chat plan (including free tiers) --
those don't grant API access. You need an API key with billing/credits set up at
[console.anthropic.com](https://console.anthropic.com).

---

## Cost notes

Every run makes normal AI API calls (billed per token, by OpenAI or Anthropic depending on
`--ai-provider`) and normal cloud read-only API calls (all of which are typically free or
near-free at low volume). There's nothing to "tear down" afterward -- it's a script, not deployed
infrastructure.

Each fetch is capped at ~2000 events and ~400K characters of log text (see
`log_analyzer/config.py` to change this), so one noisy log source can't blow up a single
request's cost or overflow the model's context window.

---

## Project layout (for anyone extending this)

```
log_analyzer/
  cli.py                  # thin orchestrator: top-level parser, provider registry, chat merge
  cli_common.py           # shared analyze/mode helpers (MODE_PROMPTS, run_analysis, argparse helpers)
  config.py               # cloud-agnostic defaults (model, max tokens, event caps)
  formatting.py           # turns fetched events into prompt text
  analysis/
    anthropic_client.py    # Anthropic Messages API wrapper
    openai_client.py        # OpenAI Chat Completions API wrapper
    prompts.py              # system prompts per mode + chat (provider-agnostic)
  aws/
    client.py               # boto3 session/client helper
    config.py               # AWS region default
    cli.py                  # AWS analyze/list subcommands + chat tools
    sources/
      cloudwatch.py, cloudtrail.py, vpc_flow_logs.py, s3_access_logs.py
  gcp/
    client.py               # google-auth + Cloud Logging client helper
    config.py               # GCP project default
    cli.py                  # GCP analyze subcommand + chat tools
    sources/
      cloud_logging.py
  azure/
    client.py               # DefaultAzureCredential + MonitorManagementClient helper
    config.py               # Azure subscription default
    cli.py                  # Azure analyze subcommand + chat tools
    sources/
      activity_log.py
```

Adding a new source to an existing provider, or a new provider entirely, follows this same
pattern: a `sources/*.py` fetcher returning `{timestamp, message}`-shaped events (or events adapted
to that shape before analysis, for structured audit-log-style data), wired into that provider's
`cli.py` as an `analyze` subcommand and a chat tool/dispatch entry.
