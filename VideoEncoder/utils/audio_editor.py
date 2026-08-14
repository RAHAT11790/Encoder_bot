"""
Core ffmpeg logic for /remove_audio_1 and /add_audio_1.

Both operations keep the video stream untouched when no watermark is
configured (-c:v copy) -- the video comes out byte-identical in quality,
only its audio track changes. If the user has a watermark enabled, the
video stream is re-encoded to burn it in (a watermark can't be applied to
a copied stream).
"""

import asyncio
import os
import subprocess

# A single atempo pass only sounds natural within this range (ffmpeg's own
# supported range for one atempo instance is 0.5-2.0 anyway). Outside this,
# don't force an unnaturally slow/warped tempo change (nobody wants 0.2x
# audio) -- pad with silence or trim instead, which keeps the audio itself
# sounding completely normal.
TEMPO_MIN = 0.5
TEMPO_MAX = 2.0


async def run_ffmpeg_simple(cmd, task_id=None, message=None):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    if task_id:
        # Let /cancel actually terminate this process while it's running,
        # same as a full encode.
        from ..svcs.task_manager import task_manager
        task = task_manager.get_task(task_id)
        if task:
            task["process"] = proc
        elif message is not None:
            task_manager.register_encode(task_id, proc, message)
    stdout, stderr = await proc.communicate()
    if task_id:
        from ..svcs.task_manager import task_manager
        task = task_manager.get_task(task_id)
        if task and task.get("cancelled"):
            return -1, "Cancelled by user"
    return proc.returncode, stderr.decode(errors="ignore").strip()


def precise_duration(filepath):
    """
    ffprobe-based, sub-second-accurate duration -- needed here because the
    codebase's other get_duration() (hachoir-based, via timedelta.seconds)
    truncates to whole seconds, which isn't precise enough for lining
    audio up against video.
    """
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return float(out)
    except Exception:
        return 0.0


async def _build_watermark_filter(user_settings, tag):
    """
    Builds the extra ffmpeg args that burn a user's watermark into the
    video stream. Returns ([extra_args], video_encoder_params) where
    extra_args are the additional -i / -filter args and
    video_encoder_params replace "-c:v copy" (a watermark CANNOT be burned
    in while copying the stream, so the video must be re-encoded).
    Returns (None, None) if no watermark is configured.
    """
    if not user_settings.get('watermark'):
        return None, None

    from .encoding import _create_watermark, _get_image_watermark_filter, _escape_filter_path

    wm_type = user_settings.get('watermark_type', 'text')
    wm_position = user_settings.get('watermark_position', 'bc')
    wm_size = user_settings.get('watermark_size', 'medium')
    wm_color = user_settings.get('watermark_color', 'white')
    wm_start = user_settings.get('watermark_time_start')
    wm_end = user_settings.get('watermark_time_end')

    chain = []
    extra = []
    if wm_type in ('text', 'both'):
        wm_path = await _create_watermark(
            user_settings.get('watermark_text', '@RS_WONER'),
            tag, wm_position, wm_size, wm_start, wm_end, wm_color
        )
        chain.append(f"subtitles='{_escape_filter_path(wm_path)}'")
    if wm_type in ('image', 'both') and user_settings.get('watermark_image'):
        data = await _get_image_watermark_filter(
            user_settings.get('watermark_image'), wm_position, wm_size,
            tag, wm_start, wm_end
        )
        if data:
            extra.extend(['-i', data['path']])
            wm_chain = ",".join(chain) if chain else "null"
            fc = (
                f"[0:v]{wm_chain}[vout];"
                f"[1:v]scale={data['scale']}:-1,format=rgba,colorchannelmixer=aa=0.7[wm];"
                f"[vout][wm]overlay={data['pos']}{data['enable']}[finalv]"
            )
            chain = [fc]
            return extra, ['-filter_complex', fc]

    if chain:
        return extra, ['-vf', ','.join(chain)]
    return None, None


async def remove_audio(video_path, output_path, task_id=None, message=None, user_settings=None):
    """
    Strips every audio track from the video. By default the video stream is
    pure stream copy (-c:v copy) -- never re-encoded/re-compressed. If a
    watermark is configured the video MUST be re-encoded to burn it in.
    """
    extra_args = []
    v_params = ['-c:v', 'copy']
    if user_settings:
        extra_args, wm_v_params = await _build_watermark_filter(user_settings, task_id or 0)
        if wm_v_params:
            v_params = ['-c:v', 'libx264', '-crf', '22', '-preset', 'veryfast'] + wm_v_params

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", video_path,
    ]
    cmd.extend(extra_args)
    cmd += [
        "-map", "0:v:0", *v_params, "-an",
        "-map_metadata", "0",
        output_path,
    ]
    returncode, err = await run_ffmpeg_simple(cmd, task_id, message)
    if returncode != 0 or not os.path.isfile(output_path) or os.path.getsize(output_path) < 1024:
        if os.path.isfile(output_path):
            os.remove(output_path)
        return None, err
    return output_path, None


async def add_audio(video_path, audio_path, output_path, task_id=None, message=None, user_settings=None):
    """
    Replaces whatever audio the video has (if any) with the given audio
    file as the SOLE/default track, matched 1:1 to the video's length.
    Video stream is -c:v copy by default -- never re-encoded/re-compressed.
    If a watermark is configured the video stream is re-encoded to burn it in.

    How the duration mismatch is handled:
    - Small/no mismatch: muxed as-is.
    - Moderate mismatch (audio needs to run 0.5x-2.0x speed to fit): a
      single natural-sounding atempo pass.
    - Large mismatch, audio too SHORT: padded with silence at the end
      instead of stretched into unnaturally slow/warped audio.
    - Large mismatch, audio too LONG: cleanly trimmed to the video's
      length (natural pitch/speed kept for the part that's used).
    """
    video_duration = precise_duration(video_path)
    audio_duration = precise_duration(audio_path)

    if not video_duration or not audio_duration:
        return None, "Could not read duration from the video or audio file."

    ratio = audio_duration / video_duration
    mismatch = abs(audio_duration - video_duration)
    needs_adjustment = mismatch > max(0.25, video_duration * 0.005)

    audio_filter = None
    if needs_adjustment:
        if TEMPO_MIN <= ratio <= TEMPO_MAX:
            audio_filter = f"atempo={ratio:.6f}"
        elif audio_duration < video_duration:
            audio_filter = "apad"
        # else audio_duration > video_duration: no filter needed, the
        # "-t <video_duration>" output flag below trims it cleanly.

    extra_args = []
    v_params = ['-c:v', 'copy']
    if user_settings:
        extra_args, wm_v_params = await _build_watermark_filter(user_settings, task_id or 0)
        if wm_v_params:
            v_params = ['-c:v', 'libx264', '-crf', '22', '-preset', 'veryfast'] + wm_v_params

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video_path, "-i", audio_path]
    cmd.extend(extra_args)
    if audio_filter:
        cmd += ["-filter:a", audio_filter]
    cmd += [
        "-map", "0:v:0", "-map", "1:a:0",
        *v_params, "-c:a", "aac", "-b:a", "192k",
        "-t", str(video_duration),
        output_path,
    ]

    returncode, err = await run_ffmpeg_simple(cmd, task_id, message)
    if returncode != 0 or not os.path.isfile(output_path) or os.path.getsize(output_path) < 1024:
        if os.path.isfile(output_path):
            os.remove(output_path)
        return None, err
    return output_path, None

