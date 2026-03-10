from typing import Optional

# Мобільні коди України у форматі 380XX...
VALID_UA_MOBILE_CODES = {
    "39", "50", "63", "66", "67", "68", "73", "91", "92", "93", "94", "95", "96", "97", "98", "99"
}


def normalize_phone(phone_input: str) -> str:
    return "".join(phone_input.split()).lstrip("+")


def validate_phone(phone: str) -> Optional[str]:
    if not phone.startswith("380") or len(phone) != 12 or not phone.isdigit():
        return "Номер у форматі 380971234567 або +380971234567"

    operator_code = phone[3:5]
    if operator_code not in VALID_UA_MOBILE_CODES:
        return "Номер має містити валідний мобільний код оператора України"

    return None
