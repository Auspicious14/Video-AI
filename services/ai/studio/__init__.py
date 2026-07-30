"""AI-first YouTube production studio services."""


async def run_youtube_studio_production(*args, **kwargs):
    """Lazy wrapper so specialist imports do not load runtime app config."""
    from services.ai.studio.pipeline import run_youtube_studio_production as _run

    return await _run(*args, **kwargs)

__all__ = ["run_youtube_studio_production"]
