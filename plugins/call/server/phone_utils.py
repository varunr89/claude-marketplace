import re

def normalize_phone(number: str) -> str:
    digits = re.sub(r'[^\d+]', '', number)
    if digits.startswith('+'):
        if len(digits) == 12 and digits.startswith('+1'):
            return digits
        raise ValueError(f"Unsupported country code: {digits}")
    if len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    raise ValueError(f"Invalid phone number: {number} ({len(digits)} digits)")

def redact_phone(e164: str, for_filename: bool = False) -> str:
    if for_filename:
        return f"xxxx{e164[-4:]}"
    area = e164[2:5]
    last4 = e164[-4:]
    return f"({area}) ***-{last4}"
