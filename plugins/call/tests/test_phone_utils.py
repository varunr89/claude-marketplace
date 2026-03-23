import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from phone_utils import normalize_phone, redact_phone

def test_ten_digit():
    assert normalize_phone("3606765437") == "+13606765437"

def test_with_country_code():
    assert normalize_phone("+13606765437") == "+13606765437"

def test_with_parens():
    assert normalize_phone("(360) 676-5437") == "+13606765437"

def test_with_dashes():
    assert normalize_phone("360-676-5437") == "+13606765437"

def test_eleven_digit():
    assert normalize_phone("13606765437") == "+13606765437"

def test_invalid_short():
    try:
        normalize_phone("12345")
        assert False, "Should have raised"
    except ValueError:
        pass

def test_redact():
    assert redact_phone("+13606765437") == "(360) ***-5437"

def test_redact_filename():
    assert redact_phone("+13606765437", for_filename=True) == "xxxx5437"
