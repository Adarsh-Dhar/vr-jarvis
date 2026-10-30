using System.Collections.Generic;
using UnityEngine;

namespace JarvisVR
{
  /// <summary>
  /// Procedural neon skyline for the spatial workspace: three rings of lit towers plus a magenta horizon haze.
  /// Cost: 4 draw calls, about 900 vertices, one 128x128 texture, no lights, no shadows. Disable with PlayerPrefs "jarvis.city" = 0.
  /// </summary>
  public static class JarvisCityscape
  {
    public static bool Enabled { get { return PlayerPrefs.GetInt("jarvis.city", 1) == 1; } }

    private struct Ring { public float Radius, MinH, MaxH, MinW, MaxW, Alpha; public int Count; public Color Tint; }

    /// <param name="root">The workspace root: the skyline is centered on it and uses its local space.</param>
    /// <param name="floorY">Local height of the floor grid, so towers stand on it.</param>
    public static void Build(Transform root, float floorY = -1.2f, int seed = 7)
    {
      if (!Enabled) return;
      var go = new GameObject("JARVIS Cityscape");
      go.transform.SetParent(root, false);

      Texture2D windows = WindowTexture(seed);
      JarvisPalette pal = JarvisPalette.Current;
      Ring[] rings =
      {
        // far ring first: it is drawn first (lower render queue) so nearer, brighter towers cover it
        new Ring { Radius = 34f, MinH = 18f, MaxH = 46f, MinW = 3.5f, MaxW = 7.5f, Alpha = 0.55f, Count = 46, Tint = Color.Lerp(pal.Violet, Color.white, 0.25f) },
        new Ring { Radius = 24f, MinH = 10f, MaxH = 30f, MinW = 2.5f, MaxW = 5.5f, Alpha = 0.75f, Count = 38, Tint = Color.Lerp(pal.Violet, pal.Cyan, 0.5f) },
        new Ring { Radius = 15f, MinH = 5f,  MaxH = 16f, MinW = 1.8f, MaxW = 3.8f, Alpha = 0.92f, Count = 30, Tint = Color.Lerp(pal.Cyan, Color.white, 0.35f) },
      };

      var rng = new System.Random(seed);
      for (int i = 0; i < rings.Length; i++) BuildRing(go.transform, rings[i], i, floorY, windows, rng);
      BuildHaze(go.transform, floorY, JarvisSpatialFx.Magenta);
    }

    private static float Range(System.Random r, float a, float b) { return a + (float)r.NextDouble() * (b - a); }

    private static void BuildRing(Transform parent, Ring ring, int index, float floorY, Texture2D windows, System.Random rng)
    {
      var verts = new List<Vector3>(); var uvs = new List<Vector2>(); var cols = new List<Color>(); var tris = new List<int>();
      for (int k = 0; k < ring.Count; k++)
      {
        float ang = (k + Range(rng, -0.3f, 0.3f)) / ring.Count * Mathf.PI * 2f;
        float r = ring.Radius + Range(rng, -2f, 2f);
        float w = Range(rng, ring.MinW, ring.MaxW), h = Range(rng, ring.MinH, ring.MaxH);
        Vector3 c = new Vector3(Mathf.Sin(ang) * r, floorY, Mathf.Cos(ang) * r);
        Vector3 t = new Vector3(Mathf.Cos(ang), 0f, -Mathf.Sin(ang)) * (w * 0.5f);   // along the ring, so the face looks at the center
        Vector3 up = Vector3.up * h;

        // one 16x16-cell window tile spans 16 windows: about 0.9 m wide and 1.2 m tall per window
        float cols16 = Mathf.Max(1f, Mathf.Round(w / 0.9f)) / 16f, rows16 = Mathf.Max(1f, Mathf.Round(h / 1.2f)) / 16f;
        float u0 = (float)rng.NextDouble(), v0 = (float)rng.NextDouble();
        int b = verts.Count;
        verts.Add(c - t); verts.Add(c + t); verts.Add(c + t + up); verts.Add(c - t + up);
        uvs.Add(new Vector2(u0, v0)); uvs.Add(new Vector2(u0 + cols16, v0));
        uvs.Add(new Vector2(u0 + cols16, v0 + rows16)); uvs.Add(new Vector2(u0, v0 + rows16));
        float shade = Range(rng, 0.7f, 1f);   // per-tower brightness
        Color vc = new Color(ring.Tint.r * shade, ring.Tint.g * shade, ring.Tint.b * shade, ring.Alpha);
        for (int j = 0; j < 4; j++) cols.Add(vc);
        tris.AddRange(new[] { b, b + 1, b + 2, b, b + 2, b + 3 });
      }
      Spawn(parent, "Skyline " + index, verts, uvs, cols, tris, windows, 1.5f, 2990 + index);
    }

