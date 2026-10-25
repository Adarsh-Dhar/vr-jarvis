using System;
using UnityEngine;

namespace JarvisVR
{
    /// <summary>Clickable world-space node used by the dependency map.</summary>
    public sealed class JarvisGraphNode : MonoBehaviour
    {
        private string _nodeId;
        private Action<string> _onPinch;
        private Action<string, Vector3> _onClusterDrag;
        private Action<string> _onHold;

        public string NodeId { get { return _nodeId; } }

        public void Initialize(string nodeId, Action<string> onPinch, Action<string, Vector3> onClusterDrag,
          Action<string> onHold = null)
        {
            _nodeId = nodeId;
            _onPinch = onPinch;
            _onClusterDrag = onClusterDrag;
            _onHold = onHold;
        }

        public void Select() { if (_onPinch != null) _onPinch(_nodeId); }
        public void Hold() { if (_onHold != null) _onHold(_nodeId); }
        public void DragCluster(Vector3 worldDelta) { if (_onClusterDrag != null) _onClusterDrag(_nodeId, worldDelta); }
    }
}
