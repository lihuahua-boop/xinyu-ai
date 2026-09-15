# -*- coding: utf-8 -*-
"""程序化生成头像（SVG）。

不调用任何图片模型：用外观参数 + 名字哈希生成稳定、可复现的抽象肖像。
零成本、可无限次重生成，也避免了真人肖像的授权与合规风险。
"""

from .common import stable_hash

PALETTES = [
    ("#26344f", "#5b7db1", "#cfe0ff"),
    ("#3a2440", "#8a5ea8", "#f0d8ff"),
    ("#1f3b38", "#3f8f7d", "#d8f5ec"),
    ("#3d2a1f", "#a8743f", "#ffe3c4"),
    ("#2b2b3f", "#6b6ba8", "#e0e0ff"),
    ("#40262e", "#b05a72", "#ffd9e2"),
]

HAIR_SHAPES = ["soft", "short", "wave", "tie"]


def generate_svg(name, appearance=None, seed=None):
    """生成 SVG 字符串。"""
    appearance = appearance or {}
    seed_text = "%s|%s|%s" % (seed or name, appearance.get("style", ""), appearance.get("vibe", ""))
    palette_index = stable_hash(seed_text) % len(PALETTES)
    background, mid, light = PALETTES[palette_index]

    hair_index = stable_hash(seed_text + "hair") % len(HAIR_SHAPES)
    hair = appearance.get("hairstyle")
    if hair in HAIR_SHAPES:
        hair_index = HAIR_SHAPES.index(hair)
    hair_shape = HAIR_SHAPES[hair_index]

    glow_y = 96 + (stable_hash(seed_text + "y") % 40)
    hair_path = _hair_path(hair_shape, light)

    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320" width="320" height="320" role="img" aria-label="{name} 的头像">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{background}"/>
      <stop offset="100%" stop-color="{mid}"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.4" r="0.6">
      <stop offset="0%" stop-color="{light}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="{light}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="320" height="320" fill="url(#bg)"/>
  <ellipse cx="160" cy="{glow_y}" rx="150" ry="130" fill="url(#glow)"/>
  <ellipse cx="160" cy="196" rx="86" ry="96" fill="{light}" opacity="0.16"/>
  <circle cx="160" cy="132" r="54" fill="{light}" opacity="0.92"/>
  {hair}
  <path d="M92 292c6-52 34-80 68-80s62 28 68 80z" fill="{light}" opacity="0.9"/>
  <circle cx="160" cy="132" r="54" fill="none" stroke="{background}" stroke-opacity="0.25" stroke-width="2"/>
</svg>
""".format(name=name, background=background, mid=mid, light=light,
           glow_y=glow_y, hair=hair_path)


def _hair_path(shape, color):
    """不同发型用不同的路径，让头像之间有区分度。"""
    if shape == "short":
        return '<path d="M104 126c0-34 24-56 56-56s56 22 56 56c0-18-22-30-56-30s-56 12-56 30z" fill="%s" opacity="0.95"/>' % color
    if shape == "wave":
        return ('<path d="M100 132c-6-42 24-66 60-66s66 24 60 66c-6-14-16-22-30-24'
                'c-14 12-34 16-52 10c-16-6-28 0-38 14z" fill="%s" opacity="0.95"/>' % color)
    if shape == "tie":
        return ('<path d="M106 128c0-36 24-58 54-58s54 22 54 58c0-16-20-26-54-26s-54 10-54 26z" fill="%s" opacity="0.95"/>'
                '<circle cx="226" cy="112" r="16" fill="%s" opacity="0.9"/>' % (color, color))
    return ('<path d="M102 134c-4-44 26-68 58-68s62 24 58 68c-4-16-18-26-34-28'
            'c-14 10-34 14-50 8c-14-6-26 2-32 20z" fill="%s" opacity="0.95"/>' % color)


def appearance_options():
    """前端可选的外观选项。"""
    return {
        "age_range": ["22-25", "26-29", "30-33", "34-38"],
        "height_range": ["175-180", "180-185", "185-190"],
        "hairstyle": [
            {"key": "soft", "label": "温柔碎发"},
            {"key": "short", "label": "干净短发"},
            {"key": "wave", "label": "微卷"},
            {"key": "tie", "label": "低马尾/长发"},
        ],
        "style": ["白衬衫", "休闲卫衣", "黑色西装", "针织毛衣", "风衣"],
        "vibe": ["温柔", "沉稳", "清冷", "阳光", "神秘"],
    }
