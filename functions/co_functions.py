import re
import time
import aiohttp
import base64
from urllib.parse import unquote

HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://checkout.stripe.com",
    "referer": "https://checkout.stripe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

_co_session = None


async def _get_co_session():
    global _co_session
    if _co_session is None or _co_session.closed:
        _co_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
            timeout=aiohttp.ClientTimeout(total=20, connect=5),
        )
    return _co_session


def get_currency_symbol(currency: str) -> str:
    symbols = {
        "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥",
        "CNY": "¥", "KRW": "₩", "RUB": "₽", "BRL": "R$", "CAD": "C$",
        "AUD": "A$", "MXN": "MX$", "SGD": "S$", "HKD": "HK$", "THB": "฿",
        "VND": "₫", "PHP": "₱", "IDR": "Rp", "MYR": "RM", "ZAR": "R",
        "CHF": "CHF", "SEK": "kr", "NOK": "kr", "DKK": "kr", "PLN": "zł",
        "TRY": "₺", "AED": "د.إ", "SAR": "﷼", "ILS": "₪", "TWD": "NT$",
    }
    return symbols.get(currency, "")


def extract_checkout_url(text: str) -> str:
    patterns = [
        r'https?://checkout\.stripe\.com/c/pay/cs_[^\s\"\'\<\>\)]+',
        r'https?://checkout\.stripe\.com/[^\s\"\'\<\>\)]+',
        r'https?://buy\.stripe\.com/[^\s\"\'\<\>\)]+',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).rstrip('.,;:')
    return None


def decode_pk_from_url(url: str) -> dict:
    result = {"pk": None, "cs": None, "site": None}
    try:
        cs_match = re.search(r'cs_(live|test)_[A-Za-z0-9]+', url)
        if cs_match:
            result["cs"] = cs_match.group(0)

        if '#' not in url:
            return result

        hash_part = url.split('#')[1]
        hash_decoded = unquote(hash_part)

        try:
            decoded_bytes = base64.b64decode(hash_decoded)
            xored = ''.join(chr(b ^ 5) for b in decoded_bytes)

            pk_match = re.search(r'pk_(live|test)_[A-Za-z0-9]+', xored)
            if pk_match:
                result["pk"] = pk_match.group(0)

            site_match = re.search(r'https?://[^\s\"\'\<\>]+', xored)
            if site_match:
                result["site"] = site_match.group(0)
        except Exception:
            pass
    except Exception:
        pass
    return result


async def get_checkout_info(url: str) -> dict:
    start = time.perf_counter()
    result = {
        "url": url,
        "pk": None,
        "cs": None,
        "merchant": None,
        "price": None,
        "currency": None,
        "product": None,
        "country": None,
        "mode": None,
        "customer_name": None,
        "customer_email": None,
        "support_email": None,
        "support_phone": None,
        "cards_accepted": None,
        "success_url": None,
        "cancel_url": None,
        "init_data": None,
        "error": None,
        "time": 0,
    }

    try:
        decoded = decode_pk_from_url(url)
        result["pk"] = decoded.get("pk")
        result["cs"] = decoded.get("cs")

        if result["pk"] and result["cs"]:
            s = await _get_co_session()
            body = f"key={result['pk']}&eid=NA&browser_locale=en-US&redirect_type=url"

            async with s.post(
                f"https://api.stripe.com/v1/payment_pages/{result['cs']}/init",
                headers=HEADERS,
                data=body,
            ) as r:
                init_data = await r.json()

            if "error" not in init_data:
                result["init_data"] = init_data

                acc = init_data.get("account_settings", {})
                result["merchant"] = acc.get("display_name") or acc.get("business_name")
                result["support_email"] = acc.get("support_email")
                result["support_phone"] = acc.get("support_phone")
                result["country"] = acc.get("country")

                lig = init_data.get("line_item_group")
                inv = init_data.get("invoice")
                if lig:
                    result["price"] = lig.get("total", 0) / 100
                    result["currency"] = lig.get("currency", "").upper()
                    if lig.get("line_items"):
                        items = lig["line_items"]
                        currency = lig.get("currency", "").upper()
                        sym = get_currency_symbol(currency)
                        product_parts = []
                        for item in items:
                            qty = item.get("quantity", 1)
                            name = item.get("name", "Product")
                            amt = item.get("amount", 0) / 100
                            interval = item.get("recurring_interval")
                            if interval:
                                product_parts.append(
                                    f"{qty} x {name} (at {sym}{amt:.2f} / {interval})"
                                )
                            else:
                                product_parts.append(f"{qty} x {name} ({sym}{amt:.2f})")
                        result["product"] = ", ".join(product_parts)
                elif inv:
                    result["price"] = inv.get("total", 0) / 100
                    result["currency"] = inv.get("currency", "").upper()

                mode = init_data.get("mode", "")
                if mode:
                    result["mode"] = mode.upper()
                elif init_data.get("subscription"):
                    result["mode"] = "SUBSCRIPTION"
                else:
                    result["mode"] = "PAYMENT"

                cust = init_data.get("customer") or {}
                result["customer_name"] = cust.get("name")
                result["customer_email"] = (
                    init_data.get("customer_email") or cust.get("email")
                )

                pm_types = init_data.get("payment_method_types") or []
                if pm_types:
                    cards = [t.upper() for t in pm_types if t != "card"]
                    if "card" in pm_types:
                        cards.insert(0, "CARD")
                    result["cards_accepted"] = ", ".join(cards) if cards else "CARD"

                result["success_url"] = init_data.get("success_url")
                result["cancel_url"] = init_data.get("cancel_url")
            else:
                result["error"] = init_data.get("error", {}).get("message", "Init failed")
        else:
            result["error"] = "Could not decode PK/CS from URL"
    except Exception as e:
        result["error"] = str(e)

    result["time"] = round(time.perf_counter() - start, 2)
    return result


async def check_checkout_active(pk: str, cs: str) -> bool:
    try:
        s = await _get_co_session()
        body = f"key={pk}&eid=NA&browser_locale=en-US&redirect_type=url"
        async with s.post(
            f"https://api.stripe.com/v1/payment_pages/{cs}/init",
            headers=HEADERS,
            data=body,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as r:
            data = await r.json()
            return "error" not in data
    except Exception:
        return False
