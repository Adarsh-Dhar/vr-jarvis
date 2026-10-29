using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.Events;
using UnityEngine.UI;

namespace JarvisVR
{
    /// <summary>
    /// Builds the JARVIS review workspace as a world-space UI so the sample can be
    /// added to the supplied Interaction SDK scene without editing vendor assets.
    /// The included account-deletion review is fixture data, not a live repository.
    /// </summary>
    public sealed partial class JarvisWorkspaceBootstrap : MonoBehaviour
    {
        private const int CanvasWidth = 1440;
        private const int CanvasHeight = 810;
        private const float WorldScale = 0.0013f;
        private const float VrTextScale = 1.15f;
        private const float CurveRadiusMeters = 2.4f; // 0 = flat

        private JarvisPalette _pal;
        private JarvisPalette Pal => _pal ??= JarvisPalette.Current;
        private Color Space => Pal.SpaceTop;
        private Color Panel => new Color(Pal.Glass.r, Pal.Glass.g, Pal.Glass.b, 1f);
        private Color PanelRaised => Pal.PanelRaised;
        private Color Border => new Color(Pal.Cyan.r, Pal.Cyan.g, Pal.Cyan.b, 0.28f);
        private Color Cyan => Pal.Cyan;
        private Color Amber => Pal.Amber;
        private Color Red => Pal.Red;
        private Color Green => Pal.Green;
        private Color Violet => Pal.Violet;
        private Color MainText => Pal.Text;
        private Color MutedText => Pal.TextMuted;

        private readonly Dictionary<string, GameObject> _graphObjects = new();
        private readonly Dictionary<string, GameObject> _graphLabels = new();
        private readonly Dictionary<string, RectTransform> _clusterUiRoots = new();
        private readonly Dictionary<string, Transform> _clusterWorldRoots = new();
        private readonly Dictionary<string, Vector2> _clusterUiOrigins = new();
        private readonly List<LineRenderer> _graphLines = new();
        private readonly List<GraphEdgeSegment> _graphEdgeSegments = new();
        private readonly bool[] _overlays = { true, true, false, false };
        private readonly List<Transform> _clusterShells = new();
        private readonly List<(string From, string To)> _edgePairs = new();
        private string _expandedNode;

        private Canvas _canvas;
        private GraphicRaycaster _raycaster;
        private RectTransform _contentRoot;
        private RectTransform _mapGraph;
        private Transform _graphWorldRoot;
        private EventSystem _eventSystem;
        private Sprite _roundedSprite;
        private string _activeMode = "MAP";
        private string _selectedNode = "service.delete";
        private string _codeTab = "CODE";
        private int _flowStep = 3;
        private bool _flowPlaying;
        private float _flowNextAt;
        private bool _approved;
        private bool _rejected;
        private float _mapScale = 1f;
        private float _codePanelScale = 1f;
        private Vector3 _codePanelOffset;
        private Text _assistantMessage;
        private Text _mapZoomReadout;
        private Image _orb;
        private Image _approvalFill;
        private Text _approvalHint;
        private readonly List<Image> _voiceBars = new();

        private NodeFixture[] Nodes => new NodeFixture[]
        {
            new("route.delete", "DELETE /account/:id", "api/", 166, 278, Amber),
            new("auth.require", "requireAuth", "auth/", 360, 214, Cyan),
            new("service.delete", "deleteAccount", "services/", 514, 294, Amber),
            new("auth.owner", "checkOwner ?", "auth/", 671, 354, Red),
            new("db.delete", "users.repo.delete", "db/", 704, 465, Cyan),
            new("test.own-account", "delete.own-account", "tests/", 432, 475, Violet),
            new("db.repo", "users.repo", "db/", 547, 535, Cyan),
        };

        private sealed class NodeFixture
        {
            public readonly string Id;
            public readonly string Label;
            public readonly string Cluster;
            public readonly float X;
            public readonly float Y;
            public readonly Color Color;

            public NodeFixture(string id, string label, string cluster, float x, float y, Color color)
            {
                Id = id;
                Label = label;
                Cluster = cluster;
                X = x;
                Y = y;
                Color = color;
            }
        }

        private sealed class GraphEdgeSegment
        {
            public readonly LineRenderer Line;
            public readonly string FromId;
            public readonly string ToId;
            public readonly float StartT;
            public readonly float EndT;

            public GraphEdgeSegment(LineRenderer line, string fromId, string toId, float startT, float endT)
            {
                Line = line;
                FromId = fromId;
                ToId = toId;
                StartT = startT;
                EndT = endT;
            }
        }

        private void Start()
        {
            Camera camera = Camera.main;
            if (camera == null)
            {
                camera = FindObjectsByType<Camera>(FindObjectsInactive.Include)
                    .FirstOrDefaultCamera();
            }

            if (camera == null)
            {
                Debug.LogError("JARVIS needs an active XR camera. Open the generated scene from the supplied Meta Interaction SDK project.");
                enabled = false;
                return;
            }

            BuildCanvas(camera);
            BuildPersistentFrame();
            BuildGraph();
            ShowMode(_activeMode);

            _eventSystem = FindAnyObjectByType<EventSystem>();
            if (_eventSystem == null)
            {
                _eventSystem = new GameObject("JARVIS Event System").AddComponent<EventSystem>();
            }

            JarvisPinchInteractor input = gameObject.AddComponent<JarvisPinchInteractor>();
            input.Initialize(_canvas, _raycaster, _eventSystem, SetMapScale, () => _activeMode == "MAP");
            gameObject.AddComponent<JarvisPalmMenu>().Initialize(
                ShowMode, new[] { "MAP", "FLOW", "CODE", "OPS" }, m => m == _activeMode);
            JarvisVoice voice = gameObject.AddComponent<JarvisVoice>();
            voice.Transcript += OnVoiceTranscript;
            voice.Notice += SetAssistantMessage;
            if (_orb != null) // pinch the orb to talk
            {
                _orb.raycastTarget = true;
                Button orbButton = _orb.gameObject.AddComponent<Button>();
                orbButton.targetGraphic = _orb;
                orbButton.onClick.AddListener(() => voice.ToggleListening());
            }
            InitBridge();
            JarvisAudio.Play(JarvisAudio.Cue.RiskPing);
        }

        private void OnVoiceTranscript(string text)
        {
            SetAssistantMessage(text);
            AskAgent(text);
        }

        private void AskAgent(string text)
        {
            RunAsk(text);
        }

