import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from call_state import CallState, InvalidTransition

def test_initial_state():
    cs = CallState()
    assert cs.state == "requested"

def test_valid_transition():
    cs = CallState()
    cs.transition("dialing")
    assert cs.state == "dialing"

def test_invalid_transition():
    cs = CallState()
    try:
        cs.transition("completed")
        assert False
    except InvalidTransition:
        pass

def test_full_voicemail_flow():
    cs = CallState()
    cs.transition("dialing")
    cs.transition("ringing")
    cs.transition("answered")
    cs.transition("voicemail")
    cs.transition("leaving_msg")
    cs.transition("completed", reason="voicemail_left")
    assert cs.state == "completed"
    assert cs.reason == "voicemail_left"
    assert cs.is_terminal()

def test_full_human_flow():
    cs = CallState()
    cs.transition("dialing")
    cs.transition("ringing")
    cs.transition("answered")
    cs.transition("human")
    cs.transition("transferring")
    cs.transition("completed", reason="transferred")
    assert cs.state == "completed"
    assert cs.reason == "transferred"

def test_ivr_flow():
    cs = CallState()
    cs.transition("dialing")
    cs.transition("ringing")
    cs.transition("answered")
    cs.transition("ivr_nav")
    cs.transition("navigating")
    cs.transition("human")
    cs.transition("transferring")
    cs.transition("completed", reason="transferred")
    assert cs.is_terminal()

def test_event_queue():
    cs = CallState()
    cs.add_event("amd_result", {"result": "human"})
    cs.add_event("transcript", {"text": "Press 1 for enrollment"})
    events = cs.get_events(after=0)
    assert len(events) == 2
    assert events[0]["event"] == "amd_result"

def test_event_cursor():
    cs = CallState()
    cs.add_event("amd_result", {"result": "human"})
    cs.add_event("transcript", {"text": "Hello"})
    events = cs.get_events(after=1)
    assert len(events) == 1
    assert events[0]["event"] == "transcript"

def test_state_history():
    cs = CallState()
    cs.transition("dialing")
    cs.transition("ringing")
    assert cs.history == ["requested", "dialing", "ringing"]

def test_failed_state():
    cs = CallState()
    cs.transition("failed", reason="error")
    assert cs.is_terminal()
    assert cs.reason == "error"

def test_no_transition_from_terminal():
    cs = CallState()
    cs.transition("failed", reason="error")
    try:
        cs.transition("dialing")
        assert False
    except InvalidTransition:
        pass
