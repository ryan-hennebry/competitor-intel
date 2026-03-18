# Competitive Analysis Methodology

## Goal

Generate an intelligence briefing that answers: **How do competitors position relative to me, and what changed?**

## Research Depth

Two modes, configured in context.md under `research_depth`:

**Deep Mode** (default)
- Sources: Competitor websites + third-party research
- Gathers external validation, funding data, news, community sentiment
- Use: All runs unless explicitly set to fast

**Fast Mode** (opt-in)
- Sources: Competitor websites only
- Use: Quick checks when time-constrained

## Discovery Phase

Figure out which pages matter for each company:
- What pages reveal positioning, pricing, customers, hiring, strategy?
- Check sitemap.xml and robots.txt
- Follow strategic links, skip noise
- Track which pages you attempted and which failed

## Third-Party Intelligence (Deep Mode)

Find external sources that validate or extend website findings: funding, metrics, sentiment, rankings, recent news.

Use WebSearch. Stop at 3-5 quality sources per competitor or after 5 searches yield nothing new. Track effective sources in context.md.

## Required Extraction (Per Competitor)

You MUST attempt these dimensions. Report status for each:
- **[Extracted]** — Found and documented
- **[Not found - checked X pages]** — Couldn't find
- **[Not applicable]** — Doesn't apply

### Positioning
- Hero headline and tagline
- Core value proposition
- Narrative bet (thesis they're pushing)

### Target Audience
- Primary ICP
- Secondary ICP
- ICP overlap with user's company (High/Med/Low + reasoning)

### Product
- Key features
- Differentiators vs user's company
- Technical capabilities

### Pricing
- Model (token-based, SaaS, freemium, usage-based)
- Specific tiers/costs if available (note original currency)
- Tier structure comparison (free vs paid feature gates)
- Enterprise signals (custom pricing, "contact sales", security/compliance features)

### Customers
- Named customers/partners
- Evidence quality: case study > logo+quote > logo > press mention
- Metrics cited, enterprise partner count

### Business Model & GTM
- Revenue model: SaaS/usage-based/freemium/enterprise
- GTM: PLG/sales-led/hybrid
- Monetization signals from pricing page

### Company Size & Stage
- Employee count (LinkedIn proxy)
- Funding stage/total raised
- Market maturity indicator (startup/growth/enterprise)

### Content Types
- Blog: frequency, topics, depth (thought leadership vs. SEO)
- Video: YouTube presence, style (demos, thought leadership, tutorials)
- Podcast: own show or guest appearances
- Documentation: quality, depth, developer-focus signals
- Social: primary channels (LinkedIn, Twitter/X), tone, cadence
- Community: Discord/Slack/forum presence
- Gated content: whitepapers, ebooks (demand gen signals)
- Events: webinars, conference sponsorships

### Growth Engines
Infer from observable signals:
- Inbound (blog/SEO), Outbound (demo CTAs, SDR hiring)
- Product virality (referrals, free tier), Events (webinars, conferences)
- Ecosystem (integrations, partners), Lifecycle (nurture, onboarding)

### Hiring
- Open roles (if careers page accessible)
- Department breakdown
- Growth direction signals

### Recent Moves
- Product launches
- Partnership announcements
- Messaging changes from previous run

### Third-Party Intelligence (Deep Mode)
- External validation, sentiment, rankings, recent news
- Report: **[Found: N sources]**, **[Not found - searched X]**, or **[Skipped - Fast Mode]**

## Snapshot Workflow

For EACH competitor, AFTER extraction:
1. Write current state to `output/snapshots/{domain}.json`
2. If previous snapshot exists, compare each dimension
3. Note changes: `"Hero: 'old' → 'new'"`

### Snapshot Schema

```json
{
  "domain": "competitor.com",
  "captured": "2026-01-16",
  "research_depth": "deep|fast",
  "positioning": { "headline": "", "tagline": "", "value_proposition": "" },
  "target_audience": { "primary": "", "secondary": "" },
  "differentiators": [],
  "pricing": "",
  "customers": { "named": [], "evidence": "" },
  "business_model": { "revenue_model": "", "gtm_motion": "", "monetization_signals": [] },
  "company_stage": { "employee_count": "", "funding_stage": "", "total_raised": "", "market_maturity": "" },
  "content_types": { "blog": {}, "video": {}, "podcast": "", "documentation": {}, "social": {}, "community": {}, "gated_content": false, "events": {} },
  "growth_engines": { "primary": [], "signals": {} },
  "hiring": { "open_roles": [], "departments": [], "growth_signals": "" },
  "recent_moves": [],
  "third_party": { "analyst_coverage": {}, "sentiment": {}, "metrics": {} },
  "sources": [{ "url": "", "type": "primary|research|news|data|sentiment", "date": "" }]
}
```

## Self-Monitoring

Also monitor the user's own company:
- Logo/partner changes
- Messaging shifts
- Feature announcements
- Customer additions/removals
- Pricing changes

Report in "What Changed" table with "Your Company" as competitor name.

## Change Detection

### Per-Source Coverage (Primary)
| Source | Status | Pages Checked | Confidence |
|--------|--------|---------------|------------|
| competitor-a.com | Extracted | homepage, pricing, about, careers | High |
| competitor-b.com | Extracted | homepage, pricing | Medium |
| competitor-c.com | Partial | homepage only (pricing 404) | Low |

### Third-Party Coverage (Deep Mode)
| Competitor | Research | Funding | News | Sentiment | Data |
|------------|----------|---------|------|-----------|------|
| Competitor A | Found | Found | 2 articles | Reddit | Data provider |
| Competitor B | Not found | Found | Not found | Not found | N/A |

### Per-Dimension Coverage
| Dimension | Competitor A | Competitor B | Competitor C |
|-----------|--------------|--------------|--------------|
| Positioning | check | check | check |
| Pricing | check | check | Not found - 404 |
| Customers | check | Not found - no page | check |
| Hiring | Not applicable | check | Not found - 403 |
| Third-Party | 4 sources | 2 sources | Skipped - Fast Mode |

### Confidence Reporting

Per dimension: what found, where, confidence. Note conflicts in Open Questions.
