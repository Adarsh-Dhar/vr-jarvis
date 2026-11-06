using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;

namespace JarvisVR
{
  /// <summary>
  /// Spatial JARVIS workspace: a 3D code graph in the middle and independent floating panels around it.
  /// Replaces the single 1440x810 canvas of JarvisWorkspaceBootstrap. Turn it off with PlayerPrefs "jarvis.spatial" = 0.
  /// </summary>
  public sealed class JarvisSpatialWorkspace : MonoBehaviour
  {
    public static bool Enabled { get { return PlayerPrefs.GetInt("jarvis.spatial", 1) == 1; } }
    /// <summary>UI-only stage: scripted local answers, no network. Default is the REAL server (reads /repository).
    /// Set PlayerPrefs "jarvis.mock" to 1 (menu: JARVIS > Use mock data) for the scripted placeholder data.</summary>
    public static bool MockMode { get { return PlayerPrefs.GetInt("jarvis.mock", 0) == 1; } }

    private const float WorkspaceDistance = 1.5f;   // metres in front of the user
    private const float LabelSize = 0.010f;         // TextMesh characterSize; raise for bigger node labels
    private const int MaxCodeLines = 17;

    private enum OrbState { Idle, Listening, Thinking, Speaking, Approval, Error }

    private sealed class NodeView
    {
      public GraphNodeDto Dto; public Transform Root, BodyT; public Renderer Body; public TextMesh Label;
      public JarvisRiskRing Risk; public Color Base; public bool NoCallers; public string Badge = "";
      public ClusterView Cluster; public int In, Out; public JarvisNodeFx Fx;
    }
    private sealed class EdgeView { public GraphEdgeDto Dto; public NodeView From, To; public LineRenderer Line; public Color Base; public string Style; }
    private sealed class ClusterView { public string Name; public readonly List<NodeView> Members = new List<NodeView>(); public Transform Shell; public TextMesh Label; public bool Collapsed; }

    // ---- scene ----
    private Camera _cam;
    private Transform _root, _graphRoot;
    private IJarvisBackend _bridge;
    private bool _mock;
    private JarvisVoice _voice;
    private readonly Dictionary<string, JarvisSpatialPanel> _panels = new Dictionary<string, JarvisSpatialPanel>();
    private readonly Dictionary<string, NodeView> _nodes = new Dictionary<string, NodeView>();
    private readonly List<EdgeView> _edges = new List<EdgeView>();
    private readonly Dictionary<string, ClusterView> _clusters = new Dictionary<string, ClusterView>();
    private readonly Dictionary<string, SourceResponse> _source = new Dictionary<string, SourceResponse>();
    private readonly HashSet<string> _hot = new HashSet<string>();
    private HashSet<string> _keep;
    private bool _edgesDirty = true;

    // ---- state ----
    private GraphDto _graph;
    private HealthDto _health;
    private string[] _agentEvidence;          // node ids the agents examined for the last answer (from /ask)
    private string _agentTestResults;        // test run text from the last answer (from /ask)
    private JarvisSpatialButton _quickChange;
    private ReposDto _repos;
    private RepoTreeDto _repoTree;
    private RepoFileDto _openFile;
    private JarvisSpatialPanel _repoPanel, _codePanel;
    private JarvisSpatialButton _repoBack, _repoHome, _repoPrev, _repoNext;
    private JarvisSpatialButton _codePrev, _codeClose, _codeNext;
    private readonly List<GameObject> _repoRows = new List<GameObject>();
    private string _browserRepo, _browserPath = "";
    private int _browserPage, _openFilePage;
    private bool _treeLoading, _switching;
    private string _browserError;
    private const int BrowserRowsPerPage = 7;
    private const int EditorLinesPerPage = 18;
    private bool _serverOnline;
    private string _selected, _mode = "MAP", _pending, _ghostDiff, _testSummary = "No test run yet.";
    private readonly List<string> _log = new List<string>();
    private float _errorUntil;
    private int _progressSeen;
    private float _progressAt;
    private Transform _orb, _halo;
    private Material _orbMat;
    private JarvisOrbFx _orbFx;
    private readonly List<JarvisPathDot> _pulses = new List<JarvisPathDot>();
    private JarvisSpatialPanel _menu;
    private string _menuNode;

    public void Initialize(Camera cam)
    {
      _cam = cam;
      JarvisSceneCleanup.HideMetaDemo();
      // JarvisSceneCleanup.DisableProblematicComponents();  // Disabled to preserve hand/controller visualization
      JarvisLook.Apply(cam);
      _root = new GameObject("JARVIS Spatial Root").transform;
      Recenter();
      Invoke(nameof(Recenter), 1.0f);   // headset tracking settles after the first frames

      _graphRoot = new GameObject("Graph").transform;
      _graphRoot.SetParent(_root, false);
      _graphRoot.localPosition = new Vector3(0f, 0.05f, 0f);
      _graphRoot.localScale = Vector3.one * 0.85f;

      _mock = MockMode;
      _bridge = _mock ? (IJarvisBackend)gameObject.AddComponent<JarvisMockBackend>() : gameObject.AddComponent<JarvisBridge>();
      _voice = gameObject.AddComponent<JarvisVoice>();
      _voice.Transcript += Ask;
      _voice.Notice += m => Say(m);
      _voice.Transcriber = _bridge.Transcribe;   // speech to text on the server, no Meta Voice SDK needed

      BuildPanels();
      BuildOrb();
      JarvisAtmosphere.BuildFloor(_root, JarvisPalette.Current.Cyan);
      JarvisAtmosphere.BuildDust(_root, JarvisSpatialFx.Magenta, JarvisPalette.Current.Cyan);
      JarvisCityscape.Build(_root);
      LoadGraph(JarvisGraphModel.Sample());
      SetMode("REPOS");                 // begin with the repository picker, like an IDE start screen
      Select("service.delete");

      gameObject.AddComponent<JarvisSpatialInput>().Initialize(_cam, _graphRoot, ToggleVoice);
      Say("Hi. Pinch the orb to talk, or tap a quick question.");
      Log("workspace ready (sample graph)");

      _bridge.GetHealth(h => { _health = h; _serverOnline = h != null && h.ok; RefreshStatus(); }, e => { _serverOnline = false; RefreshStatus(); });
      FetchRepos();
      if (!_mock) _bridge.GetGraph(g =>
      {
        if (g == null || g.nodes == null || g.nodes.Count == 0) return;
        _serverOnline = true;
        LoadGraph(g);
        Log("graph from server: " + g.nodes.Count + " nodes");
        string first = g.nodes[0].id;
        Select(_nodes.ContainsKey(_selected ?? "") ? _selected : first);
        RefreshStatus();
      });
    }

    private void Recenter()
    {
      if (_cam == null || _root == null) return;
      Vector3 fwd = _cam.transform.forward; fwd.y = 0f;
      if (fwd.sqrMagnitude < 0.01f) fwd = Vector3.forward;
      fwd.Normalize();
      Vector3 p = _cam.transform.position + fwd * WorkspaceDistance;
      p.y = _cam.transform.position.y - 0.05f;
      _root.position = p;
      _root.rotation = Quaternion.LookRotation(fwd, Vector3.up);
    }

    // =========================================================== panels

    private static readonly string[] NavModes = { "MAP", "CODE", "FLOW", "ISSUES", "TESTS", "GIT", "AGENT" };
    private static readonly Dictionary<string, string[]> ModePanels = new Dictionary<string, string[]>
    {
      { "REPOS",  new[] { "repo" } },
      { "MAP",    new[] { "repo", "code", "evidence", "legend" } },
      { "CODE",   new[] { "repo", "code", "evidence", "legend" } },
      { "FLOW",   new[] { "activity", "evidence" } },
      { "ISSUES", new[] { "repo", "evidence" } },
      { "TESTS",  new[] { "tests", "code", "legend" } },
      { "GIT",    new[] { "ghost", "approval" } },
      { "AGENT",  new[] { "activity", "ghost" } },
    };

    // Panels live on a dome around the user instead of one flat wall:
    //   front wall (XY plane): status above the graph, caption below it
    //   left / right walls (YZ plane): repository + legend on the left, code + evidence on the right, activity / tests behind
    //   floor (ZX plane): navigation tablet at your feet      ceiling (ZX plane): legend
    // Value = (azimuth degrees, 0 = toward the graph, + = right; elevation degrees, + = up; radius in metres).
    // Panels that are never visible together (code/ghost, evidence/approval) deliberately share a slot.
    private static readonly Dictionary<string, Vector3> Slots = new Dictionary<string, Vector3>
    {
      { "status",   new Vector3(   0f,  34f, 2.0f) },
      { "caption",  new Vector3(   0f, -30f, 1.6f) },
      { "nav",      new Vector3(   0f, -54f, 1.25f) },
      { "repo",     new Vector3( -65f,   6f, 1.9f) },
      { "code",     new Vector3(  65f,   6f, 1.9f) },
      { "ghost",    new Vector3(  65f,   6f, 1.9f) },
      { "evidence", new Vector3(  65f, -28f, 1.8f) },
      { "approval", new Vector3( 65f, -28f, 1.8f) },
      { "activity", new Vector3(-125f,   0f, 2.0f) },
      { "tests",    new Vector3( 125f,   0f, 2.0f) },
      { "legend",   new Vector3( -30f,  58f, 1.7f) },
    };

