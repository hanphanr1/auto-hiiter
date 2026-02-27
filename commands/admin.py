from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from functions.access import is_owner, add_user, remove_user, get_all_users

router = Router()

NOT_ADMIN = (
    "<blockquote><code>Access Denied</code></blockquote>\n\n"
    "<blockquote>「❃」 Only admin can use this command</blockquote>"
)


@router.message(Command("adduser"))
async def adduser_handler(msg: Message):
    if not is_owner(msg.from_user.id):
        await msg.answer(NOT_ADMIN, parse_mode=ParseMode.HTML)
        return

    args = msg.text.split(maxsplit=1)

    if len(args) < 2:
        await msg.answer(
            "<blockquote><code>Add User</code></blockquote>\n\n"
            "<blockquote>「❃」 Usage : <code>/adduser user_id</code>\n"
            "「❃」 Example : <code>/adduser 123456789</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        user_id = int(args[1].strip())
    except ValueError:
        await msg.answer(
            "<blockquote><code>Error</code></blockquote>\n\n"
            "<blockquote>「❃」 Detail : <code>Invalid user ID</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    if add_user(user_id):
        await msg.answer(
            "<blockquote><code>User Added</code></blockquote>\n\n"
            f"<blockquote>「❃」 User ID : <code>{user_id}</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.answer(
            "<blockquote><code>Already Exists</code></blockquote>\n\n"
            f"<blockquote>「❃」 User ID : <code>{user_id}</code> is already authorized</blockquote>",
            parse_mode=ParseMode.HTML,
        )


@router.message(Command("removeuser"))
async def removeuser_handler(msg: Message):
    if not is_owner(msg.from_user.id):
        await msg.answer(NOT_ADMIN, parse_mode=ParseMode.HTML)
        return

    args = msg.text.split(maxsplit=1)

    if len(args) < 2:
        await msg.answer(
            "<blockquote><code>Remove User</code></blockquote>\n\n"
            "<blockquote>「❃」 Usage : <code>/removeuser user_id</code>\n"
            "「❃」 Example : <code>/removeuser 123456789</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        user_id = int(args[1].strip())
    except ValueError:
        await msg.answer(
            "<blockquote><code>Error</code></blockquote>\n\n"
            "<blockquote>「❃」 Detail : <code>Invalid user ID</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    if remove_user(user_id):
        await msg.answer(
            "<blockquote><code>User Removed</code></blockquote>\n\n"
            f"<blockquote>「❃」 User ID : <code>{user_id}</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.answer(
            "<blockquote><code>Not Found</code></blockquote>\n\n"
            f"<blockquote>「❃」 User ID : <code>{user_id}</code> is not in the list</blockquote>",
            parse_mode=ParseMode.HTML,
        )


@router.message(Command("users"))
async def users_handler(msg: Message):
    if not is_owner(msg.from_user.id):
        await msg.answer(NOT_ADMIN, parse_mode=ParseMode.HTML)
        return

    users = get_all_users()

    if users:
        user_list = "\n".join([f"    • <code>{uid}</code>" for uid in users[:20]])
        if len(users) > 20:
            user_list += f"\n    • <code>... and {len(users) - 20} more</code>"
    else:
        user_list = "    • <code>None</code>"

    await msg.answer(
        "<blockquote><code>Authorized Users</code></blockquote>\n\n"
        f"<blockquote>「❃」 Users ({len(users)}) :\n{user_list}</blockquote>\n\n"
        "<blockquote>「❃」 Add : <code>/adduser user_id</code>\n"
        "「❃」 Remove : <code>/removeuser user_id</code></blockquote>",
        parse_mode=ParseMode.HTML,
    )
