# Competitor Intel Agent

Track competitor changes and get a weekly briefing on the shifts that actually matter.

No coding experience required.

<img src="assets/cli-demo-full.gif" alt="Competitor Intel CLI onboarding and first briefing preview demo" width="896" />

## Quick start

**Prerequisite:** Claude Code installed and authenticated. [Setup instructions](https://code.claude.com/docs/en/quickstart).

1. Paste this command into **Terminal** (Mac) or **PowerShell** (Windows):

```bash
git clone https://github.com/ryan-hennebry/competitor-intel.git && cd competitor-intel && claude --dangerously-skip-permissions
```

2. In Claude Code, complete onboarding with the agent. It will walk you through setup one question at a time.

## The onboarding flow

- Provide your company URL (or a description)
- The agent suggests competitors (you can add/remove)
- Set priorities (keep defaults or customize)
- Pick delivery: files only, email, Slack, or both

## What you receive

A weekly briefing with:

- A quick take on the single most important shift
- Recommendations grouped into Act Now, Watch, and Opportunity
- What changed across competitors and your own company
- A threat landscape showing why each move matters
- Open questions worth tracking in the next run

## Once your first briefing has been generated

Continue to interact with the agent for deeper analysis:
- "Which competitor changed positioning most in the last 30 days?"
- "Compare [Competitor A] vs [Competitor B] on ICP overlap."
- "What are the top 3 risks to our narrative this quarter?"
- "Show only changes that should alter pricing or packaging."
- "What assumptions in the latest briefing are low confidence?"

## Optional delivery

- **Files only** (default): saves each briefing to `output/briefings/`
- **Email via Resend:** optional one-time [Resend](https://resend.com/docs/dashboard/api-keys/introduction) setup guided in chat
- **Slack:** optional one-time [Slack](https://api.slack.com/apps) setup guided in chat
- **Email + Slack:** enable both if you want a saved file plus delivery

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/how-it-works-dark.svg">
  <img src="assets/how-it-works-light.svg" alt="How Competitor Intel Agent works" width="560" />
</picture>

*Diagram source: `assets/how-it-works.mmd`.*

## The agent's output

- Saved weekly briefings in `output/briefings/`
- Per-competitor snapshots in `output/snapshots/` for change tracking
- Company context, competitors, priorities, and delivery preferences in `context.md`

## Project standards

- [MIT License](LICENSE)
- [Security Policy](SECURITY.md)
- [Contributing Guide](CONTRIBUTING.md)