    /// <summary>Low magenta glow band at the horizon: vertex-color gradient, no texture.</summary>
    private static void BuildHaze(Transform parent, float floorY, Color tint)
    {
      const int seg = 48; const float radius = 38f, height = 16f;
      var verts = new List<Vector3>(); var uvs = new List<Vector2>(); var cols = new List<Color>(); var tris = new List<int>();
      for (int s = 0; s <= seg; s++)
      {
        float a = s / (float)seg * Mathf.PI * 2f;
        Vector3 p = new Vector3(Mathf.Sin(a) * radius, floorY, Mathf.Cos(a) * radius);
        verts.Add(p); uvs.Add(Vector2.zero); cols.Add(new Color(tint.r, tint.g, tint.b, 0.5f));
        verts.Add(p + Vector3.up * height); uvs.Add(Vector2.zero); cols.Add(new Color(tint.r, tint.g, tint.b, 0f));
        if (s < seg) { int i = s * 2; tris.AddRange(new[] { i, i + 1, i + 2, i + 1, i + 3, i + 2 }); }
      }
      Spawn(parent, "Horizon haze", verts, uvs, cols, tris, null, 1.2f, 2989);
    }

    private static void Spawn(Transform parent, string name, List<Vector3> v, List<Vector2> uv, List<Color> c, List<int> t,
      Texture2D tex, float intensity, int queue)
    {
      var mesh = new Mesh { name = name };
      mesh.SetVertices(v); mesh.SetUVs(0, uv); mesh.SetColors(c); mesh.SetTriangles(t, 0);
      mesh.RecalculateBounds();
      var go = new GameObject(name, typeof(MeshFilter), typeof(MeshRenderer));
      go.transform.SetParent(parent, false);
      go.GetComponent<MeshFilter>().sharedMesh = mesh;
      var mr = go.GetComponent<MeshRenderer>();
      Material m = JarvisSpatialGfx.Line(Color.white, intensity);   // NeonUnlit: alpha-blended, vertex colored, HDR for bloom
      if (tex != null) m.mainTexture = tex;
      m.renderQueue = queue;
      mr.sharedMaterial = m;
      JarvisSpatialGfx.Flat(mr);
    }

    /// <summary>16x16 grid of window cells, about a third lit in cyan, magenta, amber or white. Mipmapped so distant towers haze out instead of shimmering.</summary>
    private static Texture2D WindowTexture(int seed)
    {
      const int px = 128, cell = 8;
      var tex = new Texture2D(px, px, TextureFormat.RGBA32, true) { wrapMode = TextureWrapMode.Repeat, filterMode = FilterMode.Bilinear, anisoLevel = 2 };
      var rng = new System.Random(seed * 31 + 5);
      Color[] lit = { new Color(0.3f, 0.95f, 1f), new Color(1f, 0.3f, 0.85f), new Color(1f, 0.75f, 0.3f), new Color(0.9f, 0.95f, 1f) };
      var pixels = new Color[px * px];
      for (int cy = 0; cy < px / cell; cy++)
        for (int cx = 0; cx < px / cell; cx++)
        {
          bool on = rng.NextDouble() < 0.34;
          Color window = lit[rng.Next(lit.Length)];
          float body = 0.012f + (float)rng.NextDouble() * 0.02f;
          for (int y = 0; y < cell; y++)
            for (int x = 0; x < cell; x++)
            {
              bool inside = x >= 2 && x <= 5 && y >= 2 && y <= 6;
              pixels[(cy * cell + y) * px + cx * cell + x] = on && inside ? window : new Color(body, body * 1.3f, body * 2.6f, 1f);
            }
        }
      tex.SetPixels(pixels);
      tex.Apply(true);
      return tex;
    }
  }
}
