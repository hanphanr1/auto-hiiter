import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", "8080"))

PROXY_FILE = os.environ.get("PROXY_FILE", "proxies.json")
USERS_FILE = os.environ.get("USERS_FILE", "users.json")
