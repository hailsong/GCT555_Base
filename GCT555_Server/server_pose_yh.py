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
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles

# Configuration
SOCKET_HOST = '0.0.0.0'
SOCKET_PORT = 5050
WEB_PORT = 5000
CAMERA_INDEX = 0
DEBUG_MODE = False
MODEL_PATH = 'models/pose_landmarker_heavy.task'

# Global variables to share data between threads
current_frame = None
current_landmarks_result = None
lock = threading.Lock()

# Initialize Flask
app = Flask(__name__)


# added by yh:
# Pose landmark indices (MediaPipe pose)
L_SHOULDER, R_SHOULDER = 11, 12
L_HIP, R_HIP = 23, 24

def compute_pose_depth_z(world_lms):
    """Return a robust representative depth (z) from pose world landmarks."""
    if world_lms is None:
        return None
    zs = []
    try:
        if len(world_lms) > R_HIP:
            mid_hip_z = 0.5 * (world_lms[L_HIP].z + world_lms[R_HIP].z)
            zs.append(mid_hip_z)
        if len(world_lms) > R_SHOULDER:
            mid_sh_z = 0.5 * (world_lms[L_SHOULDER].z + world_lms[R_SHOULDER].z)
            zs.append(mid_sh_z)
    except Exception:
        return None

    if not zs:
        return None
    return float(np.median(zs))
### 


def draw_landmarks_on_image(rgb_image, detection_result):
    pose_landmarks_list = detection_result.pose_landmarks
    annotated_image = np.copy(rgb_image)

    # Note: drawing_styles.get_default_pose_landmarks_style() might be missing in some versions
    # We can try to use it or define a custom one if it fails.
    # The user provided snippet suggests it works.
    try:
        pose_landmark_style = drawing_styles.get_default_pose_landmarks_style()
    except AttributeError:
        pose_landmark_style = drawing_utils.DrawingSpec(color=(255, 255, 255), thickness=1)

    pose_connection_style = drawing_utils.DrawingSpec(color=(0, 255, 0), thickness=2)

    for pose_landmarks in pose_landmarks_list:
        drawing_utils.draw_landmarks(
            image=annotated_image,
            landmark_list=pose_landmarks,
            connections=vision.PoseLandmarksConnections.POSE_LANDMARKS,
            landmark_drawing_spec=pose_landmark_style,
            connection_drawing_spec=pose_connection_style)

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
                        if current_landmarks_result and current_landmarks_result.pose_landmarks:
                            # Typically there's one pose, so we take the first list of landmarks
                            pose_landmarks = current_landmarks_result.pose_landmarks[0]
                            
                            landmarks_list = []
                            for lm in pose_landmarks:
                                landmarks_list.append({
                                    'x': lm.x,
                                    'y': lm.y,
                                    'z': lm.z,
                                    'visibility': lm.visibility
                                })
                            
                            # Also include world landmarks if needed?
                            # Unity usually wants normalized landmarks for 2D overlay or world landmarks for 3D?
                            # For "3D skeleton coordinates", pose_world_landmarks is better if available,
                            # but the standard pose_landmarks are normalized [0,1].
                            # detection_result.pose_world_landmarks provides meters-based coordinates.
                            
                            # modified by yh:
                            world_landmarks_list = []
                            world_obj = None
                            if current_landmarks_result.pose_world_landmarks:
                                world_obj = current_landmarks_result.pose_world_landmarks[0]
                                for lm in world_obj:
                                    world_landmarks_list.append({
                                        'x': lm.x,
                                        'y': lm.y,
                                        'z': lm.z,
                                        'visibility': lm.visibility
                                    })

                            depth_z = compute_pose_depth_z(world_obj)

                            data_to_send = json.dumps({
                                'landmarks': landmarks_list,
                                'world_landmarks': world_landmarks_list,
                                'depth_z': depth_z  # ✅ 추가
                            })
                            ###

                    
                    if data_to_send:
                        # Send data followed by a newline as a delimiter
                        client_socket.sendall((data_to_send + "\n").encode('utf-8'))
                    
                    # Sleep briefly to match typical frame rate
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
            
            # Encode the frame in JPEG format
            ret, buffer = cv2.imencode('.jpg', current_frame)
            frame_bytes = buffer.tobytes()

        # Yield the output frame in the byte format
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
    return "<h1>MediaPipe Pose Server</h1><p><a href='/video_feed'>View Stream</a></p>"

def main():
    global current_frame, current_landmarks_result

    # Start Socket Server thread
    t_socket = threading.Thread(target=socket_server_thread, daemon=True)
    t_socket.start()

    # Start Flask thread
    t_flask = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=WEB_PORT, debug=False, use_reloader=False), daemon=True)
    t_flask.start()
    print(f"[Web] Server running on http://localhost:{WEB_PORT}")

    # Set up MediaPipe Pose Landmarker
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        output_segmentation_masks=False)
    detector = vision.PoseLandmarker.create_from_options(options)

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

        # MediaPipe works with RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)

        # Detect pose landmarks
        detection_result = detector.detect(mp_image)

        # Process results
        
        # Create annotated image
        annotated_image = draw_landmarks_on_image(image, detection_result)
        
        # Convert back to BGR for OpenCV display and Streaming
        annotated_image_bgr = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)

        with lock:
            current_landmarks_result = detection_result
            current_frame = annotated_image_bgr

        if DEBUG_MODE:
            cv2.imshow('MediaPipe Pose - Server', annotated_image_bgr)
            if cv2.waitKey(5) & 0xFF == 27:
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
