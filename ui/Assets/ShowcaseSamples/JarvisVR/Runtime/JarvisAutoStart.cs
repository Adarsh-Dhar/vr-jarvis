using UnityEngine;
using UnityEngine.SceneManagement;

namespace JarvisVR
{
  /// <summary>Safety net: if the scene named JarvisWorkspace is loaded but does not contain the JARVIS bootstrap
  /// (for example it is still an unmodified copy of Meta's BodyPoseDetectionExamples), build the workspace at runtime
  /// and hide Meta's demo room, sky and pose boards.</summary>
  public static class JarvisAutoStart
  {
    private static readonly string[] MetaDemoObjects = { "MiniPoses", "RoomEnvironment", "BackgroundSkydome" };

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Run()
    {
      if (SceneManager.GetActiveScene().name != "JarvisWorkspace") return;
      if (Object.FindAnyObjectByType<JarvisWorkspaceBootstrap>() != null) return;

      Debug.LogWarning("JARVIS: JarvisWorkspace.unity had no JarvisWorkspaceBootstrap (it was an unmodified copy of Meta's " +
                       "body-pose demo). Starting the workspace at runtime. Re-run Tools > JARVIS > Generate Quest Workspace Scene to fix the asset.");
      foreach (GameObject root in SceneManager.GetActiveScene().GetRootGameObjects())
        foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
          foreach (string n in MetaDemoObjects)
            if (t.name == n) t.gameObject.SetActive(false);

      Camera cam = Camera.main != null ? Camera.main : Object.FindAnyObjectByType<Camera>();
      if (cam != null) { cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color32(0x05, 0x08, 0x0F, 0xFF); }
      new GameObject("JARVIS Workspace").AddComponent<JarvisWorkspaceBootstrap>();
    }
  }
}
