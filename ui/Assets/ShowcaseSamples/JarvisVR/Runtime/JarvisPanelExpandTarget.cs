using System;
using UnityEngine;

namespace JarvisVR
{
    /// <summary>
    /// Lets a pinch pull an entire code-workbench panel toward the user and enlarge it.
    /// </summary>
    public sealed class JarvisPanelExpandTarget : MonoBehaviour
    {
        private const float PullThreshold = 0.035f;
        private const float MaxPullDistance = 0.24f;
        private const float ScalePerMeter = 2.5f;
        private const float MaxScale = 1.65f;

        private RectTransform _rect;
        private Vector3 _startPointerPosition;
        private Vector3 _startHitPoint;
        private Vector3 _startPanelPosition;
        private Vector3 _startPanelScale;
        private Vector3 _localGrabPoint;
        private Vector3 _towardUser;
        private Camera _uiCamera;
        private bool _isPinching;
        private Action<float, Vector3> _onTransformChanged;

        public void SetTransformChangedCallback(Action<float, Vector3> callback)
        {
            _onTransformChanged = callback;
        }

        public bool BeginPull(Vector3 pointerPosition, Vector2 screenPosition, Camera uiCamera)
        {
            _rect = transform as RectTransform;
            if (_rect == null || uiCamera == null ||
                !RectTransformUtility.ScreenPointToWorldPointInRectangle(
                    _rect, screenPosition, uiCamera, out Vector3 hitPoint))
            {
                return false;
            }

            _uiCamera = uiCamera;
            _startPointerPosition = pointerPosition;
            _startHitPoint = hitPoint;
            _startPanelPosition = _rect.position;
            _startPanelScale = _rect.localScale;
            _localGrabPoint = _rect.InverseTransformPoint(_startHitPoint);
            _towardUser = -uiCamera.transform.forward.normalized;
            _isPinching = true;
            return true;
        }

        public bool UpdatePull(Vector3 pointerPosition, Vector2 screenPosition)
        {
            if (!_isPinching || _rect == null || _uiCamera == null)
            {
                return false;
            }

            Vector3 pointerDelta = pointerPosition - _startPointerPosition;
            float pullDistance = Vector3.Dot(pointerDelta, _towardUser);
            if (pullDistance < PullThreshold)
            {
                _rect.position = _startPanelPosition;
                _rect.localScale = _startPanelScale;
                NotifyTransformChanged();
                return false;
            }

            float appliedPull = Mathf.Clamp(pullDistance, 0f, MaxPullDistance);
            float scale = Mathf.Min(MaxScale, _startPanelScale.x * (1f + appliedPull * ScalePerMeter));
            _rect.localScale = Vector3.one * scale;
            _rect.position = _startPanelPosition + _towardUser * appliedPull;
            if (RectTransformUtility.ScreenPointToWorldPointInRectangle(
                _rect, screenPosition, _uiCamera, out Vector3 desiredGrabPoint))
            {
                _rect.position += desiredGrabPoint - _rect.TransformPoint(_localGrabPoint);
            }
            NotifyTransformChanged();
            return true;
        }

        public void EndPull()
        {
            _isPinching = false;
            _uiCamera = null;
        }

        private void NotifyTransformChanged()
        {
            _onTransformChanged?.Invoke(_rect.localScale.x, _rect.localPosition);
        }
    }
}
