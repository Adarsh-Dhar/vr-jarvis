using UnityEngine;

namespace JarvisVR
{
  /// <summary>Where the app finds the JARVIS server, and the shared secret. Lives in a Resources folder, so it is
  /// packed into the Quest build. Edit it in the Inspector or with the JARVIS > Server menu.
  /// Token must be exactly the value of the JARVIS_TOKEN environment variable the server was started with.</summary>
  [CreateAssetMenu(fileName = "JarvisServerSettings", menuName = "JARVIS/Server Settings")]
  public sealed class JarvisServerSettings : ScriptableObject
  {
    [Tooltip("Editor / XR Simulator: http://127.0.0.1:8000.  Quest: http://<your computer's LAN IP>:8000")]
    public string ServerUrl = "http://127.0.0.1:8000";

    [Tooltip("Must equal JARVIS_TOKEN on the server.")]
    public string Token = "dev-token";

    public static JarvisServerSettings Load() { return Resources.Load<JarvisServerSettings>("JarvisServerSettings"); }
  }
}