# Competitor Intel Agent

Configure once in Claude, then receive weekly competitor briefings on market changes, threat shifts, and positioning opportunities.

## Quick Start

**Prerequisite:** Claude Code CLI installed and authenticated.

1. Open **Terminal** (Mac) or **PowerShell** (Windows)
2. Paste this single block:

```bash
git clone https://github.com/ryan-hennebry/competitor-intel.git && cd competitor-intel && claude
```

You do not need to edit files or write code.
After this command, setup happens in chat.

## Onboarding Flow

- Your company URL (or plain-English description)
- Suggested competitors (you can add/remove)
- Tracking priorities (positioning, partnerships, features, enterprise signals, hiring)
- Delivery preference

## Delivery Modes

- **Files only** (default): saves to `output/briefings/`
- **Email:** requires `RESEND_API_KEY`
- **Slack:** requires `SLACK_TOKEN`
- **Email + Slack:** both channels

## How It Works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/how-it-works-dark.svg">
  <img src="assets/how-it-works-light.svg" alt="How Competitor Intel Agent works" width="500" />
</picture>

*Editable source: `assets/how-it-works.mmd` (rendered with beautiful-mermaid for light/dark GitHub themes).*

## Visual Proof

![Generated briefing placeholder](assets/readme-briefing-preview.png)
*Placeholder: screenshot of a real briefing page (threat landscape + recommendations).*

![CLI workflow placeholder](assets/readme-cli-proof.png)
*Placeholder: cropped CLI strip showing onboarding and a completed run.*

## Outputs

- `context.md` -> source of truth for company context, competitors, priorities, delivery, run history
- `output/briefings/` -> generated briefing outputs
- `output/snapshots/` -> per-competitor snapshots for change tracking
- `output/last_run.json` -> latest run metadata and status (`success`, `error`, `skipped`)

## Try These Prompts

Use natural prompts:
- "Generate this week's briefing"
- "Add [competitor]"
- "What changed since last run?"
- "Set up scheduled briefings"
