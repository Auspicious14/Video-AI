// src/Root.tsx
// ─────────────────────────────────────────────────────────────────────────────
// Registers all four compositions. Each reads its own props from the brief.
// Dimensions and duration are driven by the DesignBrief passed via --props.
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";
import { Composition } from "remotion";
import { DesignBrief, DIMENSIONS, FPS } from "./types";
import { MinimalTemplate } from "./templates/Minimal";
import { BoldTemplate } from "./templates/Bold";
import { GlassmorphismTemplate } from "./templates/Glassmorphism";
import { NeonTemplate } from "./templates/Neon";

// Default brief — used for Remotion Studio preview only.
// Python always passes its own props via --props.
const DEFAULT_BRIEF: DesignBrief = {
  style: "minimal",
  aspectRatio: "9:16",
  durationSeconds: 15,
  brandName: "VideoAI",
  brandColor: "#F4A931",
  accentColor: "#FF6B35",
  bgColor: "#0A0A0A",
  textColor: "#FFFFFF",
  title: "Motion Design Preview",
  subtitle: "Powered by Remotion",
  bodyText:
    "This is a sample quote or body text that appears in the minimal template.",
  tagline: "Your brand. Animated.",
  cta: "Get Started",
  stats: [
    { label: "Revenue", value: "₦2.4M", prefix: "₦", numericValue: 2400 },
    { label: "Users", value: "12K", suffix: "K", numericValue: 12 },
    { label: "Growth", value: "340%", suffix: "%", numericValue: 340 },
    { label: "Countries", value: "6", numericValue: 6 },
  ],
  listItems: [
    {
      index: 1,
      headline: "Start with a strong hook",
      body: "Grab attention in the first 2 seconds",
      emoji: "🎯",
    },
    {
      index: 2,
      headline: "Keep it visual",
      body: "Show, don't tell",
      emoji: "📸",
    },
    {
      index: 3,
      headline: "End with a clear CTA",
      body: "Tell them exactly what to do next",
      emoji: "🚀",
    },
  ],
  animationSpeed: "normal",
  fontPairing: "syne_dmsans",
  sourceType: "prompt",
};

// Helper: compute durationInFrames from brief props
function getDuration(props: DesignBrief) {
  return (props.durationSeconds ?? DEFAULT_BRIEF.durationSeconds) * FPS;
}

function getDims(props: DesignBrief) {
  return DIMENSIONS[props.aspectRatio ?? "9:16"];
}

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* ── 1. Minimal — Quote cards & flyers ──────────────────────────── */}
      <Composition
        id="MinimalVideo"
        component={({ brief }: { brief: DesignBrief }) => (
          <MinimalTemplate brief={brief} />
        )}
        durationInFrames={getDuration(DEFAULT_BRIEF)}
        fps={FPS}
        width={getDims(DEFAULT_BRIEF).width}
        height={getDims(DEFAULT_BRIEF).height}
        defaultProps={{ brief: DEFAULT_BRIEF }}
        calculateMetadata={({ props }) => ({
          durationInFrames: getDuration(props.brief),
          width: getDims(props.brief).width,
          height: getDims(props.brief).height,
        })}
      />

      {/* ── 2. Bold — Brand intros ──────────────────────────────────────── */}
      <Composition
        id="BoldVideo"
        component={({ brief }: { brief: DesignBrief }) => (
          <BoldTemplate brief={brief} />
        )}
        durationInFrames={getDuration(DEFAULT_BRIEF)}
        fps={FPS}
        width={getDims(DEFAULT_BRIEF).width}
        height={getDims(DEFAULT_BRIEF).height}
        defaultProps={{ brief: { ...DEFAULT_BRIEF, style: "bold" } }}
        calculateMetadata={({ props }) => ({
          durationInFrames: getDuration(props.brief),
          width: getDims(props.brief).width,
          height: getDims(props.brief).height,
        })}
      />

      {/* ── 3. Glassmorphism — Stats & data reveals ─────────────────────── */}
      <Composition
        id="GlassmorphismVideo"
        component={({ brief }: { brief: DesignBrief }) => (
          <GlassmorphismTemplate brief={brief} />
        )}
        durationInFrames={getDuration(DEFAULT_BRIEF)}
        fps={FPS}
        width={getDims(DEFAULT_BRIEF).width}
        height={getDims(DEFAULT_BRIEF).height}
        defaultProps={{ brief: { ...DEFAULT_BRIEF, style: "glassmorphism" } }}
        calculateMetadata={({ props }) => ({
          durationInFrames: getDuration(props.brief),
          width: getDims(props.brief).width,
          height: getDims(props.brief).height,
        })}
      />

      {/* ── 4. Neon — Listicles & tip lists ────────────────────────────── */}
      <Composition
        id="NeonVideo"
        component={({ brief }: { brief: DesignBrief }) => (
          <NeonTemplate brief={brief} />
        )}
        durationInFrames={getDuration(DEFAULT_BRIEF)}
        fps={FPS}
        width={getDims(DEFAULT_BRIEF).width}
        height={getDims(DEFAULT_BRIEF).height}
        defaultProps={{ brief: { ...DEFAULT_BRIEF, style: "neon" } }}
        calculateMetadata={({ props }) => ({
          durationInFrames: getDuration(props.brief),
          width: getDims(props.brief).width,
          height: getDims(props.brief).height,
        })}
      />
    </>
  );
};
