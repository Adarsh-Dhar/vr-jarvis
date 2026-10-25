using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace JarvisVR
{
  public sealed class JarvisPalmMenu : MonoBehaviour
  {
    // VERIFY: bone ids differ between SDK versions. If these fail to compile, use the
    // XRHand_Wrist / XRHand_IndexProximal / XRHand_LittleProximal / XRHand_IndexTip names.
    private const OVRSkeleton.BoneId Wrist = OVRSkeleton.BoneId.Hand_WristRoot;
    private const OVRSkeleton.BoneId IndexBase = OVRSkeleton.BoneId.Hand_Index1;
    private const OVRSkeleton.BoneId PinkyBase = OVRSkeleton.BoneId.Hand_Pinky1;
    private const OVRSkeleton.BoneId IndexTip = OVRSkeleton.BoneId.Hand_IndexTip;

    /// <summary>Set to -1 if the menu appears when the back of your hand faces up.</summary>
    public float PalmNormalSign = 1f;
    public float FistDistance = 0.10f; // fingertip-to-wrist, metres. VERIFY on device.

    private OVRSkeleton _skeleton;
    private Transform _root;
    private Camera _cam;
    private bool _visible;
    private float _nextFind;
    private Func<string, bool> _isActive;
    private readonly List<KeyValuePair<string, Image>> _buttons = new List<KeyValuePair<string, Image>>();

    public void Initialize(Action<string> onMode, string[] modes, Func<string, bool> isActive)
    {
      _isActive = isActive;
      JarvisPalette pal = JarvisPalette.Current;
      _root = new GameObject("JARVIS PalmMenu").transform;
      for (int i = 0; i < modes.Length; i++)
      {
        string mode = modes[i];
        GameObject go = new GameObject("Palm " + mode, typeof(RectTransform), typeof(Canvas), typeof(BoxCollider));
        go.transform.SetParent(_root, false);
        go.GetComponent<Canvas>().renderMode = RenderMode.WorldSpace;
        RectTransform rt = go.GetComponent<RectTransform>();
        rt.sizeDelta = new Vector2(200f, 64f);
        rt.localScale = Vector3.one * 0.00028f; // 5.6 cm x 1.8 cm
        rt.localPosition = new Vector3((i - (modes.Length - 1) * 0.5f) * 0.062f, 0f, 0f);
        go.GetComponent<BoxCollider>().size = new Vector3(200f, 64f, 14f);

        GameObject bg = new GameObject("bg", typeof(RectTransform), typeof(Image));
        bg.transform.SetParent(go.transform, false);
        RectTransform bgr = bg.GetComponent<RectTransform>();
        bgr.anchorMin = Vector2.zero; bgr.anchorMax = Vector2.one; bgr.offsetMin = bgr.offsetMax = Vector2.zero;
        Image img = bg.GetComponent<Image>();
        img.sprite = JarvisGfx.RoundedRect();
        img.type = Image.Type.Sliced;
        img.color = pal.PanelRaised;

        GameObject tx = new GameObject("label", typeof(RectTransform), typeof(Text));
        tx.transform.SetParent(go.transform, false);
        RectTransform tr = tx.GetComponent<RectTransform>();
        tr.anchorMin = Vector2.zero; tr.anchorMax = Vector2.one; tr.offsetMin = tr.offsetMax = Vector2.zero;
        Text t = tx.GetComponent<Text>();
        JarvisFonts.Resolve(FontRole.Heading, mode, FontStyle.Bold, out Font f, out FontStyle fs);
        t.font = f; t.fontStyle = fs; t.fontSize = 26; t.text = mode;
        t.alignment = TextAnchor.MiddleCenter; t.color = pal.Text; t.raycastTarget = false;

        go.AddComponent<JarvisGraphNode>().Initialize("mode:" + mode, id => onMode(mode), null);
        _buttons.Add(new KeyValuePair<string, Image>(mode, img));
      }
      _root.gameObject.SetActive(false);
    }

    private void Update()
    {
      if (_root == null) return;
      if (_skeleton == null)
      {
        if (Time.unscaledTime >= _nextFind)
        {
          _nextFind = Time.unscaledTime + 1f;
          GameObject left = GameObject.Find("LeftOVRHand");
          if (left != null) _skeleton = left.GetComponentInChildren<OVRSkeleton>();
        }
        Show(false);
        return;
      }

      if (!_skeleton.IsInitialized || !_skeleton.IsDataValid || !_skeleton.IsDataHighConfidence) { Show(false); return; }
      if (!TryBone(Wrist, out Vector3 w) || !TryBone(IndexBase, out Vector3 i) ||
          !TryBone(PinkyBase, out Vector3 p) || !TryBone(IndexTip, out Vector3 tip)) { Show(false); return; }

      Vector3 normal = Vector3.Cross(i - w, p - w).normalized * PalmNormalSign;
      float up = Vector3.Dot(normal, Vector3.up);
      bool fist = Vector3.Distance(tip, w) < FistDistance;
      bool want = !fist && (_visible ? up > 0.5f : up > 0.75f); // hysteresis
      Show(want);
      if (!want) return;

      if (_cam == null) _cam = Camera.main;
      _root.position = (w + i + p) / 3f + Vector3.up * 0.11f;
      if (_cam != null)
        _root.rotation = Quaternion.LookRotation(_root.position - _cam.transform.position, Vector3.up);

      JarvisPalette pal = JarvisPalette.Current;
      foreach (KeyValuePair<string, Image> b in _buttons)
        b.Value.color = _isActive != null && _isActive(b.Key)
          ? new Color(pal.Cyan.r, pal.Cyan.g, pal.Cyan.b, 0.35f) : pal.PanelRaised;
    }

    private void Show(bool v)
    {
      if (_visible == v) return;
      _visible = v;
      _root.gameObject.SetActive(v);
    }

    private bool TryBone(OVRSkeleton.BoneId id, out Vector3 position)
    {
      position = default(Vector3);
      IList<OVRBone> bones = _skeleton.Bones;
      if (bones == null) return false;
      for (int n = 0; n < bones.Count; n++)
      {
        if (bones[n].Id == id && bones[n].Transform != null) { position = bones[n].Transform.position; return true; }
      }
      return false;
    }
  }
}
