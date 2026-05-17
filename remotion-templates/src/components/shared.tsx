// src/components/shared.tsx
// ─────────────────────────────────────────────────────────────────────────────
// Reusable animation primitives used across all four templates.
// ─────────────────────────────────────────────────────────────────────────────

import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";

// ── Hook: spring-based entrance value ─────────────────────────────────────────
export function useEntrance(delayFrames = 0, stiffness = 80) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({
    frame: frame - delayFrames,
    fps,
    config: { stiffness, damping: 18, mass: 0.8 },
    clamp: true,
  });
}

// ── Hook: count-up animation (returns current display number) ──────────────────
export function useCountUp(
  targetValue: number,
  startFrame: number,
  durationFrames: number,
): number {
  const frame = useCurrentFrame();
  const progress = interpolate(
    frame,
    [startFrame, startFrame + durationFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    },
  );
  return Math.round(targetValue * progress);
}

// ── Hook: fade value ───────────────────────────────────────────────────────────
export function useFade(
  inStart: number,
  inEnd: number,
  outStart?: number,
  outEnd?: number,
) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const _outStart = outStart ?? durationInFrames - 15;
  const _outEnd = outEnd ?? durationInFrames;

  return interpolate(
    frame,
    [inStart, inEnd, _outStart, _outEnd],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
}

// ── Component: FadeSlideIn ─────────────────────────────────────────────────────
interface FadeSlideInProps {
  children: React.ReactNode;
  delay?: number; // frames
  direction?: "up" | "down" | "left" | "right";
  distance?: number; // px
  style?: React.CSSProperties;
}

export const FadeSlideIn: React.FC<FadeSlideInProps> = ({
  children,
  delay = 0,
  direction = "up",
  distance = 40,
  style,
}) => {
  const entrance = useEntrance(delay);
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const fadeOut = interpolate(
    frame,
    [durationInFrames - 15, durationInFrames],
    [1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );

  const offset = (1 - entrance) * distance;
  const tx =
    direction === "left" ? offset : direction === "right" ? -offset : 0;
  const ty = direction === "up" ? offset : direction === "down" ? -offset : 0;

  return (
    <div
      style={{
        opacity: entrance * fadeOut,
        transform: `translate(${tx}px, ${ty}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

// ── Component: ScaleIn ────────────────────────────────────────────────────────
export const ScaleIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
  fromScale?: number;
  style?: React.CSSProperties;
}> = ({ children, delay = 0, fromScale = 0.6, style }) => {
  const entrance = useEntrance(delay, 100);
  const scale = fromScale + (1 - fromScale) * entrance;
  return (
    <div style={{ transform: `scale(${scale})`, opacity: entrance, ...style }}>
      {children}
    </div>
  );
};

// ── Component: GradientBg ─────────────────────────────────────────────────────
export const GradientBg: React.FC<{
  color1: string;
  color2: string;
  angle?: number;
  style?: React.CSSProperties;
}> = ({ color1, color2, angle = 135, style }) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      background: `linear-gradient(${angle}deg, ${color1}, ${color2})`,
      ...style,
    }}
  />
);

// ── Component: BrandDot ───────────────────────────────────────────────────────
export const BrandDot: React.FC<{ color: string; size?: number }> = ({
  color,
  size = 12,
}) => (
  <span
    style={{
      display: "inline-block",
      width: size,
      height: size,
      borderRadius: "50%",
      background: color,
      marginRight: 8,
      verticalAlign: "middle",
    }}
  />
);

// ── Component: AnimatedLine ───────────────────────────────────────────────────
export const AnimatedLine: React.FC<{
  color: string;
  delay?: number;
  thickness?: number;
  style?: React.CSSProperties;
}> = ({ color, delay = 0, thickness = 3, style }) => {
  const frame = useCurrentFrame();
  const width = interpolate(frame, [delay, delay + 20], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        height: thickness,
        width: `${width}%`,
        background: color,
        borderRadius: thickness,
        ...style,
      }}
    />
  );
};
