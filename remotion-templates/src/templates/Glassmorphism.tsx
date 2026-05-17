// src/templates/Glassmorphism.tsx
// ─────────────────────────────────────────────────────────────────────────────
// GLASSMORPHISM — Stats & data reveals
// Aesthetic: frosted glass cards, counting numbers, aurora background
// Content types: business metrics, social stats, financial highlights
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
  useCountUp,
  GradientBg,
} from "../components/shared";

const FONT_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');
`;

function getFont(pairing: DesignBrief["fontPairing"]) {
  if (pairing === "syne_dmsans") return { heading: "Syne", body: "DM Sans" };
  return { heading: "Inter", body: "Inter" };
}

// Aurora orb — the glowing background blobs
const AuroraOrb: React.FC<{
  color: string;
  size: number;
  x: string;
  y: string;
  pulseDelay?: number;
}> = ({ color, size, x, y, pulseDelay = 0 }) => {
  const frame = useCurrentFrame();
  const pulse = Math.sin((frame + pulseDelay) * 0.02) * 0.08 + 1;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: size * pulse,
        height: size * pulse,
        borderRadius: "50%",
        background: color,
        filter: `blur(${size * 0.35}px)`,
        opacity: 0.55,
        transform: "translate(-50%, -50%)",
      }}
    />
  );
};

// Glass card wrapper
const GlassCard: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  tint?: string;
}> = ({ children, style, tint = "255,255,255" }) => (
  <div
    style={{
      background: `rgba(${tint}, 0.1)`,
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
      border: `1px solid rgba(${tint}, 0.2)`,
      borderRadius: 24,
      padding: "32px 40px",
      ...style,
    }}
  >
    {children}
  </div>
);

// Individual stat card with count-up
const StatCard: React.FC<{
  label: string;
  value: string;
  prefix?: string;
  suffix?: string;
  numericValue: number;
  brandColor: string;
  accentColor: string;
  textColor: string;
  fonts: { heading: string; body: string };
  delay: number;
  cardWidth: number;
}> = ({
  label,
  value,
  prefix,
  suffix,
  numericValue,
  brandColor,
  accentColor,
  textColor,
  fonts,
  delay,
  cardWidth,
}) => {
  const counted = useCountUp(numericValue, delay + 15, 45);

  // Format: if the value has decimals or letters (e.g. "2.4M"), show raw value after count
  const isSimpleNumber =
    /^\d+$/.test(String(numericValue)) && numericValue < 10000;
  const displayValue = isSimpleNumber ? counted : value;

  return (
    <ScaleIn delay={delay} style={{ width: cardWidth }}>
      <GlassCard>
        {/* Accent top line */}
        <div
          style={{
            height: 3,
            background: brandColor,
            borderRadius: 2,
            marginBottom: 20,
            width: "40%",
          }}
        />

        {/* Value */}
        <div
          style={{
            fontFamily: fonts.heading,
            fontWeight: 800,
            fontSize: cardWidth > 300 ? 72 : 56,
            lineHeight: 1,
            color: textColor,
            letterSpacing: "-0.02em",
            marginBottom: 8,
          }}
        >
          {prefix && (
            <span style={{ fontSize: "0.5em", color: accentColor }}>
              {prefix}
            </span>
          )}
          {displayValue}
          {suffix && (
            <span
              style={{ fontSize: "0.45em", color: accentColor, marginLeft: 2 }}
            >
              {suffix}
            </span>
          )}
        </div>

        {/* Label */}
        <div
          style={{
            fontFamily: fonts.body,
            fontWeight: 400,
            fontSize: 22,
            color: textColor + "99",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
          }}
        >
          {label}
        </div>
      </GlassCard>
    </ScaleIn>
  );
};

export const GlassmorphismTemplate: React.FC<{ brief: DesignBrief }> = ({
  brief,
}) => {
  const { width, height } = DIMENSIONS[brief.aspectRatio];
  const fonts = getFont(brief.fontPairing);
  const totalFrames = brief.durationSeconds * FPS;

  const isPortrait = brief.aspectRatio === "9:16";
  const isLandscape = brief.aspectRatio === "16:9";
  const isSquare = brief.aspectRatio === "1:1";

  const px = isPortrait ? 60 : isLandscape ? 100 : 70;
  const titleSize = isPortrait ? 58 : isLandscape ? 64 : 52;
  const speed =
    brief.animationSpeed === "fast"
      ? 0.6
      : brief.animationSpeed === "slow"
        ? 1.6
        : 1;

  const stats = brief.stats ?? [];

  // Layout: portrait → vertical stack; landscape → 2-column grid; square → 2x2 grid
  const cardWidth = isPortrait
    ? width - px * 2
    : isLandscape
      ? (width - px * 2 - 32) / 2
      : (width - px * 2 - 24) / 2;

  const statsGrid: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: isPortrait ? "1fr" : "1fr 1fr",
    gap: isPortrait ? 20 : 24,
    width: "100%",
  };

  return (
    <AbsoluteFill style={{ background: brief.bgColor, overflow: "hidden" }}>
      <style dangerouslySetInnerHTML={{ __html: FONT_STYLE }} />

      {/* Aurora background */}
      <AuroraOrb
        color={brief.brandColor}
        size={500}
        x="80%"
        y="20%"
        pulseDelay={0}
      />
      <AuroraOrb
        color={brief.accentColor}
        size={400}
        x="15%"
        y="75%"
        pulseDelay={60}
      />
      <AuroraOrb
        color={brief.brandColor + "80"}
        size={300}
        x="50%"
        y="50%"
        pulseDelay={120}
      />

      {/* Top: Brand + Title */}
      <div
        style={{
          position: "absolute",
          top: isPortrait ? 80 : 60,
          left: px,
          right: px,
        }}
      >
        {/* Brand pill */}
        {brief.brandName && (
          <FadeSlideIn delay={Math.round(5 * speed)} direction="down">
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                background: brief.brandColor + "30",
                border: `1px solid ${brief.brandColor}60`,
                borderRadius: 100,
                padding: "8px 20px",
                marginBottom: 20,
              }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: brief.brandColor,
                }}
              />
              <span
                style={{
                  fontFamily: fonts.body,
                  fontWeight: 600,
                  fontSize: 20,
                  color: brief.brandColor,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                {brief.brandName}
              </span>
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
              lineHeight: 1.1,
              color: brief.textColor,
              margin: 0,
              marginBottom: 8,
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
                fontSize: isPortrait ? 28 : 32,
                color: brief.textColor + "AA",
                margin: 0,
              }}
            >
              {brief.subtitle}
            </p>
          </FadeSlideIn>
        )}
      </div>

      {/* Stats grid */}
      {stats.length > 0 && (
        <div
          style={{
            position: "absolute",
            left: px,
            right: px,
            top: isPortrait ? "35%" : "40%",
            ...statsGrid,
          }}
        >
          {stats.map((stat, i) => (
            <StatCard
              key={i}
              label={stat.label}
              value={stat.value}
              prefix={stat.prefix}
              suffix={stat.suffix}
              numericValue={stat.numericValue}
              brandColor={brief.brandColor}
              accentColor={brief.accentColor}
              textColor={brief.textColor}
              fonts={fonts}
              delay={Math.round((25 + i * 10) * speed)}
              cardWidth={cardWidth}
            />
          ))}
        </div>
      )}

      {/* Fallback if no stats: show body text in glass card */}
      {stats.length === 0 && brief.bodyText && (
        <ScaleIn
          delay={Math.round(25 * speed)}
          style={{
            position: "absolute",
            left: px,
            right: px,
            top: isPortrait ? "40%" : "45%",
          }}
        >
          <GlassCard>
            <p
              style={{
                fontFamily: fonts.body,
                fontWeight: 300,
                fontSize: isPortrait ? 36 : 40,
                color: brief.textColor,
                lineHeight: 1.6,
                margin: 0,
              }}
            >
              {brief.bodyText}
            </p>
          </GlassCard>
        </ScaleIn>
      )}

      {/* CTA */}
      {brief.cta && (
        <FadeSlideIn
          delay={Math.round(55 * speed)}
          direction="up"
          style={{
            position: "absolute",
            bottom: isPortrait ? 80 : 50,
            left: px,
            right: px,
            textAlign: "center",
          }}
        >
          <span
            style={{
              fontFamily: fonts.heading,
              fontWeight: 700,
              fontSize: 26,
              color: brief.brandColor,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              borderBottom: `2px solid ${brief.brandColor}`,
              paddingBottom: 6,
            }}
          >
            {brief.cta}
          </span>
        </FadeSlideIn>
      )}
    </AbsoluteFill>
  );
};
