using System;
using System.Collections.Generic;
using UnityEngine;

[Serializable]
public class Landmark
{
    public float x;
    public float y;
    public float z;
    public float visibility;
    public Vector3 worldPosition;
}

[Serializable]
public class PoseData
{
    public List<Landmark> landmarks;
    public List<Landmark> world_landmarks;
}

[Serializable]
public class Hand
{
    public string handedness;
    public List<Landmark> landmarks;
    public List<Landmark> world_landmarks;
}

[Serializable]
public class HandData
{
    public List<Hand> hands;
}

[Serializable]
public class Face
{
    public List<Landmark> landmarks;
}

[Serializable]
public class FaceData
{
    public List<Face> faces;
    // Blendshapes parsing might need a custom parser or different structure depending on JsonUtility limits
    // but for now we focus on landmarks.
}
