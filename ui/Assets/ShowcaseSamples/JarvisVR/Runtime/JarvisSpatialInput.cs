using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace JarvisVR
{
  public sealed class JarvisSpatialInput : MonoBehaviour
  {
    /// <summary>Per-frame input logging. Off by default: it floods the Console and slows the editor.</summary>
    public static bool VerboseLogging = false;

    private sealed class Slot
    {
      public Ray Ray; public bool Valid, Down, WasDown;
      public Transform Reticle;
      public JarvisSpatialButton Hover, Btn; public float BtnTime; public bool BtnFired;
      public JarvisGraphNode Node; public Vector3 NodeStart, NodeLast; public float NodeDist, NodeTime; public bool NodeDragging, NodeHeld;
      public JarvisNodeFx HoverFx;
      public JarvisSpatialResize Resize; public float ResizeDist, ResizeStartScale, ResizeStartDistance;
      public JarvisSpatialGrab Grab; public float GrabDist; public Vector3 GrabOffset;
      public Vector2 Thumbstick; // Trackpad/thumbstick input
      public Vector2 PointerPos; // Virtual pointer position (normalized 0-1) for trackpad-based cursor
      public bool UsingPointer; // True when using thumbstick-based pointer instead of controller forward
      public bool Busy { get { return Btn != null || Node != null || Grab != null || Resize != null; } }
    }

    // 0 left hand, 1 right hand, 2 editor mouse, 3 left controller, 4 right controller, 5 head-gaze fallback (editor)
    private readonly Slot[] _slots = { new Slot(), new Slot(), new Slot(), new Slot(), new Slot(), new Slot() };
    private OVRHand[] _hands;
    private readonly System.Collections.Generic.List<OVRHand>[] _bySide =
      { new System.Collections.Generic.List<OVRHand>(), new System.Collections.Generic.List<OVRHand>() };   // [0] left, [1] right
    private Transform _tracking;   // tracking space: controller poses are reported in it
    private Camera _cam;
    private Transform _graphRoot;
    private Action _toggleVoice;
    private bool _zooming;
    private float _zoomStartDistance, _zoomStartScale = 1f;
    private const float PointerSensitivity = 0.5f; // Sensitivity for trackpad-based pointer movement

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
      // These are NOT skipped in the editor: Meta XR Simulator turns the mouse into simulated controller or hand input
      // and delivers it through OpenXR, so this is the path a simulator click arrives on.
      for (int i = 0; i < 2; i++)
      {
        Slot c = _slots[3 + i];
        bool wasValid = c.Valid;
        c.Valid = false; c.Down = false; c.Thumbstick = Vector2.zero;
        OVRInput.Controller ctrl = i == 0 ? OVRInput.Controller.LTouch : OVRInput.Controller.RTouch;
        if (_slots[i].Valid || !OVRInput.IsControllerConnected(ctrl)) continue;
        Vector3 lp = OVRInput.GetLocalControllerPosition(ctrl);
        Quaternion lr = OVRInput.GetLocalControllerRotation(ctrl);
        Vector3 origin = _tracking != null ? _tracking.TransformPoint(lp) : lp;
        Quaternion world = (_tracking != null ? _tracking.rotation : Quaternion.identity) * lr;
        c.Ray = new Ray(origin, world * Vector3.forward);
        c.Valid = true;
        c.Down = OVRInput.Get(OVRInput.Button.PrimaryIndexTrigger, ctrl) || OVRInput.Get(OVRInput.Button.PrimaryThumbstick, ctrl);
        c.Thumbstick = OVRInput.Get(OVRInput.Axis2D.PrimaryThumbstick, ctrl);

        // Initialize pointer position when controller becomes valid
        if (!wasValid && c.Valid && _cam != null)
        {
          c.PointerPos = new Vector2(0.5f, 0.5f); // Start at center of screen
          c.UsingPointer = false;
        }

        // Update pointer position based on thumbstick movement
        if (c.Thumbstick.magnitude > 0.1f)
        {
          c.UsingPointer = true;
          c.PointerPos += c.Thumbstick * PointerSensitivity * Time.unscaledDeltaTime;
          c.PointerPos = new Vector2(Mathf.Clamp01(c.PointerPos.x), Mathf.Clamp01(c.PointerPos.y));
        }

        // Always use pointer ray if pointer mode was activated
        if (c.UsingPointer && _cam != null)
        {
          Vector3 p = new Vector3(c.PointerPos.x * _cam.pixelWidth, c.PointerPos.y * _cam.pixelHeight, 0f);
          Camera.MonoOrStereoscopicEye eye = _cam.stereoEnabled ? Camera.MonoOrStereoscopicEye.Left : Camera.MonoOrStereoscopicEye.Mono;
          c.Ray = _cam.ScreenPointToRay(p, eye);
        }
      }
#if UNITY_EDITOR
      // Plain Unity mouse. It only receives clicks while the Unity Game view has focus; when Meta XR Simulator has focus the
      // simulator consumes the mouse and sends it as controller/hand input instead (handled above), so this slot is hidden.
      Slot m = _slots[2];
      Vector3 mp = Input.mousePosition;
      bool overGameView = mp.x >= 0f && mp.y >= 0f && mp.x <= Screen.width && mp.y <= Screen.height;
      m.Valid = _cam != null && Input.mousePresent && Application.isFocused && overGameView;
      if (m.Valid)
      {
        // The Game view and the XR eye texture can differ in size, so normalise before building the ray.
        Vector3 p = new Vector3(mp.x / Mathf.Max(1, Screen.width) * _cam.pixelWidth, mp.y / Mathf.Max(1, Screen.height) * _cam.pixelHeight, 0f);
        Camera.MonoOrStereoscopicEye eye = _cam.stereoEnabled ? Camera.MonoOrStereoscopicEye.Left : Camera.MonoOrStereoscopicEye.Mono;
        m.Ray = _cam.ScreenPointToRay(p, eye);
        // Enter is a held-key click fallback that works when mouse clicks do not reach Unity.
        m.Down = Input.GetMouseButton(0) || Input.GetKey(KeyCode.Return) || Input.GetKey(KeyCode.KeypadEnter);
        if (VerboseLogging && (Input.GetMouseButtonDown(0) || Input.GetKeyDown(KeyCode.Return)))
          Debug.Log("JARVIS: editor click, mousePos=" + mp + ", Down=" + m.Down + ", ray=" + m.Ray);
      }
      if (Input.GetKeyDown(KeyCode.Space) && _toggleVoice != null) _toggleVoice();

      // Head-gaze fallback: when no hand, controller or mouse pointer is available (for example the simulator window has focus and
      // Unity is not receiving the mouse), show a white pointer straight ahead so there is always something to aim with.
      // Enter clicks it while Unity has focus.
      Slot g = _slots[5];
      bool otherPointer = _slots[0].Valid || _slots[1].Valid || _slots[2].Valid || _slots[3].Valid || _slots[4].Valid;
      g.Valid = _cam != null && !otherPointer;
      g.Down = false;
      if (g.Valid)
      {
        g.Ray = new Ray(_cam.transform.position, _cam.transform.forward);
        g.Down = Input.GetKey(KeyCode.Return) || Input.GetKey(KeyCode.KeypadEnter);
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
      Color restColor = s == _slots[5] ? Color.white : new Color(0.24f, 0.84f, 0.91f);
      s.Reticle.GetComponent<Renderer>().sharedMaterial.color = s.Down ? new Color(0.96f, 0.65f, 0.14f) : restColor;

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
        Debug.Log("JARVIS: Press-down detected! hoverBtn=" + (hoverBtn != null ? hoverBtn.name : "null") + ", Interactable=" + (hoverBtn != null && hoverBtn.Interactable));
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
          Debug.Log("JARVIS: Clicked on node");
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
          s.ResizeStartDistance = Mathf.Max(0.05f, Vector3.Distance(s.Ray.GetPoint(s.ResizeDist), hoverResize.Panel.transform.position));
        }
        else if (hasHit)
        {
          // We hit something but it wasn't an interactive target - try clicking on the hover button if we have one
          if (s.Hover != null && s.Hover.Interactable)
          {
            s.Btn = s.Hover; s.Btn.SetPressed(true); s.BtnTime = Time.unscaledTime; s.BtnFired = false;
            if (s.Btn.HoldSeconds <= 0f)
            {
              s.BtnFired = true;
              FireButton(s.Btn);
            }
          }
          else
          {
            Debug.Log("JARVIS: Click hit something but no interactive target (hasHit=" + hasHit + ")");
          }
        }
        else
        {
          Debug.Log("JARVIS: Click hit nothing (hasHit=" + hasHit + ")");
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
      if (VerboseLogging) Debug.Log("JARVIS: Raycast found " + hits.Length + " hits, nearest on " + selected.collider.gameObject.name);

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
      Debug.Log("JARVIS input: firing button click on " + button.name + " (OnClick=" + (button.OnClick != null ? "set" : "null") + ")");
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