        private void BuildCanvas(Camera camera)
        {
            GameObject canvasObject = new("JARVIS · VR Workspace",
                typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvasObject.transform.SetParent(transform, false);
            JarvisCurve.RadiusPixels = CurveRadiusMeters > 0f ? CurveRadiusMeters / WorldScale : 0f;
            _canvas = canvasObject.GetComponent<Canvas>();
            _canvas.renderMode = RenderMode.WorldSpace;
            _canvas.worldCamera = camera;
            _canvas.sortingOrder = 20;
            _raycaster = canvasObject.GetComponent<GraphicRaycaster>();

            RectTransform canvasRect = canvasObject.GetComponent<RectTransform>();
            canvasRect.sizeDelta = new Vector2(CanvasWidth, CanvasHeight);
            canvasRect.localScale = Vector3.one * WorldScale;
            Transform cameraTransform = camera.transform;
            canvasRect.position = cameraTransform.position + cameraTransform.forward * 1.6f;
            canvasRect.rotation = cameraTransform.rotation;

            CanvasScaler scaler = canvasObject.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ConstantPixelSize;
            scaler.referencePixelsPerUnit = 100;

            _roundedSprite = JarvisGfx.RoundedRect();
            Image backdrop = CreateImage(canvasRect, "Glass Backdrop", 0, 0, CanvasWidth, CanvasHeight,
                new Color(1f, 1f, 1f, 0.92f));
            backdrop.sprite = JarvisGfx.VerticalGradient(Pal.SpaceTop, Pal.SpaceBottom);
            backdrop.type = Image.Type.Simple;
            backdrop.raycastTarget = false;
            _contentRoot = CreateRect(canvasRect, "Workspace", 0, 0, CanvasWidth, CanvasHeight);
        }

        private void BuildPersistentFrame()
        {
            CreatePanel(_contentRoot, "Top status", 18, 16, 1404, 62, Panel, Border);
            Text(_contentRoot, "JARVIS  /  SOFTWARE INTELLIGENCE", 42, 29, 450, 30, 24, MainText, FontStyle.Bold);
            CreateImage(_contentRoot, "Repository indexed indicator", 804, 40, 10, 10, Green);
            Text(_contentRoot, "REPO INDEXED · DEMO", 824, 31, 154, 28, 14, MainText, FontStyle.Bold);
            Text(_contentRoot, "acme-shop   /   fix/account-delete   ·   7 changed",
                956, 31, 430, 28, 16, MutedText, FontStyle.Normal, TextAnchor.MiddleRight);

            CreatePanel(_contentRoot, "JARVIS briefing", 24, 96, 272, 570, Panel, Border);
            CreateOrb(_contentRoot, 50, 119);
            Text(_contentRoot, "JARVIS", 106, 118, 150, 28, 21, MainText, FontStyle.Bold);
            Text(_contentRoot, "Demo fixture · visual briefing", 106, 145, 176, 24, 13, MutedText);
            Text(_contentRoot,
                "The latest change touches account deletion. I couldn't find an ownership check on the path to the database.",
                48, 188, 220, 150, 18, MainText);
            Text(_contentRoot, "Two downstream paths have no direct tests. Both are highlighted.",
                48, 346, 220, 86, 16, MutedText);
            Button(_contentRoot, "Show the risk", 42, 452, 236, 48, Red, () => ShowMode("CODE"));
            Button(_contentRoot, "What changed?", 42, 512, 236, 48, Amber, () => ShowMode("FLOW"));
            Text(_contentRoot, "Evidence is labeled as fact, missing, or AI hypothesis.",
                48, 583, 220, 54, 14, MutedText);

            CreatePanel(_contentRoot, "Main view", 316, 96, 842, 570,
                new Color(Panel.r, Panel.g, Panel.b, Pal.Glass.a), Border);
            _contentRoot = CreateRect(_contentRoot, "Dynamic view", 316, 96, 842, 570);

            CreatePanel(_contentRoot.parent as RectTransform, "Navigation rail", 24, 696, 1392, 88, Panel, Border);
            CreateNavigation();
            CreateVoicePrompt();
        }

        private void Update()
        {
            if (_orb != null)
            {
                JarvisVoice v = JarvisVoice.Instance;
                JarvisVoice.State state = v != null ? v.Current : JarvisVoice.State.Idle;
                float level = v != null ? v.Level : 0f;
                float rate = state == JarvisVoice.State.Listening ? 3.4f : state == JarvisVoice.State.Speaking ? 6f : 1.4f;
                float amp = state == JarvisVoice.State.Idle ? 0.04f
                    : state == JarvisVoice.State.Listening ? 0.08f + level * 0.25f : 0.10f;
                _orb.rectTransform.localScale = Vector3.one * (1f + Mathf.Sin(Time.unscaledTime * rate) * amp);
                Color target = state == JarvisVoice.State.Idle ? new Color(Cyan.r, Cyan.g, Cyan.b, 0.75f) : Cyan;
                _orb.color = Color.Lerp(_orb.color, target, 8f * Time.unscaledDeltaTime);
                UpdateVoiceBars(level, state);
            }

            if (_activeMode == "FLOW" && _flowPlaying && Time.unscaledTime >= _flowNextAt)
            {
                if (_flowStep >= 4)
                {
                    _flowPlaying = false;
                    ShowMode("FLOW");
                }
                else
                {
                    _flowStep++;
                    _flowNextAt = Time.unscaledTime + 1.6f;
                    ShowMode("FLOW");
                }
            }
        }

        private void CreateNavigation()
        {
            string[] modes = { "MAP", "FLOW", "CODE", "OPS" };
            for (int i = 0; i < modes.Length; i++)
            {
                string mode = modes[i];
                Button(_contentRoot.parent as RectTransform, mode, 42 + i * 86, 714, 76, 50,
                    _activeMode == mode ? Cyan : PanelRaised, () => ShowMode(mode), 16);
            }

            Text(_contentRoot.parent as RectTransform, "Pinch to select · tabs switch views",
                1120, 718, 260, 52, 14, MutedText, FontStyle.Normal, TextAnchor.MiddleCenter);
        }

        private void CreateVoicePrompt()
        {
            RectTransform ui = _contentRoot.parent as RectTransform;
            CreatePanel(ui, "Voice prompt", 396, 706, 580, 66, PanelRaised, Border);
            Image voiceOrb = CreateImage(ui, "Voice orb", 414, 718, 38, 38, Cyan);
            voiceOrb.sprite = JarvisGfx.Circle();
            Text(ui, "JARVIS", 464, 716, 78, 20, 13, Cyan, FontStyle.Bold);
            _assistantMessage = Text(ui, "“What breaks if I change deleteAccount?”", 464, 737, 330, 25, 18, MainText);

            _voiceBars.Clear();
            for (int i = 0; i < 5; i++)
            {
                Image bar = CreateImage(ui, "Voice bar " + i, 806 + i * 12, 722, 6, 30, Cyan);
                bar.rectTransform.pivot = new Vector2(0f, 0.5f);
                bar.rectTransform.anchoredPosition = new Vector2(806 + i * 12, -737);
                bar.raycastTarget = false;
                _voiceBars.Add(bar);
            }

            Button(ui, "TALK", 888, 716, 76, 46, Cyan, () =>
            {
                JarvisVoice v = JarvisVoice.Instance;
                if (v != null) v.ToggleListening();
                else SetAssistantMessage("Voice service is not running.");
            }, 14);
        }

        private void UpdateVoiceBars(float level, JarvisVoice.State state)
        {
            for (int i = 0; i < _voiceBars.Count; i++)
            {
                float wobble = 0.6f + 0.4f * Mathf.Sin(Time.unscaledTime * 9f + i * 1.3f);
                float h = state == JarvisVoice.State.Idle ? 6f : 6f + Mathf.Clamp01(level * 6f * wobble) * 26f;
                _voiceBars[i].rectTransform.sizeDelta = new Vector2(6f, h);
            }
        }

        private void BuildGraph()
        {
            // The graph is rendered on the world-space panel; the interactive spheres
            // sit slightly in front of it so pinch-ray selection has real depth.
            RectTransform graphArea = CreateRect(_contentRoot, "Graph area", 20, 0, 802, 570);
            graphArea.pivot = new Vector2(0.5f, 0.5f);
            graphArea.anchoredPosition = new Vector2(421, -285);
            _mapGraph = graphArea;

            GameObject worldRoot = new("JARVIS map spatial root");
            worldRoot.transform.SetParent(_canvas.transform, false);
            worldRoot.transform.localPosition = CanvasPointToLocal(737, 381, 0);
            worldRoot.transform.localScale = Vector3.one * _mapScale;
            _graphWorldRoot = worldRoot.transform;

            Cluster(graphArea, "api", 56, 104, 184, 164);
            Cluster(graphArea, "auth", 250, 76, 220, 184);
            Cluster(graphArea, "services", 388, 208, 198, 174);
            Cluster(graphArea, "db", 490, 340, 230, 154);
            Cluster(graphArea, "tests", 194, 340, 226, 156);

            foreach (NodeFixture node in Nodes)
            {
                CreateNode(node);
                string clusterId = node.Cluster.TrimEnd('/');
                Vector2 clusterOrigin = _clusterUiOrigins[clusterId];
                RectTransform clusterRoot = _clusterUiRoots[clusterId];
                Text label = Text(clusterRoot, node.Label,
                    node.X - 67 - clusterOrigin.x, node.Y + 34 - clusterOrigin.y, 150, 28, 14, MainText,
                    FontStyle.Normal, TextAnchor.MiddleCenter, FontRole.Mono);
                _graphLabels[node.Id] = label.gameObject;
            }

            Link(graphArea, "route.delete", "auth.require", Cyan, false);
            Link(graphArea, "route.delete", "service.delete", Amber, false);
            Link(graphArea, "service.delete", "db.repo", Amber, false);
            Link(graphArea, "db.repo", "db.delete", Cyan, false);
            Link(graphArea, "service.delete", "auth.owner", Red, true);   // UI hint: checkOwner exists but is never called
            Link(graphArea, "test.own-account", "service.delete", Violet, true);
            UpdateGraphLines();
        }

        private void CreateNode(NodeFixture node)
        {
            GameObject sphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            sphere.name = "Graph node · " + node.Id;
            string clusterId = node.Cluster.TrimEnd('/');
            sphere.transform.SetParent(_clusterWorldRoots[clusterId], false);
            Vector2 clusterOrigin = _clusterUiOrigins[clusterId];
            Vector3 nodePoint = CanvasPointToLocal(node.X + 336, node.Y + 116, -22);
            Vector3 clusterPoint = CanvasPointToLocal(336 + clusterOrigin.x, 96 + clusterOrigin.y, 0);
            sphere.transform.localPosition = nodePoint - clusterPoint;
            sphere.transform.localScale = Vector3.one * (node.Id == _selectedNode ? 35f : 25f);
            Renderer renderer = sphere.GetComponent<Renderer>();
            Material material = new(Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Unlit/Color"));
            material.color = node.Color;
            if (material.HasProperty("_EmissionColor"))
            {
                material.EnableKeyword("_EMISSION");
                material.SetColor("_EmissionColor", node.Color * 0.65f);
            }
            renderer.material = material;
            Collider nodeCollider = sphere.GetComponent<Collider>();
            nodeCollider.isTrigger = false;
            if (nodeCollider is SphereCollider sphereCollider)
            {
                sphereCollider.radius = 1.5f;
            }
            JarvisGraphNode selectable = sphere.AddComponent<JarvisGraphNode>();
            selectable.Initialize(node.Id, SelectNode, MoveCluster, ExpandAround);
            _graphObjects[node.Id] = sphere;
            if (node.Color == Red) sphere.AddComponent<JarvisRiskRing>();
        }

        private void Link(RectTransform parent, string fromId, string toId, Color color, bool dashed)
        {
            NodeFixture from = FindNode(fromId);
            NodeFixture to = FindNode(toId);
            if (from == null || to == null)
            {
                return;
            }

            _edgePairs.Add((fromId, toId));

            Vector3 start = _graphWorldRoot.InverseTransformPoint(_graphObjects[fromId].transform.position);
            Vector3 end = _graphWorldRoot.InverseTransformPoint(_graphObjects[toId].transform.position);
            int segments = dashed ? 9 : 1;
            for (int i = 0; i < segments; i++)
            {
                float t0 = dashed ? (float)i / segments : 0f;
                float t1 = dashed ? (i + 0.58f) / segments : 1f;
                GameObject lineObject = new("Graph edge");
                lineObject.transform.SetParent(_graphWorldRoot, false);
                LineRenderer line = lineObject.AddComponent<LineRenderer>();
                line.useWorldSpace = false;
                line.positionCount = 2;
                line.SetPosition(0, Vector3.Lerp(start, end, t0));
                line.SetPosition(1, Vector3.Lerp(start, end, t1));
                line.startWidth = line.endWidth = dashed ? 2.8f : 4f;
                line.material = new Material(Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Unlit/Color"));
                line.startColor = line.endColor = color;
                _graphLines.Add(line);
                _graphEdgeSegments.Add(new GraphEdgeSegment(line, fromId, toId, t0, t1));
                if (!dashed && color == Amber) lineObject.AddComponent<JarvisEdgePulse>().Setup(line);
            }
        }

        private void UpdateGraphLines()
        {
            if (_graphWorldRoot == null)
            {
                return;
            }

            ApplyCurveToNodes();

            foreach (GraphEdgeSegment segment in _graphEdgeSegments)
            {
                if (segment.Line == null ||
                    !_graphObjects.TryGetValue(segment.FromId, out GameObject from) ||
                    !_graphObjects.TryGetValue(segment.ToId, out GameObject to))
                {
                    continue;
                }

                Vector3 start = _graphWorldRoot.InverseTransformPoint(from.transform.position);
                Vector3 end = _graphWorldRoot.InverseTransformPoint(to.transform.position);
                segment.Line.SetPosition(0, Vector3.Lerp(start, end, segment.StartT));
                segment.Line.SetPosition(1, Vector3.Lerp(start, end, segment.EndT));
            }
        }

        private void SetMapScale(float scale)
        {
            _mapScale = Mathf.Clamp(scale, 0.7f, 1.15f);
            if (_mapGraph != null)
            {
                _mapGraph.localScale = Vector3.one * _mapScale;
            }
            if (_graphWorldRoot != null)
            {
                _graphWorldRoot.localScale = Vector3.one * _mapScale;
            }
            UpdateGraphLines();
            if (_mapZoomReadout != null)
            {
                _mapZoomReadout.text = $"MAP ZOOM  ·  {Mathf.RoundToInt(_mapScale * 100)}%";
            }
        }

        private void ApplyCurveToNodes()
        {
            if (_canvas == null) return;
            foreach (KeyValuePair<string, GameObject> pair in _graphObjects)
            {
                Transform t = pair.Value.transform;
                float x = _canvas.transform.InverseTransformPoint(t.position).x;
                Vector3 lp = t.localPosition;
                lp.z = -22f - JarvisCurve.Sag(x) / Mathf.Max(_mapScale, 0.001f);
                t.localPosition = lp;
            }
            foreach (Transform shell in _clusterShells)
            {
                if (shell == null) continue;
                float x = _canvas.transform.InverseTransformPoint(shell.position).x;
                Vector3 lp = shell.localPosition;
                lp.z = 6f - JarvisCurve.Sag(x) / Mathf.Max(_mapScale, 0.001f);
                shell.localPosition = lp;
            }
        }

        private void MoveCluster(string nodeId, Vector3 worldDelta)
        {
            NodeFixture node = FindNode(nodeId);
            if (node == null)
            {
                return;
            }

            string clusterId = node.Cluster.TrimEnd('/');
            if (!_clusterUiRoots.TryGetValue(clusterId, out RectTransform uiRoot) ||
                !_clusterWorldRoots.TryGetValue(clusterId, out Transform worldRoot))
            {
                return;
            }

            Vector3 canvasDelta = _canvas.transform.InverseTransformVector(worldDelta) /
                                  Mathf.Max(_mapScale, 0.001f);
            Vector2 delta = new(canvasDelta.x, canvasDelta.y);
            uiRoot.anchoredPosition += delta;
            worldRoot.localPosition += new Vector3(delta.x, delta.y, 0);
            UpdateGraphLines();
        }

        private void Cluster(RectTransform parent, string title, float x, float y, float width, float height)
        {
            RectTransform clusterUi = CreateRect(parent, "Cluster group · " + title, x, y, width, height);
            _clusterUiRoots[title] = clusterUi;
            _clusterUiOrigins[title] = new Vector2(x, y);
            // Flat shell removed: a 3D ClusterShell sphere is created below.
            Text(clusterUi, title + "/", 12, 9, width - 24, 22, 15, Cyan, FontStyle.Bold);

            GameObject worldCluster = new("JARVIS graph cluster · " + title);
            worldCluster.transform.SetParent(_graphWorldRoot, false);
            Vector3 clusterPoint = CanvasPointToLocal(336 + x, 96 + y, 0);
            worldCluster.transform.localPosition = clusterPoint - CanvasPointToLocal(737, 381, 0);
            _clusterWorldRoots[title] = worldCluster.transform;
            CreateClusterShell(worldCluster.transform, width, height);
        }

        private void CreateClusterShell(Transform clusterRoot, float width, float height)
        {
            GameObject shell = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            shell.name = "ClusterShell";
            Destroy(shell.GetComponent<Collider>()); // never blocks node pinch rays
            shell.transform.SetParent(clusterRoot, false);
            // The cluster root sits at the cluster's top-left corner, so move to its centre.
            shell.transform.localPosition = new Vector3(width * 0.5f, -height * 0.5f, 6f);
            float d = Mathf.Max(width, height) * 1.1f;
            shell.transform.localScale = new Vector3(d, d, d * 0.6f); // flattened so nodes stay inside
            Renderer r = shell.GetComponent<Renderer>();
            Shader sh = Shader.Find("JARVIS/FresnelShell");
            if (sh != null)
            {
                Material m = new Material(sh);
                m.SetColor("_Color", Cyan);
                r.sharedMaterial = m;
            }
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            _clusterShells.Add(shell.transform);
        }

        private void ShowMode(string mode)
        {
            _activeMode = mode;
            if (mode != "FLOW")
            {
                _flowPlaying = false;
            }
            if (_contentRoot == null)
            {
                return;
            }

            for (int i = _contentRoot.childCount - 1; i >= 0; i--)
            {
                Transform child = _contentRoot.GetChild(i);
                if (child == _mapGraph)
                {
                    child.gameObject.SetActive(mode == "MAP");
                }
                else
                {
                    Destroy(child.gameObject);
                }
            }

            ApplyGraphOverlays();

            switch (mode)
            {
                case "MAP": BuildMapView(); break;
                case "FLOW": BuildFlowView(); break;
                case "CODE": BuildCodeView(); break;
                case "OPS": BuildOpsView(); break;
                default: BuildMapView(); break;
            }
            UpdateNavigation();
        }

        private void BuildMapView()
        {
            JarvisAudio.Play(JarvisAudio.Cue.PathPulse);
            Text(_contentRoot, "SYSTEM MAP", 26, 18, 360, 32, 20, MainText, FontStyle.Bold);
            Text(_contentRoot, "Account deletion · 7 connected functions · 1 review gap",
                26, 50, 720, 26, 15, MutedText);

            CreatePanel(_contentRoot, "Overlay controls", 852, 0, 246, 570, PanelRaised, Border);
            Text(_contentRoot, "OVERLAYS", 870, 18, 210, 26, 16, MainText, FontStyle.Bold);
            string[] labels = { "Git changes", "Risks", "Test coverage", "Data flow" };
            for (int i = 0; i < labels.Length; i++)
            {
                int index = i;
                Color accent = i == 1 ? Red : i == 0 ? Amber : Cyan;
                Button(_contentRoot, labels[i] + (_overlays[i] ? "   ON" : "   OFF"),
                    866, 58 + i * 54, 212, 42,
                    _overlays[i] ? new Color(accent.r, accent.g, accent.b, 0.28f) : Panel,
                    () =>
                    {
                        _overlays[index] = !_overlays[index];
                        ApplyGraphOverlays();
                        ShowMode("MAP");
                    }, 14);
            }

            Text(_contentRoot, "EDGES", 870, 302, 190, 24, 14, MainText, FontStyle.Bold);
            Legend(_contentRoot, 870, 334, Cyan, "Parser fact");
            Legend(_contentRoot, 870, 366, Violet, "AI inference");
            Legend(_contentRoot, 870, 398, Amber, "Change path");
            Text(_contentRoot, "HAND INPUT", 870, 438, 200, 22, 13, MainText, FontStyle.Bold);
            Text(_contentRoot, "Pinch a node and pull to move its cluster. Pinch with both hands; spread or squeeze to zoom the map.",
                870, 462, 204, 82, 12, MutedText);
            _mapZoomReadout = Text(_contentRoot, $"MAP ZOOM  ·  {Mathf.RoundToInt(_mapScale * 100)}%",
                870, 547, 204, 18, 11, Cyan, FontStyle.Bold);
        }

        private void BuildFlowView()
        {
            Text(_contentRoot, "EXECUTION VIEW", 26, 18, 360, 32, 20, MainText, FontStyle.Bold);
            Text(_contentRoot, "“Investigate the account deletion flow and find authorization gaps.”",
                26, 50, 770, 28, 15, MutedText);
            string[] detail =
            {
                "Route entry · routes/account.ts:12 receives DELETE /account/:id.",
                "Authentication · requireAuth checks that a signed-in user exists.",
                "Changed code · deleteAccount receives the requested target id.",
                "Ownership · no signed-in-user vs target-id comparison was found in this fixture.",
                "Database · users.repo.delete writes the supplied id."
            };
            Color detailColor = _flowStep == 3 ? Red : _flowStep == 2 ? Amber : Cyan;
            CreatePanel(_contentRoot, "Selected edge evidence", 28, 88, 786, 48,
                new Color(detailColor.r, detailColor.g, detailColor.b, 0.13f), detailColor);
            Text(_contentRoot, "STOP DETAIL   " + detail[_flowStep],
                44, 101, 754, 28, 14, MainText, FontStyle.Normal, TextAnchor.MiddleLeft);
            string[] steps =
            {
                "DELETE /account/:id",
                "requireAuth",
                "deleteAccount",
                "ownership check ?",
                "users.repo.delete",
            };
            for (int i = 0; i < steps.Length; i++)
            {
                int x = 28 + i * 157;
                Color color = i == 3 ? Red : i == 2 ? Amber : Cyan;
                CreatePanel(_contentRoot, "Flow step " + i, x, 152, 142, 112,
                    i == _flowStep ? new Color(color.r, color.g, color.b, 0.24f) : PanelRaised, color);
                Image stepSurface = _contentRoot.Find("Flow step " + i)?.GetComponent<Image>();
                if (stepSurface != null)
                {
                    Button stepButton = stepSurface.gameObject.AddComponent<Button>();
                    stepButton.targetGraphic = stepSurface;
                    ColorBlock stepColors = stepButton.colors;
                    stepColors.normalColor = stepSurface.color;
                    stepColors.highlightedColor = Color.Lerp(stepSurface.color, Color.white, 0.16f);
                    stepColors.pressedColor = Color.Lerp(stepSurface.color, Color.white, 0.3f);
                    stepButton.colors = stepColors;
                    int stepIndex = i;
                    stepButton.onClick.AddListener(() => ChangeFlowTo(stepIndex));
                }
                Text(_contentRoot, (i + 1).ToString("0") + "  ·  " + steps[i],
                    x + 12, 168, 118, 42, 15, MainText, FontStyle.Bold);
                Text(_contentRoot, i == 3 ? "NOT FOUND" : "source-backed path",
                    x + 12, 220, 118, 26, 12, i == 3 ? Red : MutedText, FontStyle.Bold);
                if (i < steps.Length - 1)
                {
                    Text(_contentRoot, "→", x + 141, 188, 22, 24, 19, color, FontStyle.Bold, TextAnchor.MiddleCenter);
                }
            }

            EvidenceCard(_contentRoot, "PARSER FACT",
                "deleteAccount is reached from the route after authentication middleware runs.",
                28, 316, 242, 134, Cyan);
            EvidenceCard(_contentRoot, "NOT FOUND",
                "No comparison between the signed-in user and target id appears in this fixture.",
                286, 316, 242, 134, Red);
            EvidenceCard(_contentRoot, "AI HYPOTHESIS · UNVERIFIED",
                "A logged-in user may be able to delete another account. Confirm with a test.",
                544, 316, 272, 134, Violet);

            Button(_contentRoot, "PREVIOUS", 28, 478, 118, 46, PanelRaised, () =>
            {
                _flowPlaying = false;
                ChangeFlow(-1);
            }, 14);
            Text(_contentRoot, $"STOP  {_flowStep + 1} / {steps.Length}", 198, 489, 240, 24, 14, MutedText, FontStyle.Bold);
            Button(_contentRoot, _flowPlaying ? "PAUSE" : "PLAY PATH", 436, 478, 128, 46,
                PanelRaised, ToggleFlowPlayback, 14);
            Button(_contentRoot, "NEXT STOP", 686, 478, 128, 46, Cyan, () =>
            {
                _flowPlaying = false;
                ChangeFlow(1);
            }, 14);
            Text(_contentRoot, "Pinch a stop to inspect its evidence · playback advances each stop.",
                28, 534, 760, 22, 13, MutedText);
        }

        private void BuildCodeView()
        {
            Text(_contentRoot, "CODE WORKBENCH", 26, 18, 360, 32, 20, MainText, FontStyle.Bold);
            NodeFixture selectedNode = FindNode(_selectedNode);
            Text(_contentRoot, "Selected · " + (selectedNode != null ? selectedNode.Label : _selectedNode),
                26, 50, 740, 28, 15, MutedText);

            CreatePanel(_contentRoot, "Callers panel", 24, 104, 220, 290, PanelRaised, Border);
            Text(_contentRoot, "CALLERS · 2", 42, 120, 180, 24, 15, MainText, FontStyle.Bold);
            Button(_contentRoot, "routes/account.ts:14", 40, 158, 188, 42, Panel,
                () => SelectNode("route.delete"), 12);
            Button(_contentRoot, "admin/purge.ts:33  ·  inferred", 40, 208, 188, 52,
                new Color(Violet.r, Violet.g, Violet.b, 0.16f),
                () => SetAssistantMessage("Caller relationship is an AI inference in this fixture, not a parser-confirmed edge."), 12);
            Text(_contentRoot, "CALLS · 3", 42, 278, 180, 24, 15, MainText, FontStyle.Bold);
            Button(_contentRoot, "users.repo.delete", 40, 312, 188, 40, Panel,
                () => SelectNode("db.delete"), 12);
            Button(_contentRoot, "audit.log  ·  mailer", 40, 360, 188, 36, Panel,
                () => SetAssistantMessage("These downstream calls are illustrative fixture data."), 12);

            GetSelectedCodeFixture(out string sourceTitle, out string sourceBody,
                out string sourceFinding, out Color findingColor);
            if (_codeTab == "DIFF")
            {
                sourceBody = "  39  await audit.log(id);\n" +
                             "+ 40  if (req.user.id !== id) {\n" +
                             "+ 41    throw new ForbiddenError();\n" +
                             "+ 42  }\n" +
                             "  43  await users.repo.delete(id);";
                sourceFinding = "GHOST DIFF · illustrative only; not applied to a repository.";
                findingColor = Amber;
            }
            else if (_codeTab == "BLAME")
            {
                sourceBody = "38  export async function deleteAccount(id) {\n" +
                             "39  · fixture author · 12 days ago\n" +
                             "40  · demo branch · today\n" +
                             "41  · source metadata unavailable";
                sourceFinding = "BLAME DATA · demo fixture; no live Git history is connected.";
                findingColor = Violet;
            }
            else if (_codeTab == "NOTE")
            {
                sourceBody = "Review note\n\n" +
                             "Authentication proves who is signed in. It does not prove that the requested account belongs to that user.\n\n" +
                             "Confirm the policy and add a negative test.";
                sourceFinding = "NOTE · recommendation only; no file is being edited.";
                findingColor = Cyan;
            }
            RectTransform sourcePanelRoot = CreateRect(_contentRoot, "Expandable source panel", 258, 104, 348, 392);
            sourcePanelRoot.pivot = new Vector2(0.5f, 0.5f);
            sourcePanelRoot.anchoredPosition = new Vector2(432, -300);
            Vector3 sourcePanelBasePosition = sourcePanelRoot.localPosition;
            sourcePanelRoot.localScale = Vector3.one * _codePanelScale;
            sourcePanelRoot.localPosition = sourcePanelBasePosition + _codePanelOffset;
            JarvisPanelExpandTarget expandTarget = sourcePanelRoot.gameObject.AddComponent<JarvisPanelExpandTarget>();
            expandTarget.SetTransformChangedCallback((scale, localPosition) =>
            {
                _codePanelScale = scale;
                _codePanelOffset = localPosition - sourcePanelBasePosition;
            });
            CreatePanel(sourcePanelRoot, "Source panel", 0, 0, 348, 392, Panel, findingColor);
            Text(sourcePanelRoot, sourceTitle + "  ·  DEMO FIXTURE", 20, 15, 306, 26, 14, MainText, FontStyle.Bold);
            string[] tabs = { "CODE", "DIFF", "BLAME", "NOTE" };
            for (int i = 0; i < tabs.Length; i++)
            {
                string tab = tabs[i];
                bool active = _codeTab == tab;
                Button(sourcePanelRoot, tab, 16 + i * 78, 47, 72, 34,
                    active ? new Color(Cyan.r, Cyan.g, Cyan.b, 0.22f) : PanelRaised,
                    () => SetCodeTab(tab), 11);
            }
            Text(sourcePanelRoot, sourceBody,
                20, 90, 306, 178, 13, MainText, FontStyle.Normal);
            CreatePanel(sourcePanelRoot, "Finding", 16, 286, 316, 70,
                new Color(findingColor.r, findingColor.g, findingColor.b, 0.16f), findingColor);
            Text(sourcePanelRoot, sourceFinding, 30, 302, 286, 48, 14, findingColor, FontStyle.Bold);

            CreatePanel(_contentRoot, "Tests panel", 620, 104, 196, 290, PanelRaised, Border);
            Text(_contentRoot, "TESTS · 2", 638, 120, 156, 24, 15, MainText, FontStyle.Bold);
            Button(_contentRoot, "●  delete.happy-path  ·  pass", 636, 158, 164, 52,
                new Color(Green.r, Green.g, Green.b, 0.16f),
                () => SetAssistantMessage("Happy-path test is listed as a demo fixture; it has not run in this UI."), 10);
            Button(_contentRoot, "●  delete.other-user  ·  missing", 636, 220, 164, 60,
                new Color(Red.r, Red.g, Red.b, 0.16f),
                () => SetAssistantMessage("No cross-account deletion test is present in this fixture. The risk remains unverified."), 10);
            Text(_contentRoot, "HISTORY", 638, 304, 156, 24, 15, MainText, FontStyle.Bold);
            Text(_contentRoot, "Edited 4× in 30 days.\n3 files · 5 functions · 1 route",
                638, 338, 156, 48, 13, MutedText);
            Chip(_contentRoot, "BLAST RADIUS  ·  3 files", 630, 410, 178, 40, Amber);

            Button(_contentRoot, "DRAFT FIX + TEST", 24, 514, 190, 44, Amber, () => ShowMode("OPS"), 14);
            Button(_contentRoot, "WHAT BREAKS?", 232, 514, 170, 44, PanelRaised, () => ShowMode("FLOW"), 14);
            Button(_contentRoot, "BACK TO MAP", 420, 514, 170, 44, PanelRaised, () => ShowMode("MAP"), 14);
            Text(_contentRoot, "Read-only demo · pinch callers/tests to inspect; pinch the source panel and pull it toward you to enlarge.",
                24, 560, 770, 40, 12, MutedText);
        }

        private void BuildOpsView()
        {
            Text(_contentRoot, "MISSION  ·  Fix the account-deletion authorization gap",
                26, 18, 790, 32, 19, MainText, FontStyle.Bold);

            string[] labels = { "1 · Investigate", "2 · Patch", "3 · Test", "4 · Your review" };
            for (int i = 0; i < labels.Length; i++)
            {
                int x = 26 + i * 198;
                Color color = i == 3 ? (_approved ? Green : _rejected ? Red : Amber) :
                    i == 2 ? Amber : Green;
                CreatePanel(_contentRoot, labels[i], x, 74, 184, 92,
                    i == 3 && !_approved && !_rejected
                        ? new Color(Amber.r, Amber.g, Amber.b, 0.16f)
                        : new Color(color.r, color.g, color.b, 0.1f), color);
                Text(_contentRoot, labels[i], x + 12, 84, 160, 24, 14, MainText, FontStyle.Bold);
                Text(_contentRoot,
                    i == 0 ? "Fixture finding · no live repo" :
                    i == 1 ? "Illustrative guard diff · not applied" :
                    i == 2 ? "Test fixtures · not run here" :
                    _approved ? "Approved · demo only" : _rejected ? "Rejected · demo only" : "Waiting for your review",
                    x + 12, 111, 160, 34, 12, MutedText);
                Text(_contentRoot,
                    i == 0 ? "DEMO · COMPLETE" :
                    i == 1 ? "DIFF PREVIEW" :
                    i == 2 ? "NOT RUN" :
                    _approved ? "APPROVED" : _rejected ? "REJECTED" : "WAITING FOR YOU",
                    x + 12, 146, 160, 14, 10, color, FontStyle.Bold);
            }

            EvidenceCard(_contentRoot, "DIFF · GHOST LAYER",
                !string.IsNullOrEmpty(_ghostDiff) ? (_ghostDiff.Length > 420 ? _ghostDiff.Substring(0, 420) + "…" : _ghostDiff) + "\n\nProposed · not applied" : "+ if (req.user.id !== id) throw Forbidden();\n   await users.repo.delete(id);\n\nIllustrative · not applied",
                26, 192, 250, 176, Amber);
            CreatePanel(_contentRoot, "Test results", 292, 192, 236, 176, PanelRaised, Border);
            Text(_contentRoot, "ILLUSTRATIVE RESULTS", 310, 208, 196, 24, 13, MainText, FontStyle.Bold);
            Text(_contentRoot, "Fixture: 13 passed\nProposed: delete.other-user\nFixture: 0 failed\nNot run: staging DB",
                310, 248, 196, 104, 14, MutedText);
            CreatePanel(_contentRoot, "Agent permissions", 544, 192, 272, 176, PanelRaised, Border);
            Text(_contentRoot, "WHAT JARVIS MAY DO", 562, 208, 230, 24, 14, MainText, FontStyle.Bold);
            Text(_contentRoot, "Read + explain           AUTO\nEdit files (branch)       ASK\nRun tests (sandbox)       ASK\nMerge / commit            YOU ONLY",
                562, 248, 232, 104, 13, MutedText);

            Button(_contentRoot, "REJECT", 182, 426, 180, 64, new Color(Red.r, Red.g, Red.b, 0.22f),
                () => RejectProposal(), 18);
            string approvalLabel = _approved ? "APPROVED" :
                _rejected ? "REJECTED" : "PINCH + HOLD TO APPROVE";
            Button(_contentRoot, approvalLabel,
                426, 426, 280, 64, new Color(Green.r, Green.g, Green.b, 0.22f), () => { }, 16);
            Text(_contentRoot, "Pinch and hold for 2 seconds. Release early to cancel.",
                258, 505, 400, 28, 14, MutedText, FontStyle.Normal, TextAnchor.MiddleCenter);
            Text(_contentRoot,
                "Demo only: the patch, test output, and approval are illustrative. No repository files are modified or committed.",
                26, 548, 790, 26, 13, MutedText);
        }

        private void UpdateNavigation()
        {
            string[] modes = { "MAP", "FLOW", "CODE", "OPS" };
            for (int i = 0; i < modes.Length; i++)
            {
                Button button = _contentRoot.parent.Find(modes[i] + " button")?.GetComponent<Button>();
                Text label = button != null ? button.GetComponentInChildren<Text>() : null;
                if (button == null || label == null) continue;
                bool selected = modes[i] == _activeMode;
                Image buttonImage = button.GetComponent<Image>();
                if (buttonImage != null) buttonImage.color = selected ? Cyan : PanelRaised;
                label.color = selected ? Space : MainText;
            }
        }

        private void CreateOrb(RectTransform parent, float x, float y)
        {
            Image outer = CreateImage(parent, "JARVIS orb glow", x, y, 44, 44,
                new Color(Cyan.r, Cyan.g, Cyan.b, 0.18f));
            outer.raycastTarget = false;
            Image inner = CreateImage(parent, "JARVIS orb", x + 8, y + 8, 28, 28, Cyan);
            inner.raycastTarget = false;
            _orb = inner;
        }

        private void Legend(RectTransform parent, float x, float y, Color color, string label)
        {
            Image swatch = CreateImage(parent, "Legend", x, y + 7, 22, 4, color);
            swatch.raycastTarget = false;
            Text(parent, label, x + 34, y, 140, 22, 13, MutedText);
        }

        private void EvidenceCard(RectTransform parent, string tag, string body,
            float x, float y, float width, float height, Color accent)
        {
            CreatePanel(parent, tag, x, y, width, height, PanelRaised, new Color(accent.r, accent.g, accent.b, 0.55f));
            Text(parent, tag, x + 14, y + 12, width - 28, 22, 12, accent, FontStyle.Bold);
            Text(parent, body, x + 14, y + 42, width - 28, height - 50, 14, MainText);
        }

        private void Chip(RectTransform parent, string label, float x, float y, float width, float height, Color accent)
        {
            CreatePanel(parent, label, x, y, width, height,
                new Color(accent.r, accent.g, accent.b, 0.12f), new Color(accent.r, accent.g, accent.b, 0.4f));
            Text(parent, label, x + 10, y + 6, width - 20, height - 12, 12, MainText);
        }

        private Image CreatePanel(RectTransform parent, string name, float x, float y, float width, float height,
            Color fill, Color outline)
        {
            Image border = CreateImage(parent, name + " border", x, y, width, height, outline);
            border.sprite = _roundedSprite;
            border.type = Image.Type.Sliced;
            Image inner = CreateImage(parent, name, x + 1, y + 1, width - 2, height - 2, fill);
            inner.sprite = _roundedSprite;
            inner.type = Image.Type.Sliced;
            return inner;
        }

        private Image CreateImage(RectTransform parent, string name, float x, float y, float width, float height, Color color)
        {
            GameObject imageObject = new(name, typeof(RectTransform), typeof(Image));
            imageObject.transform.SetParent(parent, false);
            SetRect(imageObject.GetComponent<RectTransform>(), x, y, width, height);
            Image image = imageObject.GetComponent<Image>();
            image.color = color;
            image.sprite = _roundedSprite;
            image.type = Image.Type.Sliced;
            imageObject.AddComponent<JarvisCurve>();
            return image;
        }

        private Text Text(RectTransform parent, string value, float x, float y, float width, float height,
            int size, Color color, FontStyle style = FontStyle.Normal,
            TextAnchor alignment = TextAnchor.UpperLeft, FontRole role = FontRole.Auto)
        {
            GameObject textObject = new(value, typeof(RectTransform), typeof(Text));
            textObject.transform.SetParent(parent, false);
            SetRect(textObject.GetComponent<RectTransform>(), x, y, width, height);
            Text text = textObject.GetComponent<Text>();
            text.text = value;
            JarvisFonts.Resolve(role, value, style, out Font resolvedFont, out FontStyle resolvedStyle);
            text.font = resolvedFont;
            text.fontSize = Mathf.RoundToInt(size * VrTextScale);
            text.fontStyle = resolvedStyle;
            text.color = color;
            text.alignment = alignment;
            text.horizontalOverflow = HorizontalWrapMode.Wrap;
            text.verticalOverflow = VerticalWrapMode.Overflow;
            text.raycastTarget = false;
            textObject.AddComponent<JarvisCurve>();
            return text;
        }

        private Button Button(RectTransform parent, string label, float x, float y, float width, float height,
            Color color, UnityAction action, int fontSize = 16)
        {
            Image image = CreateImage(parent, label + " button", x, y, width, height, color);
            image.raycastTarget = true;
            Button button = image.gameObject.AddComponent<Button>();
            button.targetGraphic = image;
            ColorBlock colors = button.colors;
            colors.normalColor = color;
            colors.highlightedColor = Color.Lerp(color, Color.white, 0.16f);
            colors.pressedColor = Color.Lerp(color, Color.white, 0.3f);
            colors.selectedColor = colors.highlightedColor;
            button.colors = colors;
            Text labelText = Text(image.transform as RectTransform, label, 8, 6, width - 16, height - 12,
                fontSize, MainText, FontStyle.Bold, TextAnchor.MiddleCenter);
            labelText.raycastTarget = false;
            button.onClick.AddListener(action);
            button.onClick.AddListener(() => JarvisAudio.Play(JarvisAudio.Cue.SelectTick));

            if (label == "PINCH + HOLD TO APPROVE")
            {
                _approvalFill = CreateImage(image.transform as RectTransform, "Hold progress",
                    8, height - 8, width - 16, 4, Green);
                _approvalFill.type = Image.Type.Filled;
                _approvalFill.fillMethod = Image.FillMethod.Horizontal;
                _approvalFill.fillAmount = 0;
                _approvalFill.raycastTarget = false;
                _approvalHint = labelText;
                JarvisApprovalHold hold = image.gameObject.AddComponent<JarvisApprovalHold>();
                hold.Configure(ApproveProposal, _approvalFill, _approvalHint);
                hold.ProgressChanged += JarvisAudio.SetCharge;
                hold.HoldCompleted += () => { JarvisAudio.SetCharge(0f); JarvisAudio.Play(JarvisAudio.Cue.ApproveClick); };
                hold.HoldCancelled += () => JarvisAudio.SetCharge(0f);
            }

            return button;
        }

        private RectTransform CreateRect(RectTransform parent, string name, float x, float y, float width, float height)
        {
            GameObject rectObject = new(name, typeof(RectTransform));
            rectObject.transform.SetParent(parent, false);
            SetRect(rectObject.GetComponent<RectTransform>(), x, y, width, height);
            return rectObject.GetComponent<RectTransform>();
        }

        private static void SetRect(RectTransform rect, float x, float y, float width, float height)
        {
            rect.anchorMin = new Vector2(0, 1);
            rect.anchorMax = new Vector2(0, 1);
            rect.pivot = new Vector2(0, 1);
            rect.anchoredPosition = new Vector2(x, -y);
            rect.sizeDelta = new Vector2(width, height);
        }

        private Vector3 CanvasPointToLocal(float x, float y, float z)
        {
            return new Vector3(x - CanvasWidth * 0.5f,
                CanvasHeight * 0.5f - y, z);
        }

        private void SelectNode(string nodeId)
        {
            JarvisAudio.Play(JarvisAudio.Cue.SelectTick);
            _selectedNode = nodeId;
            _codeTab = "CODE";
            if (_graphObjects.TryGetValue(nodeId, out GameObject selected))
            {
                selected.transform.localScale = Vector3.one * 35f;
            }
            foreach (KeyValuePair<string, GameObject> pair in _graphObjects)
            {
                if (pair.Key != nodeId)
                {
                    pair.Value.transform.localScale = Vector3.one * 25f;
                }
            }
            ShowMode("CODE");
        }

        private void ApplyGraphOverlays()
        {
            bool mapVisible = _activeMode == "MAP";
            foreach (NodeFixture node in Nodes)
            {
                bool show = mapVisible && !(node.Id == "test.own-account" && !_overlays[2]);
                if (_graphObjects.TryGetValue(node.Id, out GameObject graphObject))
                {
                    graphObject.SetActive(show);
                    JarvisRiskRing ring = graphObject.GetComponent<JarvisRiskRing>();
                    if (ring != null) ring.SetVisible(_overlays[1]);
                    Renderer renderer = graphObject.GetComponent<Renderer>();
                    if (renderer != null)
                    {
                        Color nodeColor = node.Color;
                        nodeColor = SceneOverrideColor(node.Id, nodeColor);
                        if (!IsNeighbor(node.Id)) nodeColor = new Color(0.25f, 0.32f, 0.42f, 1f);
                        if ((nodeColor == Amber && !_overlays[0]) ||
                            (nodeColor == Red && !_overlays[1]))
                        {
                            nodeColor = new Color(0.42f, 0.5f, 0.6f, 1f);
                        }
                        Material nodeMaterial = renderer.material;
                        nodeMaterial.color = nodeColor;
                        if (nodeMaterial.HasProperty("_EmissionColor"))
                        {
                            nodeMaterial.SetColor("_EmissionColor", nodeColor * 0.65f);
                        }
                    }
                }
                if (_graphLabels.TryGetValue(node.Id, out GameObject label))
                {
                    label.SetActive(show);
                    Text labelText = label.GetComponent<Text>();
                    if (labelText != null)
                    {
                        labelText.color = NodeColorForLabel(node, show);
                    }
                }
            }

            foreach (LineRenderer line in _graphLines)
            {
                line.enabled = mapVisible;
                float width = _overlays[3] ? 4f : 2.4f;
                line.startWidth = line.endWidth = width;
            }
        }

        private Color NodeColorForLabel(NodeFixture node, bool visible)
        {
            if (!visible) return MutedText;
            if (!IsNeighbor(node.Id)) return MutedText;
            if ((node.Color == Amber && !_overlays[0]) || (node.Color == Red && !_overlays[1]))
            {
                return MutedText;
            }
            return MainText;
        }

        private void ChangeFlow(int delta)
        {
            _flowStep = Mathf.Clamp(_flowStep + delta, 0, 4);
            ShowMode("FLOW");
        }

        private void ToggleFlowPlayback()
        {
            _flowPlaying = !_flowPlaying;
            if (_flowStep >= 4 && _flowPlaying)
            {
                _flowStep = 0;
            }
            _flowNextAt = Time.unscaledTime + 1.6f;
            ShowMode("FLOW");
        }

        private void ChangeFlowTo(int step)
        {
            _flowPlaying = false;
            _flowStep = Mathf.Clamp(step, 0, 4);
            ShowMode("FLOW");
        }

        private void SetCodeTab(string tab)
        {
            _codeTab = tab;
            ShowMode("CODE");
        }

        private void GetSelectedCodeFixture(out string title, out string source, out string finding, out Color accent)
        {
            if (TryLiveFixture(out title, out source, out finding, out accent)) return;
            switch (_selectedNode)
            {
                case "route.delete":
                    title = "routes/account.ts";
                    source = "12  router.delete('/account/:id', requireAuth, async (req, res) => {\n" +
                             "13    await deleteAccount(req.params.id);\n" +
                             "14    res.sendStatus(204);\n" +
                             "15  });";
                    finding = "AUTHENTICATION RUNS · ownership is not checked here.";
                    accent = Amber;
                    return;
                case "auth.require":
                    title = "auth/middleware.ts";
                    source = "6  export function requireAuth(req, res, next) {\n" +
                             "7    if (!req.user) return res.sendStatus(401);\n" +
                             "8    next();\n" +
                             "9  }";
                    finding = "PARSER FACT · this confirms sign-in, not target ownership.";
                    accent = Cyan;
                    return;
                case "auth.owner":
                    title = "ownership check · not found";
                    source = "Search result: no ownership comparison was found\n" +
                             "on the traced route → service → database path.";
                    finding = "NOT FOUND · verify the missing guard with a test.";
                    accent = Red;
                    return;
                case "db.delete":
                    title = "db/users.repo.ts";
                    source = "24  export async function deleteUser(id) {\n" +
                             "25    return db.user.delete({ where: { id } });\n" +
                             "26  }";
                    finding = "PARSER FACT · repository deletes the supplied id.";
                    accent = Cyan;
                    return;
                case "test.own-account":
                    title = "tests/account.test.ts";
                    source = "test('delete other user is rejected', async () => {\n" +
                             "  // No matching test found in this fixture.\n" +
                             "});";
                    finding = "TEST GAP · a cross-account deletion test is missing.";
                    accent = Violet;
                    return;
                case "db.repo":
                    title = "db/users.repo.ts";
                    source = "18  export const users = {\n" +
                             "19    repo: { delete: deleteUser }\n" +
                             "20  };";
                    finding = "PARSER FACT · this node delegates to the delete operation.";
                    accent = Cyan;
                    return;
                default:
                    title = "services/account.ts";
                    source = "38  export async function deleteAccount(id) {\n" +
                             "39    await audit.log(id);\n" +
                             "40    await users.repo.delete(id);\n" +
                             "41    return { ok: true };\n" +
                             "42  }";
                    finding = "MISSING · compare req.user.id with id before line 40.";
                    accent = Amber;
                    return;
            }
        }

        private void ApproveProposal()
        {
            if (_rejected)
            {
                return;
            }
            _approved = true;
            OnApprovalCompleted(true);
            ShowMode("OPS");
        }

        private void RejectProposal()
        {
            if (_approved)
            {
                return;
            }
            _rejected = true;
            OnApprovalCompleted(false);
            ShowMode("OPS");
        }

        private void SetAssistantMessage(string message)
        {
            if (_assistantMessage != null)
            {
                _assistantMessage.text = message;
            }
        }

        private NodeFixture FindNode(string id)
        {
            foreach (NodeFixture node in Nodes)
            {
                if (node.Id == id)
                {
                    return node;
                }
            }
            return null;
        }

        private static Color Hex(string value)
        {
            ColorUtility.TryParseHtmlString(value, out Color color);
            return color;
        }

        private void ExpandAround(string nodeId)
        {
            _expandedNode = _expandedNode == nodeId ? null : nodeId; // hold again to collapse
            JarvisAudio.Play(JarvisAudio.Cue.ExpandWhoosh);

            int callers = 0, calls = 0;
            foreach ((string From, string To) e in _edgePairs)
            {
                if (e.To == nodeId) callers++;
                if (e.From == nodeId) calls++;
            }
            NodeFixture n = FindNode(nodeId);
            SetAssistantMessage(_expandedNode == null
                ? "Collapsed."
                : (n != null ? n.Label : nodeId) + ": " + callers + " caller(s), " + calls + " call(s).");

            ApplyGraphOverlays();
            foreach (GraphEdgeSegment segment in _graphEdgeSegments)
            {
                bool connected = _expandedNode == null ||
                    segment.FromId == _expandedNode || segment.ToId == _expandedNode;
                segment.Line.startWidth = segment.Line.endWidth = connected ? 5f : 1.4f;
            }
        }

        private bool IsNeighbor(string id)
        {
            if (_expandedNode == null || id == _expandedNode) return true;
            foreach ((string From, string To) e in _edgePairs)
                if ((e.From == _expandedNode && e.To == id) || (e.To == _expandedNode && e.From == id)) return true;
            return false;
        }
    }

    internal static class CameraArrayExtensions
    {
        public static Camera FirstOrDefaultCamera(this Camera[] cameras)
        {
            foreach (Camera camera in cameras)
            {
                if (camera != null && camera.isActiveAndEnabled)
                {
                    return camera;
                }
            }
            return null;
        }
    }
}
