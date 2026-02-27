import random
from datetime import datetime


def luhn_checksum(card_number: str) -> int:
    digits = [int(d) for d in card_number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10


def generate_luhn_card(prefix: str, length: int = 16) -> str:
    remaining = length - len(prefix) - 1
    body = prefix + ''.join([str(random.randint(0, 9)) for _ in range(remaining)])
    for check in range(10):
        candidate = body + str(check)
        if luhn_checksum(candidate) == 0:
            return candidate
    return body + '0'


def is_amex(bin_str: str) -> bool:
    return bin_str.startswith('34') or bin_str.startswith('37')


def detect_bin(text: str) -> str:
    text = text.strip()
    if text.isdigit() and 6 <= len(text) <= 16:
        if '|' not in text and '/' not in text:
            return text
    return None


def generate_card_from_bin(bin_str: str) -> dict:
    amex = is_amex(bin_str)
    card_length = 15 if amex else 16
    cc = generate_luhn_card(bin_str, card_length)

    now = datetime.now()
    year = random.randint(now.year + 1, now.year + 5)
    month = random.randint(1, 12)

    cvv_length = 4 if amex else 3
    cvv = ''.join([str(random.randint(0, 9)) for _ in range(cvv_length)])

    return {
        "cc": cc,
        "month": str(month).zfill(2),
        "year": str(year)[2:],
        "cvv": cvv,
    }


def generate_cards_from_bin(bin_str: str, count: int = 50) -> list:
    cards = []
    seen = set()
    attempts = 0
    max_attempts = count * 3

    while len(cards) < count and attempts < max_attempts:
        attempts += 1
        card = generate_card_from_bin(bin_str)
        if card["cc"] not in seen:
            seen.add(card["cc"])
            cards.append(card)

    return cards
