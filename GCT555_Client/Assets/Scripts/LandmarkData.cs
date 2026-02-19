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
    public float depth_z; // added by yh
}

[Serializable]
public class Hand
{
    public string handedness;
    public List<Landmark> landmarks;
    public List<Landmark> world_landmarks;
    public float depth_z; // added by yh
}

[Serializable]
public class HandData
{
    public List<Hand> hands;
}


// added by yh:

/*
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
*/

[Serializable]
public class FacePose
{
    public float tx;
    public float ty;
    public float tz;
}

[Serializable]
public class Face
{
    public List<Landmark> landmarks;
    public FacePose face_pose;   // 추가
}

[Serializable]
public class FaceData
{
    public List<Face> faces;
}
