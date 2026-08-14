"""
============================================================
 ENCODING BOT -- CONFIG (permanent, hardcoded values)
============================================================
No .env / config.env is used anymore. Just fill in the values
below directly and run the bot with:

    python3 bot.py

Every value below is already filled in with what was previously
in VideoEncoder/core/cfg.py -- nothing was changed, just moved
here so it's all in one obvious place.
============================================================
"""

# ------------------------------------------------------------
# 1) Telegram API credentials
#    Get API_ID + API_HASH from: https://my.telegram.org
#    Get BOT_TOKEN from @BotFather on Telegram
# ------------------------------------------------------------
API_ID = 25976192
API_HASH = "8ba23141980539b4896e5adbc4ffd2e2"
BOT_TOKEN = "8381237934:AAGFH3iqNOuoYCHsebMAycYrhaTwEKoRMpw"


# ------------------------------------------------------------
# 2) Database
#    MongoDB connection string (from cloud.mongodb.com)
# ------------------------------------------------------------
MONGO_URI = "mongodb+srv://RAHAT1132:RAHAT11a@rahat.txn4lkk.mongodb.net/?appName=Rahat"

# Just a label used for the Pyrogram session file name.
SESSION_NAME = "RsEncoder"


# ------------------------------------------------------------
# 3) Admin / access control
#    OWNER_ID / SUDO_USERS / EVERYONE_CHATS -- space separated for
#    multiple ids. EVERYONE_CHATS is your authorized group's chat id.
# ------------------------------------------------------------
OWNER_ID = "6621572366"
SUDO_USERS = "6621572366"
EVERYONE_CHATS = "-1004366562744"

# Log channel -- where startup/new-user notices get posted.
LOG_CHANNEL = "-1003945380422"


# ------------------------------------------------------------
# 4) Local folders
#    These are just local directory paths used to store files while
#    downloading/encoding. They'll be created automatically if they
#    don't exist.
# ------------------------------------------------------------
DOWNLOAD_DIR = "VideoEncoder/downloads/"
ENCODE_DIR = "VideoEncoder/encodes/"


# ------------------------------------------------------------
# 5) Optional: Google Drive upload
#    Leave blank unless you use the Drive upload feature.
# ------------------------------------------------------------
DRIVE_DIR = ""
INDEX_URL = ""


# ------------------------------------------------------------
# 6) Your VPS's real resource allocation
#    Used to keep the bot's own resource usage inside these limits
#    and to show accurate status. Update if your allocation changes.
# ------------------------------------------------------------
VPS_RAM_MB = 1024
VPS_CORES = 2
