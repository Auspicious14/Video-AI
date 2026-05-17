#!/usr/bin/env bash
# setup_remotion.sh
# ─────────────────────────────────────────────────────────────────────────────
# Run this once on your server to set up the Remotion motion design pipeline.
# Usage: bash setup_remotion.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  VideoAI.ng — Remotion Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Check Node.js ──────────────────────────────────────────────────────────
echo "→ Checking Node.js..."
node_version=$(node --version 2>/dev/null || echo "not found")

if [[ "$node_version" == "not found" ]]; then
  echo "  ✗ Node.js not found. Install Node.js 18+ first."
  echo "    Ubuntu: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs"
  exit 1
fi

echo "  ✓ Node.js $node_version"

# ── 2. Install Remotion CLI globally ─────────────────────────────────────────
echo ""
echo "→ Installing Remotion CLI globally..."
npm install -g remotion @remotion/cli

echo "  ✓ Remotion CLI installed: $(remotion --version 2>/dev/null || echo 'check manually')"

# ── 3. Install remotion-templates dependencies ───────────────────────────────
echo ""
echo "→ Installing remotion-templates npm dependencies..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/remotion-templates"

if [[ ! -d "$TEMPLATES_DIR" ]]; then
  echo "  ✗ remotion-templates/ not found at $TEMPLATES_DIR"
  echo "    Make sure you cloned the full VideoAI.ng repo."
  exit 1
fi

cd "$TEMPLATES_DIR"
npm install

echo "  ✓ Templates dependencies installed"

# ── 4. Test render (optional sanity check) ───────────────────────────────────
echo ""
echo "→ Running a quick test render (MinimalVideo, 5 frames)..."

TEST_PROPS=$(cat <<'EOF'
{
  "brief": {
    "style": "minimal",
    "aspectRatio": "9:16",
    "durationSeconds": 5,
    "brandName": "VideoAI",
    "brandColor": "#F4A931",
    "accentColor": "#FF6B35",
    "bgColor": "#0A0A0A",
    "textColor": "#FFFFFF",
    "title": "Setup Test",
    "subtitle": "Remotion is working",
    "bodyText": "If you can read this, motion design is ready.",
    "cta": "Let's Go",
    "animationSpeed": "fast",
    "fontPairing": "syne_dmsans",
    "sourceType": "prompt"
  }
}
EOF
)

TEST_PROPS_FILE=$(mktemp /tmp/remotion_test_props_XXXX.json)
echo "$TEST_PROPS" > "$TEST_PROPS_FILE"

TEST_OUTPUT="/tmp/videoai_remotion_test.mp4"

remotion render src/index.ts MinimalVideo \
  --props="$TEST_PROPS_FILE" \
  --output="$TEST_OUTPUT" \
  --concurrency=1 \
  --frames=0-4 \
  --log=error 2>&1

rm -f "$TEST_PROPS_FILE"

if [[ -f "$TEST_OUTPUT" && $(stat -c%s "$TEST_OUTPUT" 2>/dev/null || stat -f%z "$TEST_OUTPUT") -gt 5000 ]]; then
  echo "  ✓ Test render succeeded: $TEST_OUTPUT"
  rm -f "$TEST_OUTPUT"
else
  echo "  ⚠ Test render may have failed — check output above."
  echo "    If Chrome/Chromium is missing, install it:"
  echo "    Ubuntu: sudo apt install -y chromium-browser"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  Remotion setup complete!"
echo ""
echo "  Motion Design pipeline is ready."
echo "  POST /generate/motion-design       — topic → video"
echo "  POST /generate/motion-design/flyer — flyer image → video"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""