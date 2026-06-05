import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { CLI_LINES, ScriptLine } from "./cliDemoData";

const kindColor = (kind: ScriptLine["kind"]): string => {
  switch (kind) {
    case "command":
      return "#e6edf3";
    case "assistant":
      return "#e6edf3";
    case "user":
      return "#e6edf3";
    case "option":
      return "#e6edf3";
    case "section":
      return "#f0f6fc";
    case "status":
      return "#e6edf3";
    default:
      return "#e6edf3";
  }
};

const kindPrefix = (kind: ScriptLine["kind"]): string => {
  switch (kind) {
    case "assistant":
      return "• Claude";
    case "user":
      return "> You";
    case "status":
      return "• Status";
    default:
      return "";
  }
};

export const CliDemoComposition: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const reveal = spring({
    fps,
    frame,
    config: { damping: 160, stiffness: 120 },
  });

  const visible = CLI_LINES.map((line) => {
    if (frame < line.start) {
      return null;
    }

    if (line.kind === "reset") {
      return {
        ...line,
        shownText: "",
        isTyping: false,
      };
    }

    if (line.kind !== "command" && line.kind !== "user") {
      return {
        ...line,
        shownText: line.text,
        isTyping: false,
      };
    }

    const speed = line.typingSpeed ?? 2;
    const chars = Math.max(0, Math.floor((frame - line.start) / speed));
    const shownText = line.text.slice(0, chars);
    const isTyping = chars < line.text.length;

    if (!shownText.length) {
      return null;
    }

    return {
      ...line,
      shownText,
      isTyping,
    };
  }).filter(Boolean);

  let lastResetIndex = -1;
  for (let i = visible.length - 1; i >= 0; i -= 1) {
    const typedLine = visible[i] as { kind: ScriptLine["kind"] };
    if (typedLine.kind === "reset") {
      lastResetIndex = i;
      break;
    }
  }
  const postReset =
    lastResetIndex >= 0 ? visible.slice(lastResetIndex + 1) : visible;
  const linesToRender = postReset.slice(-11);
  const blink = Math.floor(frame / 12) % 2 === 0;

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(circle at 18% 14%, #161b22 0%, #0d1117 42%, #080c12 100%)",
        fontFamily:
          "'JetBrains Mono', 'SFMono-Regular', Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
      }}
    >
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          transform: `translateY(${interpolate(reveal, [0, 1], [18, 0])}px)`,
        }}
      >
        <div
          style={{
            width: 1120,
            height: 620,
            borderRadius: 10,
            border: "1px solid #30363d",
            background: "#0d1117",
            boxShadow: "0 18px 50px rgba(0, 0, 0, 0.55)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: 48,
              borderBottom: "1px solid #30363d",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "0 18px",
              background: "#161b22",
              color: "#e6edf3",
              fontSize: 16,
              fontWeight: 500,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ width: 10, height: 10, borderRadius: 999, background: "#f85149" }} />
              <span style={{ width: 10, height: 10, borderRadius: 999, background: "#d29922" }} />
              <span style={{ width: 10, height: 10, borderRadius: 999, background: "#3fb950" }} />
              <span style={{ color: "#e6edf3" }}>competitor-intel</span>
            </div>
            <span style={{ color: "#e6edf3", fontSize: 16 }}>claude code</span>
          </div>

          <div
            style={{
              padding: "26px 32px",
              fontSize: 18,
              lineHeight: 1.65,
              whiteSpace: "pre-wrap",
              letterSpacing: 0,
            }}
          >
            {linesToRender.map((line, index) => {
              const typedLine = line as {
                kind: ScriptLine["kind"];
                shownText: string;
                isTyping: boolean;
              };

              const isActive = typedLine.isTyping && index === linesToRender.length - 1;

              return (
                <div
                  key={`${index}-${typedLine.shownText}`}
                  style={{
                    color: kindColor(typedLine.kind),
                    marginBottom:
                      typedLine.kind === "section"
                        ? 28
                        : typedLine.kind === "assistant" ||
                            typedLine.kind === "user" ||
                            typedLine.kind === "status"
                          ? 16
                          : 10,
                    fontWeight: typedLine.kind === "section" ? 700 : 500,
                    marginTop: typedLine.kind === "section" ? 6 : 0,
                  }}
                >
                  {typedLine.kind === "section" ? (
                    `--- ${typedLine.shownText} ---`
                  ) : typedLine.kind === "assistant" ||
                    typedLine.kind === "user" ||
                    typedLine.kind === "status" ? (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "118px 1fr",
                        columnGap: 18,
                        alignItems: "start",
                      }}
                    >
                      <span style={{ color: "#e6edf3", fontWeight: 600 }}>{kindPrefix(typedLine.kind)}</span>
                      <span>
                        {typedLine.shownText}
                        {isActive && blink ? " █" : ""}
                      </span>
                    </div>
                  ) : (
                    <>
                      {typedLine.shownText}
                      {isActive && blink ? " █" : ""}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
