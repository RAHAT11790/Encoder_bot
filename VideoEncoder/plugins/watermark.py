import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from ..utils.helper import check_chat
from ..db.users import users_db
from ..core.cfg import cfg
from ..utils.ui import cbtn
from ..utils.watermark_colors import color_keys, get_color_name, WATERMARK_COLORS

POSITION_LABELS = {
    'tl': '↖️', 'tc': '⬆️', 'tr': '↗️',
    'ml': '⬅️', 'mc': '⏺️', 'mr': '➡️',
    'bl': '↙️', 'bc': '⬇️', 'br': '↘️'
}

SIZE_LABELS = {'small': '🔹', 'medium': '🔷', 'large': '🔶'}

TYPE_LABELS = {'text': 'Text', 'image': 'Logo', 'both': 'Text + Logo'}

# Logo watermark uploads are capped at this many MB -- a 50MB PNG gets
# scaled down to near-invisible anyway, it just wastes RAM/disk/time.
LOGO_MAX_MB = 5


@Client.on_message(filters.command(['watermark', 'watermark_1']))
async def watermark_settings_handler(app, message):
    if not await check_chat(message, chat='Both'):
        return
    
    if message.chat.type != "private":
        bot_info = await app.get_me()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Open Settings in DM", url=f"https://t.me/{bot_info.username}?start=watermark")]
        ])
        await message.reply(
            "▸ <b>Watermark</b>\n"
            "Status: ● Private Only\n\n"
            "<blockquote>Settings can only be configured in private chat.\n"
            "Please DM me to manage your watermark preferences.</blockquote>",
            reply_markup=keyboard
        )
        return
    
    u_id = message.from_user.id
    user = await users_db.get_user(u_id)
    
    if not user:
        await users_db.add_user(u_id)
        user = await users_db.get_user(u_id)
    
    text, markup = get_watermark_panel(user)
    await message.reply(text, reply_markup=markup)

def get_watermark_panel(user):
    wm_enabled = "ON" if user.get('watermark', False) else "OFF"
    wm_type = user.get('watermark_type', 'text')
    wm_pos = user.get('watermark_position', 'bc')
    wm_size = user.get('watermark_size', 'medium')
    wm_color = user.get('watermark_color', 'white')
    wm_text = user.get('watermark_text', '@RS_WONER')
    has_image = user.get('watermark_image') is not None
    
    type_label = TYPE_LABELS.get(wm_type, 'Text')
    pos_label = POSITION_LABELS.get(wm_pos, '↘️')
    size_label = wm_size.capitalize()
    color_label = get_color_name(wm_color)
    
    wm_range = ""
    ws, we = user.get('watermark_time_start'), user.get('watermark_time_end')
    if ws is not None or we is not None:
        wm_range = f"<b>Time Range:</b> {_fmt_ts(ws or 0)} - {_fmt_ts(we) if we is not None else 'end'}\n"

    text = (
        f"▸ <b>Watermark</b>\n"
        f"Status: ● {wm_enabled}\n\n"
        f"<b>Type:</b> {type_label}\n"
        f"<b>Position:</b> {pos_label}\n"
        f"<b>Size:</b> {size_label}\n"
        f"{wm_range}"
    )
    
    if wm_type in ('text', 'both'):
        text += f"<b>Text:</b> <code>{wm_text}</code>\n"
        text += f"<b>Color:</b> ▉ {color_label}\n"
    if wm_type in ('image', 'both'):
        text += f"<b>Logo:</b> {'Saved' if has_image else 'Not Set'}\n"
    
    text += (
        "\n<blockquote>Send a photo to set as your logo watermark.\n"
        f"Logo size limit: {LOGO_MAX_MB}MB.\n\n"
        "Note: Adding watermark may slightly increase file size.</blockquote>"
    )
    
    wm_status = "✅" if user.get('watermark', False) else "❌"
    keyboard = [
        [cbtn(f"Watermark: {wm_status}", "wm_toggle")],
        [
            cbtn(f"Type: {type_label}", "wm_type"),
            cbtn(f"Size: {size_label}", "wm_size")
        ],
        [
            cbtn(f"Position: {pos_label}", "wm_position"),
            cbtn(f"Color: ▉", "wm_color")
        ],
        [cbtn("⏱ Time Range", "wm_timerange")],
        [cbtn("Set Text", "setWatermark")],
        [
            cbtn("Set Logo", "wm_setlogo", style="success"),
            cbtn("Del Logo", "wm_delogo", style="danger")
        ],
        [cbtn("🖼 Preview", "wm_preview", style="primary")],
        [cbtn("« Back", "OpenSettings")]
    ]
    
    return text, InlineKeyboardMarkup(keyboard)


