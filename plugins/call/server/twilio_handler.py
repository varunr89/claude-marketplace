"""Twilio webhook signature validation."""
from twilio.request_validator import RequestValidator


class TwilioValidator:
    def __init__(self, auth_token: str):
        self.validator = RequestValidator(auth_token)

    def validate(self, url: str, params: dict, signature: str) -> bool:
        return self.validator.validate(url, params, signature)
