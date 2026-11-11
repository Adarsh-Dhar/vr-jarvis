#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

/// <summary>Editor shortcuts for the JARVIS data source. Values are stored in PlayerPrefs, which the runtime reads.</summary>
public static class JarvisMenu
{
  [MenuItem("JARVIS/Server URL = http://127.0.0.1:8000")]
  static void LocalUrl() { PlayerPrefs.SetString("jarvis.server", "http://127.0.0.1:8000"); PlayerPrefs.Save(); }
}
#endif
