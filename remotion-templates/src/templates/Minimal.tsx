// src/templates/Minimal.tsx
// ─────────────────────────────────────────────────────────────────────────────
// MINIMAL — Quote cards & flyer-to-motion
// Aesthetic: editorial typography, generous whitespace, single accent line
// Content types: quote cards, promotional flyers, clean announcements
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  AbsoluteFill,
  Sequence,
} from "remotion";
import { DesignBrief, DIMENSIONS, FPS } from "../types";
import {
  FadeSlideIn,
  AnimatedLine,
  useFade,
  GradientBg,
} from "../components/shared";

// ── Font URLs (loaded via @remotion/google-fonts alternative: inline style) ───
const FONT_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=Inter:wght@300;400;600&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
`;

function getFont(pairing: DesignBrief["fontPairing"]) {
  switch (pairing) {
    case "syne_dmsans":
      return { heading: "Syne", body: "DM Sans" };
    case "playfair_inter":
      return { heading: "Playfair Display", body: "Inter" };
    default:
      return { heading: "Inter", body: "Inter" };
  }
}

// ── Main component ─────────────────────────────────────────────────────────────
export const MinimalTemplate: React.FC<{ brief: DesignBrief }> = ({
  brief,
}) => {
  const { width, height } = DIMENSIONS[brief.aspectRatio];
  const fonts = getFont(brief.fontPairing);
  const totalFrames = brief.durationSeconds * FPS;

  // Speed multiplier
  const speed =
    brief.animationSpeed === "fast"
      ? 0.6
      : brief.animationSpeed === "slow"
        ? 1.6
        : 1;

  const isPortrait = brief.aspectRatio === "9:16";
  const isLandscape = brief.aspectRatio === "16:9";

  const px = isPortrait ? 80 : isLandscape ? 160 : 100;
  const titleSize = isPortrait ? 72 : isLandscape ? 80 : 68;
  const bodySize = isPortrait ? 36 : isLandscape ? 36 : 34;
  const subtitleSz = isPortrait ? 40 : isLandscape ? 44 : 38;

  return (
    <AbsoluteFill style={{ background: brief.bgColor, fontFamily: fonts.body }}>
      <style dangerouslySetInnerHTML={{ __html: FONT_STYLE }} />

      {/* Subtle gradient wash */}
      <GradientBg
        color1={brief.bgColor}
        color2={brief.brandColor + "18"}
        angle={160}
      />

      {/* Decorative top accent bar */}
      <Sequence from={0} durationInFrames={totalFrames}>
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 6,
            background: brief.brandColor,
          }}
        />
      </Sequence>

      {/* Brand name (top-left) */}
      {brief.brandName && (
        <FadeSlideIn
          delay={5 * speed}
          direction="down"
          style={{
            position: "absolute",
            top: 48,
            left: px,
          }}
        >
          <span
            style={{
              fontFamily: fonts.heading,
              fontWeight: 700,
              fontSize: 26,
              color: brief.brandColor,
              letterSpacing: "0.15em",
              textTransform: "uppercase",
            }}
          >
            {brief.brandName}
          </span>
        </FadeSlideIn>
      )}

      {/* Main content block */}
      <div
        style={{
          position: "absolute",
          left: px,
          right: px,
          top: "50%",
          transform: "translateY(-50%)",
          display: "flex",
          flexDirection: "column",
          gap: 32,
        }}
      >
        {/* Accent line */}
        <AnimatedLine
          color={brief.brandColor}
          delay={Math.round(8 * speed)}
          thickness={4}
        />

        {/* Title */}
        <FadeSlideIn delay={Math.round(12 * speed)} direction="up">
          <h1
            style={{
              fontFamily: fonts.heading,
              fontWeight: 800,
              fontSize: titleSize,
              lineHeight: 1.1,
              color: brief.textColor,
              margin: 0,
              letterSpacing: "-0.02em",
            }}
          >
            {brief.title}
          </h1>
        </FadeSlideIn>

        {/* Body / Quote text */}
        {brief.bodyText && (
          <FadeSlideIn delay={Math.round(22 * speed)} direction="up">
            <p
              style={{
                fontFamily: fonts.body,
                fontWeight: 300,
                fontSize: bodySize,
                lineHeight: 1.65,
                color: brief.textColor + "CC",
                margin: 0,
              }}
            >
              {brief.bodyText}
            </p>
          </FadeSlideIn>
        )}

        {/* Subtitle */}
        {brief.subtitle && (
          <FadeSlideIn delay={Math.round(28 * speed)} direction="up">
            <p
              style={{
                fontFamily: fonts.body,
                fontWeight: 500,
                fontSize: subtitleSz,
                color: brief.accentColor,
                margin: 0,
              }}
            >
              {brief.subtitle}
            </p>
          </FadeSlideIn>
        )}
      </div>

      {/* CTA bottom */}
      {brief.cta && (
        <FadeSlideIn
          delay={Math.round(35 * speed)}
          direction="up"
          style={{
            position: "absolute",
            bottom: 80,
            left: px,
            right: px,
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 12,
              borderBottom: `2px solid ${brief.brandColor}`,
              paddingBottom: 8,
            }}
          >
            <span
              style={{
                fontFamily: fonts.heading,
                fontWeight: 700,
                fontSize: 30,
                color: brief.textColor,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}
            >
              {brief.cta}
            </span>
            <span style={{ color: brief.brandColor, fontSize: 30 }}>→</span>
          </div>
        </FadeSlideIn>
      )}

      {/* Decorative bottom-right corner dot */}
      <FadeSlideIn
        delay={Math.round(20 * speed)}
        style={{
          position: "absolute",
          bottom: 60,
          right: px,
        }}
      >
        <div
          style={{
            width: 60,
            height: 60,
            borderRadius: "50%",
            border: `3px solid ${brief.brandColor}40`,
          }}
        />
      </FadeSlideIn>
    </AbsoluteFill>
  );
};
