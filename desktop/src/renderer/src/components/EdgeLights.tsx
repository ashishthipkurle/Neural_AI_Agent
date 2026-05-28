import { useEffect, useState } from "react";

type IndraState = "idle" | "listening" | "thinking" | "speaking" | "executing";

const STATE_COLORS: Record<IndraState, [string, string]> = {
  idle:      ["transparent", "transparent"],
  listening: ["#00d4ff", "#0099ff"],      // Cyan — "I hear you"
  thinking:  ["#a855f7", "#6366f1"],      // Purple — "Processing"
  speaking:  ["#22c55e", "#10b981"],      // Green — "Speaking"
  executing: ["#f59e0b", "#ef4444"],      // Amber — "Working"
};

export default function EdgeLights() {
  const [state, setState] = useState<IndraState>("idle");

  // Poll INDRA state every 500ms via REST
  useEffect(() => {
    let active = true;

    const poll = async () => {
      while (active) {
        try {
          const res = await fetch("http://127.0.0.1:8001/api/state");
          if (res.ok) {
            const data = await res.json();
            if (data.state) setState(data.state as IndraState);
          }
        } catch {
          // INDRA not running — stay idle
        }
        await new Promise(r => setTimeout(r, 500));
      }
    };

    poll();
    return () => { active = false; };
  }, []);

  if (state === "idle") return null;

  const [c1, c2] = STATE_COLORS[state] || STATE_COLORS.idle;

  return (
    <>
      <div style={{
        position: "fixed", top: 0, left: 0, right: 0, height: 3,
        zIndex: 9999, pointerEvents: "none",
        background: `linear-gradient(90deg, transparent, ${c1}, ${c2}, ${c1}, transparent)`,
        animation: "edgePulse 1.5s ease-in-out infinite",
      }} />
      <div style={{
        position: "fixed", bottom: 0, left: 0, right: 0, height: 3,
        zIndex: 9999, pointerEvents: "none",
        background: `linear-gradient(90deg, transparent, ${c1}, ${c2}, ${c1}, transparent)`,
        animation: "edgePulse 1.5s ease-in-out infinite",
      }} />
      <div style={{
        position: "fixed", top: 0, left: 0, bottom: 0, width: 3,
        zIndex: 9999, pointerEvents: "none",
        background: `linear-gradient(180deg, transparent, ${c1}, ${c2}, ${c1}, transparent)`,
        animation: "edgePulse 1.5s ease-in-out infinite",
      }} />
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: 3,
        zIndex: 9999, pointerEvents: "none",
        background: `linear-gradient(180deg, transparent, ${c1}, ${c2}, ${c1}, transparent)`,
        animation: "edgePulse 1.5s ease-in-out infinite",
      }} />

      <style>{`
        @keyframes edgePulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
      `}</style>
    </>
  );
}
