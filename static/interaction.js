/* Synchronises the control page with both independent display pages. */
(function () {
  "use strict";

  const form = document.getElementById("situation-form");
  const selfType = document.body.dataset.selfType;

  // ---------- Control page ----------
  if (form) {
    const input = document.getElementById("situation");
    const submitButton = document.getElementById("submit-button");
    const resetButton = document.getElementById("reset-button");
    const status = document.getElementById("form-status");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const situation = input.value.trim();
      if (!situation) return input.focus();

      submitButton.disabled = true;
      status.textContent = "Sending your words across time…";

      try {
        const response = await fetch("/respond", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ situation }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "The screens did not respond.");
        if (data.response_source === "local") {
          status.textContent = "The local AI has answered on both screens.";
        } else if (data.response_source === "mock-fallback") {
          status.textContent = "The local AI was unavailable, so the safe backup answered.";
        } else {
          status.textContent = "Sent. Both screens have received the mock responses.";
        }
      } catch (error) {
        status.textContent = error.message;
      } finally {
        submitButton.disabled = false;
      }
    });

    resetButton.addEventListener("click", async () => {
      resetButton.disabled = true;
      status.textContent = "Resetting both screens…";
      try {
        await fetch("/reset", { method: "POST" });
        input.value = "";
        status.textContent = "Both screens are ready for a new visitor.";
        input.focus();
      } catch (error) {
        status.textContent = "Could not reset the screens.";
      } finally {
        resetButton.disabled = false;
      }
    });
    return;
  }

  // ---------- Past and Future display pages ----------
  if (!selfType) return;

  const voice = document.querySelector(".voice");
  const intro = document.getElementById("voice-intro");
  const message = document.getElementById("voice-message");
  const caption = document.getElementById("voice-caption");
  const listening = document.getElementById("listening");
  let lastVersion = -1;

  const opening = {
    past: {
      intro: "Hi, I am you in the Past.",
      message: "How have you been lately?",
      caption: "I still remember where we began.",
    },
    future: {
      intro: "Hi, I am you in the Future.",
      message: "How have you been lately?",
      caption: "I can see where this is leading.",
    },
  };

  function changeMessage(state) {
    const response = state[`${selfType}_response`];

    if (state.status === "thinking" && !response) {
      voice.hidden = true;
      listening.classList.add("is-visible");
      listening.setAttribute("aria-hidden", "false");
      return;
    }

    voice.hidden = false;
    listening.classList.remove("is-visible");
    listening.setAttribute("aria-hidden", "true");
    const text = response ? {
      intro: selfType === "past" ? "I remember this feeling." : "I remember you here.",
      message: response,
      caption: selfType === "past" ? "— Yourself, from before" : "— Yourself, from ahead",
    } : opening[selfType];

    voice.classList.remove("is-changing");
    intro.textContent = text.intro;
    message.textContent = text.message;
    caption.textContent = text.caption;
    void voice.offsetWidth;
    voice.classList.add("is-changing");
  }

  async function updateFromServer() {
    try {
      const response = await fetch("/state", { cache: "no-store" });
      const state = await response.json();
      if (state.version !== lastVersion) {
        lastVersion = state.version;
        changeMessage(state);
      }
    } catch (error) {
      // A temporary network interruption should not disturb the artwork.
      // The next poll will quietly try again.
    }
  }

  updateFromServer();
  window.setInterval(updateFromServer, 700);
})();
