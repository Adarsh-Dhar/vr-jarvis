using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace JarvisVR.EditorTools
{
  public static class JarvisSceneGenerator
  {
    private const string SourceScene =
      "Assets/Samples/Meta XR Interaction SDK/207.0.0/Example Scenes/BodyPoseDetectionExamples.unity";
    private const string TargetScene = "Assets/ShowcaseSamples/JarvisVR/Scenes/JarvisWorkspace.unity";
    private static readonly string[] DisableByName = { "MiniPoses", "RoomEnvironment", "BackgroundSkydome" };

    [MenuItem("Tools/JARVIS/Generate Quest Workspace Scene")]
    public static void Generate()
    {
      if (!File.Exists(SourceScene))
      {
        EditorUtility.DisplayDialog("JARVIS", "Missing source scene:\n" + SourceScene +
          "\nImport the Interaction SDK 207.0.0 samples first.", "OK");
        return;
      }

      Directory.CreateDirectory(Path.GetDirectoryName(TargetScene));
      if (File.Exists(TargetScene))
      {
        if (!EditorUtility.DisplayDialog("JARVIS", "JarvisWorkspace.unity exists. Overwrite?", "Overwrite", "Cancel"))
          return;
        AssetDatabase.DeleteAsset(TargetScene);
      }

      if (!AssetDatabase.CopyAsset(SourceScene, TargetScene))
      {
        Debug.LogError("JARVIS: could not copy the source scene.");
        return;
      }

      Scene scene = EditorSceneManager.OpenScene(TargetScene, OpenSceneMode.Single);
      foreach (string name in DisableByName)
      {
        GameObject go = FindDeep(scene, name);
        if (go != null) go.SetActive(false);
      }

      if (Object.FindFirstObjectByType<JarvisWorkspaceBootstrap>() == null)
        new GameObject("JARVIS Workspace").AddComponent<JarvisWorkspaceBootstrap>();

      Camera cam = Camera.main != null ? Camera.main : Object.FindFirstObjectByType<Camera>();
      if (cam != null)
      {
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color32(0x05, 0x08, 0x0F, 0xFF);
      }

      EditorSceneManager.MarkSceneDirty(scene);
      EditorSceneManager.SaveScene(scene);

      var list = EditorBuildSettings.scenes.Where(s => s.path != TargetScene).ToList();
      list.Insert(0, new EditorBuildSettingsScene(TargetScene, true));
      EditorBuildSettings.scenes = list.ToArray();

      Debug.Log("JARVIS: generated " + TargetScene);
    }

    private static GameObject FindDeep(Scene scene, string name)
    {
      foreach (GameObject root in scene.GetRootGameObjects())
        foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
          if (t.name == name) return t.gameObject;
      return null;
    }
  }
}
