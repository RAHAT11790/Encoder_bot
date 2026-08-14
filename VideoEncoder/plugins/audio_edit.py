"""
/remove_audio_1  -- reply to a video: strips all audio, video untouched.
/add_audio_1     -- reply to a video: prompts for an audio file, then sets
                     it as the video's sole/default audio track, time-
                     matched 1:1 to the video's length. Video untouched.
"""

from pyrogram import Client, filters

from ..svcs.queue_svc import queue_svc
from ..svcs.audio_svc import remove_audio_task, add_audio_task
from ..svcs.user_svc import add_user_if_new
from ..utils.helper import check_chat
from ..core.cfg import cfg

# In-memory "waiting for an audio file" state, keyed by user id. Short-
# lived (cleared as soon as the audio arrives, or replaced by a newer
# /add_audio_1 call) so a plain dict is enough -- no DB persistence needed.
_pending_add_audio = {}


def _is_video(m):
    return bool(m.video or (m.document and m.document.mime_type in cfg.VIDEO_MIMETYPES))


@Client.on_message(filters.command('remove_audio_1'))
async def remove_audio_cmd(app, message):
    if not await check_chat(message, chat='Both'):
        return

    if not message.reply_to_message or not _is_video(message.reply_to_message):
        await message.reply(
            "▸ <b>Remove Audio</b>\nStatus: ✗ Failed\n"
            "<blockquote>Reply to a video with <code>/remove_audio_1</code>.</blockquote>"
        )
        return

    await add_user_if_new(app, message)
    await queue_svc.add(message.reply_to_message, 'audio_remove', remove_audio_task)
    await message.reply("▸ <b>Remove Audio</b>\nStatus: ● Queued")


@Client.on_message(filters.command(['add_audio', 'add_audio_1']))
async def add_audio_cmd(app, message):
    if not await check_chat(message, chat='Both'):
        return

    if not message.reply_to_message or not _is_video(message.reply_to_message):
        await message.reply(
            "▸ <b>Add Audio</b>\nStatus: ✗ Failed\n"
            "<blockquote>Reply to a video with <code>/add_audio_1</code>.</blockquote>"
        )
        return

    await add_user_if_new(app, message)
    u_id = message.from_user.id
    _pending_add_audio[u_id] = message.reply_to_message

    await message.reply(
        "▸ <b>Add Audio</b>\nStatus: ● Waiting for audio\n"
        "<blockquote>Now send me the audio file (as audio, voice, or an "
        "audio document) to add to that video. It'll become the video's "
        "only/default audio track, automatically time-matched to the "
        "video's exact length.</blockquote>"
    )


def _is_audio_message(_, __, m):
    if m.audio or m.voice:
        return True
    if m.document and (m.document.mime_type or "").startswith("audio/"):
        return True
    return False


@Client.on_message(filters.create(_is_audio_message))
async def add_audio_input_handler(app, message):
    u_id = message.from_user.id if message.from_user else None
    if u_id not in _pending_add_audio:
        return  # not something we're waiting on -- ignore quietly

    if not await check_chat(message, chat='Both'):
        _pending_add_audio.pop(u_id, None)
        return

    video_message = _pending_add_audio.pop(u_id)
    await queue_svc.add(video_message, 'audio_add', add_audio_task, {"audio_message": message})
    await message.reply("▸ <b>Add Audio</b>\nStatus: ● Queued")
