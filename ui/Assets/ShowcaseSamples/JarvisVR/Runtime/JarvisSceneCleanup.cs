using UnityEngine;
using UnityEngine.SceneManagement;

namespace JarvisVR
{
  /// <summary>Hides Meta's demo content that the JARVIS workspace does not want: the example menu, the room, the sky dome and the pose boards.
  /// Matches every object with these names (the saved scene has two RoomEnvironment objects), active or not.</summary>
  public static class JarvisSceneCleanup
  {
    public static readonly string[] MetaDemoObjects = { "ISDKExampleMenu", "MiniPoses", "RoomEnvironment", "BackgroundSkydome" };

    public static int HideMetaDemo()
    {
      int hidden = 0;
      foreach (GameObject root in SceneManager.GetActiveScene().GetRootGameObjects())
        foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
          foreach (string n in MetaDemoObjects)
            if (t.name == n && t.gameObject.activeSelf) { t.gameObject.SetActive(false); hidden++; }
      if (hidden > 0) Debug.Log("JARVIS: hid " + hidden + " Meta demo object(s).");
      return hidden;
    }
  }
}
