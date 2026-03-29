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
    source_image_path: Optional[str] = None
    generated_image_url: Optional[str] = None
