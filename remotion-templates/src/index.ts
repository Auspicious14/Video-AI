// src/index.ts
// ─────────────────────────────────────────────────────────────────────────────
// Remotion entry point — registers all compositions.
// Python calls: remotion render <CompositionId> --props='...' --output=out.mp4
//
// Composition IDs (passed via CLI):
//   MinimalVideo
//   BoldVideo
//   GlassmorphismVideo
//   NeonVideo
// ─────────────────────────────────────────────────────────────────────────────

import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