def _fmt_ts(seconds):
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

def get_position_grid(current_pos):
    positions = [
        ['tl', 'tc', 'tr'],
        ['ml', 'mc', 'mr'],
        ['bl', 'bc', 'br']
    ]
    
    keyboard = []
    for row in positions:
        btn_row = []
        for pos in row:
            label = "✅" if pos == current_pos else POSITION_LABELS[pos]
            btn_row.append(InlineKeyboardButton(label, callback_data=f"wm_pos_{pos}"))
        keyboard.append(btn_row)
    
    keyboard.append([cbtn("« Back", "wm_back")])
    
    return InlineKeyboardMarkup(keyboard)

def get_color_grid(current_color):
    """Color picker -- one row per color, a ✓ marks the active one."""
    keyboard = []
    for key in color_keys():
        name = WATERMARK_COLORS[key][0]
        mark = "✓ " if key == current_color else ""
        keyboard.append([InlineKeyboardButton(f"{mark}{name}", callback_data=f"wm_color_{key}")])
    keyboard.append([cbtn("« Back", "wm_back")])
    return InlineKeyboardMarkup(keyboard)


async def generate_preview_image(user, msg_id):
    """
    Builds a single PNG showing every watermark size (small/medium/large)
    across every palette color, rendered against a dark 'video-ish'
    background so the user can compare contrast before committing.

    Uses the same ASS overlay machinery as real encodes, so what you see
    is exactly what gets burned into the video. Returns the image path.
    """
    from ..utils.encoding import _create_watermark

    text = user.get('watermark_text', '@RS_WONER') or '@RS_WONER'
    wm_type = user.get('watermark_type', 'text')
    colors = color_keys()
    sizes = ['small', 'medium', 'large']

    out_path = os.path.join(cfg.ENCODE_DIR, f"wm_preview_{msg_id}.png")
    ass_path = os.path.join(cfg.ENCODE_DIR, f"wm_preview_{msg_id}.ass")

    # 3 size rows x len(colors) columns, cells of 280x200.
    cell_w, cell_h = 280, 200
    canvas_w, canvas_h = cell_w * len(colors), cell_h * len(sizes)

    lines = []
    for row, size in enumerate(sizes):
        fontsize = {'small': 20, 'medium': 28, 'large': 40}[size]
        for col, color in enumerate(colors):
            x = col * cell_w + cell_w // 2
            y = row * cell_h + cell_h // 2
            rgb = WATERMARK_COLORS[color][1]
            # Override colour per-line so one ASS file can show the whole palette.
            lines.append(
                f"Dialogue: 0,0:00:00.00,0:00:02.00,Preview,,0,0,0,,"
                f"{{\\pos({x},{y})\\fs{fontsize}\\c&H{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}&}}{text}"
            )

    # PlayRes must match the actual canvas size so \pos coordinates land
    # exactly where each cell is on the generated image.
    content = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {canvas_w}\nPlayResY: {canvas_h}\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Preview, Arial, 28, &H00FFFFFF, 1, 1, 2, 1, 5, 20, 20, 20, 1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "\n".join(lines)
    )
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(content)

    try:
        proc = await asyncio.create_subprocess_exec(
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-f', 'lavfi', '-i', f"color=c=0x14141e:s={canvas_w}x{canvas_h}:r=1",
            '-vf', f"ass='{ass_path}'",
            '-frames:v', '1', out_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0 or not os.path.exists(out_path):
            return None
        return out_path
    except Exception as e:
        return None
    finally:
        try:
            if os.path.exists(ass_path):
                os.remove(ass_path)
        except Exception:
            pass


def check_logo_size(file_size):
    """True if the logo file is within the allowed size limit."""
    return file_size <= LOGO_MAX_MB * 1024 * 1024
