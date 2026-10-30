using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace JarvisVR
{
  /// <summary>Not syntax-checked in Unity. Put in Runtime/ next to the other JARVIS scripts.</summary>
  public static class JarvisSpatialFx
  {
    public static readonly Color Magenta = new Color(1f, 0.18f, 0.62f, 1f);

    public static float Smooth(float t) { return t * t * (3f - 2f * t); }

    public static float EaseOutBack(float x)
    {
      const float c1 = 1.70158f, c3 = c1 + 1f;
      float p = x - 1f;
      return 1f + c3 * p * p * p + c1 * p * p;
    }

    /// <summary>Smoked-glass sheen: cyan glow along the top edge, magenta along the bottom edge, clear in the middle.</summary>
    public static Image AddSheen(Transform parent, float w, float h, Color top)
    {
      var t = new Texture2D(1, 32, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
      for (int y = 0; y < 32; y++)
      {
        float u = y / 31f;
        Color c = Color.Lerp(Magenta, top, u);
        c.a = u > 0.5f ? 0.16f * (u - 0.5f) * 2f : 0.10f * (1f - u * 2f);
        t.SetPixel(0, y, c);
      }
      t.Apply();
      var go = new GameObject("Sheen", typeof(RectTransform), typeof(Image));
      go.transform.SetParent(parent, false);
      go.GetComponent<RectTransform>().sizeDelta = new Vector2(w, h);
      var img = go.GetComponent<Image>();
      img.sprite = Sprite.Create(t, new Rect(0, 0, 1, 32), new Vector2(0.5f, 0.5f), 100f);
      img.raycastTarget = false;
      return img;
    }
  }

  /// <summary>Fade + scale in/out with a stagger delay. While fading, panel colliders are switched off so a ghost panel never blocks rays.</summary>
  [RequireComponent(typeof(CanvasGroup))]
  public sealed class JarvisPanelAnim : MonoBehaviour
  {
    public float UserScale = 1f;
    public System.Action<bool> OnSolid;
    private CanvasGroup _group;
    private float _vis, _want = 1f, _delay;
    private bool _solid = true;

    public bool WantVisible { get { return _want > 0f; } }

    private void Awake()
    {
      _group = GetComponent<CanvasGroup>();
      _group.alpha = 0f;
    }

    /// <summary>delay (seconds) staggers mode transitions; it only applies when the target actually changes.</summary>
    public void SetVisible(bool on, float delay = 0f)
    {
      float want = on ? 1f : 0f;
      if (want != _want) _delay = delay;
      _want = want;
      if (on && !gameObject.activeSelf) gameObject.SetActive(true);
    }

    private void Update()
    {
      float dt = Time.unscaledDeltaTime;
      if (_delay > 0f) { _delay -= dt; return; }
      _vis = Mathf.MoveTowards(_vis, _want, dt / 0.22f);
      float e = JarvisSpatialFx.Smooth(_vis);
      _group.alpha = e;
      transform.localScale = Vector3.one * (JarvisSpatialPanel.Scale * UserScale * Mathf.Lerp(0.9f, 1f, e));
      bool solid = _want > 0f && _vis > 0.6f;
      if (solid != _solid) { _solid = solid; if (OnSolid != null) OnSolid(solid); }
      if (_vis <= 0f && _want <= 0f) gameObject.SetActive(false);
    }
  }

  /// <summary>Corner handle: pinch and drag scales the panel (handled in JarvisSpatialInput).</summary>
  public sealed class JarvisSpatialResize : MonoBehaviour { public JarvisPanelAnim Panel; }

  /// <summary>On each graph node root: materialize pop, smooth size, hover and selection ring.</summary>
  public sealed class JarvisNodeFx : MonoBehaviour
  {
    public bool Selected, Hovered, Shown = true;
    public float BaseSize = 0.075f, SelectedSize = 0.10f;
    private Transform _body, _ringT;
    private LineRenderer _ring;
    private Color _ringColor;
    private float _clock, _delay, _size, _alpha, _vis = 1f, _rim = 0.25f;
    private Transform _halo;
    private Material _haloMat;

    /// <summary>Collapse or expand this node with a shrink/grow animation.</summary>
    public void SetShown(bool on)
    {
      Shown = on;
      if (on && !gameObject.activeSelf) gameObject.SetActive(true);
    }

    public void Begin(Transform body, float delay, Color ringColor)
    {
      _body = body; _delay = delay; _ringColor = ringColor; _size = BaseSize;
      body.localScale = Vector3.zero;

      var holder = new GameObject("SelectionRing");
      holder.transform.SetParent(transform, false);
      holder.AddComponent<JarvisBillboard>();
      _ringT = holder.transform;
      _ring = holder.AddComponent<LineRenderer>();
      _ring.useWorldSpace = false; _ring.loop = true; _ring.positionCount = 40;
      _ring.widthMultiplier = 0.004f;
      _ring.material = JarvisSpatialGfx.Line(Color.white, 2f);
      for (int i = 0; i < 40; i++)
      {
        float a = i * Mathf.PI * 2f / 40f;
        _ring.SetPosition(i, new Vector3(Mathf.Cos(a), Mathf.Sin(a), 0f) * 0.075f);
      }
      _ring.enabled = false;

      _haloMat = JarvisSpatialGfx.Shell(ringColor, 0.03f, _rim, 3.5f);
      if (_haloMat != null)
      {
        var h = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        Object.Destroy(h.GetComponent<Collider>());
        h.transform.SetParent(transform, false);
        h.name = "NodeHalo";
        h.transform.localScale = Vector3.zero;
        h.GetComponent<Renderer>().sharedMaterial = _haloMat;
        JarvisSpatialGfx.Flat(h.GetComponent<Renderer>());
        _halo = h.transform;
      }
    }

    private void Update()
    {
      if (_body == null) return;
      float dt = Time.unscaledDeltaTime;
      _clock += dt;
      float pop = JarvisSpatialFx.EaseOutBack(Mathf.Clamp01((_clock - _delay) / 0.45f));
      float target = (Selected ? SelectedSize : BaseSize) * (Hovered ? 1.15f : 1f);
      _size = Mathf.Lerp(_size, target, 1f - Mathf.Exp(-14f * dt));
      _vis = Mathf.MoveTowards(_vis, Shown ? 1f : 0f, dt / 0.25f);
      if (_vis <= 0f && !Shown) { gameObject.SetActive(false); return; }
      float grow = pop * JarvisSpatialFx.Smooth(_vis);
      _body.localScale = Vector3.one * (_size * grow);
      if (_halo != null)
      {
        _halo.localScale = Vector3.one * (_size * grow * 2.3f);
        float wantRim = Selected ? 0.9f : Hovered ? 0.6f : 0.25f;
        _rim = Mathf.Lerp(_rim, wantRim, 1f - Mathf.Exp(-10f * dt));
        _haloMat.SetFloat("_Rim", _rim);
      }

      float wantAlpha = Selected ? 0.9f : Hovered ? 0.5f : 0f;
      _alpha = Mathf.Lerp(_alpha, wantAlpha, 1f - Mathf.Exp(-12f * dt));
      _ring.enabled = _alpha * _vis > 0.02f;
      if (_ring.enabled)
      {
        var c = new Color(_ringColor.r, _ringColor.g, _ringColor.b, _alpha * _vis);
        _ring.startColor = _ring.endColor = c;
        _ringT.localScale = Vector3.one * (1f + 0.06f * Mathf.Sin(_clock * 4f));
      }
    }
  }

  /// <summary>A bright dot that travels along an edge (data pulse / path traversal). Child of the edge's GameObject.</summary>
  public sealed class JarvisPathDot : MonoBehaviour
  {
    private LineRenderer _line;
    private Transform _dot;
    private float _clock, _delay;
    private const float Speed = 0.7f;

    public static JarvisPathDot Attach(LineRenderer line, Color color, float delay)
    {
      var go = new GameObject("PathDot");
      go.transform.SetParent(line.transform, false);
      var d = go.AddComponent<JarvisPathDot>();
      d._line = line; d._delay = delay;
      var s = GameObject.CreatePrimitive(PrimitiveType.Sphere);
      Object.Destroy(s.GetComponent<Collider>());
      s.transform.SetParent(go.transform, false);
      s.transform.localScale = Vector3.one * 0.02f;
      s.GetComponent<Renderer>().sharedMaterial = JarvisSpatialGfx.Neon(color, 2.6f);
      JarvisSpatialGfx.Flat(s.GetComponent<Renderer>());
      d._dot = s.transform;
      d._dot.gameObject.SetActive(false);
      return d;
    }

    private void Update()
    {
      _clock += Time.unscaledDeltaTime;
      int n = _line != null ? _line.positionCount : 0;
      if (_clock < _delay || n < 2) return;
      if (!_dot.gameObject.activeSelf) _dot.gameObject.SetActive(true);
      float f = Mathf.Repeat((_clock - _delay) * Speed, 1f) * (n - 1);
      int i = Mathf.Min((int)f, n - 2);
      _dot.localPosition = Vector3.Lerp(_line.GetPosition(i), _line.GetPosition(i + 1), f - i);
    }
  }

  /// <summary>Orb detail: three tilted rotating rings, three satellites with energy trails. Energy 0..1 drives speed and glow.</summary>
  public sealed class JarvisOrbFx : MonoBehaviour
  {
    public float Energy;
    public Color Tint = Color.cyan;
    private struct Ring { public Transform T; public LineRenderer L; public float Speed; }
    private readonly List<Ring> _rings = new List<Ring>();
    private readonly List<TrailRenderer> _trails = new List<TrailRenderer>();
    private readonly List<Material> _satMats = new List<Material>();

    public void Build(Color tint)
    {
      Tint = tint;
      float[] tilt = { 0f, 60f, -60f };
      for (int i = 0; i < 3; i++)
      {
        float radius = 0.70f + 0.06f * i;
        var go = new GameObject("OrbRing " + i);
        go.transform.SetParent(transform, false);
        go.transform.localRotation = Quaternion.Euler(tilt[i], i * 40f, 0f);
        var l = go.AddComponent<LineRenderer>();
        l.useWorldSpace = false; l.loop = true; l.positionCount = 64;
        l.widthMultiplier = 0.004f;   // world units; tune if rings look too thick or thin
        l.material = JarvisSpatialGfx.Line(Color.white, 2f);
        for (int j = 0; j < 64; j++)
        {
          float a = j * Mathf.PI * 2f / 64f;
          l.SetPosition(j, new Vector3(Mathf.Cos(a), Mathf.Sin(a), 0f) * radius);
        }
        _rings.Add(new Ring { T = go.transform, L = l, Speed = (i % 2 == 0 ? 1f : -1f) * (30f + 25f * i) });

        var sat = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        sat.name = "OrbSat";
        Destroy(sat.GetComponent<Collider>());
        sat.transform.SetParent(go.transform, false);
        sat.transform.localPosition = new Vector3(radius, 0f, 0f);
        sat.transform.localScale = Vector3.one * 0.06f;
        Material sm = JarvisSpatialGfx.Neon(tint, 2.4f);
        JarvisSpatialGfx.Flat(sat.GetComponent<Renderer>());
        sat.GetComponent<Renderer>().sharedMaterial = sm;
        _satMats.Add(sm);
        var tr = sat.AddComponent<TrailRenderer>();
        tr.time = 0.45f; tr.startWidth = 0.006f; tr.endWidth = 0f;
        tr.material = JarvisSpatialGfx.Line(Color.white, 2f);
        _trails.Add(tr);
      }
    }

    private void Update()
    {
      float dt = Time.unscaledDeltaTime;
      float boost = 1f + 4f * Energy;
      var c = new Color(Tint.r, Tint.g, Tint.b, 0.35f + 0.5f * Energy);
      foreach (Ring r in _rings)
      {
        r.T.Rotate(0f, 0f, r.Speed * boost * dt, Space.Self);
        r.T.localScale = Vector3.one * (1f + 0.12f * Energy);
        r.L.startColor = r.L.endColor = c;
      }
      foreach (TrailRenderer t in _trails) { t.startColor = c; t.endColor = new Color(c.r, c.g, c.b, 0f); }
      foreach (Material m in _satMats) m.color = Tint;
    }
  }

  /// <summary>Faint fading floor grid under the workspace. Works in passthrough too (it is only lines).</summary>
  public static class JarvisAtmosphere
  {
    public static void BuildFloor(Transform root, Color tint, float y = -1.2f, float half = 4f, float step = 0.5f)
    {
      var verts = new List<Vector3>(); var cols = new List<Color>(); var idx = new List<int>();
      int n = Mathf.RoundToInt(half / step);
      Color Fade(Vector3 p)
      {
        float f = 1f - Mathf.Clamp01(new Vector2(p.x, p.z).magnitude / half);
        return new Color(tint.r, tint.g, tint.b, 0.45f * f * f);
      }
      void Seg(Vector3 a, Vector3 b)
      {
        idx.Add(verts.Count); verts.Add(a); cols.Add(Fade(a));
        idx.Add(verts.Count); verts.Add(b); cols.Add(Fade(b));
      }
      for (int i = -n; i <= n; i++)
        for (int k = -n; k < n; k++)
        {
          Seg(new Vector3(k * step, y, i * step), new Vector3((k + 1) * step, y, i * step));
          Seg(new Vector3(i * step, y, k * step), new Vector3(i * step, y, (k + 1) * step));
        }
      var mesh = new Mesh();
      mesh.SetVertices(verts); mesh.SetColors(cols);
      mesh.SetIndices(idx, MeshTopology.Lines, 0);
      var go = new GameObject("JARVIS Floor Grid", typeof(MeshFilter), typeof(MeshRenderer));
      go.transform.SetParent(root, false);
      go.GetComponent<MeshFilter>().sharedMesh = mesh;
      go.GetComponent<MeshRenderer>().sharedMaterial = JarvisSpatialGfx.Line(Color.white, 1.2f);
    }

    /// <summary>Sparse drifting motes around the workspace (violet and cyan) for depth.</summary>
    public static void BuildDust(Transform root, Color a, Color b)
    {
      var go = new GameObject("JARVIS Dust");
      go.transform.SetParent(root, false);
      var ps = go.AddComponent<ParticleSystem>();
      ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
      var main = ps.main;
      main.loop = true; main.startLifetime = 14f; main.startSpeed = 0.02f; main.startSize = 0.006f;
      main.maxParticles = 160; main.simulationSpace = ParticleSystemSimulationSpace.Local;
      main.startColor = new ParticleSystem.MinMaxGradient(a, b);
      var em = ps.emission; em.rateOverTime = 12f;
      var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Box; sh.scale = new Vector3(4f, 2.2f, 3f);
      var col = ps.colorOverLifetime; col.enabled = true;
      var g = new Gradient();
      g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.7f, 0.2f), new GradientAlphaKey(0.7f, 0.8f), new GradientAlphaKey(0f, 1f) });
      col.color = new ParticleSystem.MinMaxGradient(g);
      var r = go.GetComponent<ParticleSystemRenderer>();
      r.sharedMaterial = JarvisSpatialGfx.Line(Color.white, 1.5f);
      ps.Play();
    }
  }
}
