"""Bridge SelfChat to the Raspberry Pi's local GGUF language model.

The exhibition can still be developed on Windows without the model. On the
Pi, set SELFCHAT_TOOLKIT_PATH to the supplied ``yourPrototype`` folder and
SELFCHAT_AI_MODE to ``local``. No visitor text is sent over the internet.
"""

import os
import re
import sys
import threading
from pathlib import Path


AI_MODE = os.getenv("SELFCHAT_AI_MODE", "auto").strip().lower()
TOOLKIT_ENV = os.getenv("SELFCHAT_TOOLKIT_PATH", "").strip()
MODEL_ENV = os.getenv("SELFCHAT_MODEL_PATH", "").strip()

_model = None
_load_error = ""
_model_lock = threading.RLock()


def find_toolkit_root():
    """Find the supplied Raspberry Pi toolkit without hard-coding one user."""

    # Support both convenient Raspberry Pi layouts:
    #
    #   yourPrototype/app.py
    #   yourPrototype/selfchat/app.py   (recommended for clean Git updates)
    #
    # In both cases the toolkit's llm/ folder can be found without an
    # environment variable.
    app_folder = Path(__file__).resolve().parent
    candidates = [app_folder, app_folder.parent]
    if TOOLKIT_ENV:
        # An explicit setting comes first when the user has supplied one.
        candidates.insert(0, Path(TOOLKIT_ENV).expanduser())

    # These cover the folder shown in the supplied toolkit documentation and
    # common locations when the Pi username is not literally "pi".
    candidates.extend(
        [
            Path.home() / "Desktop" / "ai-dreaming-together-code" / "yourPrototype",
            Path.home() / "Desktop" / "yourPrototype",
        ]
    )

    for candidate in candidates:
        if (candidate / "llm" / "llm.py").is_file():
            return candidate.resolve()
    return None


def local_ai_enabled():
    """Return whether SelfChat should try the real local model."""

    if AI_MODE == "mock":
        return False
    if AI_MODE == "local":
        return True
    return find_toolkit_root() is not None


def load_model():
    """Load the model once, then reuse it for every visitor."""

    global _model, _load_error

    with _model_lock:
        if _model is not None:
            return _model

        toolkit_root = find_toolkit_root()
        if toolkit_root is None:
            raise RuntimeError(
                "Local AI toolkit not found. Set SELFCHAT_TOOLKIT_PATH to "
                "the Raspberry Pi yourPrototype folder."
            )

        # The toolkit is kept outside this Git repository because its models
        # are large. Adding its root to Python's import path exposes llm.llm.
        toolkit_string = str(toolkit_root)
        if toolkit_string not in sys.path:
            sys.path.insert(0, toolkit_string)

        try:
            from llm.llm import LLM

            settings = {
                "context_size": int(os.getenv("SELFCHAT_CONTEXT_SIZE", "1024")),
                "cpu_threads": int(
                    os.getenv("SELFCHAT_CPU_THREADS", str(os.cpu_count() or 4))
                ),
                "gpu_layers": int(os.getenv("SELFCHAT_GPU_LAYERS", "0")),
                "temperature": float(os.getenv("SELFCHAT_TEMPERATURE", "0.72")),
                "top_p": 0.9,
                "max_tokens": int(os.getenv("SELFCHAT_MAX_TOKENS", "190")),
                "verbose": False,
                "system_prompt": (
                    "You write two short, emotionally sensitive reflections for an "
                    "art installation. Be warm and human, never clinical. Do not give "
                    "medical advice. Follow the requested output format exactly."
                ),
            }
            if MODEL_ENV:
                settings["model_path"] = str(Path(MODEL_ENV).expanduser())

            candidate = LLM(**settings)
            candidate.load()
            _model = candidate
            _load_error = ""
            return _model
        except Exception as error:
            _load_error = str(error)
            raise


def generate_local_responses(situation):
    """Ask the local model for both voices in one generation.

    One combined request is noticeably faster on a Raspberry Pi than loading
    or calling the same model twice. XML-like tags make the small model's
    response straightforward to split without another dependency.
    """

    prompt = f"""A visitor describes their present moment:

{situation}

Write two different responses in English.

PAST SELF: gentle, sincere, reflective and slightly vulnerable. Speak like a
past version of the visitor remembering where they came from.

FUTURE SELF: calm, grounded, wise and reassuring. Speak like a future version
looking back at this present moment.

Each response must be 2 or 3 short sentences and under 65 words. Do not repeat
the visitor's words verbatim. Return exactly this format, with no introduction:

<PAST>past response here</PAST>
<FUTURE>future response here</FUTURE>"""

    with _model_lock:
        answer = load_model().ask(prompt)

    parsed = _parse_combined_answer(answer)
    if parsed:
        return parsed

    # Small local models occasionally ignore formatting even when the prompt
    # is explicit. Two simple follow-up requests are slower, but they require
    # no parsing and keep the installation reliable.
    return _generate_separately(situation)


