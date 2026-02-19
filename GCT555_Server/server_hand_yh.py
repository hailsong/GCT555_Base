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
SOCKET_PORT = 5051
WEB_PORT = 5001
CAMERA_INDEX = 0
DEBUG_MODE = True
MODEL_PATH = 'models/hand_landmarker.task'

# Global variables to share data between threads
current_frame = None
current_landmarks_result = None
lock = threading.Lock()

# Initialize Flask
app = Flask(__name__)

# MediaPipe Hand Connections (Standard)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),           # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),           # Index
    (0, 9), (9, 10), (10, 11), (11, 12),      # Middle
    (0, 13), (13, 14), (14, 15), (15, 16),    # Ring
    (0, 17), (17, 18), (18, 19), (19, 20)     # Pinky
]

def draw_landmarks_on_image(rgb_image, detection_result):
    annotated_image = np.copy(rgb_image)
    height, width, _ = annotated_image.shape

    if detection_result.hand_landmarks:
        for hand_landmarks in detection_result.hand_landmarks:
            # Draw connections
            for connection in HAND_CONNECTIONS:
                start_idx = connection[0]
                end_idx = connection[1]
                
                start_lm = hand_landmarks[start_idx]
                end_lm = hand_landmarks[end_idx]
                
                start_point = (int(start_lm.x * width), int(start_lm.y * height))
                end_point = (int(end_lm.x * width), int(end_lm.y * height))
                
                cv2.line(annotated_image, start_point, end_point, (0, 255, 0), 2)
                
            # Draw landmarks
            for lm in hand_landmarks:
                x = int(lm.x * width)
                y = int(lm.y * height)
                cv2.circle(annotated_image, (x, y), 3, (0, 0, 255), -1)

    return annotated_image


### added by yh:
# 손바닥 대표점 인덱스 (palm 주변)
PALM_IDXS = [0, 5, 9, 13, 17]

def robust_palm_depth_z(world_lms):
    # world_lms: list of dict-like or landmark objects with .z
    zs = [world_lms[i].z for i in PALM_IDXS if i < len(world_lms)]
    if not zs:
        return None
    return float(np.median(zs))  # median이 안정적
###


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
                        if current_landmarks_result and current_landmarks_result.hand_landmarks:
                            hands_data = []
                            
                            for idx, hand_landmarks in enumerate(current_landmarks_result.hand_landmarks):
                                landmarks_list = []
                                for lm in hand_landmarks:
                                    landmarks_list.append({
                                        'x': lm.x,
                                        'y': lm.y,
                                        'z': lm.z,
                                        'visibility': lm.visibility if hasattr(lm, 'visibility') else 1.0
                                    })
                                

                                # modified by yh:
                                world_landmarks_list = []
                                world_obj_list = None

                                if current_landmarks_result.hand_world_landmarks and idx < len(current_landmarks_result.hand_world_landmarks):
                                    world_obj_list = current_landmarks_result.hand_world_landmarks[idx]
                                    for lm in world_obj_list:
                                        world_landmarks_list.append({'x': lm.x, 'y': lm.y, 'z': lm.z, 'visibility': 1.0})

                                label = "Unknown"
                                if current_landmarks_result.handedness:
                                    # handedness is a list of lists of categories
                                    if idx < len(current_landmarks_result.handedness) and len(current_landmarks_result.handedness[idx]) > 0:
                                        label = current_landmarks_result.handedness[idx][0].category_name

                                #depth_z = None
                                #if world_obj_list is not None:
                                    #depth_z = robust_palm_depth_z(world_obj_list)

                                #hands_data.append({
                                    #'handedness': label,
                                    #'landmarks': landmarks_list,
                                    #'world_landmarks': world_landmarks_list,
                                    #'depth_z': depth_z  # 추가
                                #})

                                hand_payload = {
                                    'handedness': label,
                                    'landmarks': landmarks_list,
                                    'world_landmarks': world_landmarks_list,
                                }

                                depth_z = None
                                if world_obj_list is not None:
                                    depth_z = robust_palm_depth_z(world_obj_list)

                                # ✅ None이면 key를 넣지 않는다
                                if depth_z is not None:
                                    hand_payload['depth_z'] = depth_z

                                hands_data.append(hand_payload)

                                ## 

                                
                            data_to_send = json.dumps({
                                'hands': hands_data
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
    """Generator function for the Flask video stream."""
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
    return "<h1>MediaPipe Hand Server</h1><p><a href='/video_feed'>View Stream</a></p>"

def main():
    global current_frame, current_landmarks_result

    # Start Socket Server thread
    t_socket = threading.Thread(target=socket_server_thread, daemon=True)
    t_socket.start()

    # Start Flask thread
    t_flask = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False), daemon=True)
    t_flask.start()
    print(f"[Web] Server running on http://localhost:{WEB_PORT}")

    # Set up MediaPipe Hand Landmarker
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=2)
    detector = vision.HandLandmarker.create_from_options(options)

    # Video Capture
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

        # Draw using simplified CV2 logic
        annotated_image = draw_landmarks_on_image(image, detection_result)
        
        annotated_image_bgr = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)

        with lock:
            current_landmarks_result = detection_result
            current_frame = annotated_image_bgr

        if DEBUG_MODE:
            cv2.imshow('MediaPipe Hand - Server', annotated_image_bgr)
            if cv2.waitKey(5) & 0xFF == 27:
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
