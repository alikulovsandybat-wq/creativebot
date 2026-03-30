from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CreativePlan:
    headline: str = ""
    subheadline: str = ""
    bullets: list[str] = field(default_factory=list)
    price: str = ""
    badge: str = ""
    cta: str = ""
    style: str = "minimal"
    brand_style: str = "universal"
    visual_additions: list[str] = field(default_factory=list)

    # Три разных фона под три стиля
    bg_minimal: str = ""
    bg_conversion: str = ""
    bg_premium: str = ""

    # Устаревшее поле — оставляем для совместимости
    dalle_bg_prompt: str = ""

    source_image_path: Optional[str] = None
