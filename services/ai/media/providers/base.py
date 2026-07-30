from abc import ABC, abstractmethod

from services.ai.media.asset import MediaAsset
from services.ai.media.asset_types import AssetKind
from services.ai.media.visual_intent import VisualIntent


class MediaProvider(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def supported_kinds(self) -> set[AssetKind]:
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    async def search(
        self,
        intent: VisualIntent,
        limit: int = 5,
    ) -> list[MediaAsset]:
        ...

    @property
    def priority(self):
        return 90
