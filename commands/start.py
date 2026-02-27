from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from functions.access import check_access

router = Router()

ACCESS_DENIED = (
    "<blockquote><code>Access Denied</code></blockquote>\n\n"
    "<blockquote>「❃」 Join to use : <code>@proscraperbot</code></blockquote>"
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
        "    • <code>/co url yes cc|mm|yy|cvv</code> - 3DS Bypass</blockquote>\n\n"
        "<blockquote>「❃」 Proxy Manager\n"
        "    • <code>/addproxy proxy</code> - Add Proxy\n"
        "    • <code>/removeproxy proxy</code> - Remove Proxy\n"
        "    • <code>/proxy</code> - View Proxies\n"
        "    • <code>/proxy check</code> - Check Proxies</blockquote>\n\n"
        "<blockquote>「❃」 Supported URLs\n"
        "    • <code>checkout.stripe.com</code>\n"
        "    • <code>buy.stripe.com</code></blockquote>\n\n"
        "<blockquote>「❃」 Contact : <code>@victus_xd</code></blockquote>"
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
        "「❃」 <code>/co url yes/no cards</code> - 3DS bypass option</blockquote>\n\n"
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
    await msg.answer(help_text, parse_mode=ParseMode.HTML)