    /// <summary>Where the user's head is, in the workspace root's local space (see Recenter).</summary>
    private static Vector3 UserLocal { get { return new Vector3(0f, 0.05f, -WorkspaceDistance); } }

    private static Vector3 SlotPosition(Vector3 slot)
    {
      float az = slot.x * Mathf.Deg2Rad, el = slot.y * Mathf.Deg2Rad;
      var dir = new Vector3(Mathf.Sin(az) * Mathf.Cos(el), Mathf.Sin(el), Mathf.Cos(az) * Mathf.Cos(el));
      return UserLocal + dir * slot.z;
    }

    private JarvisSpatialPanel AddPanel(string key, string title, float w, float h, float x, float y, Color accent)
    {
      Vector3 pos = Slots.TryGetValue(key, out Vector3 slot) ? SlotPosition(slot) : new Vector3(x, y, 0f);
      JarvisSpatialPanel p = JarvisSpatialPanel.Create(_root, title, w, h, pos, accent, key != "nav" && key != "status" && key != "caption");
      _panels[key] = p;
      return p;
    }

    private void BuildPanels()
    {
      JarvisPalette pal = JarvisPalette.Current;

      JarvisSpatialPanel status = AddPanel("status", "Status", 900, 90, 0f, 0.80f, pal.Cyan);
      status.SetBodyBox(46, 36); status.Body.fontSize = 22;

      _repoPanel = AddPanel("repo", "Repositories", 440, 520, -1.12f, 0.20f, pal.Cyan);
      _repoPanel.SetBodyBox(98, 24); _repoPanel.Body.fontSize = 16;
      _repoBack = _repoPanel.AddButton("< BACK", 20, 56, 126, 38, NavigateRepoBack);
      _repoHome = _repoPanel.AddButton("ROOT", 154, 56, 100, 38, OpenRepoRoot);
      _repoPrev = _repoPanel.AddButton("< PAGE", 20, 454, 190, 48, () => ChangeRepoPage(-1));
      _repoNext = _repoPanel.AddButton("PAGE >", 230, 454, 190, 48, () => ChangeRepoPage(+1));
      _repoBack.Interactable = _repoHome.Interactable = _repoPrev.Interactable = _repoNext.Interactable = false;

      _codePanel = AddPanel("code", "Code inspector", 560, 520, 1.18f, 0.20f, pal.Cyan);
      _codePanel.SetBodyBox(60, 370); _codePanel.UseMono(17);
      _codePrev = _codePanel.AddButton("< PREVIOUS", 18, 454, 166, 48, () => ChangeEditorPage(-1));
      _codeClose = _codePanel.AddButton("CLOSE FILE", 192, 454, 166, 48, CloseOpenFile);
      _codeNext = _codePanel.AddButton("NEXT >", 366, 454, 176, 48, () => ChangeEditorPage(+1));
      _codePrev.gameObject.SetActive(false); _codeClose.gameObject.SetActive(false); _codeNext.gameObject.SetActive(false);

      JarvisSpatialPanel evidence = AddPanel("evidence", "Evidence", 560, 330, 1.18f, -0.46f, pal.Violet);
      evidence.SetBodyBox(60, 260); evidence.Body.fontSize = 22;

      JarvisSpatialPanel tests = AddPanel("tests", "Tests", 560, 330, 1.18f, -0.46f, pal.Green);
      tests.SetBodyBox(60, 260); tests.Body.fontSize = 22;

      JarvisSpatialPanel activity = AddPanel("activity", "Agent activity", 440, 250, -1.12f, -0.46f, pal.Violet);
      activity.SetBodyBox(60, 180); activity.UseMono(18);

      JarvisSpatialPanel legend = AddPanel("legend", "Legend", 440, 250, -1.12f, -0.46f, pal.Cyan);
      legend.SetBodyBox(60, 180); legend.Body.fontSize = 22;
      legend.SetBody(
        "<color=#" + Hex(pal.Cyan) + ">solid</color>  static (parser fact)\n" +
        "<color=#" + Hex(pal.Violet) + ">dashed</color>  AI-inferred\n" +
        "<color=#" + Hex(pal.Green) + ">dotted</color>  seen at runtime\n" +
        "<color=#" + Hex(pal.Amber) + ">amber</color>  change path\n" +
        "<color=#" + Hex(pal.Red) + ">red ring</color>  risk: no callers found");

      JarvisSpatialPanel ghost = AddPanel("ghost", "Ghost diff (proposed)", 560, 520, 1.18f, 0.20f, pal.Amber);
      ghost.SetBodyBox(60, 450); ghost.UseMono(20);
      ghost.SetBody("No proposed change yet. Ask JARVIS to fix something.");

      JarvisSpatialPanel approval = AddPanel("approval", "Approval", 560, 250, 1.18f, -0.46f, pal.Amber);
      approval.SetBodyBox(60, 80); approval.Body.fontSize = 22;
      approval.SetBody("Nothing is waiting for approval.");
      approval.AddButton("HOLD 2s TO APPROVE", 20, 150, 330, 80, OnApprove, 2f, pal.Green);
      approval.AddButton("REJECT", 370, 150, 170, 80, OnReject, 0f, pal.Red);

      JarvisSpatialPanel caption = AddPanel("caption", "JARVIS", 820, 190, 0.15f, -0.52f, pal.Cyan);
      caption.SetBodyBox(54, 70); caption.Body.fontSize = 26;
      _quickChange = caption.AddButton("What breaks if I change this?", 20, 128, 400, 50, () => Ask(QuickChangeQuestion()));   // label follows the selection
      caption.AddButton("Show risky paths", 430, 128, 190, 50, () => Ask("Show me the risky paths in this change."));
      caption.AddButton("Run tests", 630, 128, 170, 50, () => Ask("Run the tests for this change."));

      JarvisSpatialPanel nav = AddPanel("nav", "Navigate", 1000, 110, 0.15f, -0.80f, pal.Cyan);
      float x = 12f;
      foreach (string m in NavModes)
      {
        string mode = m;
        nav.AddButton(mode, x, 52, 100, 46, () => { foreach (JarvisSpatialPanel pp in _panels.Values) pp.Reopen(); SetMode(mode); });
        x += 108f;
      }
      nav.AddButton("CENTER", x, 52, 100, 46, Recenter);
      nav.AddButton("FX", x + 108f, 52, 100, 46, CycleIsolation);

      RefreshStatus(); RefreshRepo(); RefreshActivity();
      BuildMenu();
    }

    private void SetMode(string mode)
    {
      if (mode != _mode && _panels.ContainsKey("menu")) _panels["menu"].Show(false);
      _mode = mode;
      if (_graphRoot != null) _graphRoot.gameObject.SetActive(mode != "REPOS" && mode != "CODE");
      string[] visible = ModePanels.ContainsKey(mode) ? ModePanels[mode] : ModePanels["MAP"];
      int shown = 0;
      foreach (string key in new[] { "repo", "code", "evidence", "tests", "activity", "legend", "ghost", "approval" })
      {
        bool on = visible.Contains(key);
        // approval shares its slot with evidence and tests: while something is pending, approval wins
        if (!string.IsNullOrEmpty(_pending) && key == "approval") on = true;
        if (!string.IsNullOrEmpty(_pending) && (key == "evidence" || key == "tests")) on = false;
        _panels[key].Show(on, on ? 0.05f * shown++ : 0f);
      }
      RefreshStatus();
    }

    // =========================================================== graph

    private void LoadGraph(GraphDto g)
    {
      _graph = g;
      _agentEvidence = null; _agentTestResults = null;   // ids from another repository would not resolve
      for (int i = _graphRoot.childCount - 1; i >= 0; i--) Destroy(_graphRoot.GetChild(i).gameObject);
      _nodes.Clear(); _edges.Clear(); _clusters.Clear(); _pulses.Clear();
      BuildGraph();
      RefreshRepo();
    }

