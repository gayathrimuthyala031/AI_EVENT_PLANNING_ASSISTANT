import io
import re
import hashlib
import requests
import streamlit as st
import speech_recognition as sr
from gtts import gTTS
from datetime import date, timedelta

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"

BASE_PROMPT = """You are an AI Event Planning Assistant.
Help users plan events like weddings, birthdays, parties,
corporate events and festivals.
Give practical suggestions on budget, venue, food, decoration,
guest list, schedule and checklists.
Keep answers short, clear and well organized.
If the question is not about events, politely say you only help with event planning."""

EVENT_TIPS = {
    "Birthday": "Focus on cake, theme, games, snacks, return gifts and entertainment.",
    "Wedding": "Focus on muhurtham timing, hall or mandapam, catering, decoration, photography, guest accommodation and rituals.",
    "Corporate Event": "Focus on venue, agenda, speakers, AV equipment, catering, registration and branding.",
    "Festival": "Focus on traditional decoration, pooja arrangements, food, cultural programs and community participation.",
    "Baby Shower": "Focus on theme, games, decoration, food, gifts and seating comfort.",
    "Other": "Ask the user for more details about the event if needed.",
}

QUICK_ACTIONS = {
    "🏪 Vendor Suggestions": "Tell me which vendors I need (catering, decorator, photographer, DJ, etc.), how to split my budget among them, and tips to choose each one.",
    "✅ To-Do List": "Create a to-do checklist with deadlines (like 2 weeks before, 1 week before, 1 day before) based on my event date.",
    "💌 Invitation Message": "Write a short, friendly WhatsApp invitation message for my event. Include the date and city, and leave a place for venue and time.",
    "🙏 Thank You Message": "Write a short thank you message that I can send to my guests after the event.",
}

WELCOME = {
    "English": "Hi! I am your event planner. Select your event details on the left, then type, speak 🎤 or click a Quick Action button.",
    "Telugu (తెలుగు)": "నమస్కారం! నేను మీ ఈవెంట్ ప్లానర్‌ని. ఎడమ వైపు మీ ఈవెంట్ వివరాలు ఎంచుకుని, టైప్ చేయండి, మాట్లాడండి 🎤 లేదా Quick Action బటన్ నొక్కండి.",
    "Hindi (हिन्दी)": "नमस्ते! मैं आपका इवेंट प्लानर हूँ। बाईं ओर अपने इवेंट की जानकारी चुनें, फिर टाइप करें, बोलें 🎤 या Quick Action बटन दबाएँ।",
}

# Language codes: speech recognition (voice in) and gTTS (voice out)
STT_CODES = {"English": "en-IN", "Telugu (తెలుగు)": "te-IN", "Hindi (हिन्दी)": "hi-IN"}
TTS_CODES = {"English": "en", "Telugu (తెలుగు)": "te", "Hindi (हिन्दी)": "hi"}


def speech_to_text(audio_bytes, language):
    """Voice (WAV) -> text. Needs internet. Returns (text, error)."""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language=STT_CODES[language])
        return text, None
    except sr.UnknownValueError:
        return None, "Voice artham kaaledu. Malli clear ga matladandi."
    except Exception as e:
        return None, f"Voice error: {e} (internet undo check chey)"


def text_to_speech(text, language):
    """Text -> MP3 audio bytes. Needs internet."""
    clean = re.sub(r"[*#_`>|-]", " ", text)[:1500]  # remove symbols, keep it short
    fp = io.BytesIO()
    gTTS(text=clean, lang=TTS_CODES[language]).write_to_fp(fp)
    return fp.getvalue()


st.set_page_config(page_title="AI Event Planning Assistant", page_icon="🎉")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None
if "last_audio_id" not in st.session_state:
    st.session_state.last_audio_id = None

# ---------- Sidebar ----------
st.sidebar.header("Event Details")
language = st.sidebar.selectbox(
    "Language / భాష", ["English", "Telugu (తెలుగు)", "Hindi (हिन्दी)"]
)
speak = st.sidebar.toggle("🔊 Read answers aloud", value=False)
event_type = st.sidebar.selectbox("Event Type", list(EVENT_TIPS.keys()))
event_date = st.sidebar.date_input("Event Date", date.today() + timedelta(days=30))
city = st.sidebar.text_input("City", "Hyderabad")
budget = st.sidebar.number_input("Budget (Rs)", min_value=0, value=20000, step=1000)
guests = st.sidebar.number_input("Guest Count", min_value=1, value=20, step=5)

st.sidebar.header("Quick Actions")
for label, question in QUICK_ACTIONS.items():
    if st.sidebar.button(label, use_container_width=True):
        st.session_state.pending = question

if st.sidebar.button("🗑️ Clear Chat", use_container_width=True):
    st.session_state.messages = []
    st.session_state.pending = None
    st.rerun()

days_left = (event_date - date.today()).days
system_prompt = (
    BASE_PROMPT
    + f"\n\nCurrent event details:"
    + f"\n- Event type: {event_type}"
    + f"\n- Event date: {event_date.strftime('%d %B %Y')} ({days_left} days from today)"
    + f"\n- City: {city}"
    + f"\n- Budget: Rs {budget}"
    + f"\n- Guests: {guests}"
    + f"\n\nEvent specific guidance: {EVENT_TIPS[event_type]}"
    + "\nUse these details in your suggestions. Consider the season and local context of the city."
    + f"\nIMPORTANT: Write your entire reply in {language}. Use simple, easy words that elders can understand."
)

# ---------- Main page ----------
st.title("🎉 AI Event Planning Assistant")
st.caption("Ask me anything about planning your event!")

# Voice input
voice_text = None
audio = st.audio_input("🎤 Speak your question (mic click chey, matladi, stop click chey)")
if audio is not None:
    audio_bytes = audio.getvalue()
    audio_id = hashlib.md5(audio_bytes).hexdigest()
    if audio_id != st.session_state.last_audio_id:  # process each recording only once
        st.session_state.last_audio_id = audio_id
        with st.spinner("Listening..."):
            voice_text, voice_error = speech_to_text(audio_bytes, language)
        if voice_error:
            st.warning(voice_error)

if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write(WELCOME[language])

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

typed = st.chat_input("Type your event question here...")
user_input = typed or voice_text or st.session_state.pending
st.session_state.pending = None

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system_prompt}]
        + st.session_state.messages,
        "stream": False,
    }

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(OLLAMA_URL, json=payload, timeout=180)
                response.raise_for_status()
                answer = response.json()["message"]["content"]
            except Exception as e:
                answer = f"Error: {e}. Check if Ollama is running."
        st.write(answer)

        # Voice output
        if speak and not answer.startswith("Error"):
            with st.spinner("Preparing voice..."):
                try:
                    st.audio(text_to_speech(answer, language), format="audio/mp3")
                except Exception as e:
                    st.caption(f"Voice output error: {e} (internet kavali)")

    st.session_state.messages.append({"role": "assistant", "content": answer})strea