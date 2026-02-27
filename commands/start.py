from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from functions.access import check_access, is_owner

router = Router()

ACCESS_DENIED = (
    "<blockquote><code>Access Denied</code></blockquote>\n\n"
    "<blockquote>「❃」 You are not authorized to use this bot\n"
    "「❃」 Contact admin to get access</blockquote>"
)


@router.message(Command("start"))
async def start_handler(msg: Message):
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return

    welcome = (
        "<blockquote><code>Victus Tools</code></blockquote>\n\n"
        "<blockquote>「❃」 Checkout Parser\n"
        "    • <code>/co url</code> - Parse Stripe Checkout\n"
        "    • <code>/co url cc|mm|yy|cvv</code> - Charge Card\n"
        "    • <code>/co url yes cc|mm|yy|cvv</code> - 3DS Bypass\n"
        "    • <code>/co url 424242</code> - BIN Auto Gen + Charge\n"
        "    • <code>/co url yes 424242</code> - BIN + 3DS Bypass</blockquote>\n\n"
        "<blockquote>「❃」 Proxy Manager\n"
        "    • <code>/addproxy proxy</code> - Add Proxy\n"
        "    • <code>/removeproxy proxy</code> - Remove Proxy\n"
        "    • <code>/proxy</code> - View Proxies\n"
        "    • <code>/proxy check</code> - Check Proxies</blockquote>\n\n"
        "<blockquote>「❃」 Supported URLs\n"
        "    • <code>checkout.stripe.com</code>\n"
        "    • <code>buy.stripe.com</code></blockquote>"
    )

    if is_owner(msg.from_user.id):
        welcome += (
            "\n\n<blockquote>「❃」 Admin\n"
            "    • <code>/adduser user_id</code> - Authorize user\n"
            "    • <code>/removeuser user_id</code> - Remove user\n"
            "    • <code>/users</code> - List authorized users</blockquote>"
        )

    await msg.answer(welcome, parse_mode=ParseMode.HTML)


@router.message(Command("help"))
async def help_handler(msg: Message):
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return

    help_text = (
        "<blockquote><code>Commands</code></blockquote>\n\n"
        "<blockquote>「❃」 <code>/start</code> - Show welcome message\n"
        "「❃」 <code>/help</code> - Show this help\n"
        "「❃」 <code>/co url</code> - Parse checkout info\n"
        "「❃」 <code>/co url cards</code> - Charge cards\n"
        "「❃」 <code>/co url yes/no cards</code> - 3DS bypass option\n"
        "「❃」 <code>/co url BIN</code> - Auto gen cards from BIN\n"
        "「❃」 <code>/co url yes/no BIN</code> - BIN + 3DS bypass</blockquote>\n\n"
        "<blockquote>「❃」 <code>/addproxy proxy</code> - Add proxy\n"
        "「❃」 <code>/removeproxy proxy</code> - Remove proxy\n"
        "「❃」 <code>/removeproxy all</code> - Remove all proxies\n"
        "「❃」 <code>/proxy</code> - View your proxies\n"
        "「❃」 <code>/proxy check</code> - Check proxy status</blockquote>\n\n"
        "<blockquote>「❃」 Card Format : <code>cc|mm|yy|cvv</code>\n"
        "「❃」 Example : <code>4242424242424242|12|25|123</code></blockquote>\n\n"
        "<blockquote>「❃」 Proxy Formats :\n"
        "    • <code>host:port:user:pass</code>\n"
        "    • <code>user:pass@host:port</code>\n"
        "    • <code>host:port</code></blockquote>"
    )

    if is_owner(msg.from_user.id):
        help_text += (
            "\n\n<blockquote>「❃」 Admin Commands :\n"
            "    • <code>/adduser user_id</code> - Authorize user\n"
            "    • <code>/removeuser user_id</code> - Remove user\n"
            "    • <code>/users</code> - List authorized users</blockquote>"
        )

    await msg.answer(help_text, parse_mode=ParseMode.HTML)
