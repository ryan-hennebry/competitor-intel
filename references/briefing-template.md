# Briefing Structure & Design

## Briefing Output

Generate at `output/briefings/{YYYY-MM-DD}-briefing.md`:

```
# Competitor Intelligence Briefing — {date}

## Quick Take
{2-3 sentences. Most important change + top action.}

## Recommendations

### Act Now
1. **{Title}** — {Why}. *Next step: {action}.*

### Watch
2. **{Title}** — {Why}.

### Opportunity
3. **{Title}** — {Why}.

## What Changed
| Company | Change | Significance | Action |
|---------|--------|--------------|--------|
| Your Company | {change or "No changes"} | {why} | {Act/Watch/—} |
| {Competitor} | {change} | {why} | {Act/Watch/—} |

## Threat Landscape
| Competitor | Threat | Trend | Key Gap You Exploit |
|------------|--------|-------|---------------------|
| {name} | HIGH/MED/LOW | up/down/steady | {weakness} |

## Open Questions
1. {Question for follow-up}

---
*Summary ends here. Details below.*
---

## Details by Competitor

For EACH competitor, include ALL dimensions from methodology. Minimum 300 words per competitor.

## Comparison Tables

### Content Strategy Comparison
| Competitor | Blog | Video | Podcast | Community | Gated Content | Events |
|------------|------|-------|---------|-----------|---------------|--------|

### Growth Engine Comparison
| Competitor | Primary Engines | Signals |
|------------|-----------------|---------|

### Business Model Comparison
| Competitor | Revenue Model | GTM Motion | Key Signals |
|------------|---------------|------------|-------------|

### Pricing Comparison
[Pricing tiers, models, enterprise signals]

### Narrative Bets
[Thesis each competitor is pushing]

### Competitive Matrix
[Feature/capability comparison]

## Coverage Notes
[What was/wasn't extracted and why]

## Sources

All sources as clickable markdown links so readers can dig deeper:

### Primary Sources
- [{competitor-domain}]({full URL}) — accessed {date}

### Third-Party Sources (Deep Mode)
- [{Publication}: "{Article title}"]({url}) ({date})
- [{Data provider}]({url}) — {what was extracted} ({date})
- [{Platform thread/discussion}]({url}) ({date range})
```

## Design Requirements

When generating HTML, prioritize readability:

### Typography
- Body: System sans-serif (16px)
- Headers: Same family, weight variation only
- Tables: 14px, adequate line-height
- Monospace: Code/URLs only

