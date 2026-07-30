from services.ai.media.provider_registry import ProviderRegistry

from services.ai.media.providers.google_images import GoogleImagesProvider
from services.ai.media.providers.logos_dev import LogosDevProvider
from services.ai.media.providers.pexels import PexelsProvider
from services.ai.media.providers.pixabay import PixabayProvider
from services.ai.media.providers.unsplash import UnsplashProvider
from services.ai.media.providers.website import WebsiteProvider
from services.ai.media.providers.wikimedia import WikimediaProvider


def build_registry():

    registry = ProviderRegistry()

    registry.register(PexelsProvider())

    registry.register(PixabayProvider())

    registry.register(UnsplashProvider())

    registry.register(GoogleImagesProvider())

    registry.register(WikimediaProvider())

    registry.register(WebsiteProvider())

    registry.register(LogosDevProvider())

    return registry