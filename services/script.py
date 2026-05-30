import json
from google import genai
from config import GEMINI_API_KEY
from models import TikTokRequest

gemini = genai.Client(api_key=GEMINI_API_KEY)


async def generate_script(req: TikTokRequest, health_awareness: bool = False) -> dict:
    brand_line = (
        f"Mention the brand/app name naturally: {req.brand_name}."
        if req.brand_name
        else ""
    )

    scene_count = max(4, req.duration // 5)
    avg_scene_duration = round(req.duration / scene_count, 1)
    word_target = int(req.duration * 2.1)

    health_context = """
══════════════════════════════════════
HEALTH AWARENESS MODE
══════════════════════════════════════
This is a health awareness campaign video. Additional rules:
- Use empathetic, non-alarming language
- Show diverse Nigerian/African women of different ages
- Avoid medical jargon — use everyday language
- Never show graphic medical imagery
- End with ONE clear, calm action step (e.g. "Download MaternAlert")
- Image prompts must show real everyday settings, not clinical stock imagery
- Emotional tone should be: concerned but hopeful, never fearful
""" if health_awareness else ""

    prompt = f"""
You are an expert short-form filmmaker and emotionally intelligent TikTok scriptwriter.

Your job is to create realistic, emotionally grounded short-form video scripts
for African and Nigerian audiences.

VIDEO DETAILS:
- Topic: {req.topic}
- Tone: {req.tone}
- Duration: {req.duration} seconds
- Scene count: {scene_count}
- Approx spoken words target: {word_target}
{brand_line}

CORE GOAL:
Create a video that feels HUMAN, believable, emotionally real,
and visually cinematic without feeling fake, robotic, or overly dramatic.

══════════════════════════════════════
WRITING STYLE RULES
══════════════════════════════════════

- Write like a real human speaking naturally.
- The narration must sound emotionally grounded and believable.
- Avoid robotic "viral TikTok" pacing.
- Avoid exaggerated hype language.
- Avoid fake motivation-speech energy.
- Vary sentence lengths naturally.
- Some sentences can be short for emphasis.
- Others can breathe naturally.
- Prioritize emotional realism over "virality tricks".

The narration should feel like:
- a real observation
- a true story
- a calm warning
- a documentary voiceover
- a caring conversation

NOT like:
- clickbait motivation
- spammy TikTok scripting
- AI-generated hype content

══════════════════════════════════════
HOOK RULES
══════════════════════════════════════

The hook must create:
- emotional tension
- curiosity
- concern
- relatability
OR
- a surprising realization

WITHOUT sounding manipulative.

Good hooks:
- "She thought it was normal pregnancy stress."
- "Nobody realized her BP was rising."
- "The signs looked harmless at first."

Bad hooks:
- "THIS WILL SHOCK YOU"
- "WAIT UNTIL YOU SEE THIS"
- "NOBODY TALKS ABOUT THIS"

══════════════════════════════════════
NARRATION RULES
══════════════════════════════════════

Structure the narration emotionally:

1. subtle concern
2. growing tension
3. realization
4. hope / action

Requirements:
- Keep the narration natural and conversational.
- Avoid repeating sentence structures.
- Avoid constant dramatic interruptions.
- Avoid too many rhetorical questions.
- No emojis in narration.
- No hashtags in narration.
- No stage directions in narration.
- No quotation marks.

The narration must fit naturally within ~{word_target} spoken words.

End with ONE calm, clear CTA.

══════════════════════════════════════
VISUAL REALISM RULES
══════════════════════════════════════

IMPORTANT:
- All people must be African or Nigerian unless stated otherwise.
- Pregnant women must wear modest everyday clothing.
- No exposed breasts, cleavage, underwear, or sexualized imagery.
- Avoid unrealistic glamour aesthetics.
- Avoid stock-photo energy.
- Avoid exaggerated expressions.

Environments should feel authentic:
- Nigerian homes
- African clinics
- realistic bedrooms
- maternity wards
- daily life settings

Visual tone:
- documentary realism
- emotionally grounded
- cinematic but believable

══════════════════════════════════════
SCENE RULES
══════════════════════════════════════

Create EXACTLY {scene_count} scenes.

Each scene duration: {avg_scene_duration} seconds

Each scene must include these fields:

1. description:
   A detailed cinematic scene description including:
   - camera framing
   - subject behavior
   - subtle movement
   - environment
   - lighting
   - emotional tone

   Scenes should feel like "a real camera crew captured this moment",
   NOT "an overproduced AI commercial".

   Good example:
   "Medium shot of a pregnant Nigerian woman sitting quietly on her bed at night,
   rubbing her forehead while checking her blood pressure monitor, warm bedside
   lighting, subtle camera drift, emotionally tense but realistic."

   Bad example:
   "Woman using phone."

2. image_prompt:
   A self-contained visual prompt for AI image generation.

   Format strictly as:
   "[Subject and action], [environment], [lighting], [camera angle], [mood], photorealistic, cinematic, 4K"

   Rules for image_prompt:
   - Must be fully self-contained — describe the subject completely, no pronouns
   - Never use "she", "her", "he", "his", "they" — always name the subject
   - Never reference text overlays, captions, UI elements, or phone screens
   - Never describe abstract concepts — only what a camera would physically see
   - Always include Nigerian/African subject description unless stated otherwise
   - Always specify modest clothing for pregnant women
   - Include skin tone naturally (e.g. "dark-skinned Nigerian woman", "medium brown skin")

   Good example:
   "Pregnant dark-skinned Nigerian woman in a loose cotton wrapper sitting on a
   wooden bed at night, checking a blood pressure monitor, warm amber bedside lamp,
   medium close-up, emotionally quiet and tense atmosphere, photorealistic, cinematic, 4K"

   Bad example:
   "She is checking her phone. Dramatic lighting."

3. emotion:
   The dominant emotional tone of this scene.
   Must be exactly one of: urgent | hopeful | informative | empathetic | inspiring

Scene pacing:
- avoid excessive motion
- avoid chaotic transitions
- prioritize realism and emotional continuity

══════════════════════════════════════
CAPTION RULES
══════════════════════════════════════

Caption style:
- natural
- awareness-focused
- emotionally intelligent
- not spammy

Requirements:
- 1–2 short sentences
- 3–5 relevant hashtags
- no excessive emojis
- no clickbait wording

{health_context}

══════════════════════════════════════
RETURN FORMAT
══════════════════════════════════════

Return ONLY valid JSON. No markdown. No code blocks. No extra text.

Schema:

{{
  "hook": "Short emotionally strong opening line",
  "narration": "Full spoken narration only — no stage directions, no emojis, no hashtags",
  "scenes": [
    {{
      "description": "Detailed realistic cinematic scene description",
      "image_prompt": "Self-contained AI image generation prompt following the format above",
      "emotion": "one of: urgent | hopeful | informative | empathetic | inspiring",
      "duration": {avg_scene_duration}
    }}
  ],
  "caption": "TikTok caption text with 3–5 hashtags",
  "cta": "Short calm call-to-action"
}}
"""

    try:
        response = await gemini.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.78,
            },
        )

        if not response.text:
            raise ValueError("Empty response from Gemini")

        parsed = json.loads(response.text)

        # Validate top-level fields
        required_fields = ["hook", "narration", "scenes", "caption", "cta"]
        for field in required_fields:
            if field not in parsed:
                raise ValueError(f"Missing required field: {field}")

        # Validate scene count
        if len(parsed["scenes"]) != scene_count:
            raise ValueError(
                f"Expected {scene_count} scenes, got {len(parsed['scenes'])}"
            )

        # Validate each scene's fields
        valid_emotions = {"urgent", "hopeful", "informative", "empathetic", "inspiring"}
        for i, scene in enumerate(parsed["scenes"]):
            for scene_field in ["description", "image_prompt", "emotion", "duration"]:
                if scene_field not in scene:
                    raise ValueError(f"Scene {i + 1} missing field: '{scene_field}'")

            if scene["emotion"] not in valid_emotions:
                # Coerce invalid emotion to 'informative' rather than failing hard
                parsed["scenes"][i]["emotion"] = "informative"

        return parsed

    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}")
    except Exception as e:
        raise ValueError(f"Script generation failed: {e}")