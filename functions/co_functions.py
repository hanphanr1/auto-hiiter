import re
import time
import json
import aiohttp
import base64
from urllib.parse import unquote, urlparse

HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://checkout.stripe.com",
    "referer": "https://checkout.stripe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

BROWSER_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

STRIPE_HOSTS = (
    "checkout.stripe.com",
    "buy.stripe.com",
    "donate.stripe.com",
    "invoice.stripe.com",
    "billing.stripe.com",
)

_co_session = None


async def _get_co_session():
    global _co_session
    if _co_session is None or _co_session.closed:
        _co_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
            timeout=aiohttp.ClientTimeout(total=25, connect=8),
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
        r'https?://checkout\.stripe\.com/pay/cs_[^\s\"\'\<\>\)]+',
        r'https?://checkout\.stripe\.com/[^\s\"\'\<\>\)]+',
        r'https?://buy\.stripe\.com/[^\s\"\'\<\>\)]+',
        r'https?://donate\.stripe\.com/[^\s\"\'\<\>\)]+',
        r'https?://invoice\.stripe\.com/[^\s\"\'\<\>\)]+',
        r'https?://billing\.stripe\.com/[^\s\"\'\<\>\)]+',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).rstrip('.,;:')
    return None


def _try_xor_decode(data: bytes, key: int) -> str:
    try:
        return ''.join(chr(b ^ key) for b in data)
    except Exception:
        return ""


def _b64_decode_safe(s: str) -> bytes:
    for func in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            return func(s)
        except Exception:
            pass
        try:
            padded = s + '=' * (-len(s) % 4)
            return func(padded)
        except Exception:
            pass
    return None


def decode_pk_from_url(url: str) -> dict:
    result = {"pk": None, "cs": None, "site": None}
    try:
        cs_match = re.search(r'cs_(live|test)_[A-Za-z0-9]+', url)
        if cs_match:
            result["cs"] = cs_match.group(0)

        if '#' not in url:
            return result

        hash_part = url.split('#', 1)[1]
        hash_decoded = unquote(hash_part)

        decoded_bytes = _b64_decode_safe(hash_decoded)
        if not decoded_bytes:
            return result

        for xor_key in (5, 0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 13, 42):
            xored = _try_xor_decode(decoded_bytes, xor_key)
            if not xored:
                continue

            pk_match = re.search(r'pk_(live|test)_[A-Za-z0-9]+', xored)
            if pk_match:
                result["pk"] = pk_match.group(0)

                site_match = re.search(r'https?://[^\s\"\'\<\>\x00-\x1f]+', xored)
                if site_match:
                    result["site"] = site_match.group(0)

                if not result["cs"]:
                    cs_in_hash = re.search(r'cs_(live|test)_[A-Za-z0-9]+', xored)
                    if cs_in_hash:
                        result["cs"] = cs_in_hash.group(0)
                break
    except Exception:
        pass
    return result


def _extract_pk_cs_from_html(html: str) -> dict:
    result = {"pk": None, "cs": None}

    pk_match = re.search(r'(pk_(live|test)_[A-Za-z0-9]{10,})', html)
    if pk_match:
        result["pk"] = pk_match.group(1)

    cs_match = re.search(r'(cs_(live|test)_[A-Za-z0-9]{10,})', html)
    if cs_match:
        result["cs"] = cs_match.group(1)

    if result["pk"] and result["cs"]:
        return result

    next_data_match = re.search(
        r'<script\s+id="__NEXT_DATA__"[^>]*>\s*(\{.*?\})\s*</script>',
        html, re.DOTALL,
    )
    if next_data_match:
        try:
            data = json.loads(next_data_match.group(1))
            _extract_from_json(data, result)
        except Exception:
            pass

    if result["pk"] and result["cs"]:
        return result

    for attr_name in ("publishable-key", "data-key", "data-publishable-key"):
        attr_match = re.search(
            rf'{attr_name}=["\']?(pk_(live|test)_[A-Za-z0-9]+)',
            html, re.IGNORECASE,
        )
        if attr_match:
            result["pk"] = attr_match.group(1)
            break

    return result


def _extract_from_json(data, result: dict, depth: int = 0):
    if depth > 15 or (result["pk"] and result["cs"]):
        return

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                if not result["pk"] and value.startswith("pk_") and len(value) > 20:
                    if re.match(r'pk_(live|test)_[A-Za-z0-9]+$', value):
                        result["pk"] = value
                elif not result["cs"] and value.startswith("cs_") and len(value) > 20:
                    if re.match(r'cs_(live|test)_[A-Za-z0-9]+$', value):
                        result["cs"] = value
            elif isinstance(value, (dict, list)):
                _extract_from_json(value, result, depth + 1)
            if result["pk"] and result["cs"]:
                return
    elif isinstance(data, list):
        for item in data:
            _extract_from_json(item, result, depth + 1)
            if result["pk"] and result["cs"]:
                return


def _extract_redirect_from_html(html: str) -> str:
    meta_match = re.search(
        r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*url=([^"\'>\s]+)',
        html, re.IGNORECASE,
    )
    if meta_match:
        url = meta_match.group(1).strip()
        if any(h in url for h in STRIPE_HOSTS):
            return url

    for pat in (
        r'(?:window\.location(?:\.href)?|location\.href)\s*=\s*["\']([^"\']+)',
        r'(?:window\.location\.replace|location\.replace)\s*\(\s*["\']([^"\']+)',
    ):
        js_match = re.search(pat, html, re.IGNORECASE)
        if js_match:
            url = js_match.group(1).strip()
            if any(h in url for h in STRIPE_HOSTS):
                return url

    return None


async def _fetch_stripe_page(url: str) -> tuple:
    try:
        s = await _get_co_session()
        async with s.get(
            url,
            headers=BROWSER_HEADERS,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=15, connect=8),
        ) as resp:
            final_url = str(resp.url)
            html = await resp.text()
            return final_url, html
    except Exception:
        return url, ""


async def _try_payment_link_api(pk: str, url: str, html: str) -> str:
    """For buy/donate pages: extract payment link data and try to create a checkout session."""
    try:
        parsed = urlparse(url)
        path_slug = parsed.path.strip("/")
        if not path_slug:
            return None

        s = await _get_co_session()

        body = f"key={pk}&eid=NA&browser_locale=en-US&redirect_type=url"
        async with s.post(
            f"https://api.stripe.com/v1/payment_pages/{path_slug}/init",
            headers=HEADERS,
            data=body,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            data = await r.json()
            if "error" not in data:
                cs_match = re.search(r'cs_(live|test)_[A-Za-z0-9]+', json.dumps(data))
                if cs_match:
                    return cs_match.group(0)
    except Exception:
        pass

    try:
        plink_match = re.search(r'(plink_(live|test)_[A-Za-z0-9]+)', html)
        if plink_match:
            plink_id = plink_match.group(1)
            s = await _get_co_session()
            body = f"key={pk}&eid=NA&browser_locale=en-US&redirect_type=url"
            async with s.post(
                f"https://api.stripe.com/v1/payment_pages/{plink_id}/init",
                headers=HEADERS,
                data=body,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                data = await r.json()
                if "error" not in data:
                    cs_match = re.search(r'cs_(live|test)_[A-Za-z0-9]+', json.dumps(data))
                    if cs_match:
                        return cs_match.group(0)
    except Exception:
        pass

    return None


async def resolve_stripe_url(url: str) -> dict:
    """
    Multi-step resolver for any Stripe URL.
    Returns dict with pk, cs, site, init_data (if available).
    """
    result = {"pk": None, "cs": None, "site": None, "init_data": None}

    decoded = decode_pk_from_url(url)
    result["pk"] = decoded.get("pk")
    result["cs"] = decoded.get("cs")

    if result["pk"] and result["cs"]:
        return result

    final_url, html = await _fetch_stripe_page(url)

    if final_url != url:
        redir_decoded = decode_pk_from_url(final_url)
        if redir_decoded.get("pk") and not result["pk"]:
            result["pk"] = redir_decoded["pk"]
        if redir_decoded.get("cs") and not result["cs"]:
            result["cs"] = redir_decoded["cs"]
        if not redir_decoded.get("site") and decoded.get("site"):
            pass
        elif redir_decoded.get("site"):
            result["site"] = redir_decoded["site"]

    if result["pk"] and result["cs"]:
        return result

    if html:
        html_data = _extract_pk_cs_from_html(html)
        if html_data.get("pk") and not result["pk"]:
            result["pk"] = html_data["pk"]
        if html_data.get("cs") and not result["cs"]:
            result["cs"] = html_data["cs"]

    if result["pk"] and result["cs"]:
        return result

    if html and (not result["pk"] or not result["cs"]):
        js_redir = _extract_redirect_from_html(html)
        if js_redir:
            redir_decoded2 = decode_pk_from_url(js_redir)
            if redir_decoded2.get("pk") and not result["pk"]:
                result["pk"] = redir_decoded2["pk"]
            if redir_decoded2.get("cs") and not result["cs"]:
                result["cs"] = redir_decoded2["cs"]

            if not result["pk"] or not result["cs"]:
                final_url2, html2 = await _fetch_stripe_page(js_redir)
                if final_url2 != js_redir:
                    rd3 = decode_pk_from_url(final_url2)
                    if rd3.get("pk") and not result["pk"]:
                        result["pk"] = rd3["pk"]
                    if rd3.get("cs") and not result["cs"]:
                        result["cs"] = rd3["cs"]
                if html2 and (not result["pk"] or not result["cs"]):
                    h2 = _extract_pk_cs_from_html(html2)
                    if h2.get("pk") and not result["pk"]:
                        result["pk"] = h2["pk"]
                    if h2.get("cs") and not result["cs"]:
                        result["cs"] = h2["cs"]

    if result["pk"] and result["cs"]:
        return result

    parsed = urlparse(url)
    is_payment_link = parsed.hostname in ("buy.stripe.com", "donate.stripe.com")

    if result["pk"] and not result["cs"] and is_payment_link:
        cs = await _try_payment_link_api(result["pk"], url, html or "")
        if cs:
            result["cs"] = cs

    if not result["pk"] and result["cs"]:
        for prefix in ("pk_live_", "pk_test_"):
            pk_match = re.search(rf'{prefix}[A-Za-z0-9]+', (html or "") + url + final_url)
            if pk_match:
                result["pk"] = pk_match.group(0)
                break

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
        resolved = await resolve_stripe_url(url)
        result["pk"] = resolved.get("pk")
        result["cs"] = resolved.get("cs")

        if resolved.get("init_data"):
            result["init_data"] = resolved["init_data"]
            _parse_init_data(result, resolved["init_data"])
        elif result["pk"] and result["cs"]:
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
                _parse_init_data(result, init_data)
            else:
                result["error"] = init_data.get("error", {}).get("message", "Init failed")
        else:
            missing = []
            if not result["pk"]:
                missing.append("PK")
            if not result["cs"]:
                missing.append("CS")
            result["error"] = f"Could not extract {'/'.join(missing)} from URL"
    except Exception as e:
        result["error"] = str(e)

    result["time"] = round(time.perf_counter() - start, 2)
    return result


def _parse_init_data(result: dict, init_data: dict):
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
    else:
        pi = init_data.get("payment_intent") or {}
        if pi.get("amount"):
            result["price"] = pi["amount"] / 100
            result["currency"] = (pi.get("currency") or "").upper()

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
