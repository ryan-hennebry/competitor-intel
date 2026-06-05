# Delivery & Scheduling

## When Offered

Delivery setup is offered from the POST-BRIEFING ACTIVITIES menu, after the first briefing is generated.

## Delivery Method Selection

Use AskUserQuestion:
- Question: "How should I deliver scheduled briefings?"
- Header: "Delivery"
- Options:
  - "Email me weekly (Recommended)" — I'll email every Monday at 8am
  - "Email me daily" — I'll email every day at 8am
  - "Slack me weekly" — I'll post to Slack every Monday at 8am
  - "Slack me daily" — I'll post to Slack every day at 8am
  - "Save to files only" — I'll generate but not deliver

## Email Setup

If Email selected:
1. Check if RESEND_API_KEY is set: `echo $RESEND_API_KEY | head -c 3`
2. If NOT set -> use AskUserQuestion:
   - Question: "I need your Resend key to email briefings. Ready to paste it? (resend.com/api-keys -> Create API Key -> name it -> Sending access -> copy)"
   - Header: "Resend API"
   - Options:
     - "I'll paste it" — User provides API key
     - "Skip email, save to files only" — Cancel email setup
3. If key provided:
   - Export: `export RESEND_API_KEY="<key>"`
   - Persist to shell profile (see Credential Persistence)
   - Verify: `echo $RESEND_API_KEY | head -c 3`
4. Ask for email address, store in context.md

## Slack Setup

If Slack selected:
1. Check if SLACK_TOKEN is set: `echo $SLACK_TOKEN | head -c 3`
2. If NOT set -> use AskUserQuestion:
   - Question: "I need your Slack bot token to post briefings. Ready to paste it? (api.slack.com/apps -> Create New App -> OAuth & Permissions -> add files:write + chat:write -> Install -> copy xoxb- token)"
   - Header: "Slack Token"
   - Options:
     - "I'll paste it" — User provides token
     - "Skip Slack, save to files only" — Cancel Slack setup
3. If token provided:
   - Export: `export SLACK_TOKEN="<token>"`
   - Persist to shell profile (see Credential Persistence)
   - Verify: `echo $SLACK_TOKEN | head -c 3`
4. Ask for Slack channel ID:
   "What channel should I post to? Paste the channel ID.
   (In Slack: right-click the channel -> View channel details -> copy the ID at the bottom, starts with C)"

## Required Slack Bot Scopes

| Scope | Purpose |
|-------|---------|
| `files:write` | Upload PDF files |
| `chat:write` | Post messages to channels |

## Install Cron Entry

```bash
AGENT_PATH=$(pwd)
CRON_EXPR="0 8 * * 1"  # Weekly, or "0 8 * * *" for daily

if crontab -l 2>/dev/null | grep -q "$AGENT_PATH"; then
  # Already exists
else
  (crontab -l 2>/dev/null; echo "$CRON_EXPR cd $AGENT_PATH && ./run.sh") | crontab -
fi
```

## Confirmation Messages

- Email: "Done. {Frequency} briefings will be emailed to {email}."
- Slack: "Done. {Frequency} briefings will be posted to #{channel}."
- Files: "Got it. I'll generate to output/briefings/ — check manually or set up delivery later."

Update context.md with delivery and scheduling config.

## Credential Persistence

After collecting any API key or token:
1. Export for current session: `export <VAR_NAME>="<value>"`
2. Persist to shell profile:
   - Check if `~/.zshrc` exists (prefer) or `~/.bashrc`
   - Check if already present: `grep "export <VAR_NAME>=" <profile_file>`
   - If not present: `echo 'export <VAR_NAME>="<value>"' >> <profile_file>`

## context.md: Delivery & Scheduling Section

```markdown
## Delivery
(Configured after first briefing — see Delivery & Scheduling)

## Scheduled Briefings
enabled: false
frequency:
setup_completed: false
```

Populated example:
```markdown
## Delivery
email: user@example.com
email_api_key_env: RESEND_API_KEY

## Scheduled Briefings
enabled: true
frequency: weekly
setup_completed: true
```
