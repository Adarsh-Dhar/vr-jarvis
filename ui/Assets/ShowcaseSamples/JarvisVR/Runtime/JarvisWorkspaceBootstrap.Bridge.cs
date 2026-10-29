using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace JarvisVR
{
    // Server <-> scene glue. Every id the server sends is a node id from ai_agents/data/graph.json,
    // which is identical to the ids in the Nodes fixture list.
    public sealed partial class JarvisWorkspaceBootstrap
    {
        private JarvisBridge _bridge;
        private readonly HashSet<string> _hot = new();                     // highlight_path
        private HashSet<string> _keep;                                     // dim_unrelated (null = no dimming)
        private readonly Dictionary<string, string> _badge = new();        // show_test_badges
        private readonly Dictionary<string, SourceResponse> _live = new(); // repo source by node id
        private readonly Dictionary<LineRenderer, Color> _edgeOriginal = new();
        private string _ghostDiff;
        private string _pendingApproval;

        private void InitBridge()
        {
            _bridge = gameObject.AddComponent<JarvisBridge>();
            FetchSource(_selectedNode);
#if UNITY_EDITOR
            gameObject.AddComponent<JarvisEditorInput>().Initialize(_canvas, _raycaster, _eventSystem, _canvas.worldCamera);
#endif
        }

        private void RunAsk(string text)
        {
            if (_bridge == null) return;
            SetAssistantMessage("Thinking…");
            _bridge.Ask(text, _selectedNode, OnAnswer, err => SetAssistantMessage(err));
        }

        private void OnAnswer(AskResponse r)
        {
            if (!string.IsNullOrEmpty(r.error)) { SetAssistantMessage(r.error); return; }
            ResetSceneOverlay();
            bool highlighted = false;
            if (r.scene_commands != null)
                foreach (SceneCommand c in r.scene_commands) highlighted |= ApplyCommand(c);
            _pendingApproval = r.pending_approval;
            string reply = r.reply ?? "";
            if (r.test_source == "cached") reply += "  (Test results are SIMULATED.)";
            SetAssistantMessage(reply);
            if (JarvisVoice.Instance != null) JarvisVoice.Instance.Speak(reply);
            if (!string.IsNullOrEmpty(_pendingApproval)) ShowMode("OPS");
            else if (highlighted) ShowMode("MAP");
            else ShowMode(_activeMode);
        }

        private void ResetSceneOverlay()
        {
            _hot.Clear(); _keep = null; _badge.Clear(); _ghostDiff = null;
            foreach (var kv in _edgeOriginal) if (kv.Key != null) kv.Key.startColor = kv.Key.endColor = kv.Value;
            _edgeOriginal.Clear();
            foreach (NodeFixture n in Nodes)
                if (_graphLabels.TryGetValue(n.Id, out GameObject g) && g.GetComponent<Text>() is Text t) t.text = n.Label;
        }

        /// <returns>true when the command changes what the MAP shows.</returns>
        private bool ApplyCommand(SceneCommand c)
        {
            switch (c.type)
            {
                case "highlight_path":
                    if (c.node_ids == null) return false;
                    foreach (string id in c.node_ids) if (_graphObjects.ContainsKey(id)) _hot.Add(id);
                    foreach (GraphEdgeSegment s in _graphEdgeSegments)
                        if (_hot.Contains(s.FromId) && _hot.Contains(s.ToId)) SetEdgeColor(s, Amber);
                    return true;
                case "dim_unrelated":
                    _keep = new HashSet<string>(c.keep_ids ?? new string[0]);
                    return true;
                case "open_code_panel":
                case "focus_camera":
                    if (!string.IsNullOrEmpty(c.node_id) && _graphObjects.ContainsKey(c.node_id))
                    {
                        _selectedNode = c.node_id;               // stay on MAP so the highlight stays visible
                        FetchSource(c.node_id);
                    }
                    return false;
                case "set_edge_style":
                    foreach (GraphEdgeSegment s in _graphEdgeSegments)
                        if ((s.FromId == c.src && s.ToId == c.dst) || (s.FromId == c.dst && s.ToId == c.src))
                            SetEdgeColor(s, c.style == "dashed" ? Violet : c.style == "runtime" ? Green : Cyan);
                    return false;
                case "show_ghost_diff":
                    _ghostDiff = c.diff;
                    return false;
                case "show_test_badges":
                    Badge(c.passed, "  ✓"); Badge(c.failed, "  ✗"); Badge(c.not_run, "  –");
                    return false;
                case "show_approval_prompt":
                    _pendingApproval = c.summary;
                    return false;
                default:
                    Debug.LogWarning("JARVIS: unknown scene command " + c.type);
                    return false;
            }
        }

        private void SetEdgeColor(GraphEdgeSegment s, Color color)
        {
            if (s.Line == null) return;
            if (!_edgeOriginal.ContainsKey(s.Line)) _edgeOriginal[s.Line] = s.Line.startColor;
            s.Line.startColor = s.Line.endColor = color;
        }

        private void Badge(string[] ids, string mark)
        {
            if (ids == null) return;
            foreach (string id in ids)
                if (_graphLabels.TryGetValue(id, out GameObject g) && g.GetComponent<Text>() is Text t)
                { _badge[id] = mark; t.text = FindNode(id).Label + mark; }
        }

        private Color SceneOverrideColor(string id, Color color)
        {
            if (_hot.Contains(id)) return Amber;
            if (_keep != null && !_keep.Contains(id)) return new Color(0.2f, 0.26f, 0.34f, 1f);
            return color;
        }

        private void FetchSource(string nodeId)
        {
            if (_bridge == null || string.IsNullOrEmpty(nodeId)) return;
            _bridge.GetSource(nodeId, s =>
            {
                if (s == null || s.status != "ok") return;
                _live[nodeId] = s;
                if (_activeMode == "CODE" && _selectedNode == nodeId) ShowMode("CODE");
            });
        }

        private bool TryLiveFixture(out string title, out string source, out string finding, out Color accent)
        {
            title = source = finding = null; accent = Cyan;
            if (!_live.TryGetValue(_selectedNode, out SourceResponse s)) return false;
            string[] lines = (s.source ?? "").Split('\n');
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < lines.Length; i++) sb.Append(s.first_line + i).Append("  ").Append(lines[i].TrimEnd('\r')).Append('\n');
            title = s.file; source = sb.ToString().TrimEnd();
            bool hot = _hot.Contains(_selectedNode);
            finding = hot ? "JARVIS · highlighted in the last answer." : "PARSER FACT · live source from the repository.";
            accent = hot ? Amber : Cyan;
            return true;
        }

        private void OnApprovalCompleted(bool approved)
        {
            if (_bridge == null) return;
            SetAssistantMessage(approved ? "Committing to the sandbox branch…" : "Rejecting…");
            _bridge.Approve(approved,
                r => SetAssistantMessage(approved && r.ok ? "Committed " + r.commit + " on " + r.branch + ". Main is untouched." : r.detail),
                err => SetAssistantMessage(err));
        }
    }
}
