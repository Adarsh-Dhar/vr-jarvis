using System;
using UnityEngine;

namespace JarvisVR
{
  public sealed class JarvisSpatialInput : MonoBehaviour
  {
    private sealed class Slot
    {
      public Ray Ray; public bool Valid, Down, WasDown;
      public Transform Reticle;
      public JarvisSpatialButton Hover, Btn; public float BtnTime; public bool BtnFired;
      public JarvisGraphNode Node; public Vector3 NodeStart, NodeLast; public float NodeDist, NodeTime; public bool NodeDragging, NodeHeld;
      public JarvisNodeFx HoverFx;
      public JarvisSpatialResize Resize; public float ResizeDist, ResizeStartScale, ResizeStartDistance;
      public JarvisSpatialGrab Grab; public float GrabDist; public Vector3 GrabOffset;
      public bool Busy { get { return Btn != null || Node != null || Grab != null || Resize != null; } }
    }

    private readonly Slot[] _slots = { new Slot(), new Slot(), new Slot() };   // left hand, right hand, editor mouse
    private OVRHand[] _hands;
    private Camera _cam;
    private Transform _graphRoot;
    private Action _toggleVoice;
    private bool _zooming;
    private float _zoomStartDistance, _zoomStartScale = 1f;

    public void Initialize(Camera cam, Transform graphRoot, Action toggleVoice)
    {
      _cam = cam; _graphRoot = graphRoot; _toggleVoice = toggleVoice;
      _hands = FindObjectsByType<OVRHand>(FindObjectsInactive.Include, FindObjectsSortMode.None);
      foreach (Slot s in _slots)
      {
        GameObject r = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        r.name = "JARVIS pointer";
        Destroy(r.GetComponent<Collider>());
        r.transform.localScale = Vector3.one * 0.016f;
        r.GetComponent<Renderer>().sharedMaterial = JarvisSpatialGfx.Unlit(new Color(0.24f, 0.84f, 0.91f));
        r.SetActive(false);
        s.Reticle = r.transform;
      }
    }

    private void Update()
    {
      for (int i = 0; i < 2; i++)
      {
        Slot s = _slots[i];
        OVRHand h = _hands != null && i < _hands.Length ? _hands[i] : null;
        s.Valid = h != null && h.IsTracked && h.IsPointerPoseValid && h.PointerPose != null;
        s.Down = false;
        if (s.Valid)
        {
          s.Ray = new Ray(h.PointerPose.position, h.PointerPose.forward);
          s.Down = h.GetFingerIsPinching(OVRHand.HandFinger.Index);
        }
      }
#if UNITY_EDITOR
      Slot m = _slots[2];
      m.Valid = _cam != null;
      if (m.Valid) { m.Ray = _cam.ScreenPointToRay(Input.mousePosition); m.Down = Input.GetMouseButton(0); }
      if (Input.GetKeyDown(KeyCode.Space) && _toggleVoice != null) _toggleVoice();
#endif
      foreach (Slot s in _slots) Process(s);
      UpdateTwoHandScale();
      foreach (Slot s in _slots) s.WasDown = s.Down;
    }