    private void BuildGraph()
    {
      JarvisPalette pal = JarvisPalette.Current;
      Dictionary<string, Vector3> layout = JarvisGraphModel.Layout(_graph);

      foreach (GraphNodeDto dto in _graph.nodes)
      {
        string cname = string.IsNullOrEmpty(dto.cluster) ? "other" : dto.cluster;
        if (!_clusters.TryGetValue(cname, out ClusterView cv)) _clusters[cname] = cv = new ClusterView { Name = cname };

        var nv = new NodeView { Dto = dto, Cluster = cv };
        var rootGo = new GameObject("Node " + dto.id);
        rootGo.transform.SetParent(_graphRoot, false);
        rootGo.transform.localPosition = layout[dto.id];
        nv.Root = rootGo.transform;

        // Choose primitive based on level (module, file, class, function, layer, external)
        PrimitiveType shape = dto.level == "module" ? PrimitiveType.Cube
          : dto.level == "file" ? PrimitiveType.Cube
          : dto.level == "class" ? PrimitiveType.Cylinder
          : dto.level == "layer" ? PrimitiveType.Capsule
          : dto.kind == "external" ? PrimitiveType.Cube
          : PrimitiveType.Sphere;

        GameObject body = GameObject.CreatePrimitive(shape);
        body.name = "Body";
        body.transform.SetParent(rootGo.transform, false);

        // Scale based on level
        float scale = dto.level == "module" ? 0.12f
          : dto.level == "file" ? 0.10f
          : dto.level == "class" ? 0.08f
          : dto.level == "layer" ? 0.14f
          : dto.kind == "external" ? 0.06f
          : 0.075f;
        body.transform.localScale = Vector3.one * scale;

        // Rotate layer nodes (ring-like)
        if (dto.level == "layer")
        {
          body.transform.localRotation = Quaternion.Euler(0f, 0f, 45f);
        }
        // Rotate external nodes (diamond-like)
        else if (dto.kind == "external")
        {
          body.transform.localRotation = Quaternion.Euler(45f, 45f, 0f);
        }

        nv.BodyT = body.transform;
        nv.Body = body.GetComponent<Renderer>();
        nv.Body.sharedMaterial = JarvisSpatialGfx.Neon(Color.white, 1.5f, true);
        JarvisSpatialGfx.Flat(nv.Body);

        // Color based on level
        nv.Base = dto.level == "module" ? pal.Amber
          : dto.level == "file" ? pal.Violet
          : dto.level == "class" ? pal.Green
          : dto.level == "layer" ? pal.Red
          : dto.kind == "external" ? pal.Gray
          : dto.kind == "test" ? pal.Violet
          : pal.Cyan;
        body.AddComponent<JarvisGraphNode>().Initialize(dto.id, Select, DragCluster, ShowNodeMenu);
        nv.Fx = rootGo.AddComponent<JarvisNodeFx>();
        nv.Fx.Begin(nv.BodyT, 0.06f * _nodes.Count, nv.Base);

        nv.Label = MakeLabel(rootGo.transform, dto.name, pal.Text, LabelSize, new Vector3(0f, -0.085f, 0f));
        cv.Members.Add(nv);
        _nodes[dto.id] = nv;
      }

      foreach (GraphEdgeDto e in _graph.edges)
      {
        if (!_nodes.TryGetValue(e.src ?? "", out NodeView a) || !_nodes.TryGetValue(e.dst ?? "", out NodeView b)) continue;
        a.Out++; b.In++;
        var ev = new EdgeView { Dto = e, From = a, To = b };
        DrawEdge(ev);
        _edges.Add(ev);
      }

      // Risk marker: a code node (not a route or test) that nothing calls.
      foreach (NodeView n in _nodes.Values)
      {
        n.NoCallers = n.In == 0 && n.Dto.kind != "route" && n.Dto.kind != "test";
        if (n.NoCallers) n.Risk = n.BodyT.gameObject.AddComponent<JarvisRiskRing>();
      }

      foreach (ClusterView cv in _clusters.Values)
      {
        var shell = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        shell.name = "ClusterShell " + cv.Name;
        Destroy(shell.GetComponent<Collider>());   // never blocks node pinch rays
        shell.transform.SetParent(_graphRoot, false);
        Renderer r = shell.GetComponent<Renderer>();
        Material shellMat = JarvisSpatialGfx.Shell(pal.Cyan, 0.03f, 0.45f, 3.5f);
        if (shellMat == null) { Destroy(shell); cv.Shell = null; }   // never leave a default silver sphere
        else { r.sharedMaterial = shellMat; JarvisSpatialGfx.Flat(r); cv.Shell = shell.transform; }
        cv.Label = MakeLabel(_graphRoot, cv.Name.ToUpperInvariant(), pal.TextMuted, LabelSize * 0.9f, Vector3.zero);
      }

      UpdateClusters();
      RefreshStyles();
      _edgesDirty = true;
    }

    // ---- edges: solid = static, dashed = inferred, dotted = runtime
    private static Texture2D _dashTex, _dotTex;
    // One shared material per edge style instead of one instance per edge: fewer materials and draw-call state changes on Quest.
    private static readonly Dictionary<string, Material> _edgeMats = new Dictionary<string, Material>();

    private static Material EdgeMaterial(string style)
    {
      if (_edgeMats.TryGetValue(style, out Material m) && m != null) return m;
      m = JarvisSpatialGfx.Line(Color.white, 1.8f);
      if (style == "dashed") { if (_dashTex == null) _dashTex = PatternTexture(10, 16); m.mainTexture = _dashTex; }
      else if (style == "dotted") { if (_dotTex == null) _dotTex = PatternTexture(4, 16); m.mainTexture = _dotTex; }
      _edgeMats[style] = m;
      return m;
    }

    private static Texture2D PatternTexture(int on, int total)
    {
      // mipmapped, bilinear, soft-edged: a hard Point-filtered 16 px pattern shimmers into white streaks on thin lines in VR
      var t = new Texture2D(total, 1, TextureFormat.RGBA32, true) { wrapMode = TextureWrapMode.Repeat, filterMode = FilterMode.Bilinear, anisoLevel = 4 };
      for (int x = 0; x < total; x++)
      {
        float d = Mathf.Abs(x + 0.5f - on / 2f);
        d = Mathf.Min(d, total - d);
        t.SetPixel(x, 0, new Color(1, 1, 1, Mathf.Clamp01((on / 2f + 0.5f - d) / 1.5f)));
      }
      t.Apply(true);
      return t;
    }

    private void DrawEdge(EdgeView ev)
    {
      var go = new GameObject("Edge " + ev.Dto.src + " > " + ev.Dto.dst);
      go.transform.SetParent(_graphRoot, false);
      LineRenderer line = go.AddComponent<LineRenderer>();
      line.useWorldSpace = false;
      line.numCapVertices = 0;
      line.numCornerVertices = 0;
      line.alignment = LineAlignment.View;
      JarvisSpatialGfx.Flat(line);
      ev.Line = line;
      
      // Add a collider for edge selection
      var collider = go.AddComponent<SphereCollider>();
      collider.radius = 0.05f;
      collider.isTrigger = true;
      
      // Add edge interaction component
      var edgeComponent = go.AddComponent<JarvisGraphEdge>();
      string edgeId = EdgeKey(ev.Dto);
      edgeComponent.Initialize(edgeId, OnEdgePinch, OnEdgeHold);
      
      StyleEdge(ev, ev.Dto.kind);
    }

    // Unique per call site: parallel calls between the same functions get
    // distinct edge ids so each can be selected independently.
    private static string EdgeKey(GraphEdgeDto d)
    {
      return d.src + "->" + d.dst + "|" + (d.callsite_id ?? "");
    }

    private void OnEdgePinch(string edgeId)
    {
      // Find the edge and select it
      foreach (var edge in _edges)
      {
        if (EdgeKey(edge.Dto) == edgeId)
        {
          SelectEdge(edge);
          break;
        }
      }
    }

    private void OnEdgeHold(string edgeId)
    {
      // Could show a context menu for the edge
      Debug.Log("Edge held: " + edgeId);
    }

    private void StyleEdge(EdgeView ev, string kind)
    {
      JarvisPalette pal = JarvisPalette.Current;
      // Resolution-aware styling (schema v3):
      //   confirmed calls        -> solid cyan
      //   possible (polymorphic) -> dashed violet
      //   ambiguous candidates   -> dotted green
      //   legacy inferred/runtime keep their old look
      string resolution = ev.Dto != null ? ev.Dto.resolution : null;
      string etype = ev.Dto != null ? ev.Dto.type : null;
      string style;
      if (etype == "may_call" || kind == "possible" || resolution == "polymorphic") style = "dashed";
      else if (kind == "ambiguous" || resolution == "ambiguous") style = "dotted";
      else style = kind == "inferred" || kind == "dashed" ? "dashed" : kind == "runtime" || kind == "dotted" ? "dotted" : "solid";
      ev.Style = style;
      ev.Base = style == "dashed" ? pal.Violet : style == "dotted" ? pal.Green : pal.Cyan;
      LineRenderer l = ev.Line;
      l.startColor = l.endColor = ev.Base;
      l.textureMode = LineTextureMode.Tile;
      l.sharedMaterial = EdgeMaterial(style);
      if (style == "dashed") { l.textureScale = new Vector2(1f / 0.035f, 1f); l.widthMultiplier = 0.007f; }
      else if (style == "dotted") { l.textureScale = new Vector2(1f / 0.020f, 1f); l.widthMultiplier = 0.007f; }
      else { l.widthMultiplier = 0.006f; }
      _edgesDirty = true;
    }

