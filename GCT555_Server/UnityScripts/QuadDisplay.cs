using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

public class QuadDisplay : MonoBehaviour
{
    public string snapshotUrl = "http://127.0.0.1:5000/snapshot";
    public Renderer quadRenderer;
    public float refreshRate = 0.033f; // ~30 FPS

    void Start()
    {
        if (quadRenderer == null) quadRenderer = GetComponent<Renderer>();
        StartCoroutine(FetchTextureLoop());
    }

    IEnumerator FetchTextureLoop()
    {
        while (true)
        {
            using (UnityWebRequest uwr = UnityWebRequestTexture.GetTexture(snapshotUrl))
            {
                yield return uwr.SendWebRequest();

                if (uwr.result != UnityWebRequest.Result.Success)
                {
                    // Debug.LogWarning($"Stream Error: {uwr.error}");
                }
                else
                {
                    Texture2D texture = DownloadHandlerTexture.GetContent(uwr);
                    if (quadRenderer.material.mainTexture != null)
                    {
                        // Optional: Destroy old texture to prevent leaks if not handled by Unity automatically? 
                        // Actually Unity manages resources but explicitly destroying if we create new ones is safer 
                        // IF we are replacing the material's texture property significantly.
                        // But GetContent creates a new Texture2D each time.
                        // Better to DestroyImmediate(quadRenderer.material.mainTexture) before assigning new one 
                        // OR use LoadImageIntoTexture if we reused one. 
                        // For simplicity, let's just assign. Garbage collector handles the rest mostly, 
                        // but explicit cleanup is better for 30FPS.
                        Destroy(quadRenderer.material.mainTexture);
                    }
                    quadRenderer.material.mainTexture = texture;
                }
            }
            
            yield return new WaitForSeconds(refreshRate); 
        }
    }
}
