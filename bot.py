#!/usr/bin/env python3
"""
Single entry point for the whole bot.

Run it with:
    python3 bot.py

Every plugin under VideoEncoder/plugins loads automatically, and every
config value comes from config.py (no .env needed). Run this from the
project root (same folder as config.py).
"""

import os
import sys


def _check_dependencies():
    """
    A missing package used to surface as a raw Python traceback deep
    inside Pyrogram's plugin loader (confusing -- "No module named
    'motor'" gives no hint that it just means `pip install -r
    requirements.txt` hasn't finished/run yet). Check the critical ones
    up front and fail with a clear, one-line instruction instead.

    lk21 is intentionally NOT in this list. It's only used for one
    optional feature (the /ddl_1 direct-link extractor) and the actual
    code already wraps it in try/except so the bot runs fine without it.
    lk21 itself has a bug where just importing it can crash with
    "ValueError: Invalid IPv6 URL" on some Python 3.9 patch versions
    (unrelated to whether it's actually installed) -- treating it as
    required would take the WHOLE BOT down over one optional feature.
    Every check below also catches Exception broadly, not just
    ImportError, for the same reason: a badly-behaved package can fail
    to import with almost any exception type, not just ImportError.
    """
    required = [
        "pyrogram", "motor", "dns", "hachoir", "ffmpeg",
        "aiohttp", "psutil", "pySmartDL", "requests",
    ]
    optional = ["cloudscraper", "bs4", "js2py", "lk21"]

    missing = []
    for mod in required:
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)

    for mod in optional:
        try:
            __import__(mod)
        except Exception as e:
            print(f"[Warn] Optional package '{mod}' isn't usable ({e}) -- "
                  f"the /ddl_1 direct-link feature may not work, everything else will.")

    if missing:
        # Self-heal instead of just exiting: the same missing packages
        # showing up run after run almost always means `pip install -r
        # requirements.txt` isn't actually being (re-)run before the bot
        # starts (e.g. a hosting panel that only runs `python3 bot.py`) --
        # not a real dependency problem. So just install them here.
        print("=" * 60)
        print("Missing Python packages:", ", ".join(missing))
        print("Installing automatically: pip install -r requirements.txt")
        print("=" * 60)
        import subprocess
        req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("[Auto-install FAILED]")
            print(result.stdout[-2000:])
            print(result.stderr[-2000:])
            print("=" * 60)
            print("Please run this manually and check for errors:")
            print(f"    {sys.executable} -m pip install -r requirements.txt")
            print("=" * 60)
            sys.exit(1)

        # Re-check after installing -- if something is STILL missing at
        # this point, it's a real problem worth stopping for. If
        # everything installed fine, just continue normally below.
        still_missing = []
        for mod in missing:
            try:
                __import__(mod)
            except Exception:
                still_missing.append(mod)
        if still_missing:
            print("=" * 60)
            print("Still missing after auto-install:", ", ".join(still_missing))
            print(f"Please run manually and check for errors:")
            print(f"    {sys.executable} -m pip install -r requirements.txt")
            print("=" * 60)
            sys.exit(1)
        print("[Auto-install OK] All required packages are now installed.")


_check_dependencies()

import http.client
import email.utils
import time

import dns.resolver
from pyrogram import idle

from VideoEncoder import app
from VideoEncoder.core.cfg import cfg
from VideoEncoder.core.health import start_health_server
from VideoEncoder.core.log import log

# Force a public DNS resolver -- avoids DNS issues on some VPS setups.
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8']


def sync_bot_time():
    try:
        conn = http.client.HTTPConnection("google.com", timeout=5)
        conn.request("GET", "/")
        r = conn.getresponse()
        ts = r.getheader("date")
        if ts:
            remote_time = email.utils.mktime_tz(email.utils.parsedate_tz(ts))
            offset = int(remote_time - time.time())
            if abs(offset) > 2:
                log.inf("time_sync", offset=f"{offset}s", status="applied")
                return offset
    except Exception as e:
        log.err("time_sync_failed", error=str(e))
    return 0


async def _push_commands():
    """Push the in-menu command list to BotFather on startup.

    Best-effort: if the push fails (network hiccup, Telegram throttling)
    the bot still runs fine -- the commands just don't show up in the
    menu until the next restart.
    """
    from VideoEncoder.utils.bot_commands import get_public_commands, get_sudo_commands
    from pyrogram.types import BotCommandScopeChat, BotCommandScopeDefault

    owner_ids = cfg.OWNER_ID or []

    await app.set_bot_commands(get_public_commands(), scope=BotCommandScopeDefault())

    for oid in owner_ids:
        try:
            await app.set_bot_commands(
                get_public_commands() + get_sudo_commands(),
                scope=BotCommandScopeChat(chat_id=oid)
            )
        except Exception as e:
            log.err("owner_scope_commands_failed", owner=oid, error=str(e))

    log.inf("bot_commands", status="pushed", owner_scopes=len(owner_ids))


async def main():
    # Satisfies Hugging Face Spaces' port requirement (see core/health.py) --
    # harmless no-op if you're not running on HF Spaces.
    try:
        start_health_server()
        log.inf("health_server", status="started", port=os.environ.get("PORT", 7860))
    except Exception as e:
        log.err("health_server_failed", error=str(e))

    try:
        try:
            await app.start()
        except Exception as e:
            if "[16]" in str(e):
                offset = sync_bot_time()
                if hasattr(app, "session") and app.session:
                    app.session.offset = offset
                    log.inf("time_correction", status="applied", offset=f"{offset}s")
                    await app.start()
                else:
                    raise e
            else:
                raise e

        log.inf("bot", status="started", username=(await app.get_me()).username)

        try:
            await _push_commands()
        except Exception as e:
            log.err("bot_commands_push_failed", error=str(e))

        if cfg.LOG_CHANNEL:
            try:
                await app.send_message(
                    cfg.LOG_CHANNEL,
                    f"▸ <b>VideoEncoder</b>\nStatus: ● Online\nBot: @{(await app.get_me()).username}"
                )
            except Exception as e:
                log.err("log_channel_startup_notify_failed", error=str(e))

        await idle()
    except Exception as e:
        import traceback
        traceback.print_exc()
        log.logger.exception(f"bot_fatal: {str(e)}")
    finally:
        if app.is_connected:
            await app.stop()
        log.inf("bot", status="stopped")


if __name__ == "__main__":
    app.loop.run_until_complete(main())
