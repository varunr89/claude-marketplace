import json
import os

class ConfigError(Exception):
    pass

REQUIRED_KEYS = {
    "twilio": ["account_sid", "auth_token", "from_number"],
    "azure_openai": ["endpoint", "api_key", "tts_model", "tts_voice", "stt_model"],
}

def load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise ConfigError(
            f"Config not found at {path}.\n"
            "Run the setup script first:\n"
            "  bash ~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/scripts/setup.sh"
        )
    with open(path) as f:
        cfg = json.load(f)
    validate_config(cfg)
    return cfg

def validate_config(cfg: dict) -> None:
    for section, keys in REQUIRED_KEYS.items():
        if section not in cfg:
            raise ConfigError(f"Missing config section: {section}")
        for key in keys:
            if key not in cfg[section] or not cfg[section][key]:
                raise ConfigError(f"Missing config key: {section}.{key}")
    if "transfer_to" not in cfg or not cfg["transfer_to"]:
        raise ConfigError("Missing config key: transfer_to")
    # Need either ngrok_auth_token or public_url (e.g., Tailscale Funnel)
    has_ngrok = cfg.get("ngrok_auth_token")
    has_public_url = cfg.get("public_url")
    if not has_ngrok and not has_public_url:
        raise ConfigError("Missing config key: ngrok_auth_token or public_url")
