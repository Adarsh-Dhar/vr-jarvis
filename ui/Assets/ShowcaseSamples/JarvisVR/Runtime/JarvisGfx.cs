using UnityEngine;

namespace JarvisVR
{
  public static class JarvisGfx
  {
    private static Sprite _rounded;

    private static Texture2D NewTex(int w, int h)
    {
      return new Texture2D(w, h, TextureFormat.RGBA32, false)
      {
        wrapMode = TextureWrapMode.Clamp,
        filterMode = FilterMode.Bilinear,
      };
    }

    /// <summary>9-sliced rounded rectangle, 22 px corner radius.</summary>
    public static Sprite RoundedRect(int size = 96, int radius = 22)
    {
      if (_rounded != null) return _rounded;
      Texture2D tex = NewTex(size, size);
      var px = new Color32[size * size];
      for (int y = 0; y < size; y++)
      {
        for (int x = 0; x < size; x++)
        {
          float cx = Mathf.Min(x + 0.5f, size - x - 0.5f);
          float cy = Mathf.Min(y + 0.5f, size - y - 0.5f);
          float dx = Mathf.Max(radius - cx, 0f);
          float dy = Mathf.Max(radius - cy, 0f);
          float a = Mathf.Clamp01(radius - Mathf.Sqrt(dx * dx + dy * dy) + 0.5f);
          px[y * size + x] = new Color32(255, 255, 255, (byte)(a * 255f));
        }
      }
      tex.SetPixels32(px);
      tex.Apply();
      _rounded = Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f, 0,
        SpriteMeshType.FullRect, new Vector4(radius, radius, radius, radius));
      return _rounded;
    }

    /// <summary>Ring sprite that is exactly 1 world unit wide (pixelsPerUnit = size).</summary>
    public static Sprite Ring(int size = 64, int thickness = 6)
    {
      Texture2D tex = NewTex(size, size);
      var px = new Color32[size * size];
      float c = size * 0.5f, r = c - 1f;
      for (int y = 0; y < size; y++)
      {
        for (int x = 0; x < size; x++)
        {
          float d = Mathf.Sqrt((x + 0.5f - c) * (x + 0.5f - c) + (y + 0.5f - c) * (y + 0.5f - c));
          float a = Mathf.Clamp01(r - d + 0.5f) * Mathf.Clamp01(d - (r - thickness) + 0.5f);
          px[y * size + x] = new Color32(255, 255, 255, (byte)(a * 255f));
        }
      }
      tex.SetPixels32(px);
      tex.Apply();
      return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), size);
    }

    public static Sprite Circle(int size = 64)
    {
      Texture2D tex = NewTex(size, size);
      var px = new Color32[size * size];
      float c = size * 0.5f, r = c - 1f;
      for (int y = 0; y < size; y++)
      {
        for (int x = 0; x < size; x++)
        {
          float d = Mathf.Sqrt((x + 0.5f - c) * (x + 0.5f - c) + (y + 0.5f - c) * (y + 0.5f - c));
          px[y * size + x] = new Color32(255, 255, 255, (byte)(Mathf.Clamp01(r - d + 0.5f) * 255f));
        }
      }
      tex.SetPixels32(px);
      tex.Apply();
      return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
    }

    public static Sprite VerticalGradient(Color top, Color bottom, int height = 256)
    {
      Texture2D tex = NewTex(1, height);
      for (int y = 0; y < height; y++)
        tex.SetPixel(0, y, Color.Lerp(bottom, top, y / (height - 1f)));
      tex.Apply();
      return Sprite.Create(tex, new Rect(0, 0, 1, height), new Vector2(0.5f, 0.5f), 100f);
    }
  }
}
