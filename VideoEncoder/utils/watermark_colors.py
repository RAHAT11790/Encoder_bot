"""Watermark color palette + conversion helpers.

Colors are stored in the DB as a short name key (e.g. "red"). Two render
formats are derived from that key on demand:

- ASS subtitle colour (PrimaryColour) -- used by encoding.py for the
  text-overlay watermark. ASS stores colours as &H00BBGGRR (BGR order).
- drawtext colour (0xRRGGBB) -- used when the watermark is burned in via
  the drawtext ffmpeg filter instead of an .ass overlay.

The palette is deliberately small and high-contrast: watermark text sits
over arbitrary video content, so muddled mid-tone colours vanish. Every
entry is a saturated primary/secondary or near-white/near-black.
"""

# name -> (display label, hex RRGGBB)
WATERMARK_COLORS = {
    'white':   ('White',   'FFFFFF'),
    'black':   ('Black',   '000000'),
    'red':     ('Red',     'FF0000'),
    'green':   ('Green',   '00FF00'),
    'yellow':  ('Yellow',  'FFFF00'),
    'blue':    ('Blue',    '0080FF'),
    'orange':  ('Orange',  'FF8000'),
    'purple':  ('Purple',  '9B30FF'),
    'pink':    ('Pink',    'FF66CC'),
    'cyan':    ('Cyan',    '00FFFF'),
    'lime':    ('Lime',    '80FF00'),
    'gold':    ('Gold',    'FFD700'),
    'silver':  ('Silver',  'C0C0C0'),
}

DEFAULT_COLOR = 'white'


def get_color_name(key):
    if key in WATERMARK_COLORS:
        return WATERMARK_COLORS[key][0]
    return WATERMARK_COLORS[DEFAULT_COLOR][0]


def get_hex(key):
    """Returns the RRGGBB hex string for a color key (default: white)."""
    if key in WATERMARK_COLORS:
        return WATERMARK_COLORS[key][1]
    return WATERMARK_COLORS[DEFAULT_COLOR][1]


def ass_color(key):
    """ASS PrimaryColour (&H00BBGGRR) for a color key."""
    rgb = get_hex(key)
    r, g, b = rgb[0:2], rgb[2:4], rgb[4:6]
    return f"&H00{b}{g}{r}"


def drawtext_color(key):
    """drawtext color (0xRRGGBB) for a color key."""
    return f"0x{get_hex(key)}"


def color_keys():
    """All palette keys, in display order."""
    return list(WATERMARK_COLORS.keys())
