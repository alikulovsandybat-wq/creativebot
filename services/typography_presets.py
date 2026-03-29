from dataclasses import dataclass


@dataclass
class TypographyPreset:
    name: str

    # Размеры холста
    canvas_w: int = 1080
    canvas_h: int = 1080

    # Цвета
    bg_color: tuple = (26, 26, 46)
    overlay_color: tuple = (0, 0, 0)
    overlay_alpha: int = 140          # 0-255
    accent_color: tuple = (233, 69, 96)
    text_primary: tuple = (255, 255, 255)
    text_secondary: tuple = (200, 200, 200)
    badge_bg: tuple = (233, 69, 96)
    badge_text: tuple = (255, 255, 255)
    cta_bg: tuple = (255, 255, 255)
    cta_text: tuple = (0, 0, 0)

    # Размеры шрифтов
    headline_size: int = 72
    subheadline_size: int = 36
    bullet_size: int = 32
    price_size: int = 56
    badge_size: int = 24
    cta_size: int = 30

    # Зона текста (x, y, width) — откуда начинается текстовый блок
    text_zone_x: int = 60
    text_zone_y: int = 560            # нижняя половина по умолчанию
    text_zone_width: int = 960

    # Позиция бейджа
    badge_x: int = 60
    badge_y: int = 60

    # Градиент снизу (для читаемости текста)
    gradient_from_y: float = 0.45    # откуда начинается затемнение (доля от высоты)


PRESETS = {

    "premium": TypographyPreset(
        name="premium",
        bg_color=(10, 10, 20),
        overlay_alpha=180,
        accent_color=(212, 175, 55),    # золото
        text_primary=(255, 255, 255),
        text_secondary=(180, 180, 180),
        badge_bg=(212, 175, 55),
        badge_text=(0, 0, 0),
        cta_bg=(212, 175, 55),
        cta_text=(0, 0, 0),
        headline_size=80,
        subheadline_size=34,
        bullet_size=28,
        price_size=64,
        badge_size=22,
        cta_size=28,
        text_zone_x=60,
        text_zone_y=580,
        text_zone_width=900,
        gradient_from_y=0.40,
    ),

    "conversion": TypographyPreset(
        name="conversion",
        bg_color=(20, 30, 48),
        overlay_alpha=150,
        accent_color=(41, 182, 246),    # синий
        text_primary=(255, 255, 255),
        text_secondary=(210, 230, 255),
        badge_bg=(233, 69, 96),
        badge_text=(255, 255, 255),
        cta_bg=(41, 182, 246),
        cta_text=(255, 255, 255),
        headline_size=68,
        subheadline_size=32,
        bullet_size=30,
        price_size=52,
        badge_size=22,
        cta_size=28,
        text_zone_x=60,
        text_zone_y=520,
        text_zone_width=960,
        gradient_from_y=0.38,
    ),

    "minimal": TypographyPreset(
        name="minimal",
        bg_color=(245, 245, 240),
        overlay_color=(245, 245, 240),
        overlay_alpha=120,
        accent_color=(30, 30, 30),
        text_primary=(20, 20, 20),
        text_secondary=(80, 80, 80),
        badge_bg=(20, 20, 20),
        badge_text=(255, 255, 255),
        cta_bg=(20, 20, 20),
        cta_text=(255, 255, 255),
        headline_size=72,
        subheadline_size=32,
        bullet_size=28,
        price_size=52,
        badge_size=22,
        cta_size=28,
        text_zone_x=60,
        text_zone_y=540,
        text_zone_width=960,
        gradient_from_y=0.42,
    ),
}
