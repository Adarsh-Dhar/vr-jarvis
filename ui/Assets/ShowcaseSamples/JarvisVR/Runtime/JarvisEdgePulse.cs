using UnityEngine;

namespace JarvisVR
{
  /// <summary>Slow pulse that travels from the caller to the callee along an amber change-path edge.</summary>
  public sealed class JarvisEdgePulse : MonoBehaviour
  {
    private static Texture2D _tex;
    private Material _mat;
    private const float Speed = 0.45f;

    public void Setup(LineRenderer line)
    {
      if (_tex == null) _tex = MakePulseTexture();
      line.textureMode = LineTextureMode.Stretch;
      _mat = line.material;
      _mat.mainTexture = _tex;
      _mat.color = Color.white; // the amber tint comes from line.startColor / endColor
    }

    private void Update()
    {
      if (_mat != null)
        _mat.mainTextureOffset = new Vector2(-((Time.unscaledTime * Speed) % 1f), 0f);
    }

    private static Texture2D MakePulseTexture()
    {
      var t = new Texture2D(128, 1, TextureFormat.RGBA32, false)
      {
        wrapMode = TextureWrapMode.Repeat,
        filterMode = FilterMode.Bilinear,
      };
      for (int x = 0; x < 128; x++)
      {
        float u = x / 127f;
        float bump = Mathf.Exp(-Mathf.Pow((u - 0.5f) / 0.12f, 2f));
        float v = 0.45f + 0.55f * bump;
        t.SetPixel(x, 0, new Color(v, v, v, 1f));
      }
      t.Apply();
      return t;
    }
  }
}
