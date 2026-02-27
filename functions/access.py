from aiogram.types import Message
from config import ALLOWED_GROUP, OWNER_ID


def check_access(msg: Message) -> bool:
    if ALLOWED_GROUP and msg.chat.id == ALLOWED_GROUP:
        return True
    if msg.chat.type == "private" and OWNER_ID and msg.from_user.id == OWNER_ID:
        return True
    return False
