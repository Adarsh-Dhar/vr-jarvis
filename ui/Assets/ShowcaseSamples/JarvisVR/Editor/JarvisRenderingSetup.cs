using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace JarvisVR.EditorTools
{
  /// <summary>One-click rendering setup for the JARVIS look on Quest, plus a version report.
  /// HDR must be on for the neon colors (intensity above 1) to reach Bloom; Opaque Texture is what lets the glass panels refract the scene.</summary>
  public static class JarvisRenderingSetup
  {
    [MenuItem("Tools/JARVIS/Configure Rendering for Quest")]
    public static void Configure()
    {
      ReportVersions();

      bool opaque = EditorUtility.DisplayDialog("JARVIS rendering",
        "Enable Opaque Texture so glass panels can refract and blur the scene behind them?\n\n" +
        "Yes: nicer glass, costs one screen copy per frame (profile it on the headset).\nNo: panels stay smoked glass with a glowing rim.",
        "Yes, enable", "No, keep it cheap");

      var seen = new System.Collections.Generic.HashSet<UniversalRenderPipelineAsset>();
      for (int i = 0; i < QualitySettings.names.Length; i++)
        if (QualitySettings.GetRenderPipelineAssetAt(i) is UniversalRenderPipelineAsset q) seen.Add(q);
      if (GraphicsSettings.defaultRenderPipeline is UniversalRenderPipelineAsset d) seen.Add(d);

      if (seen.Count == 0) { Debug.LogError("JARVIS: no UniversalRenderPipelineAsset is assigned in Graphics or Quality settings."); return; }

      foreach (UniversalRenderPipelineAsset a in seen)
      {
        a.supportsHDR = true;
        a.msaaSampleCount = 4;
        a.supportsCameraOpaqueTexture = opaque;
        EditorUtility.SetDirty(a);
        Debug.Log("JARVIS: configured " + a.name + " (HDR on, MSAA 4x, Opaque Texture " + (opaque ? "on" : "off") + ").");
      }
      AssetDatabase.SaveAssets();
    }

    [MenuItem("Tools/JARVIS/Report Unity and URP Versions")]
    public static void ReportVersions()
    {
      var urp = UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(UniversalRenderPipelineAsset).Assembly);
      string urpVersion = urp != null ? urp.version : "unknown";
      Debug.Log("JARVIS: Unity " + Application.unityVersion + ", URP package " + urpVersion + ". In Unity 6 the URP version normally follows the editor " +
                "minor version (6000.0 uses 17.0, 6000.2 uses 17.2). If yours is far behind, open Window > Package Manager > Universal RP and update it, " +
                "or remove the explicit \"com.unity.render-pipelines.universal\" line from Packages/manifest.json and let Unity resolve it.");
    }
  }
}