### Color
- Background: White or very light gray
- Text: Near-black (#1a1a1a)
- Accents: Threat-level colors only
  - HIGH: #dc2626 (red)
  - WATCH: #d97706 (amber)
  - LOW/OK: #16a34a (green)

### Layout
- Max-width: 800px
- Margins: Generous (40px+)
- Sections: Clear separation with subtle dividers
- Tables: Full-width, horizontal scroll if needed

### Page Breaks (Print/PDF)

Content flows naturally. Breaks only to keep blocks intact:

```css
h2, h3 { break-after: avoid; page-break-after: avoid; }
.competitor-detail, table, .table-group { break-inside: avoid; page-break-inside: avoid; }
```

Wrap each competitor in `<div class="competitor-detail">`. Validate: no orphaned headings, no large whitespace gaps, blocks stay together.

**Avoid:** Dark themes, decorative backgrounds, multiple accent colors, card-heavy layouts, fonts <14px, low contrast.

## After Briefing Generation

1. Generate HTML using `frontend-design` skill with design constraints above
2. **Content integrity checklist** (verify before proceeding):
   - [ ] All sections from markdown present in HTML
   - [ ] All table rows preserved
   - [ ] All list items preserved
   - [ ] All citations/sources included
   - [ ] Tables readable without horizontal scroll
   - [ ] Text contrast passes (dark on light)
   - [ ] No decorative elements distract from content
   - [ ] PDF prints cleanly (no dark backgrounds)
   If any missing: fix HTML before PDF generation
3. Generate PDF from HTML
4. **Validate PDF:**
   - No browser chrome in margins
   - Bullets fully visible
   - Tables complete
   - All text readable
   - No orphaned headings (heading at page bottom, content on next page)
   - If issues: fix HTML, regenerate, validate again
5. **Cleanup intermediate files:**
   - Delete the .md file (intermediate)
   - Delete the .html file (intermediate)
   - Keep only the .pdf (final deliverable)
6. Update context.md (Open Questions, Session History)
7. Confirm completion: "Done. Briefing saved to output/briefings/{date}-briefing.pdf ({size})"
8. **Offer high-leverage activities** (see post-briefing-activities in CLAUDE.md)

## Email Template

Build the email HTML with inline styles for cross-client compatibility (Gmail, Outlook, Apple Mail). Use tables for layout.

Include in email body:
- Quick Take (the core insight)
- Recommendations (Act Now / Watch / Opportunity with colored badges)
- Threat Landscape table

Exclude (available in PDF attachment):
- What Changed table
- Details by Competitor
- Comparison Tables
- Coverage Notes
- Sources

### Color Constants
Use colors from Design Requirements above (HIGH=#dc2626, WATCH=#d97706, LOW=#16a34a, Opportunity=#2563eb).

### Email HTML Structure

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table role="presentation" style="width: 100%; border-collapse: collapse;">
    <tr>
      <td style="padding: 24px;">
        <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 4px;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 24px 32px; border-bottom: 2px solid #1a1a1a;">
              <h1 style="margin: 0; font-size: 20px; font-weight: 600; color: #1a1a1a; letter-spacing: -0.025em;">Competitor Intelligence Briefing</h1>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: #525252; text-transform: uppercase; letter-spacing: 0.05em;">{DATE}</p>
            </td>
          </tr>
          <!-- Quick Take, Recommendations, Threat Landscape sections -->
          <!-- Footer: "Full briefing attached as PDF." -->
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

Substitute placeholders with briefing data. Use Color Constants for all color values.

## Slack Message Template

Build the message using Block Kit for professional structure. Include: header with date, Quick Take, Threat Landscape fields, Key Actions, footer noting PDF attachment.

## Send Commands

### Email via Resend
```bash
PDF_BASE64=$(base64 -i output/briefings/{date}-briefing.pdf)
curl -X POST https://api.resend.com/emails \
  -H "Authorization: Bearer $RESEND_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"from":"briefings@resend.dev","to":"[email]","subject":"Competitor Intelligence Briefing — [date]","html":"[EMAIL_HTML]","attachments":[{"filename":"competitor-intelligence-[date].pdf","content":"[PDF_BASE64]"}]}'
```

### Slack
```bash
# Upload PDF, then post Block Kit message
PDF_SIZE=$(wc -c < output/briefings/{date}-briefing.pdf | tr -d ' ')
UPLOAD_RESPONSE=$(curl -s -X POST "https://slack.com/api/files.getUploadURLExternal" -H "Authorization: Bearer $SLACK_TOKEN" -H "Content-Type: application/x-www-form-urlencoded" -d "filename=competitor-intelligence-{date}.pdf" -d "length=$PDF_SIZE")
UPLOAD_URL=$(echo $UPLOAD_RESPONSE | jq -r '.upload_url')
FILE_ID=$(echo $UPLOAD_RESPONSE | jq -r '.file_id')
curl -s -X POST "$UPLOAD_URL" -F "file=@output/briefings/{date}-briefing.pdf"
curl -s -X POST "https://slack.com/api/files.completeUploadExternal" -H "Authorization: Bearer $SLACK_TOKEN" -H "Content-Type: application/json" -d '{"files":[{"id":"'"$FILE_ID"'","title":"Competitor Intelligence Briefing — {date}"}],"channel_id":"'"$CHANNEL_ID"'"}'
```

Before sending: verify Quick Take complete, all recommendations with correct colors, all competitors in Threat Landscape, PDF attached.
