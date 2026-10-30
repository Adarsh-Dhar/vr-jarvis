using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace JarvisVR
{
  /// <summary>Blade Runner grade, built at runtime so it does not depend on the project's DefaultVolumeProfile (whose Bloom intensity is 0).
  /// A global high-priority Volume with controlled Bloom, teal/magenta split toning, contrast and a soft vignette.</summary>
  public static class JarvisLook
  {
    public static float BloomIntensity = 0.45f;   // Quest budget: raise slowly and profile

    public static void Apply(Camera cam)
    {
      if (cam != null)
      {
        UniversalAdditionalCameraData data = cam.GetUniversalAdditionalCameraData();
        if (data != null) data.renderPostProcessing = true;
        cam.allowHDR = true;   // without HDR the neon intensity above 1 is clamped and Bloom has nothing to bloom
        var asset = GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
        if (asset != null && !asset.supportsHDR)
          Debug.LogWarning("JARVIS: the active URP asset has HDR off, so the neon glow will look flat. Run Tools > JARVIS > Configure Rendering for Quest.");
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color32(0x03, 0x04, 0x0A, 0xFF);
      }

      var go = new GameObject("JARVIS Look Volume");
      var vol = go.AddComponent<Volume>();
      vol.isGlobal = true; vol.priority = 100f; vol.weight = 1f;
      VolumeProfile p = ScriptableObject.CreateInstance<VolumeProfile>();
      vol.profile = p;

      var bloom = p.Add<Bloom>(true);
      bloom.threshold.Override(0.85f);
      bloom.intensity.Override(BloomIntensity);
      bloom.scatter.Override(0.6f);
      bloom.tint.Override(new Color(0.85f, 0.95f, 1f));
      bloom.maxIterations.Override(4);

      var tone = p.Add<Tonemapping>(true);
      tone.mode.Override(TonemappingMode.Neutral);

      var grade = p.Add<ColorAdjustments>(true);
      grade.contrast.Override(18f);
      grade.saturation.Override(12f);
      grade.postExposure.Override(-0.15f);

      var split = p.Add<SplitToning>(true);
      split.shadows.Override(new Color(0.20f, 0.10f, 0.45f));     // deep violet shadows
      split.highlights.Override(new Color(0.20f, 0.85f, 0.95f));  // cyan highlights
      split.balance.Override(-20f);

      var vig = p.Add<Vignette>(true);
      vig.intensity.Override(0.28f);
      vig.smoothness.Override(0.6f);
      vig.color.Override(new Color(0.05f, 0f, 0.12f));
    }
  }
}
