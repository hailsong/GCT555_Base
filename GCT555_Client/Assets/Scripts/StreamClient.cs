using System;
using System.Collections;
using System.Collections.Generic;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

public class StreamClient : MonoBehaviour
{
    public enum ClientType { Pose, Hand, Face }

    [Header("Connection Settings")]
    public string ipAddress = "127.0.0.1";
    public int port = 5050;
    public ClientType clientType;
    public bool autoConnect = true;

    [Header("Visualization")]
    public GameObject landmarkPrefab; 
    public float landmarkScale = 0.04f;
    public float depthMultiplier = 10.0f; 
    public Vector3 positionOffset = new Vector3(0, 0, -0.2f); // Offset to bring closer/push back
    public bool usePseudoDepth = true;
    public float depthScale = 2.0f;
    public bool invertDepth = false;
    public bool mirrorX = true; // Default to true for "Mirror" feel on webcam
    public Transform visualizationRoot; 
    public QuadDisplay quadDisplay;

    private TcpClient socket;
    private NetworkStream stream;
    private Thread receiveThread;
    private bool isRunning = false;
    private bool dataReceived = false;
    private string latestJsonData = "";
    private List<GameObject> spawnedLandmarks = new List<GameObject>();
    public List<Landmark> activeLandmarks;

    void Start()
    {
        if (autoConnect) Connect();
    }

    void OnDestroy()
    {
        Disconnect();
    }

    public void Connect()
    {
        if (isRunning) return;
        try
        {
            socket = new TcpClient();
            socket.Connect(ipAddress, port);
            stream = socket.GetStream();
            isRunning = true;
            receiveThread = new Thread(ReceiveData);
            receiveThread.IsBackground = true;
            receiveThread.Start();
            Debug.Log($"[{clientType}] Connected to {ipAddress}:{port}");
        }
        catch (Exception e) { Debug.LogError($"[{clientType}] Connection Error: {e.Message}"); }
    }

    public void Disconnect()
    {
        isRunning = false;
        if (receiveThread != null && receiveThread.IsAlive) receiveThread.Join(100);
        if (stream != null) stream.Close();
        if (socket != null) socket.Close();
    }

    private void ReceiveData()
    {
        byte[] buffer = new byte[16384]; 
        StringBuilder jsonBuilder = new StringBuilder();

        while (isRunning)
        {
            try
            {
                if (stream.DataAvailable)
                {
                    int bytesRead = stream.Read(buffer, 0, buffer.Length);
                    string chunk = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                    jsonBuilder.Append(chunk);

                    string currentStr = jsonBuilder.ToString();
                    int newlineIndex;
                    while ((newlineIndex = currentStr.IndexOf('\n')) != -1)
                    {
                        string jsonLine = currentStr.Substring(0, newlineIndex);
                        latestJsonData = jsonLine;
                        dataReceived = true;
                        currentStr = currentStr.Substring(newlineIndex + 1);
                    }
                    jsonBuilder.Clear();
                    jsonBuilder.Append(currentStr);
                }
                else Thread.Sleep(5);
            }
            catch (Exception) { isRunning = false; }
        }
    }

    void Update()
    {
        if (dataReceived)
        {
            dataReceived = false;
            ProcessData(latestJsonData);
        }
    }

    private void ProcessData(string json)
    {
        try
        {
            switch (clientType)
            {
                case ClientType.Pose:
                    PoseData pose = JsonUtility.FromJson<PoseData>(json);
                    if (pose != null)
                    {
                        // Reverting to Hybrid/Normalized Visuals
                        UpdateHybridVisuals(pose.landmarks, pose.world_landmarks); 
                    }
                    break;
                case ClientType.Hand:
                    HandData handData = JsonUtility.FromJson<HandData>(json);
                    if (handData != null && handData.hands != null)
                    {
                        List<Landmark> allNorm = new List<Landmark>();
                        List<Landmark> allWorld = new List<Landmark>();
                        
                        foreach(var hand in handData.hands)
                        {
                            allNorm.AddRange(hand.landmarks);
                             // If world exists, add it, otherwise fill with nulls to stay consistent index-wise
                            if (hand.world_landmarks != null && hand.world_landmarks.Count > 0)
                                allWorld.AddRange(hand.world_landmarks);
                            else
                                // fill dummy to keep counts synced if mixing (shouldn't happen if server consistent)
                                for(int i=0; i<hand.landmarks.Count; i++) allWorld.Add(null);
                        }
                        UpdateHybridVisuals(allNorm, allWorld); 
                    }
                    break;
                case ClientType.Face:
                    FaceData faceData = JsonUtility.FromJson<FaceData>(json);
                    if (faceData != null && faceData.faces != null)
                    {
                         List<Landmark> allFaces = new List<Landmark>();
                        foreach(var face in faceData.faces) allFaces.AddRange(face.landmarks);
                        // Face currently no world landmarks support in this script
                        UpdateHybridVisuals(allFaces, null); 
                    }
                    break;
            }
        }
        catch (Exception e) { Debug.LogError($"JSON Parse Error: {e.Message}"); }
    }

