#if UNITY_EDITOR
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace JarvisVR
{
  /// <summary>Editor-only fallback so the workspace can be tested without tracked hands:
  /// left-click = pinch (nodes and buttons), Space = talk to JARVIS (simulated transcript).</summary>
  public sealed class JarvisEditorInput : MonoBehaviour
  {
    private Canvas _canvas; private GraphicRaycaster _raycaster; private EventSystem _events; private Camera _cam;
    private readonly List<RaycastResult> _hits = new();

    public void Initialize(Canvas canvas, GraphicRaycaster raycaster, EventSystem events, Camera cam)
    { _canvas = canvas; _raycaster = raycaster; _events = events; _cam = cam; }

    private void Update()
    {
      if (_cam == null) return;
      if (Input.GetKeyDown(KeyCode.Space) && JarvisVoice.Instance != null) JarvisVoice.Instance.ToggleListening();
      if (!Input.GetMouseButtonDown(0)) return;

      Ray ray = _cam.ScreenPointToRay(Input.mousePosition);
      if (Physics.Raycast(ray, out RaycastHit hit, 10f))
      {
        JarvisGraphNode node = hit.collider.GetComponentInParent<JarvisGraphNode>();
        if (node != null) { node.Select(); return; }
      }
      var pointer = new PointerEventData(_events) { position = Input.mousePosition };
      _hits.Clear();
      _raycaster.Raycast(pointer, _hits);
      foreach (RaycastResult r in _hits)
      {
        Button b = r.gameObject.GetComponentInParent<Button>();
        if (b != null && b.interactable) { b.onClick.Invoke(); return; }
      }
    }
  }
}
#endif