    private void RedrawEdges()
    {
      const int N = 20;
      foreach (EdgeView ev in _edges)
      {
        if (ev.Line == null) continue;
        Vector3 a = ev.From.Root.localPosition, b = ev.To.Root.localPosition;
        float d = Vector3.Distance(a, b);
        Vector3 mid = (a + b) * 0.5f + new Vector3(0f, 0.04f + 0.10f * d, -0.10f * d);   // bow toward the viewer
        ev.Line.positionCount = N + 1;
        for (int i = 0; i <= N; i++)
        {
          float t = i / (float)N, u = 1f - t;
          ev.Line.SetPosition(i, u * u * a + 2f * u * t * mid + t * t * b);
        }
      }
      _edgesDirty = false;
    }

    private void UpdateClusters()
    {
      foreach (ClusterView cv in _clusters.Values)
      {
        if (cv.Members.Count == 0 || cv.Shell == null) continue;
        Vector3 c = Vector3.zero; int cnt = 0;
        foreach (NodeView n in cv.Members) if (n.Fx.Shown) { c += n.Root.localPosition; cnt++; }
        if (cnt == 0) continue;
        c /= cnt;
        float r = 0.18f;
        foreach (NodeView n in cv.Members) if (n.Fx.Shown) r = Mathf.Max(r, Vector3.Distance(c, n.Root.localPosition) + 0.15f);
        cv.Shell.localPosition = c;
        cv.Shell.localScale = Vector3.one * (r * 2f);
        if (cv.Label != null) cv.Label.transform.localPosition = c + new Vector3(0f, r + 0.04f, 0f);
      }
    }

    private TextMesh MakeLabel(Transform parent, string text, Color color, float charSize, Vector3 localPos)
    {
      var go = new GameObject("Label");
      go.transform.SetParent(parent, false);
      go.transform.localPosition = localPos;
      var tm = go.AddComponent<TextMesh>();
      JarvisFonts.Resolve(FontRole.Auto, text, FontStyle.Normal, out Font f, out FontStyle st);
      tm.font = f; tm.fontStyle = st; tm.text = text; tm.fontSize = 48; tm.characterSize = charSize;
      tm.anchor = TextAnchor.MiddleCenter; tm.alignment = TextAlignment.Center; tm.color = color;
      go.GetComponent<MeshRenderer>().sharedMaterial = f.material;
      go.AddComponent<JarvisBillboard>();
      return tm;
    }

    // =========================================================== selection and interaction

    private void Select(string id)
    {
      if (string.IsNullOrEmpty(id) || !_nodes.ContainsKey(id)) return;
      _selected = id;
      RefreshStyles();
      RefreshEvidence();
      RefreshCode();
      Log("selected " + _nodes[id].Dto.name);
      if (_bridge != null && !_source.ContainsKey(id))
        _bridge.GetSource(id, s => { if (s != null && s.status == "ok") { _source[id] = s; if (_selected == id) RefreshCode(); } });
      RefreshQuickButtons();
    }

    private void SelectEdge(EdgeView edge)
    {
      if (edge == null) return;
      
      // Show edge information in a panel
      string edgeInfo = $"Edge: {edge.Dto.src} → {edge.Dto.dst}\n";
      edgeInfo += $"Type: {edge.Dto.type}\n";
      edgeInfo += $"Kind: {edge.Dto.kind}\n";

      if (!string.IsNullOrEmpty(edge.Dto.resolution))
        edgeInfo += $"Resolution: {edge.Dto.resolution}\n";
      if (!string.IsNullOrEmpty(edge.Dto.callsite_id))
        edgeInfo += $"Call site: {edge.Dto.callsite_id}\n";
      if (!string.IsNullOrEmpty(edge.Dto.call_type))
        edgeInfo += $"Call type: {edge.Dto.call_type}\n";
      if (edge.Dto.confidence > 0f)
        edgeInfo += $"Confidence: {edge.Dto.confidence:0.00}\n";
      if (!string.IsNullOrEmpty(edge.Dto.reason))
        edgeInfo += $"Reason: {edge.Dto.reason}\n";
      if (edge.Dto.candidates != null && edge.Dto.candidates.Length > 0)
        edgeInfo += $"Candidates: {edge.Dto.candidates.Length}\n";

      if (!string.IsNullOrEmpty(edge.Dto.file))
      {
        edgeInfo += $"File: {edge.Dto.file}\n";
      }

      if (edge.Dto.line > 0)
      {
        edgeInfo += $"Line: {edge.Dto.line}";
        if (edge.Dto.column > 0) edgeInfo += $":{edge.Dto.column}";
        edgeInfo += "\n";
      }
      
      // Highlight the edge
      edge.Line.startColor = edge.Line.endColor = JarvisPalette.Current.Amber;
      
      Log("selected edge: " + edge.Dto.src + " → " + edge.Dto.dst);
      
      // Show in code panel if available, scroll to the line
      if (_codePanel != null && !string.IsNullOrEmpty(edge.Dto.file) && edge.Dto.line > 0)
      {
        _bridge.GetSource(edge.Dto.src, s =>
        {
          if (s != null && s.status == "ok")
          {
            _source[edge.Dto.src] = s;
            _selected = edge.Dto.src;
            RefreshCode();
            Log("scrolled to line " + edge.Dto.line);
          }
        });
      }
      else if (_codePanel != null)
      {
        _codePanel.SetBody(edgeInfo);
      }
    }

    private void ExpandNode(string nodeId)
    {
      if (!_nodes.TryGetValue(nodeId, out NodeView n)) return;

      // Find all child nodes using the parent field from the graph
      var children = new List<NodeView>();
      foreach (var kvp in _nodes)
      {
        // Check if this node's parent is the expanded node
        if (kvp.Value.Dto.parent == nodeId)
        {
          children.Add(kvp.Value);
        }
      }

      // Show all children
      foreach (var child in children)
      {
        child.Root.gameObject.SetActive(true);
      }

      Log("expanded node: " + nodeId + " (" + children.Count + " children)");
    }

    private void CollapseNode(string nodeId)
    {
      if (!_nodes.TryGetValue(nodeId, out NodeView n)) return;

      // Find all child nodes using the parent field
      var children = new List<NodeView>();
      foreach (var kvp in _nodes)
      {
        if (kvp.Value.Dto.parent == nodeId)
        {
          children.Add(kvp.Value);
        }
      }

      // Hide all children
      foreach (var child in children)
      {
        child.Root.gameObject.SetActive(false);
      }

      Log("collapsed node: " + nodeId + " (" + children.Count + " children)");
    }

    private void DragCluster(string nodeId, Vector3 worldDelta)
    {
      if (!_nodes.TryGetValue(nodeId, out NodeView n)) return;
      Vector3 local = _graphRoot.InverseTransformVector(worldDelta);
      foreach (NodeView m in n.Cluster.Members) m.Root.localPosition += local;
      _edgesDirty = true;
    }

    private void ToggleVoice() { if (_voice != null) _voice.ToggleListening(); }

    private void Ask(string text)
    {
      if (_bridge == null || string.IsNullOrEmpty(text)) return;
      _progressSeen = 0;
      Say("Thinking…");
      Log("ask: " + text);
      _bridge.Ask(text, _selected, OnAnswer, err => { Say(err); Log("error: " + err); _errorUntil = Time.unscaledTime + 4f; });
    }

    private void OnAnswer(AskResponse r)
    {
      if (!string.IsNullOrEmpty(r.error))
      {
        if (r.error.Contains("took too long"))
        {
          Say("Still working. Ask again in a moment.");
          Log("timeout: " + r.error);
        }
        else
        {
          Say(r.error);
          Log("error: " + r.error);
          _errorUntil = Time.unscaledTime + 4f;
        }
        return;
      }
      ResetOverlay();
      _agentEvidence = r.evidence;
      _agentTestResults = r.test_results;
      bool graphChanged = false;
      if (r.scene_commands != null) foreach (SceneCommand c in r.scene_commands) graphChanged |= ApplyCommand(c);
      if (!string.IsNullOrEmpty(r.pending_approval)) _pending = r.pending_approval;
      string reply = r.reply ?? "";
      if (r.test_source == "cached") reply += "  (Test results are SIMULATED.)";
      Say(reply);
      Log("JARVIS answered");
      if (_voice != null) _voice.Speak(reply);
      RefreshActivity();
    }

    private void RefreshAll() { RefreshStyles(); RefreshEvidence(); RefreshCode(); RefreshGhost(); RefreshApproval(); RefreshTests(); RefreshQuickButtons(); SetMode(_mode); }

    /// <summary>The function the quick question is about: the selected node, else the most connected one in this repository.</summary>
    private string QuickTarget()
    {
      if (!string.IsNullOrEmpty(_selected) && _nodes.TryGetValue(_selected, out NodeView sel)) return sel.Dto.name;
      NodeView best = null;
      foreach (NodeView n in _nodes.Values) if (best == null || n.In + n.Out > best.In + best.Out) best = n;
      return best != null ? best.Dto.name : null;
    }

    private string QuickChangeQuestion()
    {
      string t = QuickTarget();
      return t != null ? "What breaks if I change " + t + "?" : "What does this repository do?";
    }

    private void RefreshQuickButtons()
    {
      if (_quickChange == null) return;
      string t = QuickTarget();
      if (t != null && t.Length > 13) t = t.Substring(0, 12) + "…";   // keeps the label inside the button
      _quickChange.Label.text = t != null ? "What breaks if I change " + t + "?" : "What does this repository do?";
    }

