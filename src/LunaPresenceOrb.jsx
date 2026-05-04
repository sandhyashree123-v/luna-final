import React, { useEffect, useRef } from "react";

/**
 * Gemini-style presence orb: sharp raster, restrained glow scaled by voice energy — no blur filters.
 */
export default function LunaPresenceOrb({ isSpeaking = false, lipSyncAmpRef = null }) {
  const rootRef = useRef(null);

  useEffect(() => {
    let raf = 0;

    const tick = () => {
      const root = rootRef.current;
      const t = performance.now() * 0.001;
      const idleRipple = 0.045 + Math.sin(t * 0.62) * 0.022;
      const voiceAmp = isSpeaking ? Math.min(1, Math.max(0, lipSyncAmpRef?.current ?? 0)) : 0;
      const voiceEnergy = isSpeaking
        ? Math.min(1, Math.max(0.26, voiceAmp * 1.35 + Math.sin(t * 7.2) * 0.05))
        : 0;

      const energy = idleRipple;

      if (root) {
        root.style.setProperty("--orb-energy", Math.max(0, Math.min(1, energy)).toFixed(4));
        root.style.setProperty("--voice-energy", voiceEnergy.toFixed(4));
        root.style.setProperty("--orb-tilt", `${Math.sin(t * 0.26) * 0.7}deg`);
        root.style.setProperty("--orb-wobble-x", `${Math.sin(t * 0.82) * 0.35}%`);
        root.style.setProperty("--orb-wobble-y", `${Math.cos(t * 0.72) * 0.3}%`);
        root.style.setProperty("--orb-r1", `${50 + Math.sin(t * 2.3) * 0.6}%`);
        root.style.setProperty("--orb-r2", `${50 + Math.cos(t * 1.9) * 0.5}%`);
        root.style.setProperty("--orb-r3", `${50 + Math.sin(t * 2.7 + 1.2) * 0.6}%`);
        root.style.setProperty("--orb-r4", `${50 + Math.cos(t * 2.15 + 0.8) * 0.5}%`);
        root.style.setProperty("--orb-r5", `${50 + Math.sin(t * 2.05 + 2.1) * 0.45}%`);
        root.style.setProperty("--orb-r6", `${50 + Math.cos(t * 2.55 + 1.7) * 0.5}%`);
        root.style.setProperty("--orb-r7", `${50 + Math.sin(t * 1.85 + 0.5) * 0.45}%`);
        root.style.setProperty("--orb-r8", `${50 + Math.cos(t * 2.35 + 2.6) * 0.45}%`);
      }

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [isSpeaking, lipSyncAmpRef]);

  const coreBg = `
    radial-gradient(circle at 24% 22%, rgba(201,184,220,0.46) 0 0.9px, transparent 1.4px),
    radial-gradient(circle at 63% 31%, rgba(168,146,200,0.38) 0 0.75px, transparent 1.25px),
    radial-gradient(circle at 73% 68%, rgba(138,164,184,0.36) 0 0.8px, transparent 1.3px),
    radial-gradient(circle at 38% 76%, rgba(184,154,152,0.34) 0 0.7px, transparent 1.2px),
    radial-gradient(ellipse 42% 28% at 72% 42%, rgba(201,184,220,0.34) 0%, rgba(168,146,200,0.2) 22%, transparent 58%),
    radial-gradient(ellipse 38% 26% at 24% 88%, rgba(184,154,152,0.26) 0%, rgba(168,146,200,0.16) 26%, transparent 62%),
    radial-gradient(ellipse 64% 42% at 70% 18%, rgba(201,184,220,0.3) 0%, rgba(138,164,184,0.22) 34%, transparent 64%),
    radial-gradient(ellipse 54% 42% at 88% 58%, rgba(184,154,152,0.34) 0%, rgba(168,146,200,0.24) 40%, transparent 68%),
    radial-gradient(ellipse 44% 58% at 18% 48%, rgba(201,184,220,0.28) 0%, rgba(128,110,176,0.22) 45%, transparent 72%),
    radial-gradient(ellipse 48% 60% at 62% 70%, rgba(168,146,200,0.22) 0%, transparent 60%),
    radial-gradient(circle at 48% 54%, rgba(62,53,92,0.96) 0%, rgba(34,29,66,0.98) 42%, rgba(11,9,30,1) 78%, rgba(4,3,14,1) 100%),
    radial-gradient(circle at 18% 78%, rgba(138,164,184,0.14) 0%, transparent 42%)
  `;

  return (
    <div
      ref={rootRef}
      className="luna-orb-stage"
      data-speaking={isSpeaking ? "true" : undefined}
      aria-label={isSpeaking ? "Luna is speaking" : "Luna is ready"}
      role="img"
    >
      <div className="luna-cosmos-deep" aria-hidden />
      <div className="luna-cosmos-nebula" aria-hidden />
      <div className="luna-cosmos-dust" aria-hidden />
      <div className="luna-cosmos-stars" aria-hidden />

      <div className="luna-orb-assembly">
        <div className="luna-orb-glow-sheet" aria-hidden />
        <div className="luna-orb-ground-glow" aria-hidden />

        <div className="luna-orb-body">
          <div className="luna-orb-core" style={{ background: coreBg }} />
          <div className="luna-orb-sheen" aria-hidden />
          <div className="luna-orb-spark luna-orb-spark-a" aria-hidden />
          <div className="luna-orb-spark luna-orb-spark-b" aria-hidden />
        </div>

        <div className="luna-orb-rim-lit" aria-hidden />
      </div>

      <p className="luna-orb-hint">{isSpeaking ? "Speaking" : "Listening"}</p>
    </div>
  );
}
