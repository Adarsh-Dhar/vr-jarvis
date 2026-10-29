using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace JarvisVR
{
    /// <summary>
    /// Routes index-finger pinches to UI clicks, graph selection, cluster dragging,
    /// and two-hand map zoom using the OVR hands in the supplied Interaction SDK scene.
    /// </summary>
    public sealed class JarvisPinchInteractor : MonoBehaviour
    {
        private static readonly Color Cyan = new Color(0f, 0.8f, 1f);
        private static readonly Color Amber = new Color(1f, 0.6f, 0f);

        private Canvas _canvas;
        private GraphicRaycaster _raycaster;
        private EventSystem _eventSystem;
        private OVRHand[] _hands;
        private readonly bool[] _wasPinching = new bool[2];
        private readonly bool[] _handHasPointer = new bool[2];
        private readonly bool[] _handPinching = new bool[2];
        private readonly List<RaycastResult> _raycastResults = new();
        private Button _pressedButton;
        private GameObject _pressedObject;
        private PointerEventData _pressEventData;
        private JarvisGraphNode _pressedNode;
        private JarvisPanelExpandTarget _pressedPanelTarget;
        private int _pressedHand = -1;
        private Vector3 _nodePressPoint;
        private Vector3 _lastNodePoint;
        private bool _nodeDragActive;
        private bool _nodeDragReady;
        private float _nodePressTime;
        private bool _nodeHoldFired;
        private const float NodeHoldSeconds = 0.6f;
        private bool _panelPullStarted;
        private bool _twoHandZoomActive;
        private float _twoHandStartDistance;
        private float _twoHandStartScale = 1f;
        private float _mapScale = 1f;
        private Action<float> _onMapZoom;
        private Func<bool> _canZoomMap;
        private Image _reticle;
        private RectTransform _reticleRect;

        public void Initialize(Canvas canvas, GraphicRaycaster raycaster, EventSystem eventSystem,
            Action<float> onMapZoom, Func<bool> canZoomMap)
        {
            _canvas = canvas;
            _raycaster = raycaster;
            _eventSystem = eventSystem;
            _onMapZoom = onMapZoom;
            _canZoomMap = canZoomMap;

            GameObject reticleObject = new("JARVIS pinch reticle", typeof(RectTransform), typeof(Image));
            reticleObject.transform.SetParent(_canvas.transform, false);
            _reticleRect = reticleObject.GetComponent<RectTransform>();
            _reticleRect.anchorMin = _reticleRect.anchorMax = new Vector2(0.5f, 0.5f);
            _reticleRect.pivot = new Vector2(0.5f, 0.5f);
            _reticleRect.sizeDelta = new Vector2(26, 26);
            _reticle = reticleObject.GetComponent<Image>();
            _reticle.sprite = JarvisGfx.Ring(64, 7);
            _reticle.raycastTarget = false;
            _reticle.enabled = false;
        }

        private void Start()
        {
            _hands = FindObjectsByType<OVRHand>(FindObjectsInactive.Include);
            if (_hands.Length > _wasPinching.Length)
            {
                Debug.LogWarning("JARVIS input currently tracks the first two OVR hands only.");
            }
        }

        private void Update()
        {
            if (_hands == null || _canvas == null || _raycaster == null || _eventSystem == null)
            {
                return;
            }

            int trackedHands = Mathf.Min(_hands.Length, _wasPinching.Length);
            if (_reticle != null) _reticle.enabled = false;
            for (int i = 0; i < trackedHands; i++)
            {
                OVRHand hand = _hands[i];
                _handHasPointer[i] = hand != null && hand.IsTracked && hand.IsPointerPoseValid;
                _handPinching[i] = _handHasPointer[i] && hand.GetFingerIsPinching(OVRHand.HandFinger.Index);
                if (_handHasPointer[i]) UpdateReticle(hand, _handPinching[i]);
            }
            for (int i = trackedHands; i < _wasPinching.Length; i++)
            {
                _handHasPointer[i] = false;
                _handPinching[i] = false;
            }

            // Cancel hold if tracking is lost
            for (int i = 0; i < trackedHands; i++)
            {
                OVRHand hand = _hands[i];
                if (hand != null && !hand.IsTracked && _wasPinching[i] && _pressedHand == i)
                {
                    EndPinch(hand, i);
                    _wasPinching[i] = false;
                    _handPinching[i] = false;
                }
            }

            bool bothHandsPinching = trackedHands >= 2 &&
                                     _handHasPointer[0] && _handHasPointer[1] &&
                                     _handPinching[0] && _handPinching[1] &&
                                     _canZoomMap != null && _canZoomMap();

            if (_twoHandZoomActive)
            {
                if (bothHandsPinching)
                {
                    UpdateTwoHandZoom();
                    SynchronizePinchState(trackedHands);
                    return;
                }

                _twoHandZoomActive = false;
                SynchronizePinchState(trackedHands);
                return;
            }

            if (bothHandsPinching && _pressedHand < 0)
            {
                float distance = PointerDistanceBetweenHands();
                if (distance > 0.02f)
                {
                    _twoHandZoomActive = true;
                    _twoHandStartDistance = distance;
                    _twoHandStartScale = _mapScale;
                    SynchronizePinchState(trackedHands);
                    return;
                }
            }

            for (int i = 0; i < trackedHands; i++)
            {
                OVRHand hand = _hands[i];
                bool pinching = _handPinching[i];
                if (pinching && !_wasPinching[i])
                {
                    BeginPinch(hand, i);
                }
                else if (pinching && _wasPinching[i] &&
                         _pressedNode != null && _pressedHand == i)
                {
                    UpdateNodeDrag(hand);
                }
                else if (pinching && _wasPinching[i] &&
                         _pressedPanelTarget != null && _pressedHand == i)
                {
                    UpdatePanelPull(hand);
                }
                else if (!pinching && _wasPinching[i])
                {
                    EndPinch(hand, i);
                }
                _wasPinching[i] = pinching;
            }
        }

        private void SynchronizePinchState(int trackedHands)
        {
            for (int i = 0; i < _wasPinching.Length; i++)
            {
                _wasPinching[i] = i < trackedHands && _handPinching[i];
            }
        }

        private float PointerDistanceBetweenHands()
        {
            if (_hands == null || _hands.Length < 2 ||
                _hands[0] == null || _hands[1] == null ||
                _hands[0].PointerPose == null || _hands[1].PointerPose == null)
            {
                return 0f;
            }

            return Vector3.Distance(_hands[0].PointerPose.position, _hands[1].PointerPose.position);
        }

        private void UpdateTwoHandZoom()
        {
            float distance = PointerDistanceBetweenHands();
            if (_twoHandStartDistance <= 0f || distance <= 0f)
            {
                return;
            }

            _mapScale = Mathf.Clamp(_twoHandStartScale * (distance / _twoHandStartDistance), 0.7f, 1.15f);
            _onMapZoom?.Invoke(_mapScale);
        }

        private void UpdateReticle(OVRHand hand, bool pinching)
        {
            if (_reticleRect == null || hand.PointerPose == null)
            {
                return;
            }

            Ray ray = new(hand.PointerPose.position, hand.PointerPose.forward);
            if (!JarvisCurve.TryRayToFlat(ray, _canvas.transform, out Vector3 flatPoint))
            {
                return;
            }

            Vector2 screenPosition = RectTransformUtility.WorldToScreenPoint(
                _canvas.worldCamera, flatPoint);
            if (RectTransformUtility.ScreenPointToLocalPointInRectangle(
                _canvas.transform as RectTransform, screenPosition, _canvas.worldCamera, out Vector2 localPosition))
            {
                _reticleRect.anchoredPosition = localPosition;
                _reticle.color = pinching ? Amber : Cyan;
                _reticle.enabled = true;
            }
        }

        private void BeginPinch(OVRHand hand, int handIndex)
        {
            if (_pressedHand >= 0 || hand.PointerPose == null)
            {
                return;
            }

            Ray ray = new(hand.PointerPose.position, hand.PointerPose.forward);
            if (Physics.Raycast(ray, out RaycastHit hit, 5f))
            {
                JarvisGraphNode node = hit.collider.GetComponentInParent<JarvisGraphNode>();
                if (node != null)
                {
                    _pressedNode = node;
                    _pressedHand = handIndex;
                    _nodePressTime = Time.unscaledTime;
                    _nodeHoldFired = false;
                    _nodeDragActive = false;
                    _nodeDragReady = TryGetCanvasPlanePoint(ray, out _nodePressPoint);
                    _lastNodePoint = _nodePressPoint;
                    return;
                }
            }

            if (!TryRaycastUI(ray, out PointerEventData pointer, out GameObject hitObject))
            {
                return;
            }

            Button button = hitObject.GetComponentInParent<Button>();
            JarvisPanelExpandTarget panelTarget = hitObject.GetComponentInParent<JarvisPanelExpandTarget>();
            if ((button == null && panelTarget == null) || (button != null && !button.interactable))
            {
                return;
            }

            bool panelPullBegan = panelTarget != null &&
                                  panelTarget.BeginPull(hand.PointerPose.position,
                                      pointer.position, _canvas.worldCamera);
            if (button == null && !panelPullBegan)
            {
                return;
            }

            _pressedButton = button;
            _pressedObject = button != null ? button.gameObject : null;
            _pressEventData = button != null ? pointer : null;
            _pressedPanelTarget = panelPullBegan ? panelTarget : null;
            _panelPullStarted = false;
            _pressedHand = handIndex;
            if (button != null)
            {
                ExecuteEvents.ExecuteHierarchy(hitObject, pointer, ExecuteEvents.pointerDownHandler);
            }
        }

        private void TickNodeHold()
        {
            if (_pressedNode == null || _nodeHoldFired || _nodeDragActive) return;
            if (Time.unscaledTime - _nodePressTime < NodeHoldSeconds) return;
            _nodeHoldFired = true;
            _pressedNode.Hold();
        }

        private void UpdateNodeDrag(OVRHand hand)
        {
            TickNodeHold();
            UpdateNodeDragCore(hand);
        }

        private void UpdateNodeDragCore(OVRHand hand)
        {
            if (_pressedNode == null || hand == null || hand.PointerPose == null)
            {
                return;
            }

            Ray ray = new(hand.PointerPose.position, hand.PointerPose.forward);
            if (!TryGetCanvasPlanePoint(ray, out Vector3 currentPoint))
            {
                return;
            }

            if (!_nodeDragReady)
            {
                _nodePressPoint = currentPoint;
                _lastNodePoint = currentPoint;
                _nodeDragReady = true;
                return;
            }

            if (!_nodeDragActive && Vector3.Distance(currentPoint, _nodePressPoint) < 0.025f)
            {
                return;
            }

            _nodeDragActive = true;
            Vector3 delta = currentPoint - _lastNodePoint;
            if (delta.sqrMagnitude > 0.000001f)
            {
                _pressedNode.DragCluster(delta);
            }
            _lastNodePoint = currentPoint;
        }

        private void UpdatePanelPull(OVRHand hand)
        {
            if (_pressedPanelTarget == null || hand == null || hand.PointerPose == null)
            {
                return;
            }

            Ray ray = new(hand.PointerPose.position, hand.PointerPose.forward);
            if (!TryGetCanvasPlanePoint(ray, out Vector3 canvasPoint))
            {
                return;
            }

            Vector2 screenPosition = RectTransformUtility.WorldToScreenPoint(_canvas.worldCamera, canvasPoint);
            if (_pressedPanelTarget.UpdatePull(hand.PointerPose.position, screenPosition))
            {
                _panelPullStarted = true;
            }
        }

        private void EndPinch(OVRHand hand, int handIndex)
        {
            if (_pressedHand != handIndex)
            {
                return;
            }

            if (_pressedNode != null)
            {
                if (!_nodeDragActive && !_nodeHoldFired &&
                    hand != null && hand.IsTracked && hand.IsPointerPoseValid)
                {
                    _pressedNode.Select();
                }

                _pressedNode = null;
                _pressedHand = -1;
                _nodeDragActive = false;
                _nodeDragReady = false;
                _nodeHoldFired = false;
                return;
            }

            if (_pressedPanelTarget != null)
            {
                _pressedPanelTarget.EndPull();
            }

            Button pressedButton = _pressedButton;
            GameObject pressedObject = _pressedObject;
            bool releasedOverSameButton = false;
            PointerEventData pointer = null;
            GameObject hitObject = null;
            if (!_panelPullStarted && pressedButton != null && hand != null && hand.IsTracked &&
                hand.IsPointerPoseValid && hand.PointerPose != null)
            {
                Ray ray = new(hand.PointerPose.position, hand.PointerPose.forward);
                releasedOverSameButton =
                    TryRaycastUI(ray, out pointer, out hitObject) &&
                    hitObject.GetComponentInParent<Button>() == pressedButton;
            }

            if (!releasedOverSameButton && pressedObject != null)
            {
                JarvisApprovalHold hold = pressedObject.GetComponent<JarvisApprovalHold>();
                if (hold != null) hold.CancelHold();
            }

            PointerEventData releaseEvent = pointer ?? _pressEventData;
            if (releaseEvent != null && pressedObject != null)
            {
                ExecuteEvents.ExecuteHierarchy(pressedObject, releaseEvent, ExecuteEvents.pointerUpHandler);
            }
            if (releasedOverSameButton &&
                pressedButton != null &&
                pressedButton.GetComponent<JarvisApprovalHold>() == null)
            {
                pressedButton.onClick.Invoke();
            }

            _pressedButton = null;
            _pressedObject = null;
            _pressEventData = null;
            _pressedPanelTarget = null;
            _panelPullStarted = false;
            _pressedHand = -1;
        }

        private bool TryGetCanvasPlanePoint(Ray ray, out Vector3 point)
        {
            return JarvisCurve.TryRayToFlat(ray, _canvas.transform, out point);
        }

        private bool TryRaycastUI(Ray ray, out PointerEventData pointer, out GameObject hitObject)
        {
            pointer = null;
            hitObject = null;
            if (!JarvisCurve.TryRayToFlat(ray, _canvas.transform, out Vector3 flatPoint))
            {
                return false;
            }

            Vector2 screenPosition = RectTransformUtility.WorldToScreenPoint(
                _canvas.worldCamera, flatPoint);
            pointer = new PointerEventData(_eventSystem)
            {
                position = screenPosition,
                pressPosition = screenPosition,
                button = PointerEventData.InputButton.Left,
            };
            _raycastResults.Clear();
            _raycaster.Raycast(pointer, _raycastResults);
            if (_raycastResults.Count == 0)
            {
                return false;
            }

            hitObject = _raycastResults[0].gameObject;
            return true;
        }
    }
}
