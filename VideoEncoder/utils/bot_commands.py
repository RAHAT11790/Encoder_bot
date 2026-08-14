"""BotFather command list pushed to Telegram at startup.

Every command the bot handles lives here so the in-menu command palette
matches what /help describes. Emojis in the descriptions make the command
picker scannable on mobile (Telegram shows one line per command).
"""

BOT_COMMANDS = [
    ("start", "🤖 Start the bot"),
    ("settings", "⚙️ Open control panel"),
    ("watermark", "💧 Watermark settings (text/logo)"),
    ("vset", "🔁 Apply last used settings to a video"),
    ("reset", "🔄 Reset your settings to default"),
    ("mode", "🌐 Toggle public/private mode"),
    ("help", "❓ How to use the bot"),
    ("enc", "🎬 Encode a video (reply to video)"),
    ("1080p", "📺 Encode at 1080p"),
    ("720p", "📺 Encode at 720p"),
    ("480p", "📺 Encode at 480p"),
    ("420p", "📺 Encode at 420p"),
    ("batch", "📦 Batch encode a folder/archive"),
    ("ddl", "⬇️ Download & encode from a direct link"),
    ("trim", "✂️ Trim a video segment"),
    ("sample", "🎞️ Generate a sample clip"),
    ("ss", "📸 Take screenshot(s) from a video"),
    ("audio", "🎵 Extract audio from a video"),
    ("audio_ext_time", "⏱ Extract audio with a time range"),
    ("remove_audio_1", "🔇 Remove audio from a video"),
    ("add_audio_1", "🎧 Add/replace audio on a video"),
    ("queue", "📋 Show current queue"),
    ("clear", "🗑 Clear the queue"),
    ("cancel", "🛑 Cancel current task"),
]

# Owner/administrator only -- hidden from the public palette.
SUDO_COMMANDS = [
    ("exec", "🖥 Execute a shell command"),
    ("sh", "💻 Run a shell command"),
    ("logs", "📜 View bot logs"),
    ("dupload", "📤 Upload a file as document"),
    ("vupload", "🎬 Upload a file as video"),
    ("addsudo", "➕ Add a sudo user"),
    ("rmsudo", "➖ Remove a sudo user"),
    ("addchat", "➕ Allow a chat"),
    ("rmchat", "➖ Disallow a chat"),
    ("addpremium", "💎 Add premium user"),
    ("rmpremium", "💎 Remove premium user"),
]

# The main command list. Sudo commands are appended for the owner's scope
# via set_sudo_commands().
def get_public_commands():
    from pyrogram.types import BotCommand
    return [BotCommand(cmd, desc) for cmd, desc in BOT_COMMANDS]


def get_sudo_commands():
    from pyrogram.types import BotCommand
    return [BotCommand(cmd, desc) for cmd, desc in SUDO_COMMANDS]
