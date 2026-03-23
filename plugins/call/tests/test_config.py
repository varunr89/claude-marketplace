import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from config import load_config, validate_config, ConfigError

def test_missing_file():
    try:
        load_config("/nonexistent/config.json")
        assert False
    except ConfigError as e:
        assert "not found" in str(e).lower()

def test_valid_config():
    cfg = {
        "twilio": {"account_sid": "AC123", "auth_token": "tok", "from_number": "+11234567890"},
        "azure_openai": {"endpoint": "https://x.openai.azure.com", "api_key": "k", "tts_model": "tts-hd", "tts_voice": "onyx", "stt_model": "gpt-4o-mini-transcribe"},
        "transfer_to": "+16083207152",
        "ngrok_auth_token": "ngrok_tok",
        "pipecat_port": 8765
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(cfg, f)
        f.flush()
        result = load_config(f.name)
        assert result["twilio"]["account_sid"] == "AC123"
    os.unlink(f.name)

def test_missing_twilio_key():
    cfg = {"twilio": {"account_sid": "AC123"}, "azure_openai": {}, "transfer_to": "", "ngrok_auth_token": "", "pipecat_port": 8765}
    try:
        validate_config(cfg)
        assert False
    except ConfigError as e:
        assert "auth_token" in str(e)
