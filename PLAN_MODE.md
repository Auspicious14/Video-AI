# Plan-file mode

Render a complete documentary from a hand-written (or chat-written) `production.json`
with **no LLM calls and no LLM API keys**. The studio pipeline's agent stages
(topic, research, story, script, QA, visual planning) are skipped; the plan file
replaces their output and the existing stages take over:

```
production.json -> asset retrieval per scene -> TTS per section -> render_video -> MP4
```

It reuses `services/ai/media/providers/*` (+ `MediaDownloader`), `services/audio.py`
(Kokoro, gTTS fallback) and `services/renderer.py` unchanged.

## Run

```bash
# validate + summary (no network, no ffmpeg, no keys)
python generate_from_plan.py examples/production.example.json --dry-run

# real run
python generate_from_plan.py path/to/production.json --out outputs/my_video.mp4
```

`--out` defaults to `outputs/<plan file name>.mp4`. Next to the video a
`<out>.credits.json` is written with the title/description/tags and, per scene,
the source provider, URL, author and licence (use it for YouTube attribution).

Exit codes: `0` ok, `1` ffmpeg missing, `2` invalid plan.

## Environment

| Variable | Needed for |
|---|---|
| `PEXELS_API_KEY` | `pexels_image` / `pexels_video` scenes (free key at pexels.com/api) |
| none | `wikimedia`, `url`, `text_card`, TTS (Kokoro offline, gTTS needs internet) |

Also required on the machine: `ffmpeg` and `ffprobe` on PATH. No `GEMINI_*`, `GROQ_*`,
`DEEPSEEK_*` etc. are read on this path. (Some shared modules import the LLM client
module at import time; that import needs no key, and tests assert no LLM call is made.)

If a scene's asset cannot be fetched (no key, no results, download error, bad image)
it becomes a **text card** with the scene's `text`, else `caption`, else `query`, and a
warning is printed. The render never aborts because of one bad asset.

## Schema

Unknown keys are rejected (typos fail validation).

`ProductionPlan`

| Field | Type | Default | Notes |
|---|---|---|---|
| `title` | string | required | |
| `description` | string | `""` | goes to the credits sidecar |
| `tags` | string[] | `[]` | goes to the credits sidecar |
| `aspect_ratio` | `"16:9"` \| `"9:16"` \| `"1:1"` | `"16:9"` | what `renderer.dimensions_for_aspect_ratio` supports (1920x1080 / 1080x1920 / 1080x1080) |
| `voice` | string \| null | engine default (`am_adam`) | Kokoro voice id (`am_adam`, `bf_emma`, ...) or a `VOICE_REGISTRY` key (`male_deep`). Ignored by gTTS |
| `music` | string \| null | none | local path (relative to the plan file) or http(s) URL; mixed at -18 dB under the narration |
| `hook` | string | `""` | text overlaid for the first 3 s |
| `cta` | string | `""` | text overlaid for the last 5 s |
| `subtitles` | bool | `true` | burned-in captions timed from the narration |
| `sections` | Section[] (>=1) | required | |

`Section`: `title` (string), `narration` (spoken text, non-blank), `scenes` (Scene[], >=1).

`Scene`

| Field | Type | Notes |
|---|---|---|
| `kind` | see below | required |
| `query` | string | required for `wikimedia`, `pexels_image`, `pexels_video` |
| `url` | string | required for `url` (http(s) URL, `file://`, absolute path, or path relative to the plan file) |
| `text` | string | required for `text_card`; fallback card text for other kinds |
| `caption` | string | free-form note, **not rendered**; stored in the credits sidecar |
| `duration_weight` | number > 0 | default `1`; relative share of the section's narration time |

### Visual kinds

| Kind | Source | Notes |
|---|---|---|
| `wikimedia` | Wikimedia Commons image search | no key; JPEG/PNG/GIF/WebP only; prefers results >= 1280 px wide; keep queries short (2-6 keywords) |
| `pexels_image` | Pexels photo search | needs `PEXELS_API_KEY` |
| `pexels_video` | Pexels video search | needs `PEXELS_API_KEY`; first MP4 file Pexels lists is used, looped/trimmed to the scene length |
| `url` | direct URL or local file | treated as video if the extension is `.mp4 .mov .webm .mkv .m4v`, otherwise as an image |
| `text_card` | generated offline | `text` on a dark background (renderer's fallback frame) |

Stills get the renderer's Ken Burns motion; videos are scaled onto a blurred
background (letterbox-safe) and looped if shorter than the scene. The same asset is
never reused for two search scenes in one run.

## Timing

Each section is voiced separately, so its real audio length is known. A section's
duration is divided among its scenes by `duration_weight`. Scene clips are padded by
the renderer's 0.4 s crossfade so every scene starts where its narration share starts
and the video ends with the audio. Aim for scenes of at least ~2 s (dry-run flags
shorter ones). Estimated length in `--dry-run` assumes 150 words per minute.

## Not supported / limitations

- `caption` is not drawn on screen (the renderer has no per-scene caption overlay).
- No AI image generation, no Google/Unsplash/Pixabay kinds (providers exist in the repo
  but are not exposed here); use `url` for anything else.
- Transitions (always 0.4 s fade) and motion effects are chosen by the renderer.
- Thumbnail is not rendered; write it separately.
- Narration is not checked against the visuals; the plan is trusted as written.

## Minimal example

```json
{
  "title": "Demo",
  "sections": [
    {
      "title": "Intro",
      "narration": "This is a short test of plan mode.",
      "scenes": [
        {"kind": "text_card", "text": "Plan mode"},
        {"kind": "wikimedia", "query": "mountain lake", "duration_weight": 2}
      ]
    }
  ]
}
```

See `examples/production.example.json` for a full ~85 s sample. Tests:
`python3 -m pytest -q tests/test_plan_mode.py`.