def get_ai_status():
    """Return small, JSON-safe diagnostics for the /health page."""

    toolkit_root = find_toolkit_root()
    return {
        "mode": AI_MODE,
        "local_enabled": local_ai_enabled(),
        "toolkit_found": toolkit_root is not None,
        "toolkit_path": str(toolkit_root) if toolkit_root else "",
        "model_loaded": _model is not None,
        "load_error": _load_error,
    }


def _clean_response(text):
    """Remove model formatting that would look odd on the installation."""

    text = str(text)
    # Some Qwen-family models expose an optional reasoning block. It is useful
    # internally but should never appear as part of the artwork response.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S)
    text = re.sub(r"</?(?:PAST|FUTURE)>", "", text, flags=re.I)
    text = re.sub(
        r"^\s*(?:[#>*-]\s*)*(?:\*\*)?(?:PAST|FUTURE)(?:\s+SELF)?"
        r"(?:\*\*)?\s*[:：-]?\s*",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"^\s*[*_`]+\s*", "", text)
    text = re.sub(r"\s*[*_`]+\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(' "\'')


def _parse_combined_answer(answer):
    """Accept XML tags as well as labels commonly used by small models."""

    answer = re.sub(r"<think>.*?</think>", "", str(answer), flags=re.I | re.S)

    # Preferred format: <PAST>...</PAST> and <FUTURE>...</FUTURE>.
    past_match = re.search(r"<PAST>\s*(.*?)\s*</PAST>", answer, re.I | re.S)
    future_match = re.search(
        r"<FUTURE>\s*(.*?)\s*</FUTURE>", answer, re.I | re.S
    )
    if past_match and future_match:
        return _valid_pair(past_match.group(1), future_match.group(1))

    # Also accept forms such as PAST:, **Past Self:**, or ## FUTURE SELF -.
    label_pattern = re.compile(
        r"(?:^|\n)\s*(?:[#>*-]+\s*)*(?:\*\*)?"
        r"(PAST(?:\s+SELF)?|FUTURE(?:\s+SELF)?)"
        r"\s*[:：-]\s*(?:\*\*)?\s*",
        re.I,
    )
    labels = list(label_pattern.finditer(answer))
    sections = {}
    for index, label in enumerate(labels):
        start = label.end()
        end = labels[index + 1].start() if index + 1 < len(labels) else len(answer)
        key = "past" if label.group(1).lower().startswith("past") else "future"
        sections[key] = answer[start:end]

    if "past" in sections and "future" in sections:
        return _valid_pair(sections["past"], sections["future"])
    return None


def _valid_pair(past_text, future_text):
    """Clean a parsed pair and reject empty sections."""

    past_response = _clean_response(past_text)
    future_response = _clean_response(future_text)
    if past_response and future_response:
        return past_response, future_response
    return None


def _generate_separately(situation):
    """Reliable fallback when the combined answer cannot be separated."""

    past_prompt = f"""The visitor says: {situation}

Reply as their past self. Be gentle, sincere, reflective, and slightly
vulnerable, remembering where they came from. Write only the response: 2 or 3
short sentences, under 65 words. Do not add a title, label, or explanation."""

    future_prompt = f"""The visitor says: {situation}

Reply as their future self. Be calm, grounded, wise, and reassuring, looking
back at their present moment. Write only the response: 2 or 3 short sentences,
under 65 words. Do not add a title, label, or explanation."""

    with _model_lock:
        model = load_model()
        past_response = _clean_response(model.ask(past_prompt))
        future_response = _clean_response(model.ask(future_prompt))

    if not past_response or not future_response:
        raise RuntimeError("The local model returned an empty response.")
    return past_response, future_response


if __name__ == "__main__":
    # A direct command provides the simplest possible Pi hardware test:
    # python3 local_ai.py "I am beginning something new"
    test_situation = " ".join(sys.argv[1:]).strip()
    if not test_situation:
        test_situation = "I am uncertain about a new beginning."

    print("Loading local model...")
    past, future = generate_local_responses(test_situation)
    print(f"\nPAST:\n{past}\n")
    print(f"FUTURE:\n{future}")
