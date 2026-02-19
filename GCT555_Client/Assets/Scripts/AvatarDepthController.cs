using UnityEngine;

public class AvatarDepthController : MonoBehaviour
{
    [Header("Input")]
    //public StreamClient faceClient;          // Face StreamClient (clientType=Face)
    public UserDepthFusion depthFusion;         // 업데이트
    public Transform avatarRoot;             // 이동시킬 Transform (없으면 자기 자신)
    
    [Header("Mapping")]
    public float depthToZ = 1.0f;            // userDepth(상대) -> Unity z 이동 스케일
    public float zMin = -0.5f;               // 이동 범위(로컬 기준)
    public float zMax = 0.5f;

    [Header("Smoothing (Optional)")]
    public bool extraSmoothing = true;       // StreamClient 내부 필터 + 추가로 한 번 더 부드럽게
    [Range(0.01f, 1.0f)]
    public float smoothAlpha = 0.2f;

    [Header("Tracking Loss Behavior")]
    public bool returnToBaseWhenLost = true;
    [Range(0.01f, 1.0f)]
    public float returnAlpha = 0.05f;

    private Vector3 baseLocalPos;
    private float zFiltered = 0f;

    void Start()
    {
        if (avatarRoot == null) avatarRoot = transform;
        baseLocalPos = avatarRoot.localPosition;
        zFiltered = baseLocalPos.z;
    }

    void Update()
    {
        //if (faceClient == null) return;
        if (depthFusion == null) return;

        // 1) 목표 z 계산
        float targetZ = baseLocalPos.z;

        //if (faceClient.hasFaceDepth)
        if (depthFusion.hasDepth)
        {
            // userDepth: baseline 대비 상대 변화값
            //float zOffset = faceClient.userDepth * depthToZ;
            float zOffset = depthFusion.fusedDepth * depthToZ;
            float zClamped = Mathf.Clamp(baseLocalPos.z + zOffset, baseLocalPos.z + zMin, baseLocalPos.z + zMax);
            targetZ = zClamped;
        }
        else if (returnToBaseWhenLost)
        {
            targetZ = baseLocalPos.z;
        }
        else
        {
            // 추적 끊겨도 현재 유지
            targetZ = avatarRoot.localPosition.z;
        }

        // 2) 적용 (스무딩)
        if (extraSmoothing)
            zFiltered = Mathf.Lerp(zFiltered, targetZ, smoothAlpha);
        //else if (!faceClient.hasFaceDepth && returnToBaseWhenLost)
        else if (!depthFusion.hasDepth && returnToBaseWhenLost)
            zFiltered = Mathf.Lerp(avatarRoot.localPosition.z, targetZ, returnAlpha);
        else
            zFiltered = targetZ;

        var p = avatarRoot.localPosition;
        p.z = zFiltered;
        avatarRoot.localPosition = p;
    }

    // 런타임에 기준 위치를 다시 잡고 싶을 때 호출
    public void RecalibrateBase()
    {
        baseLocalPos = avatarRoot.localPosition;
        zFiltered = baseLocalPos.z;
    }
}