    /// <returns>true when the command changes what the graph shows.</returns>
    private bool ApplyCommand(SceneCommand c)
    {
      switch (c.type)
      {
        case "show_graph":
          if (c.nodes != null && c.edges != null)
          {
            // Rebuild the scene graph with the provided nodes and edges
            var newGraph = new GraphDto();
            if (c.nodes != null)
            {
              foreach (var node in c.nodes) newGraph.nodes.Add(node);
            }
            if (c.edges != null)
            {
              foreach (var edge in c.edges) newGraph.edges.Add(edge);
            }
            LoadGraph(newGraph);
            Log("show_graph: loaded " + newGraph.nodes.Count + " nodes, " + newGraph.edges.Count + " edges");
            return true;
          }
          return false;
        case "highlight_path":
          if (c.node_ids == null) return false;
          foreach (string id in c.node_ids) if (_nodes.ContainsKey(id)) _hot.Add(id);
          foreach (EdgeView e in _edges)
            if (_hot.Contains(e.Dto.src) && _hot.Contains(e.Dto.dst)) e.Line.startColor = e.Line.endColor = JarvisPalette.Current.Amber;
          {
            // animated traversal: a dot walks the path edge by edge, in node order
            var pulsed = new HashSet<EdgeView>();
            for (int i = 0; i + 1 < c.node_ids.Length; i++)
              foreach (EdgeView e in _edges)
                if (!pulsed.Contains(e) && ((e.Dto.src == c.node_ids[i] && e.Dto.dst == c.node_ids[i + 1]) || (e.Dto.dst == c.node_ids[i] && e.Dto.src == c.node_ids[i + 1])))
                { pulsed.Add(e); _pulses.Add(JarvisPathDot.Attach(e.Line, JarvisPalette.Current.Amber, 0.6f * i)); }
            int extra = pulsed.Count;
            foreach (EdgeView e in _edges)
              if (!pulsed.Contains(e) && _hot.Contains(e.Dto.src) && _hot.Contains(e.Dto.dst))
                _pulses.Add(JarvisPathDot.Attach(e.Line, JarvisPalette.Current.Amber, 0.6f * extra++));
          }
          JarvisAudio.Play(JarvisAudio.Cue.PathPulse);
          return true;
        case "dim_unrelated":
          _keep = new HashSet<string>(c.keep_ids ?? new string[0]);
          return true;
        case "open_code_panel":
        case "focus_camera":
          if (!string.IsNullOrEmpty(c.node_id) && _nodes.ContainsKey(c.node_id)) Select(c.node_id);
          return false;
        case "set_edge_style":
          foreach (EdgeView e in _edges)
            if ((e.Dto.src == c.src && e.Dto.dst == c.dst) || (e.Dto.src == c.dst && e.Dto.dst == c.src)) StyleEdge(e, c.style);
          return false;
        case "show_ghost_diff":
          _ghostDiff = c.diff;
          return false;
        case "show_test_badges":
          Badge(c.passed, " [ok]"); Badge(c.failed, " [x]"); Badge(c.not_run, " [-]");
          _testSummary = Summarize("PASSED", c.passed) + Summarize("FAILED", c.failed) + Summarize("NOT RUN", c.not_run);
          return false;
        case "show_approval_prompt":
          _pending = c.summary;
          return false;
        case "select_node":
          if (!string.IsNullOrEmpty(c.node_id) && _nodes.ContainsKey(c.node_id)) Select(c.node_id);
          return true;
        case "set_depth":
          // Store depth for future filtering (implementation depends on graph traversal)
          Log("set_depth: " + c.depth);
          return true;
        case "set_scope":
          // Store scope for future filtering
          Log("set_scope: " + c.scope);
          return true;
        case "set_filters":
          // Store filters for future filtering
          Log("set_filters applied");
          return true;
        case "create_group":
          if (!string.IsNullOrEmpty(c.group_id) && c.node_ids != null)
          {
            // Tint the listed nodes with a group color (implementation needed)
            Log("create_group: " + c.group_id + " with " + c.node_ids.Length + " nodes");
          }
          return true;
        case "annotate":
          if (!string.IsNullOrEmpty(c.node_id) && !string.IsNullOrEmpty(c.text))
          {
            // Show floating label at node (implementation needed)
            Log("annotate: " + c.node_id + " = " + c.text);
          }
          return false;
        case "bookmark":
          if (!string.IsNullOrEmpty(c.node_id) && !string.IsNullOrEmpty(c.label))
          {
            // Save selection and camera pose (implementation needed)
            Log("bookmark: " + c.label + " for " + c.node_id);
          }
          return false;
        case "compare":
          if (!string.IsNullOrEmpty(c.node_id1) && !string.IsNullOrEmpty(c.node_id2))
          {
            if (_nodes.ContainsKey(c.node_id1)) Select(c.node_id1);
            Log("compare: " + c.node_id1 + " vs " + c.node_id2);
          }
          return true;
        case "expand_node":
          if (!string.IsNullOrEmpty(c.node_id) && _nodes.ContainsKey(c.node_id))
          {
            ExpandNode(c.node_id);
            return true;
          }
          return false;
        case "collapse_node":
          if (!string.IsNullOrEmpty(c.node_id) && _nodes.ContainsKey(c.node_id))
          {
            CollapseNode(c.node_id);
            return true;
          }
          return false;
        default:
          Debug.LogWarning("JARVIS: unknown scene command " + c.type);
          return false;
      }
    }

    private static string Summarize(string label, string[] ids)
    {
      return ids == null || ids.Length == 0 ? "" : label + ": " + string.Join(", ", ids) + "\n";
    }

    private void Badge(string[] ids, string mark)
    {
      if (ids == null) return;
      foreach (string id in ids)
        if (_nodes.TryGetValue(id, out NodeView n)) { n.Badge = mark; n.Label.text = n.Dto.name + mark; }
    }

    private void ResetOverlay()
    {
      foreach (JarvisPathDot pd in _pulses) if (pd != null) Destroy(pd.gameObject);
      _pulses.Clear();
      _hot.Clear(); _keep = null; _ghostDiff = null; _testSummary = "No test run yet.";
      foreach (NodeView n in _nodes.Values) { n.Badge = ""; n.Label.text = n.Dto.name; }
      foreach (EdgeView e in _edges) StyleEdge(e, e.Dto.kind);
      RefreshStyles();
    }

    private void OnApprove()
    {
      if (string.IsNullOrEmpty(_pending)) { Say("Nothing is waiting for approval."); return; }
      Say("Committing to the sandbox branch…"); Log("approval: approve");
      _bridge.Approve(true,
        r => { Say(r.ok ? "Committed " + r.commit + " on " + r.branch + ". Main is untouched." : r.detail); Log(r.ok ? "committed " + r.commit : "approve failed"); },
        err => { Say(err); _errorUntil = Time.unscaledTime + 4f; });
      _pending = null; RefreshAll();
    }

    private void OnReject()
    {
      if (string.IsNullOrEmpty(_pending)) return;
      Say("Rejecting…"); Log("approval: reject");
      _bridge.Approve(false, r => Say(r.ok ? "Change rejected." : r.detail), err => Say(err));
      _pending = null; RefreshAll();
    }

    // =========================================================== text and styling

    private static string Hex(Color c) { return ColorUtility.ToHtmlStringRGB(c); }

    private void Say(string msg) { if (_panels.TryGetValue("caption", out JarvisSpatialPanel p)) p.SetBody(msg); }

    private void Log(string msg)
    {
      _log.Add(DateTime.Now.ToString("HH:mm:ss") + "  " + msg);
      while (_log.Count > 8) _log.RemoveAt(0);
      RefreshActivity();
    }



    private void RefreshStatus()
    {
      if (!_panels.ContainsKey("status")) return;
      JarvisPalette pal = JarvisPalette.Current;
      string repo = _health != null && !string.IsNullOrEmpty(_health.repo) ? _health.repo : "demo repo";
      string branch = _health != null && !string.IsNullOrEmpty(_health.branch) ? _health.branch : "-";
      int changed = _health != null ? _health.changed : 0;
      string server = _mock ? "<color=#" + Hex(JarvisSpatialFx.Magenta) + ">mock data (UI only)</color>"
        : _serverOnline ? "<color=#" + Hex(pal.Green) + ">server online</color>" : "<color=#" + Hex(pal.Amber) + ">server offline: sample graph</color>";
      _panels["status"].SetBody(repo + "  ·  " + branch + "  ·  " + changed + " changed  ·  " + server + "  ·  " + _mode);
    }

    private void FetchRepos()
    {
      if (_bridge == null) return;
      _browserError = null;
      RefreshRepoBrowser();
      _bridge.GetRepos(r =>
      {
        _repos = r;
        _browserError = null;
        RefreshRepoBrowser();
      }, error =>
      {
        _browserError = error;
        RefreshRepoBrowser();
      });
    }

