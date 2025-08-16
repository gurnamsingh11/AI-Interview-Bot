import streamlit as st
import threading
import time
import asyncio
import PyPDF2
import io
from face_tracker.camera import generate_frames
from voice_assistant.main import run_audio_loop, set_stop_event, set_jd_cr

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
if "jd_text" not in st.session_state:
    st.session_state.jd_text = ""
if "cr_text" not in st.session_state:
    st.session_state.cr_text = ""
if "uploaded_pdf" not in st.session_state:
    st.session_state.uploaded_pdf = None
if "pdf_extracted_text" not in st.session_state:
    st.session_state.pdf_extracted_text = ""

# Page header
st.title("AI Interview Bot")

# Create two columns: sidebar and main content
sidebar_col, main_col = st.columns([1, 3])

# Control panel in left column
with sidebar_col:
    st.header("Config")

    # Job Description and Candidate Resume Input
    st.subheader("📝 Interview Setup")

    # Job Description input
    jd_input = st.text_area(
        "Job Description",
        value=st.session_state.jd_text,
        height=150,
        placeholder="Paste the job description here...",
        help="Enter the job description for the interview",
    )

    # Function to extract text from PDF
    def extract_text_from_pdf(pdf_file):
        """Extract text from uploaded PDF file"""
        try:
            # Read the PDF file
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file.read()))

            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"

            return text.strip()
        except Exception as e:
            st.error(f"Error extracting text from PDF: {str(e)}")
            return ""

    # Candidate Resume PDF upload
    st.markdown("**Candidate Resume**")
    uploaded_file = st.file_uploader(
        "Upload Resume (PDF)",
        type=["pdf"],
        help="Upload the candidate's resume in PDF format",
        label_visibility="collapsed",
    )

    # Process uploaded PDF
    if uploaded_file is not None:
        if uploaded_file != st.session_state.uploaded_pdf:
            # New file uploaded
            st.session_state.uploaded_pdf = uploaded_file

            with st.spinner("Extracting text from PDF..."):
                extracted_text = extract_text_from_pdf(uploaded_file)
                st.session_state.pdf_extracted_text = extracted_text
                st.session_state.cr_text = extracted_text

                if extracted_text:
                    st.success(
                        f"✅ Resume text extracted successfully! ({len(extracted_text)} characters)"
                    )
                else:
                    st.error(
                        "❌ Failed to extract text from PDF. Please try a different file."
                    )

    # Show extracted text preview (optional - can be collapsed)
    if st.session_state.pdf_extracted_text:
        with st.expander("📄 View Extracted Resume Text", expanded=False):
            st.text_area(
                "Extracted Text Preview",
                value=st.session_state.pdf_extracted_text,
                height=200,
                disabled=True,
                label_visibility="collapsed",
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Re-extract Text", help="Re-process the uploaded PDF"):
                    if st.session_state.uploaded_pdf:
                        with st.spinner("Re-extracting text..."):
                            extracted_text = extract_text_from_pdf(
                                st.session_state.uploaded_pdf
                            )
                            st.session_state.pdf_extracted_text = extracted_text
                            st.session_state.cr_text = extracted_text
                            st.rerun()

            with col2:
                if st.button("🗑️ Clear Resume", help="Remove the uploaded resume"):
                    st.session_state.uploaded_pdf = None
                    st.session_state.pdf_extracted_text = ""
                    st.session_state.cr_text = ""
                    st.rerun()

    # Update session state when JD input changes
    if jd_input != st.session_state.jd_text:
        st.session_state.jd_text = jd_input
        # Update the global variables in voice assistant
        set_jd_cr(jd_input, st.session_state.cr_text)

    # Update voice assistant when CR changes (from PDF extraction)
    if st.session_state.cr_text:
        set_jd_cr(st.session_state.jd_text, st.session_state.cr_text)

    # Show status of JD and CR
    jd_status = "✅ Ready" if st.session_state.jd_text.strip() else "❌ Missing"
    cr_status = "✅ Ready" if st.session_state.cr_text.strip() else "❌ Missing"

    st.markdown(f"**JD Status:** {jd_status}")
    st.markdown(f"**Resume Status:** {cr_status}")

    # Warning if either is missing
    if not st.session_state.jd_text.strip() or not st.session_state.cr_text.strip():
        st.warning(
            "⚠️ Please provide both Job Description and Candidate Resume before starting the voice assistant.",
            icon="⚠️",
        )

    st.divider()

    # Camera controls
    st.subheader("📹 Camera")

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

    # Check if JD and CR are provided
    can_start_voice = bool(
        st.session_state.jd_text.strip() and st.session_state.cr_text.strip()
    )

    if st.button(
        "🟢 Start Voice",
        key="start_voice",
        use_container_width=True,
        disabled=not can_start_voice,
    ):
        if not st.session_state.voice_active and can_start_voice:
            # Set JD and CR before starting
            set_jd_cr(st.session_state.jd_text, st.session_state.cr_text)

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

    # Show helpful tip when voice is disabled
    if not can_start_voice:
        st.info(
            "💡 Complete the Job Description and Resume fields above to enable voice assistant",
            icon="💡",
        )

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
            <p style="margin: 0.5rem 0; font-size: 1.1em;">Complete the interview setup, then activate camera and voice for the full AI experience!</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Interview setup status
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📋 Setup Checklist")
            setup_items = [
                ("Job Description", "✅" if st.session_state.jd_text.strip() else "❌"),
                (
                    "Candidate Resume",
                    "✅" if st.session_state.cr_text.strip() else "❌",
                ),
                ("Camera Ready", "✅" if st.session_state.camera_active else "⏸️"),
                ("Voice Assistant", "✅" if st.session_state.voice_active else "⏸️"),
            ]

            for item, status in setup_items:
                st.markdown(f"**{item}:** {status}")

        with col2:
            st.markdown("#### 🎯 Next Steps")
            if not st.session_state.jd_text.strip():
                st.markdown("1. 📝 Add Job Description")
            elif not st.session_state.cr_text.strip():
                st.markdown("1. 📄 Add Candidate Resume")
            elif not st.session_state.voice_active:
                st.markdown("1. 🎙️ Start Voice Assistant")
                st.markdown("2. 📹 Start Camera (optional)")
            else:
                st.markdown("✨ **All set! Interview ready to begin.**")

# Periodic status update (only when camera is not active to avoid interference)
if not st.session_state.camera_active:
    time.sleep(1)  # Only refresh every second when camera is off
    st.rerun()
