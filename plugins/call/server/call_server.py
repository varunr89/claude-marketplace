"""Pipecat call server -- FastAPI app with Twilio integration."""
import asyncio
import json
import os
import sys
import wave
from contextlib import asynccontextmanager
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from call_state import CallState
from config import load_config, ConfigError
from twilio_handler import TwilioValidator

# --- Globals ---
call_state: CallState | None = None
twilio_client: TwilioClient | None = None
twilio_validator: TwilioValidator | None = None
config: dict = {}
active_call_sid: str | None = None
PUBLIC_URL: str = ""


# --- Request Models ---
class StartCallRequest(BaseModel):
    to: str
    voicemail_audio: str | None = None


class DTMFRequest(BaseModel):
    digits: str


class PlayRequest(BaseModel):
    file: str


class TransferRequest(BaseModel):
    to: str
    whisper: str = ""


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, twilio_client, twilio_validator, PUBLIC_URL
    config_path = os.environ.get("CALL_CONFIG_PATH", "")
    if not config_path:
        raise RuntimeError("CALL_CONFIG_PATH env var required")
    config = load_config(config_path)
    twilio_client = TwilioClient(
        config["twilio"]["account_sid"], config["twilio"]["auth_token"]
    )
    twilio_validator = TwilioValidator(config["twilio"]["auth_token"])
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "")
    yield


app = FastAPI(lifespan=lifespan)


# --- Health ---
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "call_active": call_state is not None and not call_state.is_terminal(),
    }


# --- Start Call ---
@app.post("/call/start")
async def start_call(req: StartCallRequest):
    global call_state, active_call_sid

    if call_state and not call_state.is_terminal():
        raise HTTPException(400, "A call is already active")

    call_state = CallState()
    call_state.transition("dialing")

    twiml_url = f"{PUBLIC_URL}/twiml"
    status_url = f"{PUBLIC_URL}/call/status"

    try:
        call = twilio_client.calls.create(
            to=req.to,
            from_=config["twilio"]["from_number"],
            url=twiml_url,
            method="POST",
            machine_detection="DetectMessageEnd",
            async_amd=True,
            async_amd_status_callback=f"{PUBLIC_URL}/call/amd",
            async_amd_status_callback_method="POST",
            status_callback=status_url,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
        )
        active_call_sid = call.sid
        call_state.add_event("call_started", {"call_sid": call.sid})
        return {"call_sid": call.sid, "status": "dialing"}
    except Exception as e:
        call_state.transition("failed", reason="error")
        call_state.add_event("error", {"message": str(e)})
        raise HTTPException(500, str(e))


# --- TwiML (Twilio calls this to get call instructions) ---
@app.post("/twiml")
async def get_twiml(request: Request):
    ws_url = PUBLIC_URL.replace("https://", "wss://").replace("http://", "ws://") + "/ws"

    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=ws_url)
    stream.parameter(name="voicemail_audio", value=os.environ.get("VOICEMAIL_AUDIO", ""))
    connect.append(stream)
    response.append(connect)
    response.pause(length=300)  # Keep call alive up to 5 min

    return HTMLResponse(content=str(response), media_type="application/xml")


# --- AMD Result Callback ---
@app.post("/call/amd")
async def amd_callback(request: Request):
    form_data = await request.form()
    amd_status = form_data.get("AnsweredBy", "unknown")

    if call_state:
        result = "machine" if "machine" in amd_status.lower() else "human"
        call_state.add_event("amd_result", {"result": result, "raw": amd_status})

        if call_state.state == "dialing" or call_state.state == "ringing":
            call_state.transition("answered" if "answered" not in call_state.history else call_state.state)

        if result == "machine" and call_state.state == "answered":
            call_state.transition("voicemail")

    return JSONResponse({"status": "ok"})


# --- Call Status Callback ---
@app.post("/call/status")
async def status_callback(request: Request):
    form_data = await request.form()
    status = form_data.get("CallStatus", "")

    if call_state:
        if status == "ringing" and call_state.state == "dialing":
            call_state.transition("ringing")
        elif status == "in-progress" and call_state.state == "ringing":
            call_state.transition("answered")
        elif status == "busy" and not call_state.is_terminal():
            if call_state.state in ("dialing", "ringing"):
                call_state.transition("completed", reason="busy")
            else:
                call_state.transition("failed", reason="busy")
        elif status == "no-answer" and not call_state.is_terminal():
            if call_state.state in ("dialing", "ringing"):
                call_state.transition("completed", reason="no_answer")
            else:
                call_state.transition("failed", reason="no_answer")
        elif status == "failed" and not call_state.is_terminal():
            call_state.transition("failed", reason="error")
        elif status == "completed" and not call_state.is_terminal():
            call_state.transition("completed", reason="call_ended")

        call_state.add_event("twilio_status", {"status": status})

    return JSONResponse({"status": "ok"})