    private void OpenRepo(string name)
    {
      if (string.IsNullOrEmpty(name) || _switching || _bridge == null) return;
      if (_repos != null && _repos.active == name)
      {
        _openFile = null;
        _browserRepo = name;
        SetMode("REPOS");
        LoadRepoFolder("");
        return;
      }

      _switching = true;
      Say("Opening repository " + name + "...");
      _bridge.SelectRepo(name, ok =>
      {
        _switching = false;
        if (!ok) { Say("Could not open repository " + name + ". Check the server log."); return; }
        if (_repos != null) _repos.active = name;
        _browserRepo = name;
        _browserPath = "";
        _browserPage = 0;
        _repoTree = null;
        _openFile = null;
        SetMode("REPOS");
        // Load the file tree independently: browsing must not depend on graph indexing succeeding.
        LoadRepoFolder("");
        _bridge.GetHealth(h => { _health = h; RefreshStatus(); }, e => { });
        _bridge.GetGraph(g =>
        {
          if (g != null && g.nodes != null)
          {
            LoadGraph(g);
            if (g.nodes.Count > 0) Select(g.nodes[0].id);
            Log("repository " + name + ": " + g.nodes.Count + " graph nodes");
          }
          RefreshStatus();
        });
      });
    }

    private void LoadRepoFolder(string path)
    {
      if (string.IsNullOrEmpty(_browserRepo) || _bridge == null) return;
      _browserPath = path ?? "";
      _browserPage = 0;
      _treeLoading = true;
      RefreshRepoBrowser();
      _bridge.GetTree(_browserRepo, _browserPath, tree =>
      {
        _treeLoading = false;
        _repoTree = tree;
        RefreshRepoBrowser();
      }, error =>
      {
        _treeLoading = false;
        _repoTree = null;
        Say("Could not load folder: " + error);
        RefreshRepoBrowser();
      });
    }

    private void ReturnToRepoList()
    {
      _browserRepo = null;
      _browserPath = "";
      _repoTree = null;
      _browserPage = 0;
      _treeLoading = false;
      _openFile = null;
      if (_codePrev != null)
      {
        _codePrev.gameObject.SetActive(false);
        _codeClose.gameObject.SetActive(false);
        _codeNext.gameObject.SetActive(false);
      }
      SetMode("REPOS");
      RefreshRepoBrowser();
    }

    private void OpenRepoRoot()
    {
      if (!string.IsNullOrEmpty(_browserRepo)) LoadRepoFolder("");
      else FetchRepos();
    }

    private void NavigateRepoBack()
    {
      if (string.IsNullOrEmpty(_browserRepo)) return;
      if (string.IsNullOrEmpty(_browserPath)) { ReturnToRepoList(); return; }
      string path = _browserPath.TrimEnd('/');
      int slash = path.LastIndexOf('/');
      LoadRepoFolder(slash >= 0 ? path.Substring(0, slash) : "");
    }

    private void ChangeRepoPage(int delta)
    {
      int count = _browserRepo == null
        ? (_repos != null && _repos.repos != null ? _repos.repos.Count : 0)
        : (_repoTree != null && _repoTree.entries != null ? _repoTree.entries.Count : 0);
      int pages = Mathf.Max(1, Mathf.CeilToInt(count / (float)BrowserRowsPerPage));
      _browserPage = Mathf.Clamp(_browserPage + delta, 0, pages - 1);
      RefreshRepoBrowser();
    }

    private void RefreshRepo()
    {
      RefreshRepoBrowser();
    }

    private void ClearRepoRows()
    {
      foreach (GameObject row in _repoRows) if (row != null) Destroy(row);
      _repoRows.Clear();
    }

    private void AddRepoRow(string label, int index, Action action, Color? accent = null)
    {
      float y = 126f + index * 42f;
      JarvisSpatialButton button = _repoPanel.AddButton(label, 18f, y, 404f, 38f, action, 0f, accent);
      _repoRows.Add(button.gameObject);
    }

    private void RefreshRepoBrowser()
    {
      if (_repoPanel == null) return;
      ClearRepoRows();
      bool inRepo = !string.IsNullOrEmpty(_browserRepo);
      _repoBack.Interactable = inRepo;
      if (_repoHome.Label != null) _repoHome.Label.text = inRepo ? "ROOT" : "REFRESH";
      _repoHome.Interactable = inRepo ? !string.IsNullOrEmpty(_browserPath) : true;

      var entries = new List<RepoTreeEntryDto>();
      int count;
      if (!inRepo)
      {
        _repoPanel.SetTitle("Repositories");
        if (_repos == null || _repos.repos == null)
        {
          _repoPanel.SetBody(string.IsNullOrEmpty(_browserError)
            ? "Connecting to repository server..."
            : "Server error: " + _browserError + "\nTap RELOAD to retry.");
          count = 0;
        }
        else
        {
          _repoPanel.SetBody(_repos.repos.Count + " repositories  ·  select one to browse");
          count = _repos.repos.Count;
          int start = _browserPage * BrowserRowsPerPage;
          int end = Mathf.Min(count, start + BrowserRowsPerPage);
          for (int i = start; i < end; i++)
          {
            RepoInfoDto info = _repos.repos[i];
            string repoName = info.name;
            string branch = string.IsNullOrEmpty(info.branch) ? "" : "  ·  " + info.branch;
            int fileCount = info.files;
            AddRepoRow("REPO  " + repoName + branch + "  ·  " + fileCount + " files", i - start,
              () => OpenRepo(repoName), repoName == _repos.active ? JarvisPalette.Current.Green : (Color?)null);
          }
        }
      }
      else
      {
        string suffix = string.IsNullOrEmpty(_browserPath) ? "/" : "/" + _browserPath;
        string title = _browserRepo + suffix;
        if (title.Length > 34) title = "…" + title.Substring(title.Length - 33);
        _repoPanel.SetTitle(title);
        if (_treeLoading)
        {
          _repoPanel.SetBody("Loading folder contents...");
          count = 0;
        }
        else if (_repoTree == null || _repoTree.entries == null)
        {
          _repoPanel.SetBody("No folder data. Use BACK to return to repositories.");
          count = 0;
        }
        else
        {
          _repoPanel.SetBody(_repoTree.entries.Count + " items  ·  folders first  ·  select to open");
          entries = _repoTree.entries;
          count = entries.Count;
          int start = _browserPage * BrowserRowsPerPage;
          int end = Mathf.Min(count, start + BrowserRowsPerPage);
          for (int i = start; i < end; i++)
          {
            RepoTreeEntryDto entry = entries[i];
            string path = entry.path;
            bool directory = entry.type == "directory";
            string label = directory ? "FOLDER  " + entry.name + "/" : "FILE  " + entry.name;
            Action openEntry = directory ? new Action(() => LoadRepoFolder(path)) : new Action(() => OpenRepoFile(path));
            AddRepoRow(label, i - start, openEntry,
              directory ? JarvisPalette.Current.Cyan : (Color?)null);
          }
        }
      }

      int pageCount = Mathf.Max(1, Mathf.CeilToInt(count / (float)BrowserRowsPerPage));
      _repoPrev.Interactable = _browserPage > 0;
      _repoNext.Interactable = _browserPage < pageCount - 1;
      if (_repoPrev.Label != null) _repoPrev.Label.text = "< PAGE " + Mathf.Max(1, _browserPage) + "/" + pageCount;
      if (_repoNext.Label != null) _repoNext.Label.text = "PAGE " + Mathf.Min(pageCount, _browserPage + 2) + "/" + pageCount + " >";
    }

    private void OpenRepoFile(string path)
    {
      if (string.IsNullOrEmpty(_browserRepo) || _bridge == null) return;
      Say("Opening " + path + "...");
      _bridge.GetFile(_browserRepo, path, file =>
      {
        if (file == null || file.status != "ok") { Say("Could not open " + path + "."); return; }
        _openFile = file;
        _openFilePage = 0;
        SetMode("CODE");
        RefreshOpenFile();
        Log("opened " + path);
      }, error => Say("Could not open file: " + error));
    }

    private void ChangeEditorPage(int delta)
    {
      if (_openFile == null) return;
      string[] lines = (_openFile.content ?? "").Split('\n');
      int pages = Mathf.Max(1, Mathf.CeilToInt(lines.Length / (float)EditorLinesPerPage));
      _openFilePage = Mathf.Clamp(_openFilePage + delta, 0, pages - 1);
      RefreshOpenFile();
    }

    private static string EscapeRichText(string value)
    {
      return (value ?? "").Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;");
    }

