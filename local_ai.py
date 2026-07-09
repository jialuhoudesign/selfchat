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


def find_model_path(toolkit_root):
    """Find a Pi-friendly GGUF model so users do not need to type exports."""

    if MODEL_ENV:
        return Path(MODEL_ENV).expanduser()

    app_folder = Path(__file__).resolve().parent
    model_names = [
        # Prefer the larger 2B model for better language quality.
        "Qwen3.5-2B.gguf",
        # Smaller/local fallback model.
        "Qwen3.5.gguf",
    ]
    model_folders = [
        toolkit_root / "models",
        app_folder.parent / "models",
        app_folder / "models",
    ]

    for folder in model_folders:
        for name in model_names:
            candidate = folder / name
            if candidate.is_file():
                return candidate.resolve()
    return None


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
                "temperature": float(os.getenv("SELFCHAT_TEMPERATURE", "0.35")),
                "top_p": 0.9,
                "max_tokens": int(os.getenv("SELFCHAT_MAX_TOKENS", "150")),
                "verbose": False,
                "system_prompt": (
                    "Write short, simple, warm replies for SelfChat. "
                    "Only write the final answer. No thinking, no analysis, "
                    "no third-person narration, no medical advice."
                ),
            }
            model_path = find_model_path(toolkit_root)
            if model_path:
                settings["model_path"] = str(model_path)

            candidate = LLM(**settings)
            candidate.load()

            # Qwen uses a ChatML-style conversation template. Some GGUF files
            # do not expose enough metadata for llama-cpp-python to select it
            # automatically, which can result in multilingual token garbage.
            # Setting it explicitly is harmless when the metadata is correct.
            if getattr(candidate, "model", None) is not None:
                candidate.model.chat_format = os.getenv(
                    "SELFCHAT_CHAT_FORMAT", "chatml"
                )

            _model = candidate
            _load_error = ""
            return _model
        except Exception as error:
            _load_error = str(error)
            raise


def generate_local_responses(situation):
    """Ask the local model for the two voices separately.

    This is slower than one combined prompt, but it is much clearer for small
    local models. Each request has only one role, so Past Self and Future Self
    are less likely to mix together or talk about each other in third person.
    """

    return _generate_separately(situation)


