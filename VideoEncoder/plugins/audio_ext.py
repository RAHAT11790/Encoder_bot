"""
/audio_ext_time <ranges>  -- reply to a video or audio file: extracts the
audio (or uses the audio directly) and CUTS OUT the given time ranges,
returning the cleaned audio file.

Usage:
    /audio_ext_time 0:00-0:03,2:11-2:15

The ranges are comma separated, each one is START-END (MM:SS, HH:MM:SS or
plain seconds). Everything inside those ranges is removed; everything
outside them is kept and stitched back together in order.

Typical use-case: an audio has a long silent intro / outro or some other
garbage that has to go before it can be muxed onto a video. Give this
command the parts you want to delete and it hands back the clean audio.
"""

import os
import asyncio
import time
import re

from pyrogram import Client, filters

from ..core.cfg import cfg
from ..core.log import log
from ..utils.helper import check_chat
from ..svcs.user_svc import add_user_if_new
from ..utils.display_progress import progress_for_pyrogram, humanbytes
from ..utils.audio_editor import precise_duration


def parse_ts(token):
    """'1:30' / '00:01:30' / '90' -> seconds (float)."""
    token = token.strip()
    if ':' in token:
        seconds = 0.0
        for part in token.split(':'):
            seconds = seconds * 60 + float(part)
        return seconds
    return float(token)


def format_ts(seconds):
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def parse_ranges(text):
    """Parse '0:00-0:03,2:11-2:15' into a sorted, merged [(start, end), ...].

    Returns (ranges, None) on success or (None, error_message) on failure.
    Ranges are validated (end > start, no negatives) but not yet clamped to
    the real audio duration -- that happens later, after the file is down.
    """
    tokens = [t for t in re.split(r"[,\s]+", text) if t.strip()]
    if not tokens:
        return None, "No time ranges provided. Example: /audio_ext_time 0:00-0:03,2:11-2:15"

    ranges = []
    for tok in tokens:
        if '-' not in tok:
            return None, f"Invalid range: <code>{tok}</code> -- use START-END, e.g. 0:00-0:03"
        try:
            s_str, e_str = tok.split('-', 1)
            s, e = parse_ts(s_str), parse_ts(e_str)
        except Exception:
            return None, f"Invalid time format: <code>{tok}</code> -- use MM:SS-MM:SS or seconds"
        if s < 0 or e <= s:
            return None, f"Invalid range: <code>{tok}</code> -- end must be after start."
        ranges.append((s, e))

    ranges.sort()
    merged = []
    for s, e in ranges:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged, None


def build_keep_intervals(duration, removes):
    """Complement of the remove ranges over [0, duration], as keep intervals."""
    clamped = []
    for s, e in removes:
        if s >= duration:
            continue
        e = min(e, duration)
        if e - s < 0.05:
            continue
        clamped.append((s, e))

    keep = []
    cursor = 0.0
    for s, e in clamped:
        if s > cursor:
            keep.append((cursor, s))
        cursor = max(cursor, e)
    if duration - cursor > 0.05:
        keep.append((cursor, duration))
    return keep


def _is_audio_message(m):
    if m.audio or m.voice:
        return True
    if m.document and (m.document.mime_type or "").startswith("audio/"):
        return True
    return False


def _out_config(reply):
    """Pick (ffmpeg codec, file extension) for the output audio."""
    src = None
    if reply.audio:
        src = os.path.splitext(reply.audio.file_name or "")[1].lower() if reply.audio.file_name else None
    elif reply.document and reply.document.file_name:
        src = os.path.splitext(reply.document.file_name)[1].lower()
    elif reply.video or reply.voice:
        src = None

    if src == '.mp3':
        return 'libmp3lame', '.mp3', '192k'
    if src == '.opus':
        return 'libopus', '.opus', '128k'
    if src == '.flac':
        return 'flac', '.flac', None
    if src == '.wav':
        return 'pcm_s16le', '.wav', None
    if src == '.ogg' or src == '.oga':
        return 'libvorbis', '.ogg', '192k'
    if src == '.m4a' or src == '.aac':
        return 'aac', '.m4a', '192k'
    # video or anything unknown -> plain mp3
    return 'libmp3lame', '.mp3', '192k'


