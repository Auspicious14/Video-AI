from enum import Enum


class AssetKind(str, Enum):
    STOCK_VIDEO = "stock_video"

    STOCK_IMAGE = "stock_image"

    SCREENSHOT = "screenshot"

    WEBSITE = "website"

    LOGO = "logo"

    MAP = "map"

    CHART = "chart"

    INFOGRAPHIC = "infographic"

    HISTORICAL_PHOTO = "historical_photo"

    PRODUCT = "product"

    AI_IMAGE = "ai_image"

    AI_VIDEO = "ai_video"

    LOCAL = "local"