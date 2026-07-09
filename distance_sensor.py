"""Read a simple Arduino distance sensor over USB serial.

The Arduino should print one distance number per line, for example:

    47.2
    52.8

If the Arduino is missing, pyserial is not installed, or the port is wrong,
SelfChat keeps running and returns a clear default state.  This keeps the
exhibition stable while hardware is being adjusted.
"""

from __future__ import annotations

import glob
import os
import re
import threading
import time

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover - pyserial may be missing on dev machines.
    serial = None


BAUD_RATE = int(os.environ.get("SELFCHAT_DISTANCE_BAUD", "9600"))
GOOD_MIN_CM = float(os.environ.get("SELFCHAT_CLEAR_MIN_CM", "50"))
GOOD_MAX_CM = float(os.environ.get("SELFCHAT_CLEAR_MAX_CM", "60"))
NEAR_FULL_BLUR_CM = float(os.environ.get("SELFCHAT_NEAR_BLUR_CM", "30"))
FAR_FULL_BLUR_CM = float(os.environ.get("SELFCHAT_FAR_BLUR_CM", "75"))
MAX_BLUR_PX = float(os.environ.get("SELFCHAT_MAX_BLUR_PX", "18"))

_number_pattern = re.compile(r"-?\d+(?:\.\d+)?")
_distance_label_pattern = re.compile(
    r"distance\s*:\s*(-?\d+(?:\.\d+)?)\s*cm",
    re.IGNORECASE,
)
_cm_pattern = re.compile(r"(-?\d+(?:\.\d+)?)\s*cm", re.IGNORECASE)
_lock = threading.Lock()
_thread_started = False
_state = {
    "enabled": False,
    "status": "not-started",
    "port": "",
    "distance_cm": None,
    "clarity": 1.0,
    "blur_px": 0.0,
    "last_update": 0.0,
    "error": "",
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _auto_port() -> str:
    """Find the most likely Arduino serial port."""

    explicit = os.environ.get("SELFCHAT_DISTANCE_PORT", "").strip()
    if explicit:
        return explicit

    candidates = []
    candidates.extend(glob.glob("/dev/ttyACM*"))
    candidates.extend(glob.glob("/dev/ttyUSB*"))

    # Windows development fallback.  On Raspberry Pi this simply matches none.
    candidates.extend([f"COM{number}" for number in range(3, 16)])

    return candidates[0] if candidates else ""


def calculate_distance_state(distance_cm: float | None) -> dict:
    """Map distance to text clarity.

    50-60 cm is the clear zone.
    Too close and too far both become blurry.
    """

    if distance_cm is None:
        return {"clarity": 1.0, "blur_px": 0.0}

    distance = float(distance_cm)
    if GOOD_MIN_CM <= distance <= GOOD_MAX_CM:
        clarity = 1.0
    elif distance < GOOD_MIN_CM:
        clarity = (distance - NEAR_FULL_BLUR_CM) / (GOOD_MIN_CM - NEAR_FULL_BLUR_CM)
    else:
        clarity = 1.0 - ((distance - GOOD_MAX_CM) / (FAR_FULL_BLUR_CM - GOOD_MAX_CM))

    clarity = _clamp(clarity)
    blur_px = round((1.0 - clarity) * MAX_BLUR_PX, 2)
    return {"clarity": round(clarity, 3), "blur_px": blur_px}


def _update_state(**updates) -> None:
    with _lock:
        _state.update(updates)


def _parse_distance(line: str) -> float | None:
    # Prefer the Arduino diagnostic format:
    # "Duration: 2915 us, Distance: 49.99 cm"
    # If we used the first number, we would accidentally read the duration
    # instead of the distance.
    match = _distance_label_pattern.search(line)
    if not match:
        match = _cm_pattern.search(line)
    if not match:
        match = _number_pattern.search(line)
    if not match:
        return None
    value = float(match.group(1) if match.lastindex else match.group(0))
    # Ignore physically unlikely values and diagnostic lines.
    if value <= 0 or value > 500:
        return None
    return value


def _reader_loop() -> None:
    if serial is None:
        _update_state(enabled=False, status="disabled", error="pyserial is not installed")
        return

    port = _auto_port()
    if not port:
        _update_state(enabled=False, status="disabled", error="No Arduino serial port found")
        return

    _update_state(enabled=True, status="connecting", port=port, error="")

    smoothed_distance = None
    while True:
        try:
            with serial.Serial(port, BAUD_RATE, timeout=1) as connection:
                # Give Arduino a moment after the serial port opens.
                time.sleep(2)
                _update_state(enabled=True, status="connected", port=port, error="")

                while True:
                    raw_line = connection.readline().decode("utf-8", errors="ignore").strip()
                    distance = _parse_distance(raw_line)
                    if distance is None:
                        continue

                    if smoothed_distance is None:
                        smoothed_distance = distance
                    else:
                        smoothed_distance = smoothed_distance * 0.7 + distance * 0.3

                    mapped = calculate_distance_state(smoothed_distance)
                    _update_state(
                        enabled=True,
                        status="connected",
                        port=port,
                        distance_cm=round(smoothed_distance, 2),
                        clarity=mapped["clarity"],
                        blur_px=mapped["blur_px"],
                        last_update=time.time(),
                        error="",
                    )
        except Exception as error:
            _update_state(enabled=False, status="error", port=port, error=str(error))
            time.sleep(2)


def start_distance_sensor() -> None:
    """Start the background serial reader once."""

    global _thread_started
    if _thread_started:
        return
    _thread_started = True
    thread = threading.Thread(target=_reader_loop, daemon=True)
    thread.start()


def get_distance_state() -> dict:
    """Return a JSON-safe copy of the latest sensor state."""

    with _lock:
        state = dict(_state)

    # If readings are stale, keep the installation readable.
    if state["last_update"] and time.time() - float(state["last_update"]) > 3:
        state.update(status="stale", clarity=1.0, blur_px=0.0)

    return state
