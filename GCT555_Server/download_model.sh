#!/bin/bash
mkdir -p models

echo "Downloading pose_landmarker_heavy.task..."
curl -L "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task" -o "models/pose_landmarker_heavy.task"

echo "Downloading hand_landmarker.task..."
curl -L "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" -o "models/hand_landmarker.task"

echo "Downloading face_landmarker.task..."
curl -L "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" -o "models/face_landmarker.task"

if [ $? -ne 0 ]; then
    echo "A download failed!"
    exit 1
fi

echo "All downloads complete."
