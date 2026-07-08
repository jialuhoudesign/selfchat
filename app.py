"""SelfChat: Temporal Self Dialogue.

A tiny Flask application for an offline exhibition prototype.  The responses
are assembled locally from simple templates; no text is sent to an AI service
or anywhere else on the internet.
"""

from hashlib import sha256

from flask import Flask, jsonify, render_template, request

from local_ai import (
    generate_local_responses,
    get_ai_status,
    load_model,
    local_ai_enabled,
)


app = Flask(__name__)

# This in-memory state is shared by the two display pages and the control page.
# It resets whenever the Flask app restarts, which is useful for an exhibition.
installation_state = {
    "version": 0,
    "situation": "",
    "past_response": "",
    "future_response": "",
    "status": "idle",
    "response_source": "none",
    "ai_error": "",
}


def choose(options, text, offset=0):
    """Choose a repeatable option based on the visitor's text.

    Using a hash gives the installation a little variety while ensuring that
    the same words produce the same reply.  This keeps the mock easy to test.
    """

    number = int(sha256(text.encode("utf-8")).hexdigest(), 16)
    return options[(number + offset) % len(options)]


def create_mock_responses(situation):
    """Build two gentle, local responses from the visitor's situation."""

    lowered = situation.lower()

    # A small keyword layer makes the mock feel responsive without pretending
    # to understand the visitor like a real language model would.
    themes = {
        "tired": (
            "I remember learning that rest was not something we had to earn.",
            "You will become kinder about your limits, and that changes more than you expect.",
        ),
        "lost": (
            "There were other times we could not see the path, only the next small step.",
            "The path becomes visible by walking it; you do not need the whole map tonight.",
        ),
        "anxious": (
            "I remember that tightness—the mind trying to protect us from every possible tomorrow.",
            "Many of the futures you fear never arrive. You learn to meet the one that does.",
        ),
        "sad": (
            "I wish I could sit beside you without trying to make the feeling smaller.",
            "This sadness is not the whole landscape. Light finds its way back in, quietly.",
        ),
        "happy": (
            "Keep a little of this warmth for me. I would have loved to know it was coming.",
            "You will remember this ordinary brightness more clearly than you imagine.",
        ),
        "change": (
            "We have crossed uncertain thresholds before, even when our hands were shaking.",
            "Change does not erase you. It reveals which parts of you know how to grow.",
        ),
        "work": (
            "I remember when achievement felt like the safest way to prove we belonged.",
            "Your worth becomes much quieter than your work—and much harder to lose.",
        ),
        "alone": (
            "I knew that particular silence. I carried it too, even in crowded rooms.",
            "You are not as alone as this moment makes you feel. Connection is already moving toward you.",
        ),
    }

    theme_line = next(
        (lines for keyword, lines in themes.items() if keyword in lowered),
        None,
    )

    past_opening = choose(
        [
            "I hear you from a place you once called home.",
            "Some part of me remembers the beginning of this feeling.",
            "I am listening from the quieter rooms of your memory.",
        ],
        situation,
    )
    future_opening = choose(
        [
            "I am looking back at you with more tenderness than you can see right now.",
            "From here, this moment is not an ending. It is a turning point.",
            "I remember this version of us—and I am grateful you kept going.",
        ],
        situation,
        offset=7,
    )

    if theme_line:
        past_middle, future_middle = theme_line
    else:
        past_middle = choose(
            [
                "You do not have to explain it perfectly. I know how long you have been carrying things quietly.",
                "I can see the courage hidden inside your uncertainty. We used to overlook that.",
                "What you are feeling makes sense beside everything that brought us here.",
            ],
            situation,
            offset=13,
        )
        future_middle = choose(
            [
                "You do not solve everything at once. You make one honest choice, then another.",
                "This feeling moves through you; it does not become you.",
                "The clarity you are waiting for arrives slowly, while you are already living forward.",
            ],
            situation,
            offset=23,
        )

    past_ending = choose(
        [
            "Please be gentle with the person we became.",
            "I am proud of how far you carried us.",
            "You are living inside a tomorrow I once hoped for.",
        ],
        situation,
        offset=31,
    )
    future_ending = choose(
        [
            "Take the next small step. I will meet you there.",
            "Breathe. There is still so much room ahead of you.",
            "You are becoming me, even now. There is no need to rush.",
        ],
        situation,
        offset=41,
    )

    return (
        f"{past_opening} {past_middle} {past_ending}",
        f"{future_opening} {future_middle} {future_ending}",
    )


