# Provenance rules

1. Canonical URL first. A URL is taken from the page, never constructed. This binds every URL the
   run touches, not only the ones the brief prints: a slug handed to a tool is a constructed URL
   and is not canonical. Derive a company's LinkedIn slug from the `linkedin.com/company/...` href
   in its own footer, never from its name.
2. Blank beats guess. An empty cell is a finding; a plausible cell is a defect.
3. "No" is not "Unknown". They are distinct matrix values and render differently.
4. Verified-blocked is not verified-absent. A 403 is recorded as blocked, with the query shapes
   tried, and so is any other refusal to serve the page: a 401, a 429, or LinkedIn's 999. Only a
   404 on a canonical path is absent, and a path this run constructed is not canonical. A source
   that answers and does not carry the value is neither: that is the empty cell rule 2 calls a
   finding, and the note says the page was reached and the value was not on it.
5. Name the second source or do not call it verified. The second look uses a **different source**:
   re-reading the same URL with the same tool is not a check, because it returns the same answer
   whether that answer was right or invented, and a cached fetch returns it byte for byte, so a run
   can report a clean pass having confirmed nothing. For each claim the run calls verified, the
   ledger row names which other source carried the value.
6. Where two sources disagree and neither is decisive, carry the range, not a midpoint.
7. A green result is not a verified result. A tool that exits 0 and a page that answers 200 have
   answered about **some** entity; before the number enters the brief, confirm from the page itself
   that the entity is the company the brief is about, by its `<title>` and description, and say in
   the note what confirmed it. A page that does not carry the company's name is confirmed by the
   footer href that reached it.
