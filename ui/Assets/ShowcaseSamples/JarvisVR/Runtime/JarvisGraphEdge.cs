using System;
using UnityEngine;

namespace JarvisVR
{
    /// <summary>Clickable world-space edge used by the dependency map.</summary>
    public sealed class JarvisGraphEdge : MonoBehaviour
    {
        private string _edgeId;
        private Action<string> _onPinch;
        private Action<string> _onHold;

        public string EdgeId { get { return _edgeId; } }

        public void Initialize(string edgeId, Action<string> onPinch, Action<string> onHold = null)
        {
            _edgeId = edgeId;
            _onPinch = onPinch;
            _onHold = onHold;
        }

        public void Select() { if (_onPinch != null) _onPinch(_edgeId); }
        public void Hold() { if (_onHold != null) _onHold(_edgeId); }
    }
}
