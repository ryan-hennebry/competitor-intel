export type LineKind =
  | "command"
  | "assistant"
  | "user"
  | "option"
  | "section"
  | "status"
  | "reset";

export type ScriptLine = {
  kind: LineKind;
  text: string;
  start: number;
  typingSpeed?: number;
};

const typingDuration = (line: ScriptLine): number => {
  if (line.kind !== "command" && line.kind !== "user") {
    return 24;
  }

  const speed = line.typingSpeed ?? 2;
  return Math.max(20, line.text.length * speed);
};

export const CLI_LINES: ScriptLine[] = [
  {
    kind: "command",
    text: "$ git clone https://github.com/ryan-hennebry/competitor-intel.git && cd competitor-intel && claude --dangerously-skip-permissions",
    start: 6,
    typingSpeed: 0.85,
  },
  {
    kind: "assistant",
    text: "I'm your competitor briefing agent. I track positioning changes, threat shifts, and the moves that deserve action.",
    start: 165,
  },
  {
    kind: "assistant",
    text: "What company do you want to analyze? (URL or description)",
    start: 225,
  },
  {
    kind: "user",
    text: "cursor.com",
    start: 275,
    typingSpeed: 2.8,
  },
  {
    kind: "assistant",
    text: "I found: Cursor is positioning itself as an AI-native code editor for software engineers and technical teams. Sound right?",
    start: 330,
  },
  { kind: "section", text: "Competitors", start: 380 },
  {
    kind: "assistant",
    text: "Suggested competitors based on positioning overlap:",
    start: 410,
  },
  { kind: "option", text: "Name             Threat   Why it matters", start: 440 },
  { kind: "option", text: "Windsurf         High     AI IDE with deep agent workflows", start: 470 },
  { kind: "option", text: "GitHub Copilot   High     Broad distribution in developer tooling", start: 500 },
  { kind: "option", text: "Replit           Watch    Collaborative coding with AI assistance", start: 530 },
  { kind: "option", text: "Cody             Watch    Codebase-aware assistant for enterprise teams", start: 560 },
  {
    kind: "assistant",
    text: "Modify your competitor list?",
    start: 595,
  },
  {
    kind: "option",
    text: "Select one: accept these 4, add competitors, or remove competitors",
    start: 625,
  },
  { kind: "user", text: "Accept these 4", start: 670, typingSpeed: 2.8 },
  { kind: "section", text: "Priorities", start: 705 },
  { kind: "assistant", text: "I will track these signals by default:", start: 735 },
  { kind: "option", text: "• Positioning changes", start: 760 },
  { kind: "option", text: "• Partnership announcements", start: 780 },
  { kind: "option", text: "• New features", start: 800 },
  { kind: "option", text: "• Enterprise deals", start: 820 },
  { kind: "option", text: "• Hiring patterns", start: 840 },
  { kind: "assistant", text: "Adjust tracking priorities?", start: 870 },
  {
    kind: "option",
    text: "Select one: accept defaults or customize",
    start: 900,
  },
  { kind: "user", text: "Accept defaults", start: 940, typingSpeed: 2.8 },
  { kind: "section", text: "Delivery", start: 975 },
  { kind: "assistant", text: "Where should I send briefings?", start: 1005 },
  {
    kind: "option",
    text: "Select one: files only, email, Slack, or both",
    start: 1035,
  },
  { kind: "user", text: "Save to files only", start: 1080, typingSpeed: 2.8 },
  {
    kind: "assistant",
    text: "Setup complete. Ready to generate your first briefing?",
    start: 1125,
  },
  { kind: "user", text: "Generate this week's briefing", start: 1180, typingSpeed: 2.5 },
  { kind: "status", text: "Researching competitors and extracting changes...", start: 1250 },
  {
    kind: "status",
    text: "Comparing this week against the last saved snapshots...",
    start: 1325,
  },
  { kind: "section", text: "Briefing Preview", start: 1385 },
  {
    kind: "assistant",
    text: "Quick take: Windsurf is pushing agent workflows more aggressively this week. The main risk is losing hands-on workflow proof mindshare.",
    start: 1420,
  },
  {
    kind: "option",
    text: "Act Now: publish a side-by-side workflow proof before Windsurf owns the category story",
    start: 1495,
  },
  {
    kind: "option",
    text: "Watch: GitHub Copilot is strengthening enterprise packaging and distribution",
    start: 1540,
  },
  {
    kind: "option",
    text: "Opportunity: Cody still looks weaker on clear workflow proof for smaller teams",
    start: 1585,
  },
  {
    kind: "assistant",
    text: "Briefing saved to output/briefings/2026-03-12-briefing.pdf",
    start: 1645,
  },
  {
    kind: "assistant",
    text: "Files-only is still on. If you want, I can set up weekly email or Slack delivery next.",
    start: 1705,
  },
  {
    kind: "reset",
    text: "",
    start: 1795,
  },
];

const finalFrame = CLI_LINES.reduce((max, line) => {
  return Math.max(max, line.start + typingDuration(line));
}, 0);

export const CLI_DURATION_IN_FRAMES = finalFrame + 45;