@app.get("/")
def index():
    """Use the control page as the simple starting point."""

    return render_template("control.html")


@app.get("/control")
def control():
    """Show the visitor/operator input page."""

    return render_template("control.html")


@app.get("/past")
def past_screen():
    """Show the blue-purple Past Self display."""

    return render_template("index.html", self_type="past")


@app.get("/future")
def future_screen():
    """Show the yellow-green Future Self display."""

    return render_template("index.html", self_type="future")


@app.get("/state")
def state():
    """Let both screens read the newest installation state."""

    return jsonify(installation_state)


@app.get("/health")
def health():
    """Show whether the Flask app can see and load the local AI toolkit."""

    return jsonify(app="ok", ai=get_ai_status())


@app.post("/health/load")
def health_load():
    """Load the model now so it is warm before the first visitor."""

    if not local_ai_enabled():
        return jsonify(ok=False, error="Local AI is not enabled."), 400

    try:
        load_model()
        return jsonify(ok=True, ai=get_ai_status())
    except Exception as error:
        return jsonify(ok=False, error=str(error), ai=get_ai_status()), 500


@app.post("/respond")
def respond():
    """Return the two locally generated mock responses as JSON."""

    data = request.get_json(silent=True) or {}
    situation = str(data.get("situation", "")).strip()

    if not situation:
        return jsonify({"error": "Please share a few words first."}), 400

    # Keep extremely long accidental input from overwhelming the display.
    situation = situation[:600]
    # Tell both artwork screens that generation has started. They keep polling
    # /state while the Pi works on the local model response.
    installation_state.update(
        version=installation_state["version"] + 1,
        situation=situation,
        past_response="",
        future_response="",
        status="thinking",
        response_source="local" if local_ai_enabled() else "mock",
        ai_error="",
    )

    response_source = "mock"
    ai_error = ""
    if local_ai_enabled():
        try:
            past_response, future_response = generate_local_responses(situation)
            response_source = "local"
        except Exception as error:
            # Stability matters in an exhibition. If the local model fails or
            # formats an answer unexpectedly, the visitor still gets a reply.
            ai_error = str(error)
            past_response, future_response = create_mock_responses(situation)
            response_source = "mock-fallback"
    else:
        past_response, future_response = create_mock_responses(situation)

    # Updating one shared object lets the two screens change together when
    # their small polling requests next reach /state.
    installation_state.update(
        version=installation_state["version"] + 1,
        past_response=past_response,
        future_response=future_response,
        status="ready",
        response_source=response_source,
        ai_error=ai_error,
    )

    return jsonify(
        past_response=past_response,
        future_response=future_response,
        version=installation_state["version"],
        response_source=response_source,
        ai_error=ai_error,
    )


@app.post("/reset")
def reset():
    """Clear both display screens and return to their opening greeting."""

    installation_state.update(
        version=installation_state["version"] + 1,
        situation="",
        past_response="",
        future_response="",
        status="idle",
        response_source="none",
        ai_error="",
    )
    return jsonify(ok=True, version=installation_state["version"])


if __name__ == "__main__":
    # host="0.0.0.0" also lets another device on the same local network open
    # the installation.  debug is intentionally off for exhibition stability.
    app.run(host="0.0.0.0", port=5000, debug=False)
