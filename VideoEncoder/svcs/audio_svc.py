import os
import time
import asyncio

from ..core.log import log
from ..core.cfg import cfg
from ..utils.display_progress import progress_for_pyrogram
from ..svcs.task_manager import task_manager

# upload_worker is imported lazily inside the functions that need it (not
# here at module level) for the same reason encode_svc.py does this --
# helper.py's import chain eventually reaches back into svcs, and an eager
# import here risks the same circular-import crash that was fixed there.


async def _download(message, msg, task_id, label):
    start_time = time.time()
    user_id = message.from_user.id if message.from_user else None
    task_manager.register_download(task_id, None, None, message, user_id)
    try:
        return await message.download(
            file_name=cfg.DOWNLOAD_DIR,
            progress=progress_for_pyrogram,
            progress_args=(f"▸ <b>{label}</b> [ID: {task_id}]\nStatus: ● Downloading...", msg, start_time, task_id)
        )
    except asyncio.CancelledError:
        return None
    except Exception as e:
        log.err("audio_edit_download_failed", error=str(e), task_id=task_id)
        await msg.edit(f"▸ <b>{label}</b> [ID: {task_id}]\nStatus: ✗ Failed\n<blockquote>Download error: {str(e)[:150]}</blockquote>")
        return None


async def remove_audio_task(message, source_type, overrides=None):
    """
    message = the VIDEO message (the one /remove_audio_1 was a reply to).
    """
    from ..utils.uploads import upload_worker
    from ..utils.audio_editor import remove_audio
    from ..db.users import users_db

    task_id = task_manager.generate_id()
    msg = await message.reply_text(f"▸ <b>Remove Audio</b> [ID: {task_id}]\nStatus: ● Processing...")

    video_path = None
    output_path = None
    try:
        video_path = await _download(message, msg, task_id, "Remove Audio")
        if not video_path:
            return

        task = task_manager.get_task(task_id)
        if task and task.get("cancelled"):
            return

        u_id = message.from_user.id if message.from_user else None
        user_settings = await users_db.get_user(u_id) if u_id else {}
        if not user_settings:
            user_settings = {}

        await msg.edit(f"▸ <b>Remove Audio</b> [ID: {task_id}]\nStatus: ● Stripping audio track(s)...")

        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_noaudio{ext}"
        task_manager.register_encode(task_id, None, message, output_path)

        result, err = await remove_audio(video_path, output_path, task_id, message, user_settings)
        if not result:
            log.err("remove_audio_failed", error=err, task_id=task_id)
            await msg.edit(
                f"▸ <b>Remove Audio</b> [ID: {task_id}]\nStatus: ✗ Failed\n"
                f"<blockquote>{(err or 'Unknown error')[:200]}</blockquote>"
            )
            return

        await msg.edit(f"▸ <b>Remove Audio</b> [ID: {task_id}]\nStatus: ● Uploading...")
        link = await upload_worker(output_path, message, msg)
        await msg.edit(
            f"▸ <b>Remove Audio</b> [ID: {task_id}]\n"
            f"Status: ● Done\n"
            f"<blockquote>Audio removed -- video quality untouched (no re-encode).</blockquote>"
        )
    except asyncio.CancelledError:
        log.wrn("remove_audio_cancelled", task_id=task_id)
    except Exception as e:
        log.err("remove_audio_task", error=str(e), task_id=task_id)
        await message.reply(f"▸ <b>Error</b>\nStatus: ✗ Failed\nReason: {str(e)}")
    finally:
        task_manager.remove_task(task_id)
        for p in (video_path, output_path):
            if p and os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


async def add_audio_task(message, source_type, overrides=None):
    """
    message = the VIDEO message. overrides['audio_message'] = the audio
    file message the user sent in response to the /add_audio_1 prompt.
    """
    from ..utils.uploads import upload_worker
    from ..utils.audio_editor import add_audio
    from ..db.users import users_db

    overrides = overrides or {}
    audio_message = overrides.get("audio_message")
    if not audio_message:
        await message.reply("▸ <b>Add Audio</b>\nStatus: ✗ Failed\n<blockquote>No audio file was provided.</blockquote>")
        return

    task_id = task_manager.generate_id()
    msg = await message.reply_text(f"▸ <b>Add Audio</b> [ID: {task_id}]\nStatus: ● Processing...")

    video_path = None
    audio_path = None
    output_path = None
    try:
        video_path = await _download(message, msg, task_id, "Add Audio")
        if not video_path:
            return

        await msg.edit(f"▸ <b>Add Audio</b> [ID: {task_id}]\nStatus: ● Downloading audio track...")
        audio_path = await _download(audio_message, msg, task_id, "Add Audio")
        if not audio_path:
            return

        task = task_manager.get_task(task_id)
        if task and task.get("cancelled"):
            return

        u_id = message.from_user.id if message.from_user else None
        user_settings = await users_db.get_user(u_id) if u_id else {}
        if not user_settings:
            user_settings = {}

        await msg.edit(f"▸ <b>Add Audio</b> [ID: {task_id}]\nStatus: ● Matching audio to video duration...")

        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_dubbed{ext}"
        task_manager.register_encode(task_id, None, message, output_path)

        result, err = await add_audio(video_path, audio_path, output_path, task_id, message, user_settings)
        if not result:
            log.err("add_audio_failed", error=err, task_id=task_id)
            await msg.edit(
                f"▸ <b>Add Audio</b> [ID: {task_id}]\nStatus: ✗ Failed\n"
                f"<blockquote>{(err or 'Unknown error')[:200]}</blockquote>"
            )
            return

        await msg.edit(f"▸ <b>Add Audio</b> [ID: {task_id}]\nStatus: ● Uploading...")
        link = await upload_worker(output_path, message, msg)
        await msg.edit(
            f"▸ <b>Add Audio</b> [ID: {task_id}]\n"
            f"Status: ● Done\n"
            f"<blockquote>New audio track set as default, matched 1:1 to video length. "
            f"Video quality untouched (no re-encode).</blockquote>"
        )
    except asyncio.CancelledError:
        log.wrn("add_audio_cancelled", task_id=task_id)
    except Exception as e:
        log.err("add_audio_task", error=str(e), task_id=task_id)
        await message.reply(f"▸ <b>Error</b>\nStatus: ✗ Failed\nReason: {str(e)}")
    finally:
        task_manager.remove_task(task_id)
        for p in (video_path, audio_path, output_path):
            if p and os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
