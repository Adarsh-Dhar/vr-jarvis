using System;
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
    public Image Background, Fill;
    public Color Idle = new Color(0.1f, 0.15f, 0.24f, 1f), Hover = new Color(0.16f, 0.27f, 0.42f, 1f);
    public void SetHover(bool on) { if (Background != null) Background.color = on ? Hover : Idle; }
    public void SetProgress(float p) { if (Fill != null) { Fill.fillAmount = Mathf.Clamp01(p); Fill.enabled = p > 0.001f; } }
    public void Click() { if (OnClick != null) OnClick(); }
  }

  /// <summary>Grab handle: pinch and drag moves Target.</summary>
  public sealed class JarvisSpatialGrab : MonoBehaviour { public Transform Target; }

  public static class JarvisSpatialGfx
  {
    public static Material Unlit(Color c)
    {
      Shader s = Shader.Find("Universal Render Pipeline/Unlit");
      if (s == null) s = Shader.Find("Unlit/Color");
      var m = new Material(s);
      m.color = c;
      return m;
    }
  }

  /// <summary>One floating world-space panel: 1 canvas pixel = 1.2 mm. Independent of every other panel.</summary>
  public sealed class JarvisSpatialPanel : MonoBehaviour
  {
    public const float Scale = 0.0012f;
    public float Width, Height;
    public Text Body, TitleText;
    private Image _border;

    public static JarvisSpatialPanel Create(Transform parent, string title, float w, float h, Vector3 localPos, Color accent)
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

      p._border = NewImage(go.transform, "Border", w + 4, h + 4, new Color(accent.r, accent.g, accent.b, 0.55f));
      NewImage(go.transform, "Background", w, h, new Color(pal.Glass.r, pal.Glass.g, pal.Glass.b, 0.93f));
      NewImage(go.transform, "Handle", 70, 6, new Color(accent.r, accent.g, accent.b, 0.9f)).rectTransform.anchoredPosition = new Vector2(0, h / 2f - 12);
      p.TitleText = NewText(go.transform, "Title", title.ToUpperInvariant(), 22, pal.TextMuted, TextAnchor.UpperLeft, FontRole.Heading,
        new Vector2(w - 40, 34), new Vector2(0, h / 2f - 36));
      p.Body = NewText(go.transform, "Body", "", 26, pal.Text, TextAnchor.UpperLeft, FontRole.Auto,
        new Vector2(w - 40, h - 80), new Vector2(0, -26));

      var box = go.AddComponent<BoxCollider>();
      box.size = new Vector3(w, h, 8f);
      var grabObject = new GameObject("Grab", typeof(RectTransform));
      grabObject.transform.SetParent(go.transform, false);
      grabObject.transform.localPosition = new Vector3(0, h / 2f - 28, -6f);
      var grabBox = grabObject.AddComponent<BoxCollider>();
      grabBox.size = new Vector3(w, 56f, 10f);
      grabObject.AddComponent<JarvisSpatialGrab>().Target = go.transform;
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
    public void SetAccent(Color c) { if (_border != null) _border.color = new Color(c.r, c.g, c.b, 0.55f); }
    public void Show(bool on) { if (gameObject.activeSelf != on) gameObject.SetActive(on); }
    public bool Visible { get { return gameObject.activeSelf; } }

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
      btn.Background = NewImage(go.transform, "Bg", w, h, btn.Idle);
      Image fill = NewImage(go.transform, "Fill", w, h, new Color(a.r, a.g, a.b, 0.7f));
      fill.type = Image.Type.Filled;
      fill.fillMethod = Image.FillMethod.Horizontal;
      fill.fillAmount = 0f;
      fill.enabled = false;
      btn.Fill = fill;
      NewText(go.transform, "Label", label, 24, pal.Text, TextAnchor.MiddleCenter, FontRole.Auto, new Vector2(w - 12, h), Vector2.zero);
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
