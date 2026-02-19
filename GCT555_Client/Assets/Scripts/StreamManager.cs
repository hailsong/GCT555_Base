using System.Collections.Generic;
using UnityEngine;

public class StreamManager : MonoBehaviour
{

    // added by yh:
    [Header("Raw Depth Scales (per modality)")]
    public float faceRawDepthScale = 1.0f; // best
    public float handRawDepthScale = 1000.0f;
    public float poseRawDepthScale = 1000.0f; // using pose as depth ref is noisy.
    

    [System.Serializable]
    public class WallConfig
    {
        public string name;
        public string ipAddress = "127.0.0.1";
        public Transform quadTransform;

        [Header("Active Mode")]
        public StreamClient.ClientType activeType = StreamClient.ClientType.Pose;
        
        [Header("Socket Ports")]
        public int poseSocketPort = 5050;
        public int handSocketPort = 5051;
        public int faceSocketPort = 5052;
        
        [Header("Web Ports (Video)")]
        public int poseWebPort = 5000;
        public int handWebPort = 5001;
        public int faceWebPort = 5002;

    }

    public WallConfig wall1;
    public WallConfig wall2;

    // added by yh:
    [Header("Depth Fusion Binding")]
    public UserDepthFusion wall1Fusion;
    public UserDepthFusion wall2Fusion;

    
    public List<StreamClient> activeClients = new List<StreamClient>();

    [Header("Visualization Gloabl Settings")]
    public float globalLandmarkScale = 0.04f;
    public float globalDepthMultiplier = 10.0f;
    public bool globalUsePseudoDepth = true;
    public float globalDepthScale = 2.0f; // Scale for distance estimation
    public Vector3 globalPositionOffset = new Vector3(0, 0, -0.2f);
    public bool globalInvertDepth = false;

    [Header("Prefabs")]
    public GameObject landmarkPrefab; 

    void Start()
    {
        SetupWall(wall1);
        SetupWall(wall2);
    }

    void SetupWall(WallConfig config)
    {
        if (config.quadTransform == null) return;

        // Determine ports based on active type
        int socketPort = 0;
        int webPort = 0;

        switch (config.activeType)
        {
            case StreamClient.ClientType.Pose:
                socketPort = config.poseSocketPort;
                webPort = config.poseWebPort;
                break;
            case StreamClient.ClientType.Hand:
                socketPort = config.handSocketPort;
                webPort = config.handWebPort;
                break;
            case StreamClient.ClientType.Face:
                socketPort = config.faceSocketPort;
                webPort = config.faceWebPort;
                break;
        }

        // Add QuadDisplay if not present
        QuadDisplay display = config.quadTransform.GetComponent<QuadDisplay>();
        if (display == null) display = config.quadTransform.gameObject.AddComponent<QuadDisplay>();
        
        // Set snapshot URL based on the selected web port
        display.snapshotUrl = $"http://{config.ipAddress}:{webPort}/snapshot";

        // Create only the selected client
        CreateClient(config, config.activeType, socketPort, display);
    }

    void CreateClient(WallConfig config, StreamClient.ClientType type, int port, QuadDisplay display)
    {
        GameObject go = new GameObject($"{config.name}_{type}_Client");
        go.transform.SetParent(transform);
        
        StreamClient client = go.AddComponent<StreamClient>();
        client.ipAddress = config.ipAddress; 
        client.port = port;
        client.clientType = type;
        client.landmarkPrefab = landmarkPrefab;
        client.visualizationRoot = config.quadTransform; 
        client.quadDisplay = display;
        
        // Apply Global Settings
        client.landmarkScale = globalLandmarkScale;
        client.depthMultiplier = globalDepthMultiplier;
        client.usePseudoDepth = globalUsePseudoDepth;

        client.usePseudoDepth = globalUsePseudoDepth;
        client.depthScale = globalDepthScale;
        client.positionOffset = globalPositionOffset;
        client.invertPseudoDepth = globalInvertDepth;
        
        activeClients.Add(client);

        // added by yh:
        // ---- Auto-bind created clients into fusion (if assigned) ----
        UserDepthFusion fusion = null;
        if (config == wall1) fusion = wall1Fusion;
        else if (config == wall2) fusion = wall2Fusion;

        if (fusion != null)
        {
            switch (type)
            {
                case StreamClient.ClientType.Face:
                    client.rawDepthScale = faceRawDepthScale;
                    fusion.face = client;
                    break;
                case StreamClient.ClientType.Pose:
                    client.rawDepthScale = poseRawDepthScale;
                    fusion.pose = client;
                    break;
                case StreamClient.ClientType.Hand:
                    client.rawDepthScale = handRawDepthScale;
                    fusion.hand = client;
                    break;
            }
        }


    }
}
