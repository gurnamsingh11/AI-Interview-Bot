import streamlit as st
import threading
import time
import asyncio
from face_tracker.camera import generate_frames
from voice_assistant.main import run_audio_loop, set_stop_event

st.set_page_config(layout="wide", page_title="Voice + Vision AI Assistant")

# Initialize session state
if "voice_thread" not in st.session_state:
    st.session_state.voice_thread = None
if "voice_active" not in st.session_state:
    st.session_state.voice_active = False
if "camera_active" not in st.session_state:
    st.session_state.camera_active = False
if "camera_stop_event" not in st.session_state:
    st.session_state.camera_stop_event = threading.Event()

# Page header
st.title("AI Interview Bot")

# Create two columns: sidebar and main content
sidebar_col, main_col = st.columns([1, 3])

# Control panel in left column
with sidebar_col:
    st.header("Config")

    # Camera controls
    st.subheader("Camera")

    if st.button("🟢 Start Camera", key="start_camera", use_container_width=True):
        if not st.session_state.camera_active:
            st.session_state.camera_active = True
            st.session_state.camera_stop_event.clear()
            st.success("Camera starting...", icon="📹")

    if st.button("🔴 Stop Camera", key="stop_camera", use_container_width=True):
        if st.session_state.camera_active:
            st.session_state.camera_active = False
            st.session_state.camera_stop_event.set()
            st.info("Camera stopping...", icon="⏹️")

    camera_indicator = "🟢 Running" if st.session_state.camera_active else "⚪ Stopped"
    st.markdown(f"**Status:** {camera_indicator}")

    st.divider()

    # Voice assistant controls
    st.subheader("🎙️ Voice Assistant")

    if st.button("🟢 Start Voice", key="start_voice", use_container_width=True):
        if not st.session_state.voice_active:
            st.session_state.voice_active = True
            # Create a stop event for the voice assistant
            voice_stop_event = threading.Event()
            set_stop_event(voice_stop_event)
            st.session_state.voice_stop_event = voice_stop_event

            st.session_state.voice_thread = threading.Thread(
                target=run_audio_loop, daemon=True
            )
            st.session_state.voice_thread.start()
            st.success("Voice assistant starting...", icon="🎙️")

    if st.button("🔴 Stop Voice", key="stop_voice", use_container_width=True):
        if st.session_state.voice_active:
            st.session_state.voice_active = False
            if hasattr(st.session_state, "voice_stop_event"):
                st.session_state.voice_stop_event.set()
            st.info("Voice assistant stopping...", icon="⏹️")

    # Voice status
    voice_thread_alive = (
        st.session_state.voice_thread and st.session_state.voice_thread.is_alive()
    )

    if voice_thread_alive:
        voice_indicator = "🟢 Running"
    else:
        voice_indicator = "⚪ Stopped"
        # Auto-update voice status if thread died
        if st.session_state.voice_active and not voice_thread_alive:
            st.session_state.voice_active = False

    st.markdown(f"**Status:** {voice_indicator}")

    st.divider()


# Main content area
with main_col:
    if st.session_state.camera_active:
        st.markdown("### 🎯 Live Face Tracking")

        # Create the video container
        video_container = st.empty()

        # Import the camera stop event setter
        from face_tracker.camera import set_camera_stop_event

        set_camera_stop_event(st.session_state.camera_stop_event)

        # Run the camera loop
        try:
            frame_generator = generate_frames()

            for frame in frame_generator:
                # Check if we should stop
                if st.session_state.camera_stop_event.is_set():
                    break

                # Display the frame
                video_container.image(
                    frame,
                    channels="RGB",
                    use_container_width=True,
                    caption="Real-time face tracking with head pose detection",
                )

                # Small delay to prevent too rapid updates
                time.sleep(0.033)  # ~30 FPS

        except Exception as e:
            st.error(f"Camera error: {e}")
            st.session_state.camera_active = False

        finally:
            # Clear the video container when done
            if not st.session_state.camera_active:
                video_container.empty()

    else:
        # Welcome screen when camera is off
        st.markdown("### 📱 AI Powered Interviewer")

        # Hero section
        st.markdown(
            """
        <div style="text-align: center; padding: 2rem 0; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
                    border-radius: 10px; margin: 1rem 0; color: white;">
            <h2 style="margin: 0;">🚀 Ready to Get Started?</h2>
            <p style="margin: 0.5rem 0; font-size: 1.1em;">Activate camera and voice for the full AI experience!</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

# Periodic status update (only when camera is not active to avoid interference)
if not st.session_state.camera_active:
    time.sleep(1)  # Only refresh every second when camera is off
    st.rerun()
