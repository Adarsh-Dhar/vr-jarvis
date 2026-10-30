using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace JarvisVR
{
  /// <summary>Turns a transform to face the user (yaw only). Canvases and TextMeshes read correctly when their +Z points away from the viewer.</summary>
  public sealed class JarvisBillboard : MonoBehaviour
  {
    private Camera _cam;
    private void LateUpdate()
    {
      if (_cam == null) _cam = Camera.main;
      if (_cam == null) return;
      Vector3 d = transform.position - _cam.transform.position;
      d.y = 0f;
      if (d.sqrMagnitude > 0.0001f) transform.rotation = Quaternion.LookRotation(d, Vector3.up);
    }
  }

  /// <summary>Pinch target. HoldSeconds > 0 means the pinch must be held that long (used for approval).</summary>
  public sealed class JarvisSpatialButton : MonoBehaviour
  {
    public Action OnClick;
    public float HoldSeconds;
    public Image Background, Fill, FocusRing;
    public Text Label;
    public Color Idle = new Color(0.1f, 0.15f, 0.24f, 1f), Hover = new Color(0.16f, 0.27f, 0.42f, 1f);
    public Color Pressed = new Color(0.22f, 0.40f, 0.60f, 1f), DisabledColor = new Color(0.07f, 0.08f, 0.10f, 1f);
    public Color LabelColor = Color.white, DisabledLabel = new Color(0.42f, 0.47f, 0.53f, 1f);

    private bool _hover, _pressed, _disabled, _focused;
    private static JarvisSpatialButton _focusOwner;   // only one button has focus at a time

    /// <summary>False greys the button out and makes it ignore presses. Priority of looks: disabled, pressed, hover, idle.</summary>
    public bool Interactable
    {
      get { return !_disabled; }
      set
      {
        _disabled = !value;
        if (_disabled) { _pressed = false; _hover = false; SetProgress(0f); if (_focusOwner == this) ClearFocus(); }
        Refresh();
      }
    }

    public void SetHover(bool on) { _hover = on; Refresh(); }
    public void SetPressed(bool on) { _pressed = on && !_disabled; Refresh(); }

    /// <summary>Keyboard-style focus ring: the last button that was activated keeps an outline until another takes focus.</summary>
    public void Focus()
    {
      if (_disabled) return;
      if (_focusOwner != null && _focusOwner != this) _focusOwner.ClearFocus();
      _focusOwner = this; _focused = true; Refresh();
    }
    public void ClearFocus() { if (_focusOwner == this) _focusOwner = null; _focused = false; Refresh(); }
    private void OnDisable() { if (_focusOwner == this) _focusOwner = null; _focused = false; _pressed = false; _hover = false; }

    private void Refresh()
    {
      if (Background != null) Background.color = _disabled ? DisabledColor : _pressed ? Pressed : _hover ? Hover : Idle;
      if (FocusRing != null) FocusRing.enabled = _focused && !_disabled;
      if (Label != null) Label.color = _disabled ? DisabledLabel : LabelColor;
    }

    public void SetProgress(float p) { if (Fill != null) { Fill.fillAmount = Mathf.Clamp01(p); Fill.enabled = p > 0.001f; } }
    public void Click() { if (_disabled) return; if (OnClick != null) OnClick(); }
  }

  /// <summary>Grab handle: pinch and drag moves Target.</summary>
  public sealed class JarvisSpatialGrab : MonoBehaviour
  {
    public Transform Target;
    private Vector3 _goal, _vel;
    private bool _has;
    public void SetGoal(Vector3 p) { _goal = p; _has = true; }
    private void Update()
    {
      if (!_has || Target == null) return;
      Target.position = Vector3.SmoothDamp(Target.position, _goal, ref _vel, 0.08f, Mathf.Infinity, Time.unscaledDeltaTime);
      if ((Target.position - _goal).sqrMagnitude < 1e-8f) _has = false;
    }
  }

  public static class JarvisSpatialGfx
  {
    public static Shader Find(params string[] names)
    {
      foreach (string n in names) { Shader sh = Shader.Find(n); if (sh != null && sh.isSupported) return sh; }
      return null;
    }

    /// <summary>HDR-capable emissive unlit material (feeds Bloom). solid = writes depth (node bodies, orb).</summary>
    public static Material Neon(Color c, float intensity = 1.6f, bool solid = false)
    {
      return Make(Find("JARVIS/NeonUnlit", "Universal Render Pipeline/Unlit", "Sprites/Default", "Unlit/Color"), c, intensity, solid);
    }

    public static Material Unlit(Color c) { return Neon(c, 1f, true); }

    /// <summary>Material for LineRenderer, trails and particles: needs vertex colors.</summary>
    public static Material Line(Color c, float intensity = 1.6f)
    {
      return Make(Find("JARVIS/NeonUnlit", "Sprites/Default"), c, intensity, false);
    }

    private static Material Make(Shader sh, Color c, float intensity, bool solid)
    {
      if (sh == null) { Debug.LogError("JARVIS: no usable unlit shader found."); sh = Shader.Find("Hidden/Internal-Colored"); }
      var m = new Material(sh);
      m.color = c;
      if (m.HasProperty("_Intensity")) m.SetFloat("_Intensity", intensity);
      if (m.HasProperty("_ZWrite")) m.SetFloat("_ZWrite", solid ? 1f : 0f);
      if (solid) m.renderQueue = 2000;
      return m;
    }

    /// <summary>Fresnel bubble. Returns null when the shader is missing: callers must then remove the mesh instead of leaving a default silver sphere.</summary>
    public static Material Shell(Color c, float fill, float rim, float power)
    {
      Shader sh = Find("JARVIS/FresnelShell");
      if (sh == null) { Debug.LogWarning("JARVIS: FresnelShell shader not found; shell skipped."); return null; }
      var m = new Material(sh);
      m.SetColor("_Color", c); m.SetFloat("_Fill", fill); m.SetFloat("_Rim", rim); m.SetFloat("_Power", power);
      return m;
    }

    /// <summary>Glass panel background (JARVIS/UIGlass). Returns null when the shader is missing so the caller keeps its flat fallback.
    /// Backdrop refraction is switched on only if the active URP asset has Opaque Texture enabled (see Tools > JARVIS > Configure Rendering).</summary>
    public static Material Glass(float w, float h, Color accent)
    {
      Shader sh = Find("JARVIS/UIGlass");
      if (sh == null) { Debug.LogWarning("JARVIS: UIGlass shader not found; panels keep the flat background."); return null; }
      JarvisPalette pal = JarvisPalette.Current;
      var m = new Material(sh);
      m.SetColor("_Tint", new Color(pal.Glass.r * 0.6f, pal.Glass.g * 0.6f, pal.Glass.b * 0.7f, 0.62f));
      m.SetColor("_EdgeColor", accent);
      m.SetVector("_Size", new Vector4(w, h, 0f, 0f));
      var urp = UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline as UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset;
      if (urp != null && urp.supportsCameraOpaqueTexture) m.EnableKeyword("_REFRACT");
      return m;
    }

    /// <summary>No shadows, probes or motion vectors: keeps reflections and lighting from turning flat shapes silver.</summary>
    public static void Flat(Renderer r)
    {
      r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
      r.receiveShadows = false;
      r.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off;
      r.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
      r.motionVectorGenerationMode = MotionVectorGenerationMode.ForceNoMotion;
    }
  }

  /// <summary>One floating world-space panel: 1 canvas pixel = 1.2 mm. Independent of every other panel.</summary>
  public sealed class JarvisSpatialPanel : MonoBehaviour
  {
    public const float Scale = 0.0012f;
    public float Width, Height;
    public Text Body, TitleText;
    public JarvisPanelAnim Anim;
    public bool Pinned, UserClosed;
    private Image _border, _glow;
    public const float BarHeight = 58f;
    private readonly List<RectTransform> _frame = new List<RectTransform>();
    private readonly List<float> _framePad = new List<float>();
    private readonly HashSet<GameObject> _chrome = new HashSet<GameObject>();
    private RectTransform _resizeRt;
    private BoxCollider _rootBox;
    private bool _minimized;
    private float _c;
    private Color _accent;
    private Material _glassMat;

    public static JarvisSpatialPanel Create(Transform parent, string title, float w, float h, Vector3 localPos, Color accent, bool closable = true)
    {
      JarvisPalette pal = JarvisPalette.Current;
      var go = new GameObject("Panel " + title, typeof(RectTransform), typeof(Canvas));
      go.transform.SetParent(parent, false);
      go.transform.localPosition = localPos;
      go.transform.localScale = Vector3.one * Scale;
      go.GetComponent<RectTransform>().sizeDelta = new Vector2(w, h);
      Canvas canvas = go.GetComponent<Canvas>();
      canvas.renderMode = RenderMode.WorldSpace;
      canvas.worldCamera = Camera.main;
      var p = go.AddComponent<JarvisSpatialPanel>();
      p.Width = w; p.Height = h;
      go.AddComponent<JarvisBillboard>();
      p.Anim = go.AddComponent<JarvisPanelAnim>();
      p._accent = accent;

      // neon-noir: soft outer glow + crisp emissive edge, smoked glass, cyan/magenta sheen
      p._glow = NewImage(go.transform, "Glow", w + 22, h + 22, new Color(accent.r, accent.g, accent.b, 0.14f));
      p._border = NewImage(go.transform, "Border", w + 4, h + 4, new Color(accent.r, accent.g, accent.b, 0.9f));
      Image bg = NewImage(go.transform, "Background", w, h, new Color(pal.Glass.r * 0.6f, pal.Glass.g * 0.6f, pal.Glass.b * 0.7f, 0.62f));
      Material glass = JarvisSpatialGfx.Glass(w, h, accent);
      if (glass != null) { bg.material = glass; bg.color = Color.white; p._glassMat = glass; }   // the shader supplies tint; vertex alpha carries the fade
      Image sheen = JarvisSpatialFx.AddSheen(go.transform, w, h, accent);
      p._frame.Add(p._glow.rectTransform); p._framePad.Add(22f);
      p._frame.Add(p._border.rectTransform); p._framePad.Add(4f);
      p._frame.Add(bg.rectTransform); p._framePad.Add(0f);
      p._frame.Add(sheen.rectTransform); p._framePad.Add(0f);
      NewImage(go.transform, "Handle", 70, 6, new Color(accent.r, accent.g, accent.b, 0.9f)).rectTransform.anchoredPosition = new Vector2(0, h / 2f - 12);
      p.TitleText = NewText(go.transform, "Title", title.ToUpperInvariant(), 22, pal.TextMuted, TextAnchor.UpperLeft, FontRole.Heading,
        new Vector2(w - 40, 34), new Vector2(0, h / 2f - 36));
      p.Body = NewText(go.transform, "Body", "", 26, pal.Text, TextAnchor.UpperLeft, FontRole.Auto,
        new Vector2(w - 40, h - 80), new Vector2(0, -26));

      var box = go.AddComponent<BoxCollider>();
      box.size = new Vector3(w, h, 8f);
      p._rootBox = box;
      p.Anim.OnSolid = p.SetSolid;
      var grabObject = new GameObject("Grab", typeof(RectTransform));
      grabObject.transform.SetParent(go.transform, false);
      grabObject.transform.localPosition = new Vector3(0, h / 2f - 28, -6f);
      var grabBox = grabObject.AddComponent<BoxCollider>();
      grabBox.size = new Vector3(w, 56f, 10f);
      grabObject.AddComponent<JarvisSpatialGrab>().Target = go.transform;

      // resize handle: hangs off the bottom-right corner so it never covers buttons
      var rh = new GameObject("Resize", typeof(RectTransform), typeof(Image));
      rh.transform.SetParent(go.transform, false);
      var rrt = rh.GetComponent<RectTransform>();
      rrt.sizeDelta = new Vector2(40, 40);
      rrt.anchoredPosition = new Vector2(w / 2f + 4, -h / 2f - 4);
      var rimg = rh.GetComponent<Image>();
      rimg.sprite = JarvisGfx.RoundedRect(); rimg.type = Image.Type.Sliced;
      rimg.color = new Color(accent.r, accent.g, accent.b, 0.6f); rimg.raycastTarget = false;
      var rbox = rh.AddComponent<BoxCollider>();
      rbox.size = new Vector3(80, 80, 30f); rbox.center = new Vector3(0, 0, 8f);   // larger hit area, in front for device pinch
      rh.AddComponent<JarvisSpatialResize>().Panel = p.Anim;
      p._resizeRt = rrt;

      p.AddChrome(accent, closable);
      return p;
    }

    /// <summary>Place the body text block: topPx from the panel's top edge, heightPx tall.</summary>
    public void SetBodyBox(float topPx, float heightPx)
    {
      RectTransform rt = Body.rectTransform;
      rt.sizeDelta = new Vector2(Width - 40, heightPx);
      rt.anchoredPosition = new Vector2(0, Height / 2f - topPx - heightPx / 2f);
    }

    /// <summary>Switch the body text to the monospace font (code, diffs).</summary>
    public void UseMono(int size)
    {
      JarvisFonts.Resolve(FontRole.Mono, "{", FontStyle.Normal, out Font f, out FontStyle st);
      Body.font = f; Body.fontStyle = st; Body.fontSize = size;
    }

    public void SetBody(string text) { if (Body != null) Body.text = text ?? ""; }
    public void SetTitle(string text) { if (TitleText != null) TitleText.text = (text ?? "").ToUpperInvariant(); }
    public void SetAccent(Color c)
    {
      if (_border != null) _border.color = new Color(c.r, c.g, c.b, 0.9f);
      if (_glow != null) _glow.color = new Color(c.r, c.g, c.b, 0.14f);
    }

    /// <summary>Fade and scale in or out. A panel the user closed stays closed until Reopen().</summary>
    public void Show(bool on, float delay = 0f)
    {
      if (on && UserClosed) return;
      Anim.SetVisible(on, delay);
    }
    public bool Visible { get { return Anim.WantVisible; } }
    public void Close() { UserClosed = true; Anim.SetVisible(false); }
    public void Reopen() { UserClosed = false; }

    /// <summary>Title-bar controls: pin (lock position), minimize/restore, close.</summary>
    public void AddChrome(Color accent, bool closable)
    {
      float x = Width - 12f - 3 * 68f;
      _chrome.Add(AddButton("PIN", x, 8, 64, 34, TogglePin, 0f, accent).gameObject);
      _chrome.Add(AddButton("–", x + 68, 8, 64, 34, ToggleMinimize, 0f, accent).gameObject);
      if (closable) _chrome.Add(AddButton("×", x + 136, 8, 64, 34, Close, 0f, JarvisPalette.Current.Red).gameObject);
    }

    public bool Minimized { get { return _minimized; } }
    public void ToggleMinimize() { SetMinimized(!_minimized); }

    /// <summary>Collapses the panel to its title bar (frame shrinks, body text and action buttons hide; PIN, minimize and close stay).</summary>
    public void SetMinimized(bool m)
    {
      _minimized = m;
      foreach (Transform ch in transform)
      {
        bool content = ch.name == "Body" || (ch.name.StartsWith("Button ") && !_chrome.Contains(ch.gameObject));
        if (content) ch.gameObject.SetActive(!m);
      }
    }

    private void Update()
    {
      float target = _minimized ? 1f : 0f;
      if (Mathf.Approximately(_c, target)) return;
      _c = Mathf.MoveTowards(_c, target, Time.unscaledDeltaTime / 0.18f);
      ApplyCollapse(JarvisSpatialFx.Smooth(_c));
    }

    private void ApplyCollapse(float k)
    {
      float cur = Mathf.Lerp(Height, BarHeight, k);
      for (int i = 0; i < _frame.Count; i++)
      {
        _frame[i].sizeDelta = new Vector2(_frame[i].sizeDelta.x, cur + _framePad[i]);
        _frame[i].anchoredPosition = new Vector2(0f, (Height - cur) / 2f);   // top edge stays fixed
      }
      if (_glassMat != null) _glassMat.SetVector("_Size", new Vector4(Width, cur, 0f, 0f));   // keep the glass edge on the shrinking frame
      if (_rootBox != null) { _rootBox.size = new Vector3(Width, cur, 8f); _rootBox.center = new Vector3(0f, (Height - cur) / 2f, 0f); }
      if (_resizeRt != null) _resizeRt.anchoredPosition = new Vector2(Width / 2f + 4f, Height / 2f - cur - 4f);
    }

    /// <summary>Called by JarvisPanelAnim: no collider is active while the panel fades, so a ghost never blocks rays.</summary>
    public void SetSolid(bool solid)
    {
      foreach (Collider c in GetComponentsInChildren<Collider>(true)) c.enabled = solid;
      if (solid && Pinned) { Transform g = transform.Find("Grab"); if (g != null) g.GetComponent<Collider>().enabled = false; }
    }

    public void TogglePin()
    {
      Pinned = !Pinned;
      Transform g = transform.Find("Grab");
      if (g != null) g.GetComponent<Collider>().enabled = !Pinned;
      SetAccent(Pinned ? JarvisPalette.Current.Amber : _accent);
    }

    /// <summary>x, y are the button's top-left corner measured from the panel's top-left, in pixels.</summary>
    public JarvisSpatialButton AddButton(string label, float x, float y, float w, float h, Action onClick, float holdSeconds = 0f, Color? accent = null)
    {
      JarvisPalette pal = JarvisPalette.Current;
      var go = new GameObject("Button " + label, typeof(RectTransform));
      go.transform.SetParent(transform, false);
      var rt = go.GetComponent<RectTransform>();
      rt.sizeDelta = new Vector2(w, h);
      rt.anchoredPosition = new Vector2(x + w / 2f - Width / 2f, Height / 2f - y - h / 2f);
      var btn = go.AddComponent<JarvisSpatialButton>();
      btn.OnClick = onClick;
      btn.HoldSeconds = holdSeconds;
      Color a = accent ?? pal.Cyan;
      btn.Idle = new Color(a.r * 0.18f, a.g * 0.18f, a.b * 0.18f, 1f);
      btn.Hover = new Color(a.r * 0.40f, a.g * 0.40f, a.b * 0.40f, 1f);
      btn.Pressed = new Color(a.r * 0.62f, a.g * 0.62f, a.b * 0.62f, 1f);
      btn.LabelColor = pal.Text;
      btn.FocusRing = NewImage(go.transform, "Focus", w + 10, h + 10, new Color(a.r, a.g, a.b, 0.95f));   // drawn first, so it shows as an outline
      btn.FocusRing.enabled = false;
      btn.Background = NewImage(go.transform, "Bg", w, h, btn.Idle);
      Image fill = NewImage(go.transform, "Fill", w, h, new Color(a.r, a.g, a.b, 0.7f));
      fill.type = Image.Type.Filled;
      fill.fillMethod = Image.FillMethod.Horizontal;
      fill.fillAmount = 0f;
      fill.enabled = false;
      btn.Fill = fill;
      btn.Label = NewText(go.transform, "Label", label, 24, pal.Text, TextAnchor.MiddleCenter, FontRole.Auto, new Vector2(w - 12, h), Vector2.zero);
      var box = go.AddComponent<BoxCollider>();
      box.size = new Vector3(w, h, 12f);
      box.center = new Vector3(0, 0, -8f);   // in front of the panel so rays reach the button first
      return btn;
    }

    private static Image NewImage(Transform parent, string name, float w, float h, Color color)
    {
      var go = new GameObject(name, typeof(RectTransform), typeof(Image));
      go.transform.SetParent(parent, false);
      var rt = go.GetComponent<RectTransform>();
      rt.sizeDelta = new Vector2(w, h);
      var img = go.GetComponent<Image>();
      img.sprite = JarvisGfx.RoundedRect();
      img.type = Image.Type.Sliced;
      img.color = color;
      img.raycastTarget = false;
      return img;
    }

    public static Text NewText(Transform parent, string name, string text, int size, Color color, TextAnchor anchor,
      FontRole role, Vector2 box, Vector2 pos)
    {
      var go = new GameObject(name, typeof(RectTransform), typeof(Text));
      go.transform.SetParent(parent, false);
      var rt = go.GetComponent<RectTransform>();
      rt.sizeDelta = box;
      rt.anchoredPosition = pos;
      var t = go.GetComponent<Text>();
      JarvisFonts.Resolve(role, text, FontStyle.Normal, out Font font, out FontStyle style);
      t.font = font; t.fontStyle = style;
      t.text = text; t.fontSize = size; t.color = color; t.alignment = anchor;
      t.horizontalOverflow = HorizontalWrapMode.Wrap;
      t.verticalOverflow = VerticalWrapMode.Truncate;
      t.supportRichText = true;
      t.raycastTarget = false;
      return t;
    }
  }
}
