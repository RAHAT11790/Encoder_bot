from pyrogram.types import InlineKeyboardButton

# Telegram Bot API 9.4 (Feb 2026) added a "style" field to inline buttons:
# 'primary' (blue), 'success' (green), 'danger' (red). Whether the exact
# Pyrogram/Kurigram version installed on this VPS has already added support
# for that field is not something we can verify from here -- so this helper
# tries it, and if the installed library rejects the "style" keyword
# (raises TypeError), it transparently falls back to a plain button instead
# of crashing the whole menu. Colors are a nice-to-have; a working menu is
# not optional.
def cbtn(text, callback_data=None, url=None, style=None):
    kwargs = {}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style:
        try:
            return InlineKeyboardButton(text, style=style, **kwargs)
        except TypeError:
            pass
    return InlineKeyboardButton(text, **kwargs)
