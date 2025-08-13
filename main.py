# import asyncio
# import threading

# from voice_to_voice.main import run_audio_loop # FOR REAL TIME TALKING WITH AI ASSISTANT
# from face_tracker.main import run_eye_tracker # RUNS CAMERA FEED IN WEBCAM AND LOGS THE TRACKER ON THE CAMERA SCREEN ITSELF

# async def main():
#     eye_tracker_thread = threading.Thread(target=run_eye_tracker, daemon=True)
#     eye_tracker_thread.start()

#     await asyncio.to_thread(run_audio_loop)

# if __name__ == "__main__":
#     asyncio.run(main())


import streamlit as st
import threading
import asyncio
import time

from voice_to_voice.main import run_audio_loop
from face_tracker.main import run_eye_tracker

# Global control flags
stop_flag = False

def audio_loop_wrapper():
    global stop_flag
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while not stop_flag:
        loop.run_until_complete(run_audio_loop())

def eye_tracker_wrapper():
    global stop_flag
    while not stop_flag:
        run_eye_tracker()

# Streamlit UI
st.title("AI Assistant Control Panel")

if "threads" not in st.session_state:
    st.session_state.threads = []

col1, col2 = st.columns(2)

with col1:
    if st.button("▶ Start Assistant"):
        stop_flag = False
        audio_thread = threading.Thread(target=audio_loop_wrapper, daemon=True)
        eye_thread = threading.Thread(target=eye_tracker_wrapper, daemon=True)
        audio_thread.start()
        eye_thread.start()
        st.session_state.threads = [audio_thread, eye_thread]
        st.success("Assistant started!")

with col2:
    if st.button("⏹ Stop Assistant"):
        stop_flag = True
        st.warning("Stopping assistant...")
        time.sleep(1)  # Give threads time to close
        st.success("Assistant stopped.")

# Status
if not st.session_state.threads:
    st.info("Assistant is idle.")
else:
    st.info("Assistant is running...")
