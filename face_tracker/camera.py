import cv2
import numpy as np
import mediapipe as mp
import threading

mp_face = mp.solutions.face_mesh
face_mesh = mp_face.FaceMesh(min_detection_confidence=0.6, min_tracking_confidence=0.5)

# Global stop event for camera control
_camera_stop_event = None


def set_camera_stop_event(stop_event):
    """Set the global stop event for controlling camera"""
    global _camera_stop_event
    _camera_stop_event = stop_event


def generate_frames():
    """Generate camera frames with face tracking - matches original exactly"""
    global _camera_stop_event

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open camera")
        return

    print("📹 Camera started")

    try:
        while cap.isOpened():
            # Check if we should stop
            if _camera_stop_event and _camera_stop_event.is_set():
                print("🛑 Camera stop signal received")
                break

            ret, frame = cap.read()
            if not ret:
                break

            # Exact same processing as original
            frame = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
            results = face_mesh.process(frame)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            img_h, img_w, _ = frame.shape
            face_3d, face_2d = [], []

            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    for idx, lm in enumerate(face_landmarks.landmark):
                        if idx in [33, 263, 1, 61, 291, 199]:
                            x, y = int(lm.x * img_w), int(lm.y * img_h)
                            face_2d.append([x, y])
                            face_3d.append([x, y, lm.z])

                    face_2d = np.array(face_2d, dtype=np.float64)
                    face_3d = np.array(face_3d, dtype=np.float64)

                    focal_length = img_w
                    center = (img_w / 2, img_h / 2)
                    camera_matrix = np.array(
                        [
                            [focal_length, 0, center[0]],
                            [0, focal_length, center[1]],
                            [0, 0, 1],
                        ]
                    )
                    dist_coeffs = np.zeros((4, 1), dtype=np.float64)
                    success, rotation_vector, translation_vector = cv2.solvePnP(
                        face_3d, face_2d, camera_matrix, dist_coeffs
                    )
                    rmat = cv2.Rodrigues(rotation_vector)[0]
                    angles, *_ = cv2.RQDecomp3x3(rmat)
                    x_angle, y_angle = angles[0] * 360, angles[1] * 360

                    if y_angle < -15 or y_angle > 15 or x_angle < -7 or x_angle > 20:
                        text = "Not Looking Forward"
                    else:
                        text = "Looking Forward"

                    cv2.putText(
                        frame,
                        text,
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 0, 255),
                        2,
                    )

            yield cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    except Exception as e:
        print(f"Error in camera processing: {e}")
    finally:
        cap.release()
        print("📹 Camera stopped and released")


class CameraManager:
    """Camera manager class for better control"""

    def __init__(self):
        self.cap = None
        self.is_running = False
        self.stop_event = threading.Event()

    def start(self):
        """Start camera capture"""
        if self.is_running:
            return False

        self.stop_event.clear()
        self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            print("Error: Could not open camera")
            return False

        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.is_running = True
        print("📹 Camera manager started")
        return True

    def stop(self):
        """Stop camera capture"""
        if not self.is_running:
            return

        self.stop_event.set()
        self.is_running = False

        if self.cap:
            self.cap.release()
            self.cap = None

        print("📹 Camera manager stopped")

    def get_frame(self):
        """Get a single frame with face tracking"""
        if not self.is_running or not self.cap:
            return None

        ret, frame = self.cap.read()
        if not ret:
            return None

        # Process frame with face tracking (exact same logic as original)
        frame = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
        results = face_mesh.process(frame)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        img_h, img_w, _ = frame.shape
        face_3d, face_2d = [], []

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                # Reset arrays for each face
                face_3d, face_2d = [], []

                for idx, lm in enumerate(face_landmarks.landmark):
                    if idx in [33, 263, 1, 61, 291, 199]:
                        x, y = int(lm.x * img_w), int(lm.y * img_h)
                        face_2d.append([x, y])
                        face_3d.append([x, y, lm.z])

                # Only proceed if we have the expected number of landmarks
                if len(face_2d) == 6 and len(face_3d) == 6:
                    face_2d = np.array(face_2d, dtype=np.float64)
                    face_3d = np.array(face_3d, dtype=np.float64)

                    focal_length = img_w
                    center = (img_w / 2, img_h / 2)
                    camera_matrix = np.array(
                        [
                            [focal_length, 0, center[0]],
                            [0, focal_length, center[1]],
                            [0, 0, 1],
                        ]
                    )

                    dist_coeffs = np.zeros((4, 1), dtype=np.float64)
                    success, rotation_vector, translation_vector = cv2.solvePnP(
                        face_3d, face_2d, camera_matrix, dist_coeffs
                    )

                    if success:
                        rmat = cv2.Rodrigues(rotation_vector)[0]
                        angles, *_ = cv2.RQDecomp3x3(rmat)
                        x_angle, y_angle = angles[0] * 360, angles[1] * 360

                        # Use the exact same logic as original
                        if (
                            y_angle < -15
                            or y_angle > 15
                            or x_angle < -7
                            or x_angle > 20
                        ):
                            text = "Not Looking Forward"
                            color = (0, 0, 255)  # Red
                        else:
                            text = "Looking Forward"
                            color = (0, 255, 0)  # Green

                        # Use the same text positioning as original
                        cv2.putText(
                            frame, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2
                        )

                        # Add debug info (optional)
                        debug_text = f"Pitch: {x_angle:.1f}° Yaw: {y_angle:.1f}°"
                        cv2.putText(
                            frame,
                            debug_text,
                            (20, 80),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (255, 255, 255),
                            1,
                        )
        else:
            # No face detected
            cv2.putText(
                frame,
                "No Face Detected",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 0),
                2,
            )

        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
