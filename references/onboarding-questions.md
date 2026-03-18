# Onboarding Flow

**STOP after each question. Wait for response before continuing.**

## Agent-Native Principle

**Research first, present findings, let user validate.** Only ask for what can't be researched.

## Step 1: Company

"What company do you want to analyze? (URL or description)"
- Wait for response
- Research their website thoroughly:
  - Homepage (hero, tagline, value proposition)
  - About page (company narrative, team, mission)
  - Product pages (features, technical capabilities)
  - Pricing page (model, tiers, enterprise signals)
  - Customers/Case studies (named customers, evidence)
  - Careers (if accessible — growth signals)
- Extract and synthesize:
  - Positioning (hero headline + value proposition)
  - Primary ICP (who the messaging targets)
  - Secondary ICP (other audiences mentioned)
  - Key differentiators (unique claims)
  - Narrative bet (thesis they're pushing)
  - Key partners (from website)
- Present findings as a formatted profile:

**{Company Name}** — {one-line positioning}

| Dimension | Finding |
|-----------|---------|
| Positioning | {hero + value prop} |
| Primary ICP | {who they're targeting} |
| Differentiators | {1-3 unique claims} |
| Narrative | {thesis/bet} |

- Use AskUserQuestion:
  - Question: "Is this profile accurate?"
  - Header: "Profile"
  - Options:
    - "This looks correct (Recommended)" -> write to context.md, continue to Step 2
    - "I need to adjust something" -> ask what to change, update, re-confirm

STOP HERE — wait for response before Step 2

- Write validated profile to context.md Company section

## Step 2: Competitors

Research competitors using WebSearch based on their positioning.
Present the list with brief descriptions for each competitor.
Then use AskUserQuestion tool:
- Question: "Modify your competitor list?"
- Header: "Competitors"
- Options:
  - "Accept these [N] (Recommended)" — Proceed with suggested competitors
  - "Add competitors" — I'll ask which ones to add
  - "Remove competitors" — I'll ask which ones to remove
- If "Accept" selected -> continue to Step 3
- If "Add" selected -> ask what to add, update list, use AskUserQuestion again
- If "Remove" selected -> ask what to remove, update list, use AskUserQuestion again
- If "Other" -> parse their text response

## Step 3: Priorities

Present current defaults:
"I'll track these signals by default:
- Positioning changes
- Partnership announcements
- GTM motion shifts
- Content strategy changes
- Hiring patterns"

Then use AskUserQuestion tool:
- Question: "Adjust tracking priorities?"
- Header: "Priorities"
- Options:
  - "Accept defaults (Recommended)" — Track all 5 signal types
  - "Customize" — Add or remove signal types
- If "Accept" selected -> continue to Step 4
- If "Customize" selected -> ask what to add/remove, update, use AskUserQuestion again
- If "Other" -> parse their text response

## Step 4: Complete & Generate

Write configuration to `context.md`:
- Company profile
- Competitors list
- Priorities

"Setup complete. Generating your first briefing..."

- Execute full briefing generation (see methodology)
- After briefing: offer Delivery & Scheduling

**NEVER ask multiple questions in one message.**
