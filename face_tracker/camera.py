import cv2
import numpy as np
import mediapipe as mp

mp_face = mp.solutions.face_mesh
face_mesh = mp_face.FaceMesh(min_detection_confidence=0.6, min_tracking_confidence=0.5)


def generate_frames():
    cap = cv2.VideoCapture(0)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

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
                    frame, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2
                )

        yield cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    cap.release()