    private void Process(Slot s)
    {
      s.Reticle.gameObject.SetActive(s.Valid);
      if (!s.Valid)
      {
        if (s.HoverFx != null) { s.HoverFx.Hovered = false; s.HoverFx = null; }
        Release(s, null);
        return;
      }

      JarvisSpatialButton hoverBtn = null; JarvisGraphNode hoverNode = null; JarvisSpatialGrab hoverGrab = null;
      JarvisNodeFx hoverFx = null; JarvisSpatialResize hoverResize = null;
      float dist = 1.5f; bool hasHit = false;
      if (Physics.Raycast(s.Ray, out RaycastHit hit, 6f, ~0, QueryTriggerInteraction.Ignore))
      {
        hasHit = true; dist = hit.distance;
        hoverBtn = hit.collider.GetComponentInParent<JarvisSpatialButton>();
        hoverNode = hit.collider.GetComponentInParent<JarvisGraphNode>();
        hoverGrab = hit.collider.GetComponentInParent<JarvisSpatialGrab>();
        hoverFx = hit.collider.GetComponentInParent<JarvisNodeFx>();
        hoverResize = hit.collider.GetComponentInParent<JarvisSpatialResize>();
      }
      s.Reticle.position = s.Ray.GetPoint(hasHit ? dist - 0.01f : 1.5f);
      s.Reticle.GetComponent<Renderer>().sharedMaterial.color = s.Down ? new Color(0.96f, 0.65f, 0.14f) : new Color(0.24f, 0.84f, 0.91f);

      if (s.Hover != hoverBtn)
      {
        if (s.Hover != null) s.Hover.SetHover(false);
        if (hoverBtn != null) hoverBtn.SetHover(true);
        s.Hover = hoverBtn;
      }

      if (s.HoverFx != hoverFx)
      {
        if (s.HoverFx != null) s.HoverFx.Hovered = false;
        if (hoverFx != null) hoverFx.Hovered = true;
        s.HoverFx = hoverFx;
      }

      if (s.Down && !s.WasDown)
      {
        if (hoverBtn != null) { s.Btn = hoverBtn; s.BtnTime = Time.unscaledTime; s.BtnFired = false; }
        else if (hoverNode != null)
        {
          s.Node = hoverNode; s.NodeDist = dist; s.NodeStart = s.NodeLast = s.Ray.GetPoint(dist); s.NodeDragging = false;
          s.NodeTime = Time.unscaledTime; s.NodeHeld = false;
        }
        else if (hoverGrab != null)
        {
          s.Grab = hoverGrab; s.GrabDist = dist;
          s.GrabOffset = hoverGrab.Target.position - s.Ray.GetPoint(dist);
        }
        else if (hoverResize != null)
        {
          s.Resize = hoverResize; s.ResizeDist = dist;
          s.ResizeStartScale = hoverResize.Panel.UserScale;
          s.ResizeStartDistance = Mathf.Max(0.05f, Vector3.Distance(s.Ray.GetPoint(dist), hoverResize.Panel.transform.position));
        }
      }

      if (s.Down)
      {
        if (s.Btn != null)
        {
          if (hoverBtn != s.Btn) { s.Btn.SetProgress(0f); if (s.Btn.HoldSeconds > 0f) JarvisAudio.SetCharge(0f); s.Btn = null; }
          else if (s.Btn.HoldSeconds > 0f && !s.BtnFired)
          {
            float p = (Time.unscaledTime - s.BtnTime) / s.Btn.HoldSeconds;
            s.Btn.SetProgress(p);
            JarvisAudio.SetCharge(Mathf.Clamp01(p));
            if (p >= 1f)
            {
              s.BtnFired = true; s.Btn.SetProgress(0f); JarvisAudio.SetCharge(0f);
              JarvisAudio.Play(JarvisAudio.Cue.ApproveClick); s.Btn.Click();
            }
          }
        }
        else if (s.Node != null)
        {
          Vector3 point = s.Ray.GetPoint(s.NodeDist);
          if (!s.NodeDragging && Vector3.Distance(point, s.NodeStart) > 0.04f) s.NodeDragging = true;
          if (s.NodeDragging) { s.Node.DragCluster(point - s.NodeLast); s.NodeLast = point; }
          else if (!s.NodeHeld && Time.unscaledTime - s.NodeTime > 0.7f) { s.NodeHeld = true; JarvisAudio.Play(JarvisAudio.Cue.SelectTick); s.Node.Hold(); }
        }
        else if (s.Grab != null)
        {
          s.Grab.SetGoal(s.Ray.GetPoint(s.GrabDist) + s.GrabOffset);
        }
        else if (s.Resize != null)
        {
          float d = Vector3.Distance(s.Ray.GetPoint(s.ResizeDist), s.Resize.Panel.transform.position);
          s.Resize.Panel.UserScale = Mathf.Clamp(s.ResizeStartScale * d / s.ResizeStartDistance, 0.5f, 2.2f);
        }
      }
      else if (s.WasDown) Release(s, hoverBtn);
    }

    private void Release(Slot s, JarvisSpatialButton hoverBtn)
    {
      if (s.Btn != null)
      {
        s.Btn.SetProgress(0f);
        if (s.Btn.HoldSeconds > 0f) JarvisAudio.SetCharge(0f);
        else if (hoverBtn == s.Btn) { JarvisAudio.Play(JarvisAudio.Cue.SelectTick); s.Btn.Click(); }
      }
      if (s.Node != null && !s.NodeDragging && !s.NodeHeld) s.Node.Select();
      s.Btn = null; s.Node = null; s.Grab = null; s.Resize = null; s.NodeDragging = false; s.NodeHeld = false;
    }

    private void UpdateTwoHandScale()
    {
      Slot a = _slots[0], b = _slots[1];
      bool both = a.Valid && b.Valid && a.Down && b.Down && !a.Busy && !b.Busy;
      if (!both) { _zooming = false; return; }
      float d = Vector3.Distance(a.Ray.origin, b.Ray.origin);
      if (!_zooming) { _zooming = true; _zoomStartDistance = Mathf.Max(d, 0.05f); _zoomStartScale = _graphRoot.localScale.x; return; }
      _graphRoot.localScale = Vector3.one * Mathf.Clamp(_zoomStartScale * d / _zoomStartDistance, 0.4f, 2.2f);
    }
  }
}
