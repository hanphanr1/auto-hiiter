from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from functions.access import check_access
from functions.proxy_utils import (
    get_user_proxies,
    add_user_proxy,
    remove_user_proxy,
    check_proxies_batch,
)

router = Router()

ACCESS_DENIED = (
    "<blockquote><code>Access Denied</code></blockquote>\n\n"
    "<blockquote>「❃」 Join to use : <code>@proscraperbot</code></blockquote>"
)


@router.message(Command("addproxy"))
async def addproxy_handler(msg: Message):
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return

    args = msg.text.split(maxsplit=1)
    user_id = msg.from_user.id
    user_proxies = get_user_proxies(user_id)

    if len(args) < 2:
        if user_proxies:
            proxy_list = "\n".join([f"    • <code>{p}</code>" for p in user_proxies[:10]])
            if len(user_proxies) > 10:
                proxy_list += f"\n    • <code>... and {len(user_proxies) - 10} more</code>"
        else:
            proxy_list = "    • <code>None</code>"

        await msg.answer(
            "<blockquote><code>Proxy Manager</code></blockquote>\n\n"
            f"<blockquote>「❃」 Your Proxies ({len(user_proxies)}) :\n{proxy_list}</blockquote>\n\n"
            "<blockquote>「❃」 Add : <code>/addproxy proxy</code>\n"
            "「❃」 Remove : <code>/removeproxy proxy</code>\n"
            "「❃」 Remove All : <code>/removeproxy all</code>\n"
            "「❃」 Check : <code>/proxy check</code></blockquote>\n\n"
            "<blockquote>「❃」 Formats :\n"
            "    • <code>host:port:user:pass</code>\n"
            "    • <code>user:pass@host:port</code>\n"
            "    • <code>host:port</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    proxy_input = args[1].strip()
    proxies_to_add = [p.strip() for p in proxy_input.split('\n') if p.strip()]

    if not proxies_to_add:
        await msg.answer(
            "<blockquote><code>Error</code></blockquote>\n\n"
            "<blockquote>「❃」 Detail : <code>No valid proxies provided</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    checking_msg = await msg.answer(
        "<blockquote><code>Checking Proxies ...</code></blockquote>\n\n"
        f"<blockquote>「❃」 Total : <code>{len(proxies_to_add)}</code>\n"
        "「❃」 Threads : <code>10</code></blockquote>",
        parse_mode=ParseMode.HTML,
    )

    results = await check_proxies_batch(proxies_to_add, max_threads=10)

    alive_proxies = []
    dead_proxies = []

    for r in results:
        if r["status"] == "alive":
            alive_proxies.append(r)
            add_user_proxy(user_id, r["proxy"])
        else:
            dead_proxies.append(r)

    response = f"<blockquote><code>Proxy Check Complete</code></blockquote>\n\n"
    response += f"<blockquote>「❃」 Alive : <code>{len(alive_proxies)}/{len(proxies_to_add)}</code>\n"
    response += f"「❃」 Dead : <code>{len(dead_proxies)}/{len(proxies_to_add)}</code></blockquote>\n\n"

    if alive_proxies:
        response += "<blockquote>「❃」 Added :\n"
        for p in alive_proxies[:5]:
            response += f"    • <code>{p['proxy']}</code> ({p['response_time']})\n"
        if len(alive_proxies) > 5:
            response += f"    • <code>... and {len(alive_proxies) - 5} more</code>\n"
        response += "</blockquote>"

    await checking_msg.edit_text(response, parse_mode=ParseMode.HTML)


@router.message(Command("removeproxy"))
async def removeproxy_handler(msg: Message):
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return

    args = msg.text.split(maxsplit=1)
    user_id = msg.from_user.id

    if len(args) < 2:
        await msg.answer(
            "<blockquote><code>Remove Proxy</code></blockquote>\n\n"
            "<blockquote>「❃」 Usage : <code>/removeproxy proxy</code>\n"
            "「❃」 All : <code>/removeproxy all</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    proxy_input = args[1].strip()

    if proxy_input.lower() == "all":
        user_proxies = get_user_proxies(user_id)
        count = len(user_proxies)
        remove_user_proxy(user_id, "all")
        await msg.answer(
            "<blockquote><code>All Proxies Removed</code></blockquote>\n\n"
            f"<blockquote>「❃」 Removed : <code>{count} proxies</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    if remove_user_proxy(user_id, proxy_input):
        await msg.answer(
            "<blockquote><code>Proxy Removed</code></blockquote>\n\n"
            f"<blockquote>「❃」 Proxy : <code>{proxy_input}</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.answer(
            "<blockquote><code>Error</code></blockquote>\n\n"
            "<blockquote>「❃」 Detail : <code>Proxy not found</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )


@router.message(Command("proxy"))
async def proxy_handler(msg: Message):
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return

    args = msg.text.split(maxsplit=1)
    user_id = msg.from_user.id

    if len(args) < 2 or args[1].strip().lower() != "check":
        user_proxies = get_user_proxies(user_id)
        if user_proxies:
            proxy_list = "\n".join([f"    • <code>{p}</code>" for p in user_proxies[:10]])
            if len(user_proxies) > 10:
                proxy_list += f"\n    • <code>... and {len(user_proxies) - 10} more</code>"
        else:
            proxy_list = "    • <code>None</code>"

        await msg.answer(
            "<blockquote><code>Proxy Manager</code></blockquote>\n\n"
            f"<blockquote>「❃」 Your Proxies ({len(user_proxies)}) :\n{proxy_list}</blockquote>\n\n"
            "<blockquote>「❃」 Check All : <code>/proxy check</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    user_proxies = get_user_proxies(user_id)

    if not user_proxies:
        await msg.answer(
            "<blockquote><code>Error</code></blockquote>\n\n"
            "<blockquote>「❃」 Detail : <code>No proxies to check</code>\n"
            "「❃」 Add : <code>/addproxy proxy</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    checking_msg = await msg.answer(
        "<blockquote><code>Checking Proxies ...</code></blockquote>\n\n"
        f"<blockquote>「❃」 Total : <code>{len(user_proxies)}</code>\n"
        "「❃」 Threads : <code>10</code></blockquote>",
        parse_mode=ParseMode.HTML,
    )

    results = await check_proxies_batch(user_proxies, max_threads=10)

    alive = [r for r in results if r["status"] == "alive"]
    dead = [r for r in results if r["status"] == "dead"]

    response = f"<blockquote><code>Proxy Check Results</code></blockquote>\n\n"
    response += f"<blockquote>「❃」 Alive : <code>{len(alive)}/{len(user_proxies)}</code>\n"
    response += f"「❃」 Dead : <code>{len(dead)}/{len(user_proxies)}</code></blockquote>\n\n"

    if alive:
        response += "<blockquote>「❃」 Alive Proxies :\n"
        for p in alive[:5]:
            ip_display = p['external_ip'] or 'N/A'
            response += f"    • <code>{p['proxy']}</code>\n      IP: {ip_display} | {p['response_time']}\n"
        if len(alive) > 5:
            response += f"    • <code>... and {len(alive) - 5} more</code>\n"
        response += "</blockquote>\n\n"

    if dead:
        response += "<blockquote>「❃」 Dead Proxies :\n"
        for p in dead[:3]:
            error = p.get('error', 'Unknown')
            response += f"    • <code>{p['proxy']}</code> ({error})\n"
        if len(dead) > 3:
            response += f"    • <code>... and {len(dead) - 3} more</code>\n"
        response += "</blockquote>"

    await checking_msg.edit_text(response, parse_mode=ParseMode.HTML)
