from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CreativePlan:
    # Текстовые блоки
    headline: str = ""
    subheadline: str = ""
    bullets: list[str] = field(default_factory=list)
    price: str = ""
    badge: str = ""
    cta: str = ""

    # Визуальные решения
    style: str = "conversion"          # premium | conversion | minimal
    bg_color: str = "#1a1a2e"
    accent_color: str = "#e94560"
    text_color: str = "#ffffff"

    # Что добавить к картинке (для image_transformer в спринте 3)
    visual_additions: list[str] = field(default_factory=list)

    # Источник
    source_image_path: Optional[str] = None
    generated_image_url: Optional[str] = None
