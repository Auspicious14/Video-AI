// src/templates/Bold.tsx
// ─────────────────────────────────────────────────────────────────────────────
// BOLD — Brand intros (logo placeholder + tagline)
// Aesthetic: massive typographic statements, kinetic text, brand-forward
// Content types: product launches, brand reveals, campaign intros
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
  Easing,
} from "remotion";
import { DesignBrief, DIMENSIONS, FPS } from "../types";
import {
  FadeSlideIn,
  ScaleIn,
  GradientBg,
  useFade,
} from "../components/shared";

const FONT_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=Inter:wght@300;400;600&display=swap');
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

// Word-by-word reveal for the main title
const WordReveal: React.FC<{
  text: string;
  fontSize: number;
  color: string;
  fontFamily: string;
  startFrame: number;
  stagger?: number;
}> = ({ text, fontSize, color, fontFamily, startFrame, stagger = 6 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(" ");

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "0.25em",
        alignItems: "flex-end",
      }}
    >
      {words.map((word, i) => {
        const wordFrame = startFrame + i * stagger;
        const progress = spring({
          frame: frame - wordFrame,
          fps,
          config: { stiffness: 120, damping: 20 },
          // clamp: true,
        });
        const ty = (1 - progress) * 60;
        return (
          <span
            key={i}
            style={{
              fontFamily,
              fontWeight: 800,
              fontSize,
              color,
              lineHeight: 1.0,
              letterSpacing: "-0.03em",
              opacity: progress,
              transform: `translateY(${ty}px)`,
              display: "inline-block",
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};

// Kinetic background shape
const KineticCircle: React.FC<{
  color: string;
  size: number;
  x: string;
  y: string;
  delay: number;
}> = ({ color, size, x, y, delay }) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [delay, delay + 40], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.exp),
  });
  const opacity = interpolate(frame, [delay, delay + 20], [0, 0.15], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        opacity,
        transform: `translate(-50%, -50%) scale(${scale})`,
      }}
    />
  );
};

export const BoldTemplate: React.FC<{ brief: DesignBrief }> = ({ brief }) => {
  const { width, height } = DIMENSIONS[brief.aspectRatio];
  const fonts = getFont(brief.fontPairing);
  const totalFrames = brief.durationSeconds * FPS;
  const frame = useCurrentFrame();

  const isPortrait = brief.aspectRatio === "9:16";
  const isLandscape = brief.aspectRatio === "16:9";

  const px = isPortrait ? 70 : isLandscape ? 140 : 90;
  const titleSize = isPortrait ? 100 : isLandscape ? 120 : 90;
  const taglineSize = isPortrait ? 44 : isLandscape ? 52 : 40;
  const brandSize = isPortrait ? 28 : isLandscape ? 32 : 26;

  const speed =
    brief.animationSpeed === "fast"
      ? 0.6
      : brief.animationSpeed === "slow"
        ? 1.6
        : 1;

  // Slow background drift
  const drift = interpolate(frame, [0, totalFrames], [0, -30], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: brief.bgColor, overflow: "hidden" }}>
      <style dangerouslySetInnerHTML={{ __html: FONT_STYLE }} />

      {/* Deep gradient */}
      <GradientBg
        color1={brief.brandColor + "30"}
        color2={brief.bgColor}
        angle={120}
      />

      {/* Kinetic circles — brand energy */}
      <KineticCircle
        color={brief.brandColor}
        size={600}
        x="85%"
        y="15%"
        delay={0}
      />
      <KineticCircle
        color={brief.accentColor}
        size={400}
        x="10%"
        y="80%"
        delay={10}
      />

      {/* Vertical accent bar (left edge) */}
      <Sequence from={0} durationInFrames={totalFrames}>
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: 8,
            background: `linear-gradient(180deg, ${brief.brandColor}, ${brief.accentColor})`,
          }}
        />
      </Sequence>

      {/* Brand name top */}
      {brief.brandName && (
        <FadeSlideIn
          delay={Math.round(5 * speed)}
          direction="left"
          style={{
            position: "absolute",
            top: isPortrait ? 80 : 60,
            left: px + 20,
          }}
        >
          <span
            style={{
              fontFamily: fonts.body,
              fontWeight: 600,
              fontSize: brandSize,
              color: brief.brandColor,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
            }}
          >
            {brief.brandName}
          </span>
        </FadeSlideIn>
      )}

      {/* Main title — word-by-word kinetic reveal */}
      <div
        style={{
          position: "absolute",
          left: px,
          right: px,
          top: isPortrait ? "30%" : "25%",
          transform: `translateY(${drift}px)`,
        }}
      >
        <WordReveal
          text={brief.title}
          fontSize={titleSize}
          color={brief.textColor}
          fontFamily={fonts.heading}
          startFrame={Math.round(10 * speed)}
          stagger={Math.round(6 * speed)}
        />
      </div>

      {/* Tagline */}
      {brief.tagline && (
        <FadeSlideIn
          delay={Math.round((10 + brief.title.split(" ").length * 6) * speed)}
          direction="up"
          style={{
            position: "absolute",
            left: px,
            right: px,
            bottom: isPortrait ? 200 : 140,
          }}
        >
          <p
            style={{
              fontFamily: fonts.body,
              fontWeight: 300,
              fontSize: taglineSize,
              color: brief.textColor + "BB",
              margin: 0,
              lineHeight: 1.4,
              borderLeft: `4px solid ${brief.accentColor}`,
              paddingLeft: 24,
            }}
          >
            {brief.tagline}
          </p>
        </FadeSlideIn>
      )}

      {/* Subtitle fallback if no tagline */}
      {!brief.tagline && brief.subtitle && (
        <FadeSlideIn
          delay={Math.round((10 + brief.title.split(" ").length * 6) * speed)}
          direction="up"
          style={{
            position: "absolute",
            left: px,
            right: px,
            bottom: isPortrait ? 200 : 140,
          }}
        >
          <p
            style={{
              fontFamily: fonts.body,
              fontWeight: 300,
              fontSize: taglineSize,
              color: brief.textColor + "BB",
              margin: 0,
            }}
          >
            {brief.subtitle}
          </p>
        </FadeSlideIn>
      )}

      {/* CTA pill button */}
      {brief.cta && (
        <ScaleIn
          delay={Math.round(45 * speed)}
          style={{
            position: "absolute",
            bottom: isPortrait ? 80 : 60,
            left: px,
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 16,
              background: brief.brandColor,
              color: "#fff",
              fontFamily: fonts.heading,
              fontWeight: 700,
              fontSize: 28,
              padding: "16px 40px",
              borderRadius: 100,
              letterSpacing: "0.05em",
            }}
          >
            {brief.cta}
            <span style={{ fontSize: 22 }}>↗</span>
          </div>
        </ScaleIn>
      )}
    </AbsoluteFill>
  );
};
