import cv2
import mediapipe as mp
import socket
import threading
import json
import time
import numpy as np
from flask import Flask, Response

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Configuration
SOCKET_HOST = '0.0.0.0'
SOCKET_PORT = 5052
WEB_PORT = 5002
CAMERA_INDEX = 0
DEBUG_MODE = True
MODEL_PATH = 'models/face_landmarker.task'

# Global variables to share data between threads
current_frame = None
current_landmarks_result = None
lock = threading.Lock()

# Flask
app = Flask(__name__)

def draw_landmarks_on_image(rgb_image, detection_result):
    annotated_image = np.copy(rgb_image)
    height, width, _ = annotated_image.shape

    # Drawing 478 landmarks for face is too cluttering if we draw connections manually
    # Just draw points for now, or a subset.
    
    if detection_result.face_landmarks:
        for face_landmarks in detection_result.face_landmarks:
             for lm in face_landmarks:
                 x = int(lm.x * width)
                 y = int(lm.y * height)
                 cv2.circle(annotated_image, (x, y), 1, (0, 255, 255), -1)
    
    return annotated_image

def socket_server_thread():
    """Handles the socket connection to Unity."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_socket.bind((SOCKET_HOST, SOCKET_PORT))
        server_socket.listen(1)
        print(f"[Socket] Listening on {SOCKET_HOST}:{SOCKET_PORT}")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"[Socket] Connected by {addr}")
            try:
                while True:
                    global current_landmarks_result
                    data_to_send = None
                    
                    with lock:
                        if current_landmarks_result and current_landmarks_result.face_landmarks:
                            faces_data = []
                            for face_landmarks in current_landmarks_result.face_landmarks:
                                landmarks_list = []
                                for lm in face_landmarks:
                                    landmarks_list.append({
                                        'x': lm.x,
                                        'y': lm.y,
                                        'z': lm.z,
                                        'visibility': lm.visibility if hasattr(lm, 'visibility') else 1.0
                                    })
                                faces_data.append({'landmarks': landmarks_list})
                            
                            # Also Blendshapes if available
                            blendshapes_data = []
                            if current_landmarks_result.face_blendshapes:
                                for face_blendshapes in current_landmarks_result.face_blendshapes:
                                    # face_blendshapes is a list of categories
                                    shapes = {}
                                    for category in face_blendshapes:
                                        shapes[category.category_name] = category.score
                                    blendshapes_data.append(shapes)

                            data_to_send = json.dumps({
                                'faces': faces_data,
                                'blendshapes': blendshapes_data
                            })
                    
                    if data_to_send:
                        client_socket.sendall((data_to_send + "\n").encode('utf-8'))
                    
                    time.sleep(0.033) 
            except (ConnectionResetError, BrokenPipeError):
                print(f"[Socket] Disconnected from {addr}")
            finally:
                client_socket.close()

    except Exception as e:
        print(f"[Socket] Server Error: {e}")
    finally:
        server_socket.close()

def generate_frames():
    while True:
        with lock:
            if current_frame is None:
                time.sleep(0.01)
                continue
            ret, buffer = cv2.imencode('.jpg', current_frame)
            frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/snapshot')
def snapshot():
    with lock:
        if current_frame is None:
            return "No frame", 503
        ret, buffer = cv2.imencode('.jpg', current_frame)
        return Response(buffer.tobytes(), mimetype='image/jpeg')

@app.route('/')
def index():
    return "<h1>MediaPipe Face Server</h1><p><a href='/video_feed'>View Stream</a></p>"

def main():
    global current_frame, current_landmarks_result

    # Start Socket Server
    t_socket = threading.Thread(target=socket_server_thread, daemon=True)
    t_socket.start()

    # Start Flask
    t_flask = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False), daemon=True)
    t_flask.start()
    print(f"[Web] Server running on http://localhost:{WEB_PORT}")

    # Set up MediaPipe Face Landmarker
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
        num_faces=1)
    detector = vision.FaceLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    print("Starting Main Loop...")
    while cap.isOpened():
        success, image = cap.read()
        if not success:
            print("Ignoring empty camera frame.")
            continue

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)

        detection_result = detector.detect(mp_image)

        annotated_image = draw_landmarks_on_image(image, detection_result)
        annotated_image_bgr = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)

        with lock:
            current_landmarks_result = detection_result
            current_frame = annotated_image_bgr

        if DEBUG_MODE:
            cv2.imshow('MediaPipe Face - Server', annotated_image_bgr)
            if cv2.waitKey(5) & 0xFF == 27:
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
