using UnityEngine;

namespace JarvisVR
{
  /// <summary>Billboarded, pulsing red ring around a risk node.</summary>
  public sealed class JarvisRiskRing : MonoBehaviour
  {
    private SpriteRenderer _sr;
    private Camera _cam;

    private void Awake()
    {
      GameObject go = new GameObject("RiskRing");
      go.transform.SetParent(transform, false);
      _sr = go.AddComponent<SpriteRenderer>();
      _sr.sprite = JarvisGfx.Ring(128, 10); // exactly 1 unit wide
      _sr.color = new Color32(0xFF, 0x6B, 0x6B, 0xF2);
      _sr.sortingOrder = 30;
    }

    private void LateUpdate()
    {
      if (_cam == null) _cam = Camera.main;
      if (_cam != null) _sr.transform.rotation = _cam.transform.rotation;
      float pulse = 1f + 0.12f * Mathf.Sin(Time.unscaledTime * 3f);
      _sr.transform.localScale = Vector3.one * 2.4f * pulse; // parent sphere is ~25 canvas px
    }

    public void SetVisible(bool visible) { if (_sr != null) _sr.enabled = visible; }
  }
}