def get_ai_status():
    """Return small, JSON-safe diagnostics for the /health page."""

    toolkit_root = find_toolkit_root()
    model_path = find_model_path(toolkit_root) if toolkit_root else None
    return {
        "mode": AI_MODE,
        "local_enabled": local_ai_enabled(),
        "toolkit_found": toolkit_root is not None,
        "toolkit_path": str(toolkit_root) if toolkit_root else "",
        "model_path": str(model_path) if model_path else "",
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
    if _response_is_usable(past_response) and _response_is_usable(future_response):
        return past_response, future_response
    return None


def _generate_separately(situation):
    """Reliable fallback when the combined answer cannot be separated."""

    past_prompt = f"""Present feeling: {situation}

You are my younger self from childhood.
Talk to me like we are the same person.
Voice: curious, simple, bright, a little playful, gentle.
Purpose: cheer me up or encourage me about this exact feeling.
Use "you" and "we". Do not use third person.
Do not sound like a therapist, teacher, or friend.
Do not say: I see you, I hear you, support you, my friend, the world, sun.
Write only 2 short sentences. /no_think"""

    future_prompt = f"""Present feeling: {situation}

You are my older future self.
Talk to me like we are the same person.
Voice: calm, mature, wise, steady, hopeful.
Purpose: reassure me about this exact feeling and give one small next step.
Use "you" and "we". Do not use third person.
Do not sound like a therapist, teacher, or friend.
Do not say: I see you, I hear you, support you, my friend, the world, sun.
Write only 2 short sentences. /no_think"""

    with _model_lock:
        model = load_model()
        past_response = _ask_for_usable_response(model, past_prompt)
        future_response = _ask_for_usable_response(model, future_prompt)

    if not _response_is_usable(past_response) or not _response_is_usable(
        future_response
    ):
        return _safe_template_responses(situation)
    return past_response, future_response


def _ask_for_usable_response(model, prompt):
    """Ask once, then retry with a stricter prompt if the model exposes thinking."""

    first_answer = _clean_response(model.ask(prompt))
    if _response_is_usable(first_answer):
        return first_answer

    retry_prompt = (
        "FINAL ANSWER ONLY. No thinking. No analysis. No <think>. "
        "Speak as the same person from another time, not as a friend. "
        "Avoid my friend, dear, buddy, pal, and child.\n\n"
        f"{prompt}"
    )
    retry_answer = _clean_response(model.ask(retry_prompt))
    if _response_is_usable(retry_answer):
        return retry_answer
    return retry_answer


def _safe_template_responses(situation):
    """Readable fallback when the small local model becomes too generic."""

    lowered = situation.lower()
    if any(word in lowered for word in ["sad", "upset", "lonely", "cry"]):
        return (
            "Hey, maybe today is heavy, but we can still find one tiny bright thing. You do not have to be brave all at once.",
            "You can be sad and still be moving forward. Take one small breath, then one small step; we are not finished yet.",
        )
    if any(word in lowered for word in ["phd", "study", "school", "start", "new"]):
        return (
            "What if this is the adventure we used to imagine before we knew its name? You are allowed to be nervous and still begin.",
            "This beginning does not need to feel easy to be right. Take the next page, the next note, the next hour; we will grow into it.",
        )
    return (
        "Hey, we do not need to understand everything right now. Let us stay curious and hold this moment gently.",
        "You are not stuck here forever. Choose one small honest step, and let that be enough for now.",
    )


def _response_is_usable(text):
    """Reject token garbage before it can appear on an exhibition screen.

    The current artwork explicitly asks for short English responses. A small
    number of typographic Unicode characters is fine, but large amounts of
    mixed writing systems, code fragments, or excessive length usually mean
    that the GGUF/runtime combination generated invalid tokens.
    """

    if not text or len(text) < 12 or len(text) > 520:
        return False

    lowered = text.lower().strip(" .:;!?")
    banned_fragments = [
        "<think",
        "thinking process",
        "analyze the request",
        "**task:**",
        "**persona:**",
        "**tone:**",
        "**format:**",
        "my friend",
        "dear",
        "buddy",
        " pal",
        "i see you",
        "i hear you",
        "support you",
        "the visitor",
        "the person",
        "the world",
        " sun ",
        "new choice",
        "connects to something",
        "once dreamed about",
        "small happy things",
        "simple courage",
    ]
    if any(fragment in lowered for fragment in banned_fragments):
        return False

    third_person_pattern = re.compile(
        r"\b(he|she|they|them|their|visitor|person|someone)\b", re.I
    )
    if third_person_pattern.search(text):
        return False

    copied_placeholders = {
        "past response here",
        "future response here",
        "response here",
    }
    if lowered in copied_placeholders or "response here" in lowered:
        return False

    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
    if len(words) < 4 or len(words) > 95:
        return False

    visible_characters = [character for character in text if not character.isspace()]
    if not visible_characters:
        return False

    english_friendly = sum(
        character.isascii() or character in "—–‘’“”…"
        for character in visible_characters
    )
    if english_friendly / len(visible_characters) < 0.92:
        return False

    suspicious_symbols = sum(character in "\\{}[]<>|" for character in text)
    if suspicious_symbols > 4:
        return False

    return True


if __name__ == "__main__":
    # A direct command provides the simplest possible Pi hardware test:
    # python3 local_ai.py "I am beginning something new"
    test_situation = " ".join(sys.argv[1:]).strip()
    if not test_situation:
        test_situation = "I am uncertain about a new beginning."

    toolkit_root = find_toolkit_root()
    selected_model = find_model_path(toolkit_root) if toolkit_root else None
    if selected_model:
        print(f"Using model: {selected_model.name}")
    else:
        print("Using model: toolkit default")

    print("Loading local model...")
    past, future = generate_local_responses(test_situation)
    print(f"\nPAST:\n{past}\n")
    print(f"FUTURE:\n{future}")
