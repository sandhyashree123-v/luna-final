import React, { useMemo } from "react";
import LunaPresenceOrb from "./LunaPresenceOrb";

const MOOD_LOOKS = {
  angry: { aura: "rgba(255, 170, 155, 0.24)", light: "#ffb9aa", subtitle: "firm but calm" },
  sad: { aura: "rgba(190, 207, 255, 0.22)", light: "#d6e1ff", subtitle: "soft and close" },
  anxious: { aura: "rgba(178, 233, 255, 0.24)", light: "#d6f4ff", subtitle: "gentle and attentive" },
  overwhelmed: { aura: "rgba(212, 201, 255, 0.22)", light: "#e3dbff", subtitle: "holding steady with you" },
  tired: { aura: "rgba(255, 229, 198, 0.2)", light: "#f6ddbf", subtitle: "sleepy and warm" },
  hopeful: { aura: "rgba(255, 228, 166, 0.24)", light: "#ffe6b7", subtitle: "bright and reassuring" },
  neutral: { aura: "rgba(255, 236, 204, 0.2)", light: "#f8e4c8", subtitle: "quietly with you" },
};

function truncateCaption(text) {
  const clean = (text || "").trim();
  if (!clean) return "Luna is here with you.";
  return clean.length > 110 ? `${clean.slice(0, 110).trimEnd()}...` : clean;
}

export default function MoonScene({
  mood = "neutral",
  isSpeaking = false,
  lipSyncAmpRef = null,
  activeText = "",
}) {
  const look = MOOD_LOOKS[mood] || MOOD_LOOKS.neutral;
  const caption = useMemo(() => truncateCaption(activeText), [activeText]);

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
        borderRadius: "22px 26px 20px 18px",
        background: `
          linear-gradient(175deg, #0c0914 0%, #070610 52%, #040308 100%)
        `,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `
            radial-gradient(circle at 50% 90%, rgba(0, 0, 0, 0.2) 0%, transparent 52%)
          `,
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          position: "absolute",
          inset: "18px 18px 106px",
          borderRadius: "28px",
          overflow: "hidden",
          background: `
            radial-gradient(circle at 50% 100%, rgba(0, 0, 0, 0.32) 0%, transparent 48%),
            transparent
          `,
          boxShadow: `
            0 24px 64px rgba(0,0,0,0.38)
          `,
        }}
      >
        <LunaPresenceOrb isSpeaking={isSpeaking} lipSyncAmpRef={lipSyncAmpRef} />

        <div
          style={{
            position: "absolute",
            inset: 0,
            boxShadow: "inset 0 -72px 100px rgba(5, 6, 16, 0.65)",
            borderRadius: "28px",
            pointerEvents: "none",
          }}
        />
      </div>

      <div
        style={{
          position: "absolute",
          left: "18px",
          right: "18px",
          bottom: "18px",
          padding: "14px 16px",
          borderRadius: "17px 20px 16px 19px",
          background:
            "linear-gradient(182deg, rgba(16, 14, 26, 0.55), rgba(7, 6, 13, 0.92))",
          border: "1px solid rgba(255,255,255,0.08)",
          color: "#eceef4",
          backdropFilter: "blur(18px) saturate(1.05)",
          boxShadow: "0 14px 40px rgba(0,0,0,0.32)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "12px",
            alignItems: "center",
            marginBottom: "8px",
            fontSize: "0.7rem",
            letterSpacing: "0.06em",
            textTransform: "none",
            fontFamily: "var(--font-ui), system-ui, sans-serif",
            fontWeight: 500,
            color: "rgba(200,206,218,0.78)",
          }}
        >
          <span>Luna</span>
          <span>{isSpeaking ? "Speaking" : "Listening"}</span>
        </div>
        <div
          style={{
            fontFamily: "var(--font-ui), system-ui, sans-serif",
            fontSize: "0.9rem",
            lineHeight: 1.52,
            fontWeight: 450,
            letterSpacing: "0.01em",
          }}
        >
          {caption}
        </div>
        <div
          style={{
            marginTop: "8px",
            fontSize: "0.76rem",
            fontFamily: "var(--font-display), serif",
            fontStyle: "italic",
            letterSpacing: "0.03em",
            color: "rgba(230,226,246,0.58)",
          }}
        >
          {look.subtitle}
        </div>
      </div>
    </div>
  );
}