    private void RefreshOpenFile()
    {
      if (_codePanel == null || _openFile == null) return;
      _codePanel.SetTitle(_openFile.path);
      string[] lines = (_openFile.content ?? "").Split('\n');
      int pages = Mathf.Max(1, Mathf.CeilToInt(lines.Length / (float)EditorLinesPerPage));
      int first = _openFilePage * EditorLinesPerPage;
      int last = Mathf.Min(lines.Length, first + EditorLinesPerPage);
      var sb = new StringBuilder();
      sb.Append("<color=#").Append(Hex(JarvisPalette.Current.TextMuted)).Append(">READ-ONLY VIEW  ·  ")
        .Append(lines.Length).Append(" lines  ·  page ").Append(_openFilePage + 1).Append('/').Append(pages).Append("</color>\n\n");
      for (int i = first; i < last; i++)
      {
        sb.Append("<color=#").Append(Hex(JarvisPalette.Current.TextMuted)).Append('>')
          .Append(i + 1).Append("</color>  ").Append(EscapeRichText(lines[i].TrimEnd('\r'))).Append('\n');
      }
      if (_openFile.truncated) sb.Append("\n<color=#").Append(Hex(JarvisPalette.Current.Amber)).Append(">File truncated at 512 KB.</color>");
      _codePanel.SetBody(sb.ToString());
      _codePrev.gameObject.SetActive(true); _codeClose.gameObject.SetActive(true); _codeNext.gameObject.SetActive(true);
      _codePrev.Interactable = _openFilePage > 0;
      _codeNext.Interactable = _openFilePage < pages - 1;
    }

    private void CloseOpenFile()
    {
      _openFile = null;
      _codePrev.gameObject.SetActive(false); _codeClose.gameObject.SetActive(false); _codeNext.gameObject.SetActive(false);
      RefreshCode();
    }

    private void RefreshActivity() { if (_panels.ContainsKey("activity")) _panels["activity"].SetBody(string.Join("\n", _log)); }

    private void RefreshEvidence()
    {
      if (!_panels.ContainsKey("evidence")) return;
      NodeView n = null;
      if (!string.IsNullOrEmpty(_selected)) _nodes.TryGetValue(_selected, out n);
      bool haveAgent = _agentEvidence != null && _agentEvidence.Length > 0;
      if (n == null && !haveAgent) return;
      JarvisPalette pal = JarvisPalette.Current;
      var sb = new StringBuilder();
      if (n != null)
      {
        sb.Append("<b>").Append(n.Dto.name).Append("</b>  ").Append(n.Dto.kind).Append(" · ").Append(n.Dto.cluster).Append('\n');
        sb.Append(n.Dto.file).Append("  L").Append(n.Dto.start).Append("-").Append(n.Dto.end).Append('\n');
        sb.Append("<color=#").Append(Hex(pal.Cyan)).Append(">[static]</color> ").Append(n.In).Append(" callers, ").Append(n.Out).Append(" callees\n");
        int inferred = _edges.Count(e => (e.From == n || e.To == n) && e.Style == "dashed");
        int runtime = _edges.Count(e => (e.From == n || e.To == n) && e.Style == "dotted");
        if (inferred > 0) sb.Append("<color=#").Append(Hex(pal.Violet)).Append(">[inferred]</color> ").Append(inferred).Append(" links\n");
        if (runtime > 0) sb.Append("<color=#").Append(Hex(pal.Green)).Append(">[runtime]</color> ").Append(runtime).Append(" links\n");
        if (n.NoCallers) sb.Append("<color=#").Append(Hex(pal.Red)).Append(">[risk]</color> no callers found: may be dead code or called dynamically\n");
        if (_hot.Contains(n.Dto.id)) sb.Append("<color=#").Append(Hex(pal.Amber)).Append(">[change path]</color> on the highlighted path\n");
      }
      if (haveAgent) AppendAgentEvidence(sb, pal);
      _panels["evidence"].SetBody(sb.ToString());
    }

    /// <summary>What the agents actually looked at while answering (the evidence list returned by /ask), newest first.</summary>
    private void AppendAgentEvidence(StringBuilder sb, JarvisPalette pal)
    {
      if (sb.Length > 0) sb.Append('\n');
      sb.Append("<color=#").Append(Hex(pal.Violet)).Append("><b>Agents examined</b></color>  ").Append(_agentEvidence.Length).Append(" items\n");
      int shown = 0;
      for (int i = _agentEvidence.Length - 1; i >= 0 && shown < 5; i--, shown++)
      {
        string id = _agentEvidence[i];
        string line = _nodes.TryGetValue(id, out NodeView ev) ? ev.Dto.name + "  " + ev.Dto.file + ":" + ev.Dto.start : id;
        if (line.Length > 46) line = line.Substring(0, 45) + "…";
        sb.Append("• ").Append(line).Append('\n');
      }
      if (_agentEvidence.Length > shown) sb.Append("… ").Append(_agentEvidence.Length - shown).Append(" more\n");
    }

    private void RefreshCode()
    {
      if (_openFile != null) { RefreshOpenFile(); return; }
      if (_codePrev != null) { _codePrev.gameObject.SetActive(false); _codeClose.gameObject.SetActive(false); _codeNext.gameObject.SetActive(false); }
      if (!_panels.ContainsKey("code") || string.IsNullOrEmpty(_selected) || !_nodes.TryGetValue(_selected, out NodeView n)) return;
      JarvisPalette pal = JarvisPalette.Current;
      if (!_source.TryGetValue(_selected, out SourceResponse s))
      {
        _panels["code"].SetTitle("Code inspector");
        _panels["code"].SetBody(n.Dto.file + "  L" + n.Dto.start + "-" + n.Dto.end + "\n\n" + (_serverOnline ? "loading source…" : "Start the JARVIS server to see live source."));
        return;
      }
      _panels["code"].SetTitle(s.file);
      string[] lines = (s.source ?? "").Split('\n');
      var sb = new StringBuilder();
      for (int i = 0; i < lines.Length && i < MaxCodeLines; i++)
        sb.Append("<color=#").Append(Hex(pal.TextMuted)).Append('>').Append(s.first_line + i).Append("</color>  ").Append(lines[i].TrimEnd('\r')).Append('\n');
      if (lines.Length > MaxCodeLines) sb.Append("… ").Append(lines.Length - MaxCodeLines).Append(" more lines");
      _panels["code"].SetBody(sb.ToString());
    }

    private void RefreshGhost()
    {
      if (!_panels.ContainsKey("ghost")) return;
      JarvisPalette pal = JarvisPalette.Current;
      if (string.IsNullOrEmpty(_ghostDiff)) { _panels["ghost"].SetBody("No proposed change yet. Ask JARVIS to fix something."); return; }
      var sb = new StringBuilder();
      string[] lines = _ghostDiff.Split('\n');
      for (int i = 0; i < lines.Length && i < MaxCodeLines + 2; i++)
      {
        string l = lines[i].TrimEnd('\r');
        Color c = l.StartsWith("+") ? pal.Green : l.StartsWith("-") ? pal.Red : pal.TextMuted;
        sb.Append("<color=#").Append(Hex(c)).Append('>').Append(l).Append("</color>\n");
      }
      _panels["ghost"].SetBody(sb.ToString());
    }

    private void RefreshApproval()
    {
      if (!_panels.ContainsKey("approval")) return;
      _panels["approval"].SetBody(string.IsNullOrEmpty(_pending) ? "Nothing is waiting for approval." : _pending);
    }

    private void RefreshTests()
    {
      if (!_panels.ContainsKey("tests")) return;
      string extra = "";
      if (!string.IsNullOrWhiteSpace(_agentTestResults))       // the test run text the agents returned with the answer
      {
        string t = _agentTestResults.Trim().Replace("\r", "");
        if (t.Length > 420) t = t.Substring(0, 419) + "…";
        extra = "\n\n<b>Test run</b>\n" + t;
      }
      _panels["tests"].SetBody(_testSummary + extra);
    }

    private void RefreshStyles()
    {
      JarvisPalette pal = JarvisPalette.Current;
      foreach (NodeView n in _nodes.Values)
      {
        Color c = n.Base;
        if (_hot.Contains(n.Dto.id)) c = pal.Amber;
        else if (_keep != null && !_keep.Contains(n.Dto.id)) c = new Color(0.2f, 0.26f, 0.34f, 1f);
        n.Body.sharedMaterial.color = c;
        bool sel = n.Dto.id == _selected;
        n.Fx.Selected = sel;
        if (n.Body.sharedMaterial.HasProperty("_Intensity")) n.Body.sharedMaterial.SetFloat("_Intensity", sel ? 2.4f : 1.5f);
        n.Label.color = _keep != null && !_keep.Contains(n.Dto.id) ? pal.TextMuted : pal.Text;
      }
    }

    // =========================================================== node context menu and clusters

    private void BuildMenu()
    {
      _menu = AddPanel("menu", "Node", 380, 290, 0f, 0f, JarvisSpatialFx.Magenta);
      _menu.SetBodyBox(54, 40); _menu.Body.fontSize = 20;
      _menu.AddButton("ASK ABOUT THIS", 20, 100, 340, 50, () =>
      {
        if (_nodes.TryGetValue(_menuNode ?? "", out NodeView n)) Ask("What breaks if I change " + n.Dto.name + "?");
        _menu.Show(false);
      });
      _menu.AddButton("HIGHLIGHT CALLERS", 20, 160, 340, 50, () => HighlightCallers(_menuNode));
      _menu.AddButton("COLLAPSE / EXPAND CLUSTER", 20, 220, 340, 50, ToggleCluster);
      _menu.Show(false);
    }

