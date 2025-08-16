import streamlit as st
import threading
from face_tracker.camera import generate_frames
from voice_assistant.main import run_audio_loop
import cv2
import time

st.set_page_config(layout="wide")
st.title("🎥 Voice + Vision AI Assistant")

col1, col2 = st.columns(2)

# Camera feed placeholder
camera_placeholder = col1.empty()

# Voice assistant controls
if "voice_thread" not in st.session_state:
    st.session_state.voice_thread = None

if col2.button("Start Voice Assistant"):
    if (
        st.session_state.voice_thread is None
        or not st.session_state.voice_thread.is_alive()
    ):
        st.session_state.voice_thread = threading.Thread(
            target=run_audio_loop, daemon=True
        )
        st.session_state.voice_thread.start()
        col2.write("🎙 Voice Assistant Started")

if col2.button("Stop Voice Assistant"):
    st.warning("Stopping voice assistant is not implemented — restart app to stop.")

# Run camera feed
for frame in generate_frames():
    camera_placeholder.image(frame)
    time.sleep(0.03)  # ~30 FPS
