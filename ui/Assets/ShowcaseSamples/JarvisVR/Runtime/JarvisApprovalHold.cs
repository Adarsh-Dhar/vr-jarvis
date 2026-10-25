using System;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace JarvisVR
{
  /// <summary>Requires an unbroken pinch of HoldSeconds before onComplete fires.</summary>
  public sealed class JarvisApprovalHold : MonoBehaviour, IPointerDownHandler, IPointerUpHandler
  {
    public const float HoldSeconds = 2f;

    public event Action HoldStarted;
    public event Action HoldCancelled;
    public event Action HoldCompleted;
    public event Action<float> ProgressChanged; // 0..1

    private Action _onComplete;
    private Image _fill;
    private Text _label;
    private string _idleLabel;
    private bool _holding;
    private bool _completed;
    private float _heldFor;

    public void Configure(Action onComplete, Image fill, Text label)
    {
      _onComplete = onComplete;
      _fill = fill;
      _label = label;
      _idleLabel = label != null ? label.text : string.Empty;
      SetProgress(0f);
    }

    public void OnPointerDown(PointerEventData eventData)
    {
      if (_completed) return;
      _holding = true;
      _heldFor = 0f;
      HoldStarted?.Invoke();
    }

    public void OnPointerUp(PointerEventData eventData) { CancelHold(); }

    public void CancelHold()
    {
      if (!_holding) return;
      _holding = false;
      if (_completed) return;
      _heldFor = 0f;
      SetProgress(0f);
      if (_label != null) _label.text = _idleLabel;
      HoldCancelled?.Invoke();
    }

    private void Update()
    {
      if (!_holding || _completed) return;
      _heldFor += Time.unscaledDeltaTime;
      float p = Mathf.Clamp01(_heldFor / HoldSeconds);
      SetProgress(p);
      if (_label != null) _label.text = "HOLD  " + Mathf.CeilToInt(HoldSeconds - _heldFor);
      if (p < 1f) return;
      _completed = true;
      _holding = false;
      HoldCompleted?.Invoke();
      if (_onComplete != null) _onComplete();
    }

    private void SetProgress(float p)
    {
      if (_fill != null) _fill.fillAmount = p;
      ProgressChanged?.Invoke(p);
    }
  }
}
