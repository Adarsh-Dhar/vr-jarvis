#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

/// <summary>Editor shortcuts for the JARVIS data source. Values are stored in PlayerPrefs, which the runtime reads.</summary>
public static class JarvisMenu
{
  [MenuItem("JARVIS/Use real server (reads /repository)")]
  static void Real() { PlayerPrefs.SetInt("jarvis.mock", 0); PlayerPrefs.Save(); Debug.Log("JARVIS: real server mode. Start the server first: JARVIS_REPO=<folder> uvicorn server.jarvis_server:app --port 8000"); }

  [MenuItem("JARVIS/Use mock data (placeholder)")]
  static void Mock() { PlayerPrefs.SetInt("jarvis.mock", 1); PlayerPrefs.Save(); Debug.Log("JARVIS: mock (placeholder) mode."); }

  [MenuItem("JARVIS/Server URL = http://127.0.0.1:8000")]
  static void LocalUrl() { PlayerPrefs.SetString("jarvis.server", "http://127.0.0.1:8000"); PlayerPrefs.Save(); }
}
#endif