# --- Events (Claude Code polls this) ---
@app.get("/call/events")
async def get_events(after: int = 0):
    if not call_state:
        return {"events": [], "state": None, "reason": None}
    return {
        "events": call_state.get_events(after=after),
        "state": call_state.state,
        "reason": call_state.reason,
    }


# --- DTMF (send touch tones via Twilio REST API) ---
@app.post("/call/dtmf")
async def send_dtmf(req: DTMFRequest):
    if not active_call_sid:
        raise HTTPException(400, "No active call")
    try:
        twilio_client.calls(active_call_sid).update(
            twiml=f'<Response><Play digits="{req.digits}"/><Pause length="300"/></Response>'
        )
        if call_state:
            call_state.add_event("dtmf_sent", {"digits": req.digits})
        return {"status": "sent", "digits": req.digits}
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Play Audio ---
@app.post("/call/play")
async def play_audio(req: PlayRequest):
    if not active_call_sid:
        raise HTTPException(400, "No active call")
    try:
        file_url = f"{PUBLIC_URL}/audio/{os.path.basename(req.file)}"
        twilio_client.calls(active_call_sid).update(
            twiml=f'<Response><Play>{file_url}</Play><Pause length="2"/><Hangup/></Response>'
        )
        if call_state:
            if call_state.state == "voicemail":
                call_state.transition("leaving_msg")
            call_state.add_event("playing_audio", {"file": req.file})
        return {"status": "playing"}
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Serve cached audio files ---
@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(plugin_root, "audio", filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "Audio file not found")
    return FileResponse(filepath, media_type="audio/wav")


# --- Warm Transfer ---
@app.post("/call/transfer")
async def warm_transfer(req: TransferRequest):
    if not active_call_sid:
        raise HTTPException(400, "No active call")
    try:
        whisper_url = f"{PUBLIC_URL}/whisper?msg={quote(req.whisper)}"
        from_num = config["twilio"]["from_number"]
        twiml = (
            '<Response>'
            '<Say>Please hold one moment while I connect you.</Say>'
            f'<Dial timeout="30" callerId="{from_num}">'
            f'<Number url="{whisper_url}">{req.to}</Number>'
            '</Dial>'
            '<Say>I apologize, I was unable to connect. I will call back. Goodbye.</Say>'
            '<Hangup/>'
            '</Response>'
        )
        twilio_client.calls(active_call_sid).update(twiml=twiml)
        if call_state:
            if call_state.state == "answered":
                call_state.transition("human")
            if call_state.state == "human":
                call_state.transition("transferring")
            call_state.add_event("transfer_initiated", {"to": req.to})
        return {"status": "transferring"}
    except Exception as e:
        raise HTTPException(500, str(e))


# --- Whisper (plays context to user before bridging) ---
@app.post("/whisper")
async def whisper(request: Request):
    msg = request.query_params.get("msg", "Incoming call")
    response = VoiceResponse()
    response.say(f"Connecting you now. Context: {msg}")
    response.pause(length=1)
    return HTMLResponse(content=str(response), media_type="application/xml")


# --- Hangup ---
@app.post("/call/hangup")
async def hangup():
    if active_call_sid:
        try:
            twilio_client.calls(active_call_sid).update(status="completed")
        except Exception:
            pass
    if call_state and not call_state.is_terminal():
        call_state.transition("completed", reason="hangup")
    return {"status": "hung_up"}


# --- WebSocket (Pipecat pipeline for real-time STT) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle Twilio Media Stream WebSocket for real-time STT."""
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.runner.utils import parse_telephony_websocket
    from pipecat.serializers.twilio import TwilioFrameSerializer
    from pipecat.services.openai.stt import OpenAISTTService
    from pipecat.transports.websocket.fastapi import (
        FastAPIWebsocketParams,
        FastAPIWebsocketTransport,
    )

    await websocket.accept()

    transport_type, call_data = await parse_telephony_websocket(websocket)

    serializer = TwilioFrameSerializer(
        stream_sid=call_data["stream_id"],
        call_sid=call_data.get("call_id"),
        account_sid=config["twilio"]["account_sid"],
        auth_token=config["twilio"]["auth_token"],
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    az = config["azure_openai"]
    stt = OpenAISTTService(
        api_key=az["api_key"],
        base_url=f"{az['endpoint']}/openai",
        settings=OpenAISTTService.Settings(model=az["stt_model"]),
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
        ),
    )

    # Forward transcription events to the call state event queue
    @stt.event_handler("on_transcription")
    async def on_transcription(service, text):
        if call_state and text.strip():
            call_state.add_event("transcript", {"text": text})

    @transport.event_handler("on_client_disconnected")
    async def on_disconnect(transport, client):
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)


# --- Main ---
if __name__ == "__main__":
    port = int(os.environ.get("PIPECAT_PORT", config.get("pipecat_port", 8765)))
    uvicorn.run(app, host="127.0.0.1", port=port)