    private void UpdateHybridVisuals(List<Landmark> normalized, List<Landmark> world)
    {
        // Check availability
        bool useWorld = (world != null && world.Count == normalized.Count && world.Count > 0 && world[0] != null);
        
        int count = normalized.Count;
        while (spawnedLandmarks.Count < count)
        {
            GameObject obj = Instantiate(landmarkPrefab, this.transform);
            spawnedLandmarks.Add(obj);
        }
        for (int i = count; i < spawnedLandmarks.Count; i++) spawnedLandmarks[i].SetActive(false);

        // Calculate Pseudo-Depth based on Bounding Box Size
        float depthAdjustment = 0;
        if (usePseudoDepth && count > 0)
        {
            float minX = 1f, maxX = 0f, minY = 1f, maxY = 0f;
            for(int i=0; i<count; i++)
            {
                 Landmark lm = normalized[i];
                 if (lm.x < minX) minX = lm.x;
                 if (lm.x > maxX) maxX = lm.x;
                 if (lm.y < minY) minY = lm.y;
                 if (lm.y > maxY) maxY = lm.y;
            }
            float width = maxX - minX;
            float height = maxY - minY;
            // Use maximum dimension to estimate scale
            float size = Mathf.Max(width, height);
            
            // Heuristic: Smaller size = Further away (Positive Z in Quad local space if Z- is front)
            // If size is 1.0 (Close), adj is 0.
            // If size is 0.0 (Far), adj is depthScale.
            if(size > 0.001f) 
            {
                float val = (1.0f - size) * depthScale;
                depthAdjustment = invertDepth ? -val : val;
            }
        }

        for (int i = 0; i < count; i++)
        {
            GameObject obj = spawnedLandmarks[i];
            obj.SetActive(true);
            obj.transform.localScale = Vector3.one * landmarkScale;

            Landmark lmNorm = normalized[i];
            
            if (quadDisplay == null) continue;

            // 1. Get Base Position on Quad surface from Normalized XY
            // Flip Y for Unity (Top is +0.5)
            // Mirror X if requested
            float localX = mirrorX ? -(lmNorm.x - 0.5f) : (lmNorm.x - 0.5f);
            float localY = -(lmNorm.y - 0.5f);
            
            // 2. Depth
            // If we have World Data, use the Z from World Data (scaled).
            // If not, use Normalized Z (which is relative depth).
            
            float zDepth = 0;
            if (useWorld)
            {
                // World Z is in meters. MP Negative Z is "Towards Camera".
                // Unity Quad Local Z- is "Front/Towards Camera".
                // So MP Z should map directly to Local Z (proportional).
                zDepth = world[i].z * depthMultiplier; 
            }
            else
            {
                // Normalized Z is also roughly scale-relative.
                 zDepth = lmNorm.z * 0.5f * depthMultiplier; 
            }
            
            // Combine: Offset + Relative Depth + Absolute Pseudo-Depth
            // Quad Back is +Z, Front is -Z. 
            // We want 'Far' to go towards +Z (Into the wall).
            Vector3 basePos = new Vector3(localX, localY, zDepth + depthAdjustment); 
            Vector3 localPos = basePos + positionOffset; 

            // Transform local position relative to the Quad into World Space
            if (visualizationRoot != null)
            {
                obj.transform.position = visualizationRoot.TransformPoint(localPos);
            }
            else
            {
                obj.transform.position = localPos;
            }
            
            // Store the calculated world position into the landmark data
            lmNorm.worldPosition = obj.transform.position;
        }
        
        // Expose the list for other scripts to access
        activeLandmarks = normalized;
    }
}
