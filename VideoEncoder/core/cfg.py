import time

# All values come from config.py at the project root now -- no .env /
# config.env / dotenv needed. config.py sits next to bot.py; since bot.py
# is what you actually run, its directory is on sys.path automatically,
# so this plain "import config" works.
import config


def _split_ids(value):
    """Space-separated ids -> list[int]. Tolerates blanks/garbage safely."""
    if not value:
        return []
    return list(set(int(x) for x in str(value).split() if str(x).strip().lstrip('-').isdigit()))


class Config:
    def __init__(self):
        self.BOT_START_TIME = time.time()

        self.API_ID = int(config.API_ID)
        self.API_HASH = config.API_HASH
        self.BOT_TOKEN = config.BOT_TOKEN

        self.MONGO_URI = config.MONGO_URI
        self.SESSION_NAME = config.SESSION_NAME

        self.DRIVE_DIR = config.DRIVE_DIR
        self.INDEX_URL = config.INDEX_URL

        self.DOWNLOAD_DIR = config.DOWNLOAD_DIR
        self.ENCODE_DIR = config.ENCODE_DIR

        self.OWNER_ID = _split_ids(config.OWNER_ID)
        self.SUDO_USERS = _split_ids(config.SUDO_USERS)
        self.EVERYONE_CHATS = _split_ids(config.EVERYONE_CHATS)
        self.ALL_SUDOers = self.EVERYONE_CHATS + self.SUDO_USERS + self.OWNER_ID

        try:
            self.LOG_CHANNEL = int(config.LOG_CHANNEL)
        except (ValueError, TypeError):
            self.LOG_CHANNEL = self.OWNER_ID[0] if self.OWNER_ID else 0

        # Real VPS allocation -- used for resource-safe encoding and status.
        try:
            self.VPS_RAM_MB = int(getattr(config, "VPS_RAM_MB", 1024))
        except (ValueError, TypeError):
            self.VPS_RAM_MB = 1024
        try:
            self.VPS_CORES = int(getattr(config, "VPS_CORES", 2))
        except (ValueError, TypeError):
            self.VPS_CORES = 2

        self.VIDEO_MIMETYPES = [
            "video/x-flv", "video/mp4", "application/x-mpegURL", "video/MP2T",
            "video/3gpp", "video/quicktime", "video/x-msvideo", "video/x-ms-wmv",
            "video/x-matroska", "video/webm", "video/x-m4v", "video/mpeg"
        ]

        self.PROGRESS = """
• {0} of {1}
• Speed: {2}
• ETA: {3}
"""

cfg = Config()