@Client.on_message(filters.command(['audio_ext_time', 'audio_ext_time_1']))
async def audio_ext_time_handler(app, message):
    if not await check_chat(message, chat='Both'):
        return

    if not message.reply_to_message:
        await message.reply(
            "▸ <b>Audio Ext Time</b>\n"
            "Status: ✗ Failed\n\n"
            "<blockquote>Reply to a video or audio file with this command.\n\n"
            "Usage: /audio_ext_time <code>0:00-0:03,2:11-2:15</code>\n"
            "Comma-separated ranges, each START-END (MM:SS or seconds).\n"
            "Those parts get removed from the audio.</blockquote>"
        )
        return

    reply = message.reply_to_message
    is_video = bool(reply.video or (reply.document and (reply.document.mime_type or "").startswith("video/")))
    if not (is_video or _is_audio_message(reply)):
        await message.reply(
            "▸ <b>Audio Ext Time</b>\n"
            "Status: ✗ Failed\n\n"
            "<blockquote>The replied message is not a video or audio file.</blockquote>"
        )
        return

    if len(message.command) < 2:
        await message.reply(
            "▸ <b>Audio Ext Time</b>\n"
            "Status: ✗ No Ranges\n\n"
            "<blockquote>Example:\n"
            "<code>/audio_ext_time 0:00-0:03,2:11-2:15</code>\n\n"
            "That removes 0:00-0:03 and 2:11-2:15 from the audio.</blockquote>"
        )
        return

    ranges_text = " ".join(message.command[1:])
    removes, err = parse_ranges(ranges_text)
    if err:
        await message.reply(
            "▸ <b>Audio Ext Time</b>\n"
            f"Status: ✗ Failed\n\n<blockquote>{err}</blockquote>"
        )
        return

    await add_user_if_new(app, message)

    msg = await message.reply(
        "▸ <b>Audio Ext Time</b>\n"
        "Status: ● Downloading..."
    )

    filepath = None
    output_path = None
    try:
        start_time = time.time()
        filepath = await reply.download(
            file_name=cfg.DOWNLOAD_DIR,
            progress=progress_for_pyrogram,
            progress_args=("▸ <b>Audio Ext Time</b>\nStatus: ● Downloading...", msg, start_time)
        )

        if not filepath:
            await msg.edit("▸ <b>Audio Ext Time</b>\nStatus: ✗ Download Failed")
            return

        duration = precise_duration(filepath)
        if duration <= 0:
            await msg.edit("▸ <b>Audio Ext Time</b>\nStatus: ✗ Could not read media duration")
            return

        keep = build_keep_intervals(duration, removes)
        if not keep:
            await msg.edit(
                "▸ <b>Audio Ext Time</b>\nStatus: ✗ Nothing Left\n\n"
                "<blockquote>The given ranges cover the whole audio -- there is "
                "nothing left to keep.</blockquote>"
            )
            return

        removed_txt = ", ".join(f"{format_ts(s)}-{format_ts(e)}" for s, e in removes)
        new_duration = sum(e - s for s, e in keep)

        await msg.edit(
            f"▸ <b>Audio Ext Time</b>\n"
            f"Status: ● Removing {len(removes)} segment(s)...\n"
            f"Removed: {removed_txt}\n"
            f"New Duration: {format_ts(new_duration)}"
        )

        codec, ext, bitrate = _out_config(reply)
        basename = os.path.basename(filepath)
        name, _ = os.path.splitext(basename)
        output_path = os.path.join(cfg.ENCODE_DIR, f"ext_{name}{ext}")

        parts = []
        for i, (s, e) in enumerate(keep):
            parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=N/SR/TB[a{i}]")
        labels = "".join(f"[a{i}]" for i in range(len(keep)))
        parts.append(f"{labels}concat=n={len(keep)}:v=0:a=1[aout]")
        filter_complex = ";".join(parts)

        cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-i', filepath,
            '-filter_complex', filter_complex,
            '-map', '[aout]',
            '-c:a', codec,
        ]
        if bitrate:
            cmd.extend(['-b:a', bitrate])
        cmd.append(output_path)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            err_txt = stderr.decode(errors="ignore")[-300:] if stderr else "Unknown error"
            log.err("audio_ext_time_ffmpeg", error=err_txt)
            await msg.edit(
                f"▸ <b>Audio Ext Time</b>\nStatus: ✗ Failed\n"
                f"<blockquote>{err_txt}</blockquote>"
            )
            return

        await msg.edit("▸ <b>Audio Ext Time</b>\nStatus: ● Uploading...")

        output_size = os.path.getsize(output_path)
        await reply.reply_audio(
            output_path,
            caption=(
                f"▸ <b>Cleaned Audio</b>\n"
                f"Removed: <code>{removed_txt}</code>\n"
                f"Duration: {format_ts(new_duration)} | Size: {humanbytes(output_size)}"
            ),
            duration=int(new_duration),
            title=f"{name} (cleaned)"
        )

        await msg.delete()

    except Exception as e:
        log.err("audio_ext_time_error", error=str(e))
        await msg.edit(f"▸ <b>Audio Ext Time</b>\nStatus: ✗ Error\n{str(e)[:100]}")
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
