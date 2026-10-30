using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections.Generic;

namespace JarvisVR
{
  /// <summary>Hides Meta's demo content that the JARVIS workspace does not want: the example menu, the room, the sky dome and the pose boards.
  /// Matches every object with these names (the saved scene has two RoomEnvironment objects), active or not.</summary>
  public static class JarvisSceneCleanup
  {
    public static readonly string[] MetaDemoObjects = { "ISDKExampleMenu", "MiniPoses", "RoomEnvironment", "BackgroundSkydome" };

    // Type names that cause null reference errors when their dependencies aren't set up
    // Using string names to avoid assembly reference issues
    // NOTE: HandVisual and ControllerVisual are excluded - they're needed for hand/controller visualization
    private static readonly string[] ProblematicTypeNames = new string[]
    {
      "Oculus.Interaction.PointableCanvasModule",
      "Oculus.Interaction.Body.Input.FromOVRBodyDataSource",
      "Oculus.Interaction.HoverInteractorsGate",
      "Oculus.Interaction.CenterEyeOffset",
      "Oculus.Interaction.PoseDetection.TransformFeatureStateProvider",
      "Oculus.Interaction.PoseDetection.FingerFeatureStateProvider",
      "Oculus.Interaction.Input.FromOVRControllerDataSource",
      "Oculus.Interaction.Input.FromOVRHandDataSource",
      "Oculus.Interaction.Input.FromOVRHmdDataSource",
      "Oculus.Interaction.Locomotion.LocomotionEventsConnection",
      "Oculus.Interaction.PoseDetection.HmdOffset",
    };

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

    public static int DisableProblematicComponents()
    {
      int disabled = 0;
      foreach (GameObject root in SceneManager.GetActiveScene().GetRootGameObjects())
      {
        Component[] components = root.GetComponentsInChildren<Component>(true);
        foreach (Component c in components)
        {
          if (c == null) continue;
          string typeName = c.GetType().FullName;
          foreach (string problemTypeName in ProblematicTypeNames)
          {
            if (typeName == problemTypeName || typeName.StartsWith(problemTypeName + "."))
            {
              if (c is Behaviour b && b.enabled)
              {
                b.enabled = false;
                disabled++;
              }
              break;
            }
          }
        }
      }
      if (disabled > 0) Debug.Log("JARVIS: disabled " + disabled + " problematic Interaction SDK component(s).");
      return disabled;
    }
  }
}
