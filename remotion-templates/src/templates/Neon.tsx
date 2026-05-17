// src/templates/Neon.tsx
// ─────────────────────────────────────────────────────────────────────────────
// NEON — Listicles & tip lists
// Aesthetic: dark background, neon glow accents, numbered items with stagger
// Content types: "5 tips for...", "Top 3 reasons...", how-to lists
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
} from "remotion";
import { DesignBrief, DIMENSIONS, FPS } from "../types";
import { FadeSlideIn, ScaleIn, GradientBg } from "../components/shared";

const FONT_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');
`;

function getFont(pairing: DesignBrief["fontPairing"]) {
  if (pairing === "syne_dmsans") return { heading: "Syne", body: "DM Sans" };
  return { heading: "Inter", body: "Inter" };
}

// Neon glow text helper
function neonGlow(color: string, strength: number = 1) {
  return `0 0 ${10 * strength}px ${color}, 0 0 ${30 * strength}px ${color}60, 0 0 ${60 * strength}px ${color}30`;
}

// Scan-line overlay — subtle CRT feel
const ScanLines: React.FC = () => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      backgroundImage:
        "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)",
      pointerEvents: "none",
      zIndex: 10,
    }}
  />
);

// Neon number badge
const NeonBadge: React.FC<{
  number: number;
  color: string;
  size: number;
  fonts: { heading: string };
}> = ({ number, color, size, fonts }) => (
  <div
    style={{
      width: size,
      height: size,
      borderRadius: "50%",
      border: `2px solid ${color}`,
      boxShadow: neonGlow(color, 0.8),
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
    }}
  >
    <span
      style={{
        fontFamily: fonts.heading,
        fontWeight: 800,
        fontSize: size * 0.45,
        color,
        textShadow: neonGlow(color),
      }}
    >
      {number}
    </span>
  </div>
);

// Single list item with slide-in animation
const ListItem: React.FC<{
  index: number;
  headline: string;
  body?: string;
  emoji?: string;
  brandColor: string;
  accentColor: string;
  textColor: string;
  fonts: { heading: string; body: string };
  delay: number;
  isPortrait: boolean;
}> = ({
  index,
  headline,
  body,
  emoji,
  brandColor,
  accentColor,
  textColor,
  fonts,
  delay,
  isPortrait,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Alternate neon colors per item
  const itemColor = index % 2 === 1 ? brandColor : accentColor;

  const entrance = spring({
    frame: frame - delay,
    fps,
    config: { stiffness: 80, damping: 18 },
    // clamp: true,
  });

  const tx = (1 - entrance) * -80;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: isPortrait ? 24 : 28,
        opacity: entrance,
        transform: `translateX(${tx}px)`,
      }}
    >
      {/* Neon number */}
      <NeonBadge
        number={index}
        color={itemColor}
        size={isPortrait ? 64 : 56}
        fonts={fonts}
      />

      {/* Content */}
      <div style={{ flex: 1, paddingTop: 8 }}>
        <div
          style={{
            fontFamily: fonts.heading,
            fontWeight: 700,
            fontSize: isPortrait ? 34 : 30,
            color: textColor,
            lineHeight: 1.2,
            marginBottom: body ? 8 : 0,
          }}
        >
          {emoji && <span style={{ marginRight: 10 }}>{emoji}</span>}
          {headline}
        </div>
        {body && (
          <div
            style={{
              fontFamily: fonts.body,
              fontWeight: 300,
              fontSize: isPortrait ? 24 : 22,
              color: textColor + "88",
              lineHeight: 1.4,
            }}
          >
            {body}
          </div>
        )}
      </div>
    </div>
  );
};

// Neon divider line
const NeonDivider: React.FC<{ color: string; delay: number }> = ({
  color,
  delay,
}) => {
  const frame = useCurrentFrame();
  const width = interpolate(frame, [delay, delay + 15], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        height: 1,
        width: `${width}%`,
        background: `linear-gradient(90deg, ${color}00, ${color}80, ${color}00)`,
        boxShadow: `0 0 8px ${color}60`,
      }}
    />
  );
};

export const NeonTemplate: React.FC<{ brief: DesignBrief }> = ({ brief }) => {
  const { width, height } = DIMENSIONS[brief.aspectRatio];
  const fonts = getFont(brief.fontPairing);

  const isPortrait = brief.aspectRatio === "9:16";
  const isLandscape = brief.aspectRatio === "16:9";

  const px = isPortrait ? 60 : isLandscape ? 100 : 70;
  const titleSize = isPortrait ? 52 : isLandscape ? 60 : 48;

  const speed =
    brief.animationSpeed === "fast"
      ? 0.6
      : brief.animationSpeed === "slow"
        ? 1.6
        : 1;
  const items = brief.listItems ?? [];

  // Layout: landscape can do 2 columns if many items
  const twoColumn = isLandscape && items.length > 3;

  return (
    <AbsoluteFill style={{ background: "#050510", overflow: "hidden" }}>
      <style dangerouslySetInnerHTML={{ __html: FONT_STYLE }} />
      <ScanLines />

      {/* Deep space gradient */}
      <GradientBg color1={"#0a0a20"} color2={"#050510"} angle={180} />

      {/* Ambient neon glow blobs */}
      <div
        style={{
          position: "absolute",
          top: "-10%",
          right: "-10%",
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: brief.brandColor + "20",
          filter: "blur(80px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "-5%",
          left: "-5%",
          width: 300,
          height: 300,
          borderRadius: "50%",
          background: brief.accentColor + "15",
          filter: "blur(60px)",
        }}
      />

      {/* Header section */}
      <div
        style={{
          position: "absolute",
          top: isPortrait ? 70 : 50,
          left: px,
          right: px,
        }}
      >
        {/* Brand */}
        {brief.brandName && (
          <FadeSlideIn delay={Math.round(5 * speed)} direction="down">
            <div
              style={{
                fontFamily: fonts.body,
                fontWeight: 600,
                fontSize: 22,
                color: brief.brandColor,
                textShadow: neonGlow(brief.brandColor, 0.5),
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                marginBottom: 16,
              }}
            >
              {brief.brandName}
            </div>
          </FadeSlideIn>
        )}

        {/* Title */}
        <FadeSlideIn delay={Math.round(10 * speed)} direction="up">
          <h1
            style={{
              fontFamily: fonts.heading,
              fontWeight: 800,
              fontSize: titleSize,
              color: brief.textColor,
              margin: 0,
              lineHeight: 1.1,
              letterSpacing: "-0.02em",
            }}
          >
            {brief.title}
          </h1>
        </FadeSlideIn>

        {brief.subtitle && (
          <FadeSlideIn delay={Math.round(18 * speed)} direction="up">
            <p
              style={{
                fontFamily: fonts.body,
                fontWeight: 300,
                fontSize: isPortrait ? 28 : 30,
                color: brief.accentColor,
                margin: "12px 0 0",
                textShadow: neonGlow(brief.accentColor, 0.4),
              }}
            >
              {brief.subtitle}
            </p>
          </FadeSlideIn>
        )}

        {/* Neon rule */}
        <div style={{ marginTop: 24 }}>
          <NeonDivider
            color={brief.brandColor}
            delay={Math.round(22 * speed)}
          />
        </div>
      </div>

      {/* List items */}
      <div
        style={{
          position: "absolute",
          left: px,
          right: px,
          top: isPortrait ? "32%" : "38%",
          display: twoColumn ? "grid" : "flex",
          ...(twoColumn
            ? { gridTemplateColumns: "1fr 1fr", gap: "24px 48px" }
            : { flexDirection: "column", gap: isPortrait ? 28 : 24 }),
        }}
      >
        {items.map((item, i) => (
          <ListItem
            key={i}
            index={item.index}
            headline={item.headline}
            body={item.body}
            emoji={item.emoji}
            brandColor={brief.brandColor}
            accentColor={brief.accentColor}
            textColor={brief.textColor}
            fonts={fonts}
            delay={Math.round((28 + i * 14) * speed)}
            isPortrait={isPortrait}
          />
        ))}

        {/* Fallback body text if no list items */}
        {items.length === 0 && brief.bodyText && (
          <FadeSlideIn delay={Math.round(28 * speed)}>
            <p
              style={{
                fontFamily: fonts.body,
                fontWeight: 300,
                fontSize: isPortrait ? 34 : 36,
                color: brief.textColor + "CC",
                lineHeight: 1.6,
                margin: 0,
              }}
            >
              {brief.bodyText}
            </p>
          </FadeSlideIn>
        )}
      </div>

      {/* CTA */}
      {brief.cta && (
        <FadeSlideIn
          delay={Math.round((28 + items.length * 14 + 10) * speed)}
          direction="up"
          style={{
            position: "absolute",
            bottom: isPortrait ? 70 : 48,
            left: px,
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 12,
              border: `1px solid ${brief.brandColor}`,
              boxShadow: neonGlow(brief.brandColor, 0.6),
              borderRadius: 8,
              padding: "14px 32px",
            }}
          >
            <span
              style={{
                fontFamily: fonts.heading,
                fontWeight: 700,
                fontSize: 26,
                color: brief.brandColor,
                textShadow: neonGlow(brief.brandColor, 0.5),
                letterSpacing: "0.05em",
              }}
            >
              {brief.cta}
            </span>
          </div>
        </FadeSlideIn>
      )}
    </AbsoluteFill>
  );
};
