using UnityEngine;

public class UserDepthFusion : MonoBehaviour
{
    public StreamClient face;
    public StreamClient pose;
    public StreamClient hand;

    [Header("Weights (used only when multiple are valid)")]
    [Range(0f,1f)] public float faceW = 0.8f;
    [Range(0f,1f)] public float poseW = 0.8f;
    [Range(0f,1f)] public float handW = 0.8f;

    public bool hasDepth;
    public float fusedDepth;

    public bool smooth = true;
    [Range(0.01f,1f)] public float alpha = 0.2f;

    void Update()
    {
        bool hf = face != null && face.hasDepth;
        bool hp = pose != null && pose.hasDepth;
        bool hh = hand != null && hand.hasDepth;

        float target;
        bool ok;

        if (hf)
        {
            // face가 있으면 face 중심 + pose 약간(선택)
            float df = face.userDepth;
            float dp = hp ? pose.userDepth : 0f;
            float dh = hh ? hand.userDepth : 0f;

            float wF = faceW;
            float wP = hp ? poseW : 0f;
            float wH = hh ? handW : 0f;
            float ws = wF + wP + wH;

            target = (wF*df + wP*dp + wH*dh) / Mathf.Max(1e-6f, ws);
            ok = true;
        }
        else if (hp)
        {
            target = pose.userDepth;
            ok = true;
        }
        else if (hh)
        {
            target = hand.userDepth;
            ok = true;
        }
        else
        {
            target = 0f;
            ok = false;
        }

        hasDepth = ok;
        fusedDepth = smooth ? Mathf.Lerp(fusedDepth, target, alpha) : target;
    }
}
