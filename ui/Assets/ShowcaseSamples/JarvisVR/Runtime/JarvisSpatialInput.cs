using System;
using System.Collections.Generic;
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

    // 0 left hand, 1 right hand, 2 editor mouse, 3 left controller, 4 right controller
    private readonly Slot[] _slots = { new Slot(), new Slot(), new Slot(), new Slot(), new Slot() };
    private OVRHand[] _hands;
    private readonly System.Collections.Generic.List<OVRHand>[] _bySide =
      { new System.Collections.Generic.List<OVRHand>(), new System.Collections.Generic.List<OVRHand>() };   // [0] left, [1] right
    private Transform _tracking;   // tracking space: controller poses are reported in it
    private Camera _cam;
    private Transform _graphRoot;
    private Action _toggleVoice;
    private bool _zooming;
    private float _zoomStartDistance, _zoomStartScale = 1f;

    public void Initialize(Camera cam, Transform graphRoot, Action toggleVoice)
    {
      _cam = cam; _graphRoot = graphRoot; _toggleVoice = toggleVoice;
      _hands = FindObjectsByType<OVRHand>(FindObjectsInactive.Include, FindObjectsSortMode.None);
      foreach (OVRHand h in _hands) { int side = SideOf(h.transform); if (side >= 0) _bySide[side].Add(h); }
      if (_bySide[0].Count == 0 && _bySide[1].Count == 0 && _hands.Length > 0)
      {
        Debug.LogWarning("JARVIS: no OVRHand has Left/Right in its hierarchy name; assuming scene order (left, right).");
        for (int k = 0; k < _hands.Length && k < 2; k++) _bySide[k].Add(_hands[k]);
      }
      OVRCameraRig rig = FindAnyObjectByType<OVRCameraRig>(FindObjectsInactive.Include);
      _tracking = rig != null && rig.trackingSpace != null ? rig.trackingSpace : (cam != null ? cam.transform.parent : null);
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

    /// <summary>0 = left, 1 = right, -1 = unknown. Looks for Left/Right in the object's own and parent names.</summary>
    private static int SideOf(Transform t)
    {
      for (; t != null; t = t.parent)
      {
        string n = t.name.ToLowerInvariant();
        if (n.Contains("left")) return 0;
        if (n.Contains("right")) return 1;
      }
      return -1;
    }

    /// <summary>First tracked OVRHand on that side (the sample rig can contain several OVRHand objects per side).</summary>
    private OVRHand PickHand(int side)
    {
      foreach (OVRHand h in _bySide[side])
        if (h != null && h.isActiveAndEnabled && h.IsTracked && h.IsPointerPoseValid && h.PointerPose != null) return h;
      return null;
    }

    private void Update()
    {
      for (int i = 0; i < 2; i++)
      {
        Slot s = _slots[i];
        OVRHand h = PickHand(i);
        s.Valid = h != null && h.IsTracked && h.IsPointerPoseValid && h.PointerPose != null;
        s.Down = false;
        if (s.Valid)
        {
          s.Ray = new Ray(h.PointerPose.position, h.PointerPose.forward);
          s.Down = h.GetFingerIsPinching(OVRHand.HandFinger.Index);
        }
      }
      // Touch controllers: used only while that side's hand is not tracked, so a hand and a controller never fight.
      for (int i = 0; i < 2; i++)
      {
        Slot c = _slots[3 + i];
        OVRInput.Controller ctrl = i == 0 ? OVRInput.Controller.LTouch : OVRInput.Controller.RTouch;
        c.Valid = false; c.Down = false;
        if (_slots[i].Valid || !OVRInput.IsControllerConnected(ctrl)) continue;
        Vector3 lp = OVRInput.GetLocalControllerPosition(ctrl);
        Quaternion lr = OVRInput.GetLocalControllerRotation(ctrl);
        Vector3 origin = _tracking != null ? _tracking.TransformPoint(lp) : lp;
        Quaternion world = (_tracking != null ? _tracking.rotation : Quaternion.identity) * lr;
        c.Ray = new Ray(origin, world * Vector3.forward);
        c.Valid = true;
        c.Down = OVRInput.Get(OVRInput.Button.PrimaryIndexTrigger, ctrl);
      }
#if UNITY_EDITOR
      Slot m = _slots[2];
      m.Valid = _cam != null;
      if (m.Valid) { m.Ray = _cam.ScreenPointToRay(Input.mousePosition); m.Down = Input.GetMouseButton(0); }
      if (Input.GetKeyDown(KeyCode.Space) && _toggleVoice != null) _toggleVoice();

      // XR Simulator fallback: if hands are not tracked, use mouse ray for hand slots too
      bool anyHandValid = _slots[0].Valid || _slots[1].Valid;
      if (!anyHandValid && _cam != null)
      {
        for (int i = 0; i < 2; i++)
        {
          Slot s = _slots[i];
          s.Valid = true;
          s.Ray = _cam.ScreenPointToRay(Input.mousePosition);
          s.Down = Input.GetMouseButton(0);
        }
      }
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
        Release(s);
        return;
      }

      JarvisSpatialButton hoverBtn = null; JarvisGraphNode hoverNode = null; JarvisSpatialGrab hoverGrab = null;
      JarvisNodeFx hoverFx = null; JarvisSpatialResize hoverResize = null;
      float dist = 1.5f; bool hasHit = false;
      if (TryRaycastTarget(s.Ray, out RaycastHit hit))
      {
        hasHit = true; dist = hit.distance;
        hoverBtn = hit.collider.GetComponentInParent<JarvisSpatialButton>();
        hoverNode = hit.collider.GetComponentInParent<JarvisGraphNode>();
        hoverGrab = hit.collider.GetComponentInParent<JarvisSpatialGrab>();
        hoverFx = hit.collider.GetComponentInParent<JarvisNodeFx>();
        hoverResize = hit.collider.GetComponentInParent<JarvisSpatialResize>();
        // Pinching anywhere on a panel body (not only the thin title strip) grabs the panel, unless it is pinned.
        if (hoverBtn == null && hoverNode == null && hoverGrab == null && hoverResize == null)
        {
          JarvisSpatialPanel panel = hit.collider.GetComponentInParent<JarvisSpatialPanel>();
          if (panel != null && !panel.Pinned)
          {
            Transform g = panel.transform.Find("Grab");
            if (g != null) hoverGrab = g.GetComponent<JarvisSpatialGrab>();
          }
        }
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
        if (hoverBtn != null && hoverBtn.Interactable)
        {
          s.Btn = hoverBtn; s.Btn.SetPressed(true); s.BtnTime = Time.unscaledTime; s.BtnFired = false;
          // Activate normal buttons on press-down. Waiting for a perfectly stable release
          // ray made hand pinch and controller clicks feel unresponsive in VR. Deliberate
          // hold actions (for example approval) still wait for HoldSeconds below.
          if (s.Btn.HoldSeconds <= 0f)
          {
            s.BtnFired = true;
            FireButton(s.Btn);
          }
        }
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
          if (hoverBtn != s.Btn) { s.Btn.SetPressed(false); s.Btn.SetProgress(0f); if (s.Btn.HoldSeconds > 0f) JarvisAudio.SetCharge(0f); s.Btn = null; }
          else if (s.Btn.HoldSeconds > 0f && !s.BtnFired)
          {
            float p = (Time.unscaledTime - s.BtnTime) / s.Btn.HoldSeconds;
            s.Btn.SetProgress(p);
            JarvisAudio.SetCharge(Mathf.Clamp01(p));
            if (p >= 1f)
            {
              s.BtnFired = true; s.Btn.SetProgress(0f); JarvisAudio.SetCharge(0f);
              JarvisAudio.Play(JarvisAudio.Cue.ApproveClick);
              s.Btn.SetPressed(false);
              FireButton(s.Btn, false);
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
      else if (s.WasDown) Release(s);
    }

    /// <summary>
    /// Resolve the nearest hit while allowing a button to win over its own panel's backing
    /// collider. Raycast() returns only one hit; the panel glass/root box can overlap the
    /// button's depth by a few millimetres and otherwise swallow the click.
    /// </summary>
    private static bool TryRaycastTarget(Ray ray, out RaycastHit selected)
    {
      RaycastHit[] hits = Physics.RaycastAll(ray, 6f, ~0, QueryTriggerInteraction.Ignore);
      if (hits == null || hits.Length == 0) { selected = default; return false; }
      Array.Sort(hits, (a, b) => a.distance.CompareTo(b.distance));
      selected = hits[0];

      // 1) Buttons take priority over their own panel's backing collider. This also avoids
      // unrelated non-interactive scene colliders swallowing a UI click.
      JarvisSpatialPanel firstPanel = selected.collider != null
        ? selected.collider.GetComponentInParent<JarvisSpatialPanel>() : null;
      for (int i = 0; i < hits.Length; i++)
      {
        Collider collider = hits[i].collider;
        if (collider == null) continue;
        JarvisSpatialButton button = collider.GetComponentInParent<JarvisSpatialButton>();
        if (button == null || !button.Interactable) continue;
        JarvisSpatialPanel buttonPanel = button.GetComponentInParent<JarvisSpatialPanel>();
        if (buttonPanel != null && (firstPanel == null || buttonPanel == firstPanel || i == 0 || hits[i].distance - hits[0].distance <= 0.025f))
        {
          selected = hits[i];
          return true;
        }
      }

      // 2) Otherwise route to the nearest explicit spatial interaction target.
      for (int i = 0; i < hits.Length; i++)
      {
        Collider collider = hits[i].collider;
        if (collider == null) continue;
        if (collider.GetComponentInParent<JarvisGraphNode>() != null ||
            collider.GetComponentInParent<JarvisSpatialGrab>() != null ||
            collider.GetComponentInParent<JarvisSpatialResize>() != null)
        {
          selected = hits[i];
          return true;
        }
        JarvisSpatialPanel panel = collider.GetComponentInParent<JarvisSpatialPanel>();
        if (panel != null)
        {
          selected = hits[i];
          return true;
        }
      }

      // Keep the reticle visible on the nearest collider even when it is not actionable.
      return true;
    }

    private static void FireButton(JarvisSpatialButton button, bool playCue = true)
    {
      if (button == null || !button.Interactable) return;
      if (playCue) JarvisAudio.Play(JarvisAudio.Cue.SelectTick);
      button.Focus();
      Debug.Log("JARVIS input: clicked " + button.name);
      button.Click();
    }

    private void Release(Slot s)
    {
      if (s.Btn != null)
      {
        s.Btn.SetPressed(false);
        s.Btn.SetProgress(0f);
        if (s.Btn.HoldSeconds > 0f) JarvisAudio.SetCharge(0f);
      }
      if (s.Node != null && !s.NodeDragging && !s.NodeHeld) s.Node.Select();
      s.Btn = null; s.Node = null; s.Grab = null; s.Resize = null; s.NodeDragging = false; s.NodeHeld = false;
    }

    private void UpdateTwoHandScale()
    {
      Slot a = _slots[0], b = _slots[1];
      if (!(a.Valid && b.Valid)) { a = _slots[3]; b = _slots[4]; }   // controllers: both triggers pulled
      bool both = a.Valid && b.Valid && a.Down && b.Down && !a.Busy && !b.Busy;
      if (!both) { _zooming = false; return; }
      float d = Vector3.Distance(a.Ray.origin, b.Ray.origin);
      if (!_zooming) { _zooming = true; _zoomStartDistance = Mathf.Max(d, 0.05f); _zoomStartScale = _graphRoot.localScale.x; return; }
      _graphRoot.localScale = Vector3.one * Mathf.Clamp(_zoomStartScale * d / _zoomStartDistance, 0.4f, 2.2f);
    }
  }
}
