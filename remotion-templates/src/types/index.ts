// src/types/index.ts
// ─────────────────────────────────────────────────────────────────────────────
// DesignBrief — the structured JSON that Gemini generates and Python passes
// to Remotion via --props. Every template reads from this shape.
// ─────────────────────────────────────────────────────────────────────────────

export type AspectRatio = "9:16" | "16:9" | "1:1";
export type TemplateStyle = "minimal" | "bold" | "glassmorphism" | "neon";
export type AnimationSpeed = "slow" | "normal" | "fast";

export interface StatItem {
  label: string; // e.g. "Revenue"
  value: string; // e.g. "₦2.4M"
  suffix?: string; // e.g. "%", "x"
  prefix?: string; // e.g. "₦", "$"
  numericValue: number; // raw number for count-up animation
}

export interface ListItem {
  index: number; // 1-based
  headline: string; // "Use a strong hook"
  body?: string; // optional supporting sentence
  emoji?: string; // optional accent emoji
}

export interface DesignBrief {
  // ── Identity ──────────────────────────────────────────────────────────────
  style: TemplateStyle;
  aspectRatio: AspectRatio;
  durationSeconds: number; // 5–60

  // ── Brand ─────────────────────────────────────────────────────────────────
  brandName?: string;
  brandColor: string; // primary hex e.g. "#FF6B35"
  accentColor: string; // secondary hex
  bgColor: string; // background hex
  textColor: string; // primary text hex

  // ── Core content ──────────────────────────────────────────────────────────
  title: string; // main headline
  subtitle?: string; // supporting line
  bodyText?: string; // longer body (quote cards, flyers)
  tagline?: string; // brand intro tagline
  cta?: string; // call-to-action text

  // ── Structured data (template-specific) ───────────────────────────────────
  stats?: StatItem[]; // glassmorphism template
  listItems?: ListItem[]; // neon listicle template

  // ── Style hints ───────────────────────────────────────────────────────────
  animationSpeed: AnimationSpeed;
  fontPairing: "syne_dmsans" | "inter" | "playfair_inter";

  // ── Source flyer metadata (set if input was a flyer image) ────────────────
  sourceType: "prompt" | "flyer";
  flyerDescription?: string; // Gemini's plain-text read of the flyer
}

// Dimensions helper — used by all templates
export const DIMENSIONS: Record<
  AspectRatio,
  { width: number; height: number }
> = {
  "9:16": { width: 1080, height: 1920 },
  "16:9": { width: 1920, height: 1080 },
  "1:1": { width: 1080, height: 1080 },
};

// FPS — fixed across all templates
export const FPS = 30;
