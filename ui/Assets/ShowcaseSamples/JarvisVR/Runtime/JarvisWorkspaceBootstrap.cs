using UnityEngine;

namespace JarvisVR
{
    /// <summary>
    /// Scene-entry component for the JARVIS workspace. Finds the active XR camera and
    /// launches the spatial workspace. The serialized Unity scene references this script
    /// by name, so the class name and file must stay.
    /// </summary>
    public sealed class JarvisWorkspaceBootstrap : MonoBehaviour
    {
        private void Start()
        {
            Camera camera = Camera.main;
            if (camera == null)
            {
                foreach (Camera candidate in FindObjectsByType<Camera>(FindObjectsInactive.Include))
                {
                    if (candidate != null && candidate.isActiveAndEnabled)
                    {
                        camera = candidate;
                        break;
                    }
                }
            }

            if (camera == null)
            {
                Debug.LogError("JARVIS needs an active XR camera. Open the generated scene from the supplied Meta Interaction SDK project.");
                enabled = false;
                return;
            }

            gameObject.AddComponent<JarvisSpatialWorkspace>().Initialize(camera);
            enabled = false;
        }
    }
}
