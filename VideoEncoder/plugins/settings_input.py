from pyrogram import Client, filters
from ..db.users import users_db
from ..svcs.settings_svc import settings_svc
from ..utils.helper import check_chat

# Who's actively expected to send a thumbnail photo right now (set by the
# "Set Thumbnail" button in callbacks_.py, popped here once used). Without
# this, a bare "any photo anywhere" filter would grab EVERY photo anyone
# posts in the group as a thumbnail-set attempt, which is wrong -- most
# photos in a shared group have nothing to do with thumbnails.
pending_thumb_set = {}

# Same pattern for the watermark LOGO upload ("Set Logo" button) -- keeps a
# logo upload separate from a thumbnail upload.
pending_wm_logo_set = {}


def _parse_one_ts(token):
    token = token.strip()
    if ":" in token:
        m, s = token.split(":", 1)
        return int(m) * 60 + float(s)
    return float(token)


def _parse_time_range(text):
    """Returns (start_seconds, end_seconds, ok). start/end are None for
    'full' (ok=True). ok=False means the input couldn't be parsed at all."""
    text = text.strip()
    if text.lower() == "full":
        return None, None, True
    try:
        start_str, end_str = text.split("-", 1)
        return _parse_one_ts(start_str), _parse_one_ts(end_str), True
    except Exception:
        return None, None, False

@Client.on_message(filters.reply)
async def settings_input_handler(bot: Client, message):
    if not message.reply_to_message:
        return
        
    reply_text = message.reply_to_message.text
    if not reply_text:
        return
    user_input = message.text
    u_id = message.from_user.id
    
    if "Rename Policy" in reply_text:
        await users_db.update_user(u_id, {"rename_template": user_input})
        text, markup = await settings_svc.get_extra_settings(u_id)
        await message.reply(f"▸ <b>Rename Policy</b>\nStatus: ● Updated\nNew Template: <code>{user_input}</code>")
        await message.reply(text, reply_markup=markup)
        
    elif "Watermark Text" in reply_text:
        await users_db.update_user(u_id, {"watermark_text": user_input})
        text, markup = await settings_svc.get_extra_settings(u_id)
        await message.reply(f"▸ <b>Watermark Text</b>\nStatus: ● Updated\nNew Text: <code>{user_input}</code>")
        await message.reply(text, reply_markup=markup)

    elif "Watermark Time Range" in reply_text:
        from .watermark import get_watermark_panel
        start_s, end_s, ok = _parse_time_range(user_input)
        if not ok:
            await message.reply(
                "▸ <b>Watermark Time Range</b>\nStatus: ✗ Couldn't understand that.\n"
                "<blockquote>Use MM:SS-MM:SS, seconds-seconds, or 'full'.</blockquote>"
            )
            return
        await users_db.update_user(u_id, {"watermark_time_start": start_s, "watermark_time_end": end_s})
        user = await users_db.get_user(u_id)
        text, markup = get_watermark_panel(user)
        label = "Whole video" if start_s is None and end_s is None else f"{start_s or 0}s - {end_s if end_s is not None else 'end'}"
        await message.reply(f"▸ <b>Watermark Time Range</b>\nStatus: ● Updated\nNow visible: {label}")
        await message.reply(text, reply_markup=markup)

@Client.on_message(filters.photo)
async def thumb_input_handler(bot: Client, message):
    u_id = message.from_user.id if message.from_user else None
    if u_id not in pending_thumb_set:
        return  # not something we're waiting on -- ignore quietly, this is just a normal photo

    if not await check_chat(message, chat='Both'):
        pending_thumb_set.pop(u_id, None)
        return

    pending_thumb_set.pop(u_id, None)
    photo = message.photo
    file_id = photo.file_id
    
    await users_db.update_user(u_id, {"custom_thumbnail": file_id})
    text, markup = await settings_svc.get_thumb_settings(u_id)
    await message.reply("▸ <b>Thumbnail</b>\nStatus: ● Saved\nYour custom thumbnail has been updated!")
    await message.reply(text, reply_markup=markup)


@Client.on_message(filters.photo)
async def wm_logo_input_handler(bot: Client, message):
    u_id = message.from_user.id if message.from_user else None
    if u_id not in pending_wm_logo_set:
        return  # not waiting for a logo -- ignore quietly

    if not await check_chat(message, chat='Both'):
        pending_wm_logo_set.pop(u_id, None)
        return

    pending_wm_logo_set.pop(u_id, None)
    photo = message.photo

    # Respect the 5MB logo cap -- bigger uploads are almost always a
    # full-size picture the user actually wanted as a thumbnail.
    from .watermark import check_logo_size
    from ..utils.display_progress import humanbytes
    if not check_logo_size(photo.file_size):
        await message.reply(
            "▸ <b>Watermark Logo</b>\nStatus: ✗ Too Large\n"
            f"<blockquote>Logo size limit is 5MB. "
            f"You sent {humanbytes(photo.file_size)} -- please resize and try again.</blockquote>"
        )
        return

    file_id = photo.file_id
    await users_db.update_user(u_id, {"watermark_image": file_id})
    from .watermark import get_watermark_panel
    user = await users_db.get_user(u_id)
    text, markup = get_watermark_panel(user)
    await message.reply("▸ <b>Watermark Logo</b>\nStatus: ● Saved\nYour logo watermark has been updated!")
    await message.reply(text, reply_markup=markup)
