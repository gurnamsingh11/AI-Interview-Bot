import sys
import threading
import time
import cv2
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QFileDialog,
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QTimer
import PyPDF2
import io
from face_tracker.camera import generate_frames, set_camera_stop_event
from voice_assistant.main import run_audio_loop, set_stop_event, set_jd_cr


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
        return e


class InterviewBotUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Interview Bot")
        self.setGeometry(200, 100, 1200, 700)

        # State
        self.camera_active = False
        self.voice_active = False
        self.stop_event = threading.Event()

        # Layout
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # --- Left Panel (Config) ---
        left_panel = QVBoxLayout()

        # JD Input
        self.jd_text = QTextEdit()
        self.jd_text.setPlaceholderText("Paste Job Description here...")
        left_panel.addWidget(QLabel("📝 Job Description"))
        left_panel.addWidget(self.jd_text)

        # Resume Upload
        self.resume_btn = QPushButton("📄 Upload Resume (PDF)")
        self.resume_btn.clicked.connect(self.load_resume)
        left_panel.addWidget(self.resume_btn)

        # Camera controls
        self.start_cam_btn = QPushButton("🟢 Start Camera")
        self.stop_cam_btn = QPushButton("🔴 Stop Camera")
        self.start_cam_btn.clicked.connect(self.start_camera)
        self.stop_cam_btn.clicked.connect(self.stop_camera)
        left_panel.addWidget(self.start_cam_btn)
        left_panel.addWidget(self.stop_cam_btn)

        # Voice controls
        self.start_voice_btn = QPushButton("🟢 Start Voice Assistant")
        self.stop_voice_btn = QPushButton("🔴 Stop Voice Assistant")
        self.start_voice_btn.clicked.connect(self.start_voice)
        self.stop_voice_btn.clicked.connect(self.stop_voice)
        left_panel.addWidget(self.start_voice_btn)
        left_panel.addWidget(self.stop_voice_btn)

        main_layout.addLayout(left_panel, 1)

        # --- Right Panel (Main content / video) ---
        self.video_label = QLabel(
            "📱 AI Powered Interviewer\n\n(Activate camera to start)"
        )
        self.video_label.setStyleSheet(
            "QLabel { background: #333; color: white; padding: 20px; }"
        )
        self.video_label.setFixedSize(900, 600)
        main_layout.addWidget(self.video_label, 3)

        # Timer for updating video frames
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

    def load_resume(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Upload Resume", "", "PDF Files (*.pdf)"
        )
        if file_path:
            print("Resume uploaded:", file_path)
            extracted_text = extract_text_from_pdf(file_path)
            # TODO: Extract PDF text and call set_jd_cr(self.jd_text, extracted_text)
            return set_jd_cr(self.jd_text, extracted_text)

    def start_camera(self):
        if not self.camera_active:
            self.camera_active = True
            self.stop_event.clear()
            set_camera_stop_event(self.stop_event)
            self.frame_generator = generate_frames()
            self.timer.start(30)  # ~30 FPS

    def stop_camera(self):
        if self.camera_active:
            self.camera_active = False
            self.stop_event.set()
            self.timer.stop()
            self.video_label.setText("📱 AI Powered Interviewer\n\n(Camera stopped)")

    def update_frame(self):
        if self.camera_active:
            try:
                frame = next(self.frame_generator)
                h, w, ch = frame.shape
                img = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)
                pix = QPixmap.fromImage(img)
                self.video_label.setPixmap(
                    pix.scaled(self.video_label.width(), self.video_label.height())
                )
            except StopIteration:
                self.stop_camera()

    def start_voice(self):
        if not self.voice_active:
            self.voice_active = True
            self.voice_thread = threading.Thread(target=run_audio_loop, daemon=True)
            self.voice_thread.start()

    def stop_voice(self):
        if self.voice_active:
            self.voice_active = False
            set_stop_event(self.stop_event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InterviewBotUI()
    window.show()
    sys.exit(app.exec())
