using UnityEditor;
using UnityEngine;
using JarvisVR;

namespace JarvisVR.EditorTools
{
  /// <summary>Play-mode scale test: builds a synthetic graph, expands every cluster,
  /// then logs build time and average frame time over 120 frames.</summary>
  public static class JarvisScaleTestMenu
  {
    [MenuItem("JARVIS/Scale Test 5000")]
    private static void Scale5000() { Run(50, 100); }

    [MenuItem("JARVIS/Scale Test 20000")]
    private static void Scale20000() { Run(200, 100); }

    private static void Run(int clusters, int perCluster)
    {
      var w = Object.FindAnyObjectByType<JarvisSpatialWorkspace>();
      if (w == null)
      {
        Debug.LogWarning("[JARVIS Scale] no JarvisSpatialWorkspace found - enter Play mode first.");
        return;
      }
      w.DebugLoadSynthetic(clusters, perCluster);
    }
  }
}