    /// <summary>Long pinch on a node (JarvisGraphNode.Hold).</summary>
    private void ShowNodeMenu(string id)
    {
      if (_menu == null || !_nodes.TryGetValue(id, out NodeView n)) return;
      _menuNode = id;
      Select(id);
      _menu.SetTitle(n.Dto.name);
      _menu.SetBody(n.Cluster.Name + " · " + n.Dto.kind);
      Vector3 toCam = (_cam.transform.position - n.Root.position).normalized;
      _menu.transform.position = n.Root.position + Vector3.up * 0.22f + toCam * 0.12f;
      _menu.Reopen();
      _menu.Show(true);
    }

    private void HighlightCallers(string id)
    {
      if (string.IsNullOrEmpty(id) || !_nodes.TryGetValue(id, out NodeView n)) return;
      ResetOverlay();
      _hot.Add(id);
      Color amber = JarvisPalette.Current.Amber;
      foreach (EdgeView e in _edges)
        if (e.To == n)
        {
          _hot.Add(e.From.Dto.id);
          e.Line.startColor = e.Line.endColor = amber;
          _pulses.Add(JarvisPathDot.Attach(e.Line, amber, 0f));
        }
      JarvisAudio.Play(JarvisAudio.Cue.PathPulse);
      RefreshAll();
      _menu.Show(false);
    }

    private void ToggleCluster()
    {
      if (!_nodes.TryGetValue(_menuNode ?? "", out NodeView n)) return;
      ClusterView cv = n.Cluster;
      
      if (cv.Collapsed)
      {
        // Expanding: fetch children from server
        string clusterId = cv.Name;
        if (_bridge != null && !_mock)
        {
          _bridge.GetGraphWithFocus(clusterId, 2, g =>
          {
            if (g != null && g.nodes != null)
            {
              // Add new nodes to the graph
              foreach (var node in g.nodes)
              {
                if (!_nodes.ContainsKey(node.id))
                {
                  // This would require rebuilding the graph, for now just log
                  Debug.Log("Would add node: " + node.id);
                }
              }
            }
          }, e => Debug.LogWarning("Failed to fetch cluster children: " + e));
        }
      }
      
      cv.Collapsed = !cv.Collapsed;
      for (int i = 1; i < cv.Members.Count; i++)   // member 0 stays as the cluster anchor
      {
        cv.Members[i].Fx.SetShown(!cv.Collapsed);
        cv.Members[i].Label.gameObject.SetActive(!cv.Collapsed);
      }
      RefreshEdgeVisibility();
      _menu.Show(false);
    }

    private void RefreshEdgeVisibility()
    {
      foreach (EdgeView e in _edges)
        if (e.Line != null) e.Line.gameObject.SetActive(e.From.Fx.Shown && e.To.Fx.Shown);
      _edgesDirty = true;
    }

    // =========================================================== render isolation (FX button)
    // Press FX in the nav bar to step through: ALL, then hide one renderer group at a time. When the white streaks or silver
    // shapes disappear at some step, that group is the offender.

    private static readonly string[] IsoNames = { "ALL", "no edges", "no shells", "no halos+rings", "no labels", "no floor+dust", "no orb fx", "nodes only" };
    private static readonly string[] IsoKeys = { "", "edges", "shells", "halos", "labels", "floor", "orbfx", "" };
    private int _iso;

    private static string RenderGroup(Renderer r)
    {
      string n = r.gameObject.name;
      if (r is LineRenderer && n.StartsWith("Edge ")) return "edges";
      if (n.StartsWith("ClusterShell")) return "shells";
      if (n == "NodeHalo" || n == "SelectionRing" || n == "Halo") return "halos";
      if (n == "Label") return "labels";
      if (n == "JARVIS Floor Grid" || n == "JARVIS Dust") return "floor";
      if (n.StartsWith("OrbRing") || n == "OrbSat") return "orbfx";
      if (n == "Body") return "node";
      return null;
    }

    private void CycleIsolation()
    {
      _iso = (_iso + 1) % IsoNames.Length;
      foreach (Renderer r in _root.GetComponentsInChildren<Renderer>(true))
      {
        string g = RenderGroup(r);
        if (g == null) continue;
        bool on = _iso == 0 || (_iso == 7 ? g == "node" : g != IsoKeys[_iso]);
        if (g == "node") on = true;
        r.gameObject.SetActive(on);
      }
      RefreshEdgeVisibility();
      Say("Render isolation: " + IsoNames[_iso]);
      Log("iso: " + IsoNames[_iso]);
    }

    // =========================================================== orb

    private void BuildOrb()
    {
      JarvisPalette pal = JarvisPalette.Current;
      var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);   // replace with your orb prefab; keep the collider
      go.name = "JARVIS Orb";
      go.transform.SetParent(_root, false);
      go.transform.localPosition = new Vector3(-0.58f, -0.52f, 0f);
      go.transform.localScale = Vector3.one * 0.13f;
      _orb = go.transform;
      _orbMat = JarvisSpatialGfx.Neon(pal.Cyan, 2f, true);
      go.GetComponent<Renderer>().sharedMaterial = _orbMat;
      JarvisSpatialGfx.Flat(go.GetComponent<Renderer>());
      go.AddComponent<JarvisSpatialButton>().OnClick = ToggleVoice;   // pinch the orb to talk

      var halo = GameObject.CreatePrimitive(PrimitiveType.Sphere);
      halo.name = "Halo";
      Destroy(halo.GetComponent<Collider>());
      halo.transform.SetParent(go.transform, false);
      halo.transform.localScale = Vector3.one * 1.6f;
      Material haloMat = JarvisSpatialGfx.Shell(pal.Cyan, 0.05f, 0.6f, 3f);
      if (haloMat != null) { halo.GetComponent<Renderer>().sharedMaterial = haloMat; JarvisSpatialGfx.Flat(halo.GetComponent<Renderer>()); }
      else Destroy(halo);
      _halo = haloMat != null ? halo.transform : null;
      _orbFx = go.AddComponent<JarvisOrbFx>();
      _orbFx.Build(pal.Cyan);
    }

    private OrbState CurrentOrb()
    {
      if (Time.unscaledTime < _errorUntil) return OrbState.Error;
      if (!string.IsNullOrEmpty(_pending)) return OrbState.Approval;
      if (_voice != null && _voice.Current == JarvisVoice.State.Listening) return OrbState.Listening;
      if (_voice != null && _voice.Current == JarvisVoice.State.Speaking) return OrbState.Speaking;
      if (_bridge != null && _bridge.Busy) return OrbState.Thinking;
      return OrbState.Idle;
    }

    private void AnimateOrb()
    {
      if (_orb == null) return;
      JarvisPalette pal = JarvisPalette.Current;
      OrbState s = CurrentOrb();
      float t = Time.unscaledTime;
      Color c = pal.Cyan; float pulse = 1f + 0.04f * Mathf.Sin(t * 1.5f);
      switch (s)
      {
        case OrbState.Listening: c = pal.Cyan; pulse = 1f + 0.25f * (_voice != null ? _voice.Level : 0f) + 0.05f * Mathf.Sin(t * 8f); break;
        case OrbState.Thinking: c = JarvisSpatialFx.Magenta; pulse = 1f + 0.08f * Mathf.Sin(t * 5f); _orb.Rotate(0f, 120f * Time.unscaledDeltaTime, 0f); break;
        case OrbState.Speaking: c = pal.Green; pulse = 1f + 0.10f * Mathf.Sin(t * 12f); break;
        case OrbState.Approval: c = pal.Amber; pulse = 1f + 0.10f * Mathf.Sin(t * 3f); break;
        case OrbState.Error: c = pal.Red; pulse = 1f + 0.12f * Mathf.Sin(t * 14f); break;
      }
      float energy = s == OrbState.Listening ? (_voice != null ? _voice.Level : 0f)
                   : s == OrbState.Speaking ? 0.5f + 0.3f * Mathf.Sin(t * 9f)
                   : s == OrbState.Thinking ? 0.8f : 0.1f;
      _orbFx.Energy = Mathf.Lerp(_orbFx.Energy, energy, 0.2f);
      _orbFx.Tint = c;
      _orb.localScale = Vector3.one * 0.13f * pulse;
      _orbMat.color = c;
      if (_halo != null)
      {
        Renderer hr = _halo.GetComponent<Renderer>();
        if (hr.sharedMaterial != null && hr.sharedMaterial.HasProperty("_Color")) hr.sharedMaterial.SetColor("_Color", c);
      }
    }

    // =========================================================== loop

    private void Update()
    {
      AnimateOrb();
      if (_edgesDirty) { RedrawEdges(); UpdateClusters(); }
      if (CurrentOrb() == OrbState.Thinking && Time.unscaledTime > _progressAt)
      {
        _progressAt = Time.unscaledTime + 1f;
        _bridge.GetProgress(_progressSeen, p => { foreach (var s in p.steps) { Log(s.agent + " working"); _progressSeen = s.i + 1; } });
      }
    }
  }
}
