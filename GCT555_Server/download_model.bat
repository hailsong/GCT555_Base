@echo off
if not exist "models" mkdir models

echo Downloading pose_landmarker_heavy.task...
powershell -Command "Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task' -OutFile 'models/pose_landmarker_heavy.task'"

echo Downloading hand_landmarker.task...
powershell -Command "Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task' -OutFile 'models/hand_landmarker.task'"

echo Downloading face_landmarker.task...
powershell -Command "Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task' -OutFile 'models/face_landmarker.task'"

if %errorlevel% neq 0 (
    echo A download failed!
    pause
    exit /b %errorlevel%
)
echo All downloads complete.
