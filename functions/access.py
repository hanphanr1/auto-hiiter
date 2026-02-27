import os
import json

from aiogram.types import Message
from config import OWNER_ID, USERS_FILE


def _load_users() -> list:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _save_users(users: list):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)


def is_owner(user_id: int) -> bool:
    return OWNER_ID and user_id == OWNER_ID


def is_authorized(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    return user_id in _load_users()


def check_access(msg: Message) -> bool:
    if not msg.from_user:
        return False
    return is_authorized(msg.from_user.id)


def add_user(user_id: int) -> bool:
    users = _load_users()
    if user_id in users:
        return False
    users.append(user_id)
    _save_users(users)
    return True


def remove_user(user_id: int) -> bool:
    users = _load_users()
    if user_id not in users:
        return False
    users.remove(user_id)
    _save_users(users)
    return True


def get_all_users() -> list:
    return _load_users()
