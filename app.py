"""SelfChat: Temporal Self Dialogue.

A small Flask application for an offline exhibition prototype.

The installation can try a Raspberry Pi local LLM, but it always has a rich
local mock fallback.  This keeps the piece stable during an exhibition:

- every visitor input enters a visible "thinking" state;
- the app tries the local AI when it is enabled;
- if AI takes longer than 20 seconds, the visitor still receives a response;
- no visitor text is sent to an online API.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
import os
import random
import time

from flask import Flask, jsonify, render_template, request

from distance_sensor import get_distance_state, start_distance_sensor
from local_ai import (
    generate_local_future_response,
    generate_local_past_response,
    get_ai_status,
    load_model,
    local_ai_enabled,
)


app = Flask(__name__)

# The exhibition should never wait forever for the local model.
AI_TIMEOUT_SECONDS = 20

# If the app falls back to mock instantly, keep the thinking animation visible
# for a short moment so the experience still feels intentional.
MIN_THINKING_SECONDS = 2.4

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


def create_mock_responses(situation):
    """Build varied exhibition-safe responses from local templates.

    These are intentionally short and poetic.  Past Self sounds younger,
    curious, playful, and encouraging.  Future Self sounds grounded, calm, and
    hopeful.  The function uses random.choice so repeated visitor questions do
    not always receive the same sentence.
    """

    lowered = situation.lower()

    # Each theme has:
    # 1. keywords to detect from visitor text;
    # 2. Past Self sentences;
    # 3. Future Self sentences.
    themes = [
        (
            ["sad", "upset", "cry", "heavy", "hurt", "depressed", "down", "难过", "伤心", "想哭", "痛苦"],
            [
                "Let us find one tiny warm thing today, even if the big cloud is still here.",
                "Maybe this sadness is asking us to be held softly, not fixed all at once.",
                "I am small and curious, and I still believe a little light can sneak back in.",
                "Let us sit beside this feeling like rain on the window, not the whole sky.",
                "Even now, I want to show you something bright and say: look, we are still here.",
                "If today feels blue, we can still keep one yellow pebble in our pocket.",
            ],
            [
                "This sadness is real, but it is not the whole story; take one breath and stay with yourself.",
                "You do not need to climb out all at once; one kind action is enough for this minute.",
                "I know this feels heavy, and I also know you keep finding a way through.",
                "Let the feeling pass through without naming it forever; hope is still quietly working.",
                "You are allowed to hurt and still be moving toward a softer morning.",
                "This moment will change shape; remain gentle until it does.",
            ],
        ),
        (
            ["lost", "confused", "uncertain", "stuck", "迷茫", "困惑", "不知道", "卡住"],
            [
                "What if not knowing is just the first page of a treasure map?",
                "We can be lost and still be explorers; let us choose one little direction.",
                "Maybe the path is shy today, but one curious step can wake it up.",
                "I want to peek around the corner with you, not solve the whole maze.",
                "Being unsure can still be an adventure if we hold a small lamp.",
                "Let us draw a tiny arrow and follow it only as far as today.",
            ],
            [
                "You do not need the whole map tonight; choose the next clear step and let it be enough.",
                "This uncertainty will become information later; stay steady and move one small piece.",
                "You are not behind; you are inside the part where the shape is still forming.",
                "Clarity will arrive through movement, not pressure; begin with what is nearest.",
                "Trust the small decision you can make today; the larger path will answer later.",
                "The future is not asking for certainty; it is asking for one honest step.",
            ],
        ),
        (
            ["tired", "exhausted", "burnt", "burnout", "sleepy", "累", "疲惫", "没力气"],
            [
                "Even brave little creatures curl up sometimes; resting can be part of the adventure.",
                "What if we stop trying so hard for a moment and let the quiet help us?",
                "We do not have to sparkle every day; today we can be small and still be good.",
                "Let us become a seed for a while; seeds look still when they are growing.",
                "I think naps and tiny snacks can be heroic too.",
                "Maybe the softest thing is the bravest thing today.",
            ],
            [
                "Rest will not erase your progress; it will help you return with more of yourself.",
                "You are allowed to pause before the next step; steadiness is built slowly.",
                "Let the body be believed today, then begin again with less blame.",
                "Your worth is not measured by how much you can carry while exhausted.",
                "Slow down without shame; the path is still here when you breathe again.",
                "Recovery is not a delay; it is part of the work becoming sustainable.",
            ],
        ),
        (
            ["anxious", "nervous", "worry", "worried", "afraid", "scared", "焦虑", "害怕", "担心", "紧张"],
            [
                "Our heart is making thunder, but thunder does not always mean danger.",
                "What if we hold the scary thought like a bug in a jar and just look at it?",
                "We can be shaky and still try; tiny knees can carry brave feet.",
                "Let us count one breath, then another, like stepping stones across a stream.",
                "The fear is loud, but curiosity can still whisper: what if we are okay?",
                "Maybe courage is just our small hand reaching forward while it shakes.",
            ],
            [
                "Fear is loud right now, but it is not the only voice; take the next small action.",
                "You do not need to defeat the worry first; move gently while it becomes quieter.",
                "This feeling can ride beside you without choosing the direction.",
                "Return to the body, lower the scale, and do only the next possible thing.",
                "You are safer than the alarm says; let your breath prove the present moment.",
                "Let the future be larger than this fear; it already is.",
            ],
        ),
        (
            ["phd", "study", "school", "exam", "project", "work", "career", "start", "begin", "学习", "考试", "项目", "工作", "开始"],
            [
                "What if this big beginning is one of the dreams we used to draw in secret?",
                "We are allowed to be new at this; new things are where wonder lives.",
                "This is big, but we have always liked opening doors just to see the light inside.",
                "I want to clap for us, because trying something new still feels like magic.",
                "Let us be beginners with bright eyes; that is where the adventure starts.",
                "We do not need to know everything before we start collecting little stars.",
            ],
            [
                "Begin with the next page, the next note, the next hour; confidence will meet you in motion.",
                "You do not need to feel ready to be ready enough; start small and keep returning.",
                "This path will teach you as you walk it, and you will grow into the room.",
                "The future is built through ordinary hours; protect the next one and continue.",
                "You are not proving you belong; you are learning how to inhabit the work.",
                "Your confidence will not arrive before the work; it will be made inside it.",
            ],
        ),
        (
            ["alone", "lonely", "miss", "missing", "孤独", "想念", "一个人", "寂寞"],
            [
                "Even when it feels quiet, we are still here together inside the same little heart.",
                "What if loneliness is a room where we can light one tiny lamp?",
                "We can sit with the quiet and make it less scary by breathing slowly.",
                "I will draw a door in this lonely room, just in case someone kind is near.",
                "Maybe we can send one small signal out and see what answers.",
                "Let us make the silence less empty by being gentle inside it.",
            ],
            [
                "You are not empty; you are waiting for connection, and it can still find you.",
                "This lonely moment is real, but it is not permanent; reach for one small signal.",
                "Stay open by one inch today; that is enough for life to come closer.",
                "Reach gently, not desperately; one honest message can change the temperature of the day.",
                "The part of you that wants connection is wise; listen to it without shame.",
                "You are still connected to the life that is coming toward you.",
            ],
        ),
        (
            ["change", "move", "moving", "new life", "choice", "decision", "变化", "改变", "选择", "决定"],
            [
                "New doors are strange, but I want to touch the handle and see what shines there.",
                "Maybe changing is how we find the colors we did not know we had.",
                "We can carry our little old self with us and still step into the new place.",
                "I am scared too, but I am also excited, and that tiny excitement matters.",
                "Let us pack curiosity first; it always fits in the smallest bag.",
                "The new thing is glowing a little, even if it feels too big.",
            ],
            [
                "Change does not erase you; it reveals which parts of you know how to grow.",
                "Let the next version arrive slowly; you only need to choose with honesty today.",
                "You can be afraid and still correct; courage often feels like uncertainty at first.",
                "The old life taught you something, and the new one will not require you to disappear.",
                "Trust the part of you that is already adapting quietly.",
                "This threshold is not here to punish you; it is here because life is opening.",
            ],
        ),
        (
            ["happy", "excited", "proud", "good", "joy", "开心", "高兴", "兴奋", "骄傲"],
            [
                "I want to jump around with this feeling and put it somewhere safe in our pocket.",
                "See, joy found us; let us look at it closely so we remember its shape.",
                "This bright feeling is real, and I am so glad we get to have it.",
                "Let us keep this little sun; it can warm us on a harder day.",
                "I knew there would be golden days, and look, here is one.",
                "Let us celebrate without shrinking it; happiness can be trusted too.",
            ],
            [
                "Let yourself receive this joy fully; it is not a trick, it is part of your life.",
                "Remember this evidence: good things can reach you, and you are allowed to enjoy them.",
                "Do not rush past the brightness; gratitude is also a form of strength.",
                "This happiness belongs to you; let it teach your nervous system what safety feels like.",
                "Let this moment become proof that more light can come.",
                "You are allowed to be proud without immediately becoming afraid.",
            ],
        ),
        (
            ["angry", "mad", "frustrated", "unfair", "annoyed", "生气", "愤怒", "不公平", "烦"],
            [
                "That fire means something matters; let us hold it carefully so it does not burn us.",
                "I can stomp my feet with you, then we can decide what the fire is protecting.",
                "Maybe anger is a little guard dog barking because our heart needs care.",
                "We do not have to be polite to the feeling before we understand it.",
                "Let us listen to the spark before it becomes a wildfire.",
                "Something in us knows we deserve care; that is why the feeling is so bright.",
            ],
            [
                "Your anger may be pointing toward a boundary; listen, then answer with steadiness.",
                "Do not let the heat choose your whole response; let it show you what needs protection.",
                "You can be firm without becoming cruel; that is where your power becomes clear.",
                "Name what matters, lower the volume, and take the next clean action.",
                "The feeling is valid; the next move can still be wise.",
                "Let the fire become a boundary, not a wound you carry alone.",
            ],
        ),
        (
            ["overwhelmed", "too much", "busy", "pressure", "stress", "压力", "太多", "忙", "崩溃"],
            [
                "Everything feels huge, so let us make it tiny: one breath, one corner, one little task.",
                "What if we put the giant pile into small boxes and open only one?",
                "I know it looks like a mountain, but I found a pebble we can move first.",
                "Let us not fight the whole storm; let us find one dry match.",
                "We can make the scary thing smaller by naming only the next piece.",
                "One tiny task is still a lantern.",
            ],
            [
                "Reduce the scale until the next action becomes visible; that is not weakness, it is strategy.",
                "You do not need to hold the whole system in your body; choose one priority and release the rest for now.",
                "Pressure gets quieter when it becomes a list, a boundary, and one first step.",
                "You are allowed to simplify; a smaller plan is still a real plan.",
                "Do less, more clearly; that is how you return to yourself.",
                "The whole weight is not yours to solve at once; begin where your hands can reach.",
            ],
        ),
    ]

    for keywords, past_options, future_options in themes:
        if any(keyword in lowered for keyword in keywords):
            return random.choice(past_options), random.choice(future_options)

    # General responses when no keyword is detected.
    return (
        random.choice(
            [
                "We do not have to understand everything; let us stay curious and gentle for one more step.",
                "What if this moment is not a test, but a doorway we can peek through slowly?",
                "We can be unsure and still be full of little lights; let us follow one of them.",
                "The feeling is big, but we are still here, and that means the story is moving.",
                "Let us look for the smallest bright clue and follow it with soft feet.",
                "I do not know everything yet, but I still believe something good can be found here.",
                "Maybe this is the part where we become brave without noticing.",
                "Let us hold this moment like a mystery, not a verdict.",
                "There is still a tiny door somewhere; I want to look for it with you.",
                "We can be imperfect and still be wonderfully alive inside this moment.",
            ],
        ),
        random.choice(
            [
                "You are not stuck forever; choose one small honest step and let that be enough for now.",
                "This moment does not need to make sense yet; keep breathing and let the next step appear.",
                "You will understand more later; for now, move gently and do not abandon yourself.",
                "There is still a way through this; make the next choice smaller, kinder, and possible.",
                "You do not need certainty to continue; you need one grounded action and a little patience.",
                "The future is not asking you to be perfect, only to stay in conversation with yourself.",
                "Trust the quiet part that still wants to live forward; it has carried you before.",
                "Let hope be practical today: one breath, one boundary, one small beginning.",
                "You are already becoming someone who survives this with more tenderness.",
                "Let the next step be small enough that you can actually take it.",
            ],
        ),
    )


def create_mock_responses(situation):
    """Build paired mock responses so Past and Future always match.

    Each item is a complete Past/Future pair.  This avoids the collage feeling
    that can happen when Past and Future sentences are randomized separately.
    """

    lowered = situation.lower()

    themes = [
        (
            ["sad", "upset", "cry", "heavy", "hurt", "depressed", "down", "难过", "伤心", "想哭", "痛苦"],
            [
                {
                    "past": "Let us find one tiny warm thing today, even if the big cloud is still here.",
                    "future": "This sadness is real, but it is not the whole story; stay with yourself for one more breath.",
                },
                {
                    "past": "Maybe this sadness is asking us to be held softly, not fixed all at once.",
                    "future": "You do not need to climb out all at once; one kind action is enough for this minute.",
                },
                {
                    "past": "I am small and curious, and I still believe a little light can sneak back in.",
                    "future": "Let the feeling pass through without naming it forever; hope is still quietly working.",
                },
                {
                    "past": "If today feels blue, we can still keep one yellow pebble in our pocket.",
                    "future": "You are allowed to hurt and still be moving toward a softer morning.",
                },
                {
                    "past": "Let us sit beside this feeling like rain on the window, not the whole sky.",
                    "future": "This moment will change shape; remain gentle until it does.",
                },
            ],
        ),
        (
            ["lost", "confused", "uncertain", "stuck", "迷茫", "困惑", "不知道", "卡住"],
            [
                {
                    "past": "What if not knowing is just the first page of a treasure map?",
                    "future": "You do not need the whole map tonight; choose the next clear step and let it be enough.",
                },
                {
                    "past": "We can be lost and still be explorers; let us choose one little direction.",
                    "future": "Clarity will arrive through movement, not pressure; begin with what is nearest.",
                },
                {
                    "past": "Maybe the path is shy today, but one curious step can wake it up.",
                    "future": "This uncertainty will become information later; stay steady and move one small piece.",
                },
                {
                    "past": "Being unsure can still be an adventure if we hold a small lamp.",
                    "future": "The future is not asking for certainty; it is asking for one honest step.",
                },
                {
                    "past": "Let us draw a tiny arrow and follow it only as far as today.",
                    "future": "Trust the small decision you can make today; the larger path will answer later.",
                },
            ],
        ),
        (
            ["tired", "exhausted", "burnt", "burnout", "sleepy", "累", "疲惫", "没力气"],
            [
                {
                    "past": "Even brave little creatures curl up sometimes; resting can be part of the adventure.",
                    "future": "Rest will not erase your progress; it will help you return with more of yourself.",
                },
                {
                    "past": "What if we stop trying so hard for a moment and let the quiet help us?",
                    "future": "You are allowed to pause before the next step; steadiness is built slowly.",
                },
                {
                    "past": "Let us become a seed for a while; seeds look still when they are growing.",
                    "future": "Recovery is not a delay; it is part of the work becoming sustainable.",
                },
                {
                    "past": "I think naps and tiny snacks can be heroic too.",
                    "future": "Your worth is not measured by how much you can carry while exhausted.",
                },
                {
                    "past": "Maybe the softest thing is the bravest thing today.",
                    "future": "Slow down without shame; the path is still here when you breathe again.",
                },
            ],
        ),
        (
            ["anxious", "nervous", "worry", "worried", "afraid", "scared", "焦虑", "害怕", "担心", "紧张"],
            [
                {
                    "past": "Our heart is making thunder, but thunder does not always mean danger.",
                    "future": "Fear is loud right now, but it is not the only voice; take the next small action.",
                },
                {
                    "past": "What if we hold the scary thought like a bug in a jar and just look at it?",
                    "future": "You do not need to defeat the worry first; move gently while it becomes quieter.",
                },
                {
                    "past": "We can be shaky and still try; tiny knees can carry brave feet.",
                    "future": "This feeling can ride beside you without choosing the direction.",
                },
                {
                    "past": "Let us count one breath, then another, like stepping stones across a stream.",
                    "future": "Return to the body, lower the scale, and do only the next possible thing.",
                },
                {
                    "past": "Maybe courage is just our small hand reaching forward while it shakes.",
                    "future": "You are safer than the alarm says; let your breath prove the present moment.",
                },
            ],
        ),
        (
            ["phd", "study", "school", "exam", "project", "work", "career", "start", "begin", "学习", "考试", "项目", "工作", "开始"],
            [
                {
                    "past": "What if this big beginning is one of the dreams we used to draw in secret?",
                    "future": "Begin with the next page, the next note, the next hour; confidence will meet you in motion.",
                },
                {
                    "past": "We are allowed to be new at this; new things are where wonder lives.",
                    "future": "You do not need to feel ready to be ready enough; start small and keep returning.",
                },
                {
                    "past": "This is big, but we have always liked opening doors just to see the light inside.",
                    "future": "This path will teach you as you walk it, and you will grow into the room.",
                },
                {
                    "past": "I want to clap for us, because trying something new still feels like magic.",
                    "future": "The future is built through ordinary hours; protect the next one and continue.",
                },
                {
                    "past": "Let us be beginners with bright eyes; that is where the adventure starts.",
                    "future": "Your confidence will not arrive before the work; it will be made inside it.",
                },
            ],
        ),
        (
            ["alone", "lonely", "miss", "missing", "孤独", "想念", "一个人", "寂寞"],
            [
                {
                    "past": "What if loneliness is a room where we can light one tiny lamp?",
                    "future": "This lonely moment is real, but it is not permanent; reach for one small signal.",
                },
                {
                    "past": "Even when it feels quiet, we are still here together inside the same little heart.",
                    "future": "You are not empty; you are waiting for connection, and it can still find you.",
                },
                {
                    "past": "I will draw a door in this lonely room, just in case someone kind is near.",
                    "future": "Stay open by one inch today; that is enough for life to come closer.",
                },
                {
                    "past": "Maybe we can send one small signal out and see what answers.",
                    "future": "Reach gently, not desperately; one honest message can change the temperature of the day.",
                },
                {
                    "past": "Let us make the silence less empty by being gentle inside it.",
                    "future": "The part of you that wants connection is wise; listen to it without shame.",
                },
            ],
        ),
        (
            ["change", "move", "moving", "new life", "choice", "decision", "变化", "改变", "选择", "决定"],
            [
                {
                    "past": "New doors are strange, but I want to touch the handle and see what shines there.",
                    "future": "Change does not erase you; it reveals which parts of you know how to grow.",
                },
                {
                    "past": "Maybe changing is how we find the colors we did not know we had.",
                    "future": "Let the next version arrive slowly; you only need to choose with honesty today.",
                },
                {
                    "past": "We can carry our little old self with us and still step into the new place.",
                    "future": "The old life taught you something, and the new one will not require you to disappear.",
                },
                {
                    "past": "I am scared too, but I am also excited, and that tiny excitement matters.",
                    "future": "You can be afraid and still correct; courage often feels like uncertainty at first.",
                },
                {
                    "past": "Let us pack curiosity first; it always fits in the smallest bag.",
                    "future": "This threshold is not here to punish you; it is here because life is opening.",
                },
            ],
        ),
        (
            ["happy", "excited", "proud", "good", "joy", "开心", "高兴", "兴奋", "骄傲"],
            [
                {
                    "past": "I want to jump around with this feeling and put it somewhere safe in our pocket.",
                    "future": "Let yourself receive this joy fully; it is not a trick, it is part of your life.",
                },
                {
                    "past": "See, joy found us; let us look at it closely so we remember its shape.",
                    "future": "Remember this evidence: good things can reach you, and you are allowed to enjoy them.",
                },
                {
                    "past": "Let us keep this little sun; it can warm us on a harder day.",
                    "future": "Do not rush past the brightness; gratitude is also a form of strength.",
                },
                {
                    "past": "I knew there would be golden days, and look, here is one.",
                    "future": "Let this moment become proof that more light can come.",
                },
                {
                    "past": "Let us celebrate without shrinking it; happiness can be trusted too.",
                    "future": "You are allowed to be proud without immediately becoming afraid.",
                },
            ],
        ),
        (
            ["angry", "mad", "frustrated", "unfair", "annoyed", "生气", "愤怒", "不公平", "烦"],
            [
                {
                    "past": "That fire means something matters; let us hold it carefully so it does not burn us.",
                    "future": "Your anger may be pointing toward a boundary; listen, then answer with steadiness.",
                },
                {
                    "past": "I can stomp my feet with you, then we can decide what the fire is protecting.",
                    "future": "Do not let the heat choose your whole response; let it show you what needs protection.",
                },
                {
                    "past": "Maybe anger is a little guard dog barking because our heart needs care.",
                    "future": "You can be firm without becoming cruel; that is where your power becomes clear.",
                },
                {
                    "past": "We do not have to be polite to the feeling before we understand it.",
                    "future": "The feeling is valid; the next move can still be wise.",
                },
                {
                    "past": "Something in us knows we deserve care; that is why the feeling is so bright.",
                    "future": "Let the fire become a boundary, not a wound you carry alone.",
                },
            ],
        ),
        (
            ["overwhelmed", "too much", "busy", "pressure", "stress", "压力", "太多", "忙", "崩溃"],
            [
                {
                    "past": "Everything feels huge, so let us make it tiny: one breath, one corner, one little task.",
                    "future": "Reduce the scale until the next action becomes visible; that is not weakness, it is strategy.",
                },
                {
                    "past": "What if we put the giant pile into small boxes and open only one?",
                    "future": "Pressure gets quieter when it becomes a list, a boundary, and one first step.",
                },
                {
                    "past": "I know it looks like a mountain, but I found a pebble we can move first.",
                    "future": "You are allowed to simplify; a smaller plan is still a real plan.",
                },
                {
                    "past": "Let us not fight the whole storm; let us find one dry match.",
                    "future": "Do less, more clearly; that is how you return to yourself.",
                },
                {
                    "past": "One tiny task is still a lantern.",
                    "future": "The whole weight is not yours to solve at once; begin where your hands can reach.",
                },
            ],
        ),
    ]

    general_pairs = [
        {
            "past": "What if this moment is not a test, but a doorway we can peek through slowly?",
            "future": "This moment does not need to make sense yet; keep breathing and let the next step appear.",
        },
        {
            "past": "We can be unsure and still be full of little lights; let us follow one of them.",
            "future": "You do not need certainty to continue; you need one grounded action and a little patience.",
        },
        {
            "past": "Let us look for the smallest bright clue and follow it with soft feet.",
            "future": "There is still a way through this; make the next choice smaller, kinder, and possible.",
        },
        {
            "past": "Maybe this is the part where we become brave without noticing.",
            "future": "Trust the quiet part that still wants to live forward; it has carried you before.",
        },
        {
            "past": "Let us hold this moment like a mystery, not a verdict.",
            "future": "Let hope be practical today: one breath, one boundary, one small beginning.",
        },
        {
            "past": "There is still a tiny door somewhere; I want to look for it with you.",
            "future": "Let the next step be small enough that you can actually take it.",
        },
    ]

    for keywords, pairs in themes:
        if any(keyword in lowered for keyword in keywords):
            pair = random.choice(pairs)
            return pair["past"], pair["future"]

    pair = random.choice(general_pairs)
    return pair["past"], pair["future"]


def run_local_with_timeout(function, situation, timeout_seconds):
    """Try one local AI call, then stop waiting if the Pi is too slow.

    Python cannot safely kill a running llama thread from the outside.  Instead
    the Flask request stops waiting after the timeout and immediately falls back
    to mock text.  The next visitor input still starts a fresh AI attempt.
    """

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(function, situation)
    try:
        return future.result(timeout=timeout_seconds)
    finally:
        if not future.done():
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)


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
    """Show the warm Past Self display."""

    return render_template("index.html", self_type="past")


@app.get("/future")
def future_screen():
    """Show the cool Future Self display."""

    return render_template("index.html", self_type="future")


@app.get("/state")
def state():
    """Let both screens read the newest installation state."""

    return jsonify(installation_state)


@app.get("/distance")
def distance():
    """Return the newest distance-based text clarity state."""

    return jsonify(get_distance_state())


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
    """Generate responses for Past Self and Future Self."""

    data = request.get_json(silent=True) or {}
    situation = str(data.get("situation", "")).strip()

    if not situation:
        return jsonify({"error": "Please share a few words first."}), 400

    # Keep extremely long accidental input from overwhelming the display.
    situation = situation[:600]
    generation_started_at = time.monotonic()

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
        deadline = time.monotonic() + AI_TIMEOUT_SECONDS
        try:
            # Past Self is requested first so it can appear first if the model
            # is fast enough.
            past_response = run_local_with_timeout(
                generate_local_past_response,
                situation,
                max(0.1, deadline - time.monotonic()),
            )

            installation_state.update(
                version=installation_state["version"] + 1,
                past_response=past_response,
                future_response="",
                status="thinking",
                response_source="local",
                ai_error="",
            )

            future_response = run_local_with_timeout(
                generate_local_future_response,
                situation,
                max(0.1, deadline - time.monotonic()),
            )
            response_source = "local"
        except TimeoutError as error:
            ai_error = str(error)
            past_response, future_response = create_mock_responses(situation)
            response_source = "mock-timeout"
        except Exception as error:
            # Stability matters in an exhibition. If the local model fails or
            # formats an answer unexpectedly, the visitor still gets a reply.
            ai_error = str(error)
            past_response, future_response = create_mock_responses(situation)
            response_source = "mock-fallback"
    else:
        past_response, future_response = create_mock_responses(situation)

    # Keep the thinking state alive long enough for the display screens to
    # visibly enter the time-travel mode, even if AI/mock returns instantly.
    elapsed = time.monotonic() - generation_started_at
    if elapsed < MIN_THINKING_SECONDS:
        time.sleep(MIN_THINKING_SECONDS - elapsed)

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
    # Start reading Arduino distance values in the background. If Arduino or
    # pyserial is missing, this fails softly and text stays clear.
    start_distance_sensor()

    # host="0.0.0.0" also lets another device on the same local network open
    # the installation.  debug is intentionally off for exhibition stability.
    port = int(os.environ.get("SELFCHAT_PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
