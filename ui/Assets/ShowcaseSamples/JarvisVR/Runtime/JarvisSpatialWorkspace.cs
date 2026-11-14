using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;

namespace JarvisVR
{
  /// <summary>
  /// Spatial JARVIS workspace: a 3D code graph in the middle and independent floating panels around it.
  /// Talks to the real JARVIS server through JarvisBridge.
  /// </summary>
  public sealed class JarvisSpatialWorkspace : MonoBehaviour
  {

    private const float WorkspaceDistance = 1.5f;   // metres in front of the user
    private const float LabelSize = 0.010f;         // TextMesh characterSize; raise for bigger node labels
    private const int MaxCodeLines = 17;

    private enum OrbState { Idle, Listening, Thinking, Speaking, Approval, Error }

    private sealed class NodeView
    {
      public GraphNodeDto Dto; public Transform Root, BodyT; public Renderer Body; public TextMesh Label;
      public Color Base; public string Badge = "";
      public ClusterView Cluster; public int In, Out; public JarvisNodeFx Fx;
    }
    private sealed class EdgeView { public GraphEdgeDto Dto; public NodeView From, To; public LineRenderer Line; public Color Base; public string Style; }
    private sealed class ClusterView { public string Name; public readonly List<NodeView> Members = new List<NodeView>(); public Transform Shell; public TextMesh Label; public bool Collapsed; }

    // ---- scene ----
    private Camera _cam;
    private Transform _root, _graphRoot;
    private IJarvisBackend _bridge;
    private JarvisVoice _voice;
    private readonly Dictionary<string, JarvisSpatialPanel> _panels = new Dictionary<string, JarvisSpatialPanel>();
    private readonly Dictionary<string, JarvisSpatialButton> _navButtons = new Dictionary<string, JarvisSpatialButton>();
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
    private JarvisSpatialPanel _repoPanel, _codePanel, _impactPanel;
    private JarvisSpatialButton _repoBack, _repoHome, _repoPrev, _repoNext;
    private JarvisSpatialButton _codePrev, _codeClose, _codeNext;
    private readonly List<GameObject> _repoRows = new List<GameObject>();
    private string _browserRepo, _browserPath = "";
    private int _browserPage, _openFilePage, _pendingOpenLine;
    private bool _treeLoading, _switching;
    private string _browserError;
    private const int BrowserRowsPerPage = 7;
    private const int EditorLinesPerPage = 18;
    private bool _serverOnline;
    private string _selected, _mode = "MAP", _pending, _ghostDiff, _testSummary = "No test run yet.";
    private int _ghostPage;
    private bool _ghostSeenAll;
    private const int GhostLinesPerPage = 14;   // 14 diff lines + 1 header line fit the panel
    private bool _approving;
    private string _lastCommitBranch;
    private JarvisSpatialButton _approveBtn, _rejectBtn, _promoteBtn;
    private bool _hasTestRun, _testFailed;
    private string[] _testFailureLines;
    private TaskDto[] _tasks;
    private string[] _unverifiedEvidence;
    private string _agentMode;
    private readonly HashSet<string> _agentShown = new HashSet<string>();
    private readonly List<string> _log = new List<string>();
    private float _errorUntil;
    private int _progressSeen;
    private float _progressAt;
    private float _taskAt;
    private Transform _orb, _halo;
    private Material _orbMat;
    private TouchScreenKeyboard _kb;
    private JarvisOrbFx _orbFx;
    private readonly List<JarvisPathDot> _pulses = new List<JarvisPathDot>();
    private JarvisSpatialPanel _menu;
    private string _menuNode;
    private JarvisSpatialButton _menuAddComp, _menuRename, _menuResp, _menuDelete, _menuLink, _menuDelEdge, _menuCycleKind;
    private JarvisSpatialPanel _designReqPanel, _designCmpPanel, _designActPanel;
    private DesignStateDto _design;
    private readonly Dictionary<string, string> _compareStatus = new Dictionary<string, string>();
    private string _designLinkFrom, _menuEdgeKey;
    private bool _designDeleteArmed, _designRequested;
    private string _kbOp, _kbOpId;
    private int _taskSel, _questionSel = -1;
    private string[] _planCircular;
    private readonly HashSet<string> _cycleAccepted = new HashSet<string>();   // tasks whose circular dep the user explicitly accepted
    private readonly Dictionary<string, string> _cycleReasons = new Dictionary<string, string>();
    private string _cycleStatus, _cycleEvidence;
    private string _lastTaskError;
    private string _designWarning;   // server's fallback warning from /design/propose
    private TestRunDto _lastTestRun;
    private JarvisSpatialButton _qPrevBtn, _qNextBtn, _qSecBtn, _qResolveBtn, _qEditBtn, _qDeferBtn, _qReopenBtn;
    private JarvisSpatialButton _cmpAmbPrev, _cmpAmbNext, _cmpCandPrev, _cmpCandNext, _cmpAssignBtn;
    private readonly Dictionary<string, string> _compareOverrides = new Dictionary<string, string>();   // component_id -> node_id, resent with every compare
    private int _cmpAmbSel = -1, _cmpCandSel;
    private int _qSection;   // 0 = open, 1 = deferred, 2 = resolved
    private static readonly string[] QuestionSections = { "OPEN", "DEFERRED", "RESOLVED" };
    private JarvisSpatialButton _taskPrevBtn, _taskNextBtn, _taskStartBtn, _taskDoneBtn, _taskWorkBtn;

    // ---- conversation history, symbol outline, graph filters, settings ----
    private readonly List<string> _chat = new List<string>();   // "Y|text" = developer, "J|text" = JARVIS (active session only)
    private int _chatOffset, _chatShown;
    private const int ChatMaxEntries = 60;
    private int _outlineSel;
    private int _kindFilter;                 // index into KindFilters; 0 = ALL
    private string _edgeFilter;              // null = every relationship type
    private JarvisSpatialButton _kindFilterBtn, _edgeFilterBtn, _voiceBtn, _quitBtn, _menuEditLabel;
    private JarvisSpatialPanel _settingsPanel;
    private bool _voiceEnabled = true, _quitArmed;
    private ValidatedDto _validated;         // which change the last test/review run was about
    private const float RotateStepDegrees = 30f;

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

      _bridge = gameObject.AddComponent<JarvisBridge>();
      _voice = gameObject.AddComponent<JarvisVoice>();
      _voice.Transcript += Ask;
      _voice.Notice += m => Say(m);
      _voice.Transcriber = _bridge.Transcribe;   // speech to text on the server, no Meta Voice SDK needed

      BuildPanels();
      BuildOrb();
      JarvisAtmosphere.BuildFloor(_root, JarvisPalette.Current.Cyan);
      JarvisAtmosphere.BuildDust(_root, JarvisSpatialFx.Magenta, JarvisPalette.Current.Cyan);
      LoadGraph(new GraphDto());
      SetMode("REPOS");                 // begin with the repository picker, like an IDE start screen

      gameObject.AddComponent<JarvisSpatialInput>().Initialize(_cam, _graphRoot, ToggleVoice);
      Say("Hi. Pinch the orb to talk, or tap a quick question.");
      Log("workspace ready");

      _bridge.GetHealth(h => { _health = h; _serverOnline = h != null && h.ok; RefreshStatus(); }, e => { _serverOnline = false; RefreshStatus(); });
      FetchRepos();
      _bridge.GetGraph(g =>
      {
        if (g == null || g.nodes == null || g.nodes.Count == 0) return;
        _serverOnline = true;
        LoadGraph(g);
        Log("graph from server: " + g.nodes.Count + " nodes");
        // Select the first non-module node from the server graph
        var first = g.nodes.FirstOrDefault(n => n.kind != "module" && n.kind != "file");
        if (first != null) Select(first.id);
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

    private static readonly string[] NavModes = { "MAP", "CODE", "FLOW", "TESTS", "IMPACT", "AGENT", "DESIGN" };
    private static readonly Dictionary<string, string[]> ModePanels = new Dictionary<string, string[]>
    {
      { "REPOS",  new[] { "repo" } },
      { "MAP",    new[] { "repo", "evidence", "legend", "chat" } },
      { "CODE",   new[] { "repo", "code", "outline", "evidence", "legend" } },
      { "FLOW",   new[] { "activity", "evidence" } },
      { "TESTS",  new[] { "tests", "code", "legend" } },
      { "IMPACT", new[] { "repo", "impact", "evidence", "legend", "chat" } },
      { "AGENT",  new[] { "activity", "ghost", "chat" } },
      { "DESIGN", new[] { "design_req", "design_cmp", "design_act", "activity", "legend", "chat" } },
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
      { "impact",   new Vector3(  65f, -28f, 1.8f) },
      { "design_req", new Vector3(-65f,   6f, 1.9f) },
      { "design_cmp", new Vector3( 65f,   6f, 1.9f) },
      { "design_act", new Vector3( 65f, -28f, 1.8f) },
      { "chat",     new Vector3( -65f, -28f, 1.8f) },
      { "outline",  new Vector3( -65f, -28f, 1.8f) },
      { "tools",    new Vector3(   0f, -42f, 1.45f) },
      { "settings", new Vector3(  45f, -40f, 1.4f) },
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
      JarvisSpatialPanel p = JarvisSpatialPanel.Create(_root, title, w, h, pos, accent, key != "nav" && key != "status" && key != "caption" && key != "tools");
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
      _codePanel.Body.horizontalOverflow = HorizontalWrapMode.Overflow;
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
        "<color=#" + Hex(pal.Green) + ">dotted</color>  ambiguous\n" +
        "<color=#" + Hex(pal.Amber) + ">amber</color>  change path");

      JarvisSpatialPanel ghost = AddPanel("ghost", "Ghost diff (proposed)", 560, 520, 1.18f, 0.20f, pal.Amber);
      ghost.SetBodyBox(60, 380); ghost.UseMono(20);
      ghost.AddButton("< PREV", 20, 450, 160, 56, () => { _ghostPage--; RefreshGhost(); }, 0f, pal.Amber);
      ghost.AddButton("NEXT >", 380, 450, 160, 56, () => { _ghostPage++; RefreshGhost(); }, 0f, pal.Amber);
      ghost.SetBody("No proposed change yet. Ask JARVIS to fix something.");

      JarvisSpatialPanel approval = AddPanel("approval", "Approval", 560, 320, 1.18f, -0.46f, pal.Amber);
      approval.SetBodyBox(60, 80); approval.Body.fontSize = 22;
      approval.SetBody("Nothing is waiting for approval.");
      _approveBtn = approval.AddButton("HOLD 2s TO APPROVE", 20, 150, 330, 80, OnApprove, 2f, pal.Green);
      _rejectBtn = approval.AddButton("REJECT", 370, 150, 170, 80, OnReject, 0f, pal.Red);
      _promoteBtn = approval.AddButton("PROMOTE TO MAIN", 20, 235, 520, 70, OnPromote, 0f, pal.Violet);

      // Impact panel for change impact visualization
      _impactPanel = AddPanel("impact", "Change Impact", 560, 400, 1.18f, -0.46f, pal.Violet);
      _impactPanel.SetBodyBox(60, 340); _impactPanel.Body.fontSize = 20;
      _impactPanel.SetBody("No impact analysis yet. Select a function and ask about change impact.");

      _designReqPanel = AddPanel("design_req", "Requirements", 440, 520, -1.12f, 0.20f, pal.Violet);
      _designReqPanel.SetBodyBox(56, 350); _designReqPanel.Body.fontSize = 17;
      _qPrevBtn = _designReqPanel.AddButton("Q <", 14, 414, 64, 40, () => CycleQuestion(-1), 0f, pal.Violet);
      _qNextBtn = _designReqPanel.AddButton("Q >", 82, 414, 64, 40, () => CycleQuestion(+1), 0f, pal.Violet);
      _qSecBtn = _designReqPanel.AddButton("SEC: OPEN", 150, 414, 140, 40, CycleQuestionSection, 0f, pal.Violet);
      _qResolveBtn = _designReqPanel.AddButton("RESOLVE", 14, 462, 100, 44, ResolveQuestion, 0f, pal.Green);
      _qEditBtn = _designReqPanel.AddButton("EDIT Q", 118, 462, 100, 44, EditQuestion, 0f, pal.Amber);
      _qDeferBtn = _designReqPanel.AddButton("DEFER", 222, 462, 96, 44, DeferQuestion, 0f, pal.Amber);
      _qReopenBtn = _designReqPanel.AddButton("REOPEN", 322, 462, 96, 44, ReopenQuestion, 0f, pal.Cyan);

      _designCmpPanel = AddPanel("design_cmp", "Component", 560, 330, 1.18f, 0.20f, pal.Violet);
      _designCmpPanel.SetBodyBox(44, 232); _designCmpPanel.Body.fontSize = 16;
      _cmpAmbPrev = _designCmpPanel.AddButton("AMB <", 14, 283, 80, 40, () => CycleAmbiguous(-1), 0f, pal.Violet);
      _cmpAmbNext = _designCmpPanel.AddButton("AMB >", 100, 283, 80, 40, () => CycleAmbiguous(+1), 0f, pal.Violet);
      _cmpCandPrev = _designCmpPanel.AddButton("CAND <", 186, 283, 90, 40, () => CycleCandidate(-1), 0f, pal.Cyan);
      _cmpCandNext = _designCmpPanel.AddButton("CAND >", 282, 283, 90, 40, () => CycleCandidate(+1), 0f, pal.Cyan);
      _cmpAssignBtn = _designCmpPanel.AddButton("ASSIGN", 380, 283, 166, 40, AssignAmbiguousMatch, 0f, pal.Green);

      _designActPanel = AddPanel("design_act", "Architecture", 560, 330, 1.18f, -0.46f, pal.Cyan);
      _designActPanel.SetBodyBox(60, 120); _designActPanel.Body.fontSize = 20;
      _designActPanel.AddButton("COMPARE", 20, 132, 160, 50, DesignCompare);
      _designActPanel.AddButton("APPROVE", 190, 132, 160, 50, () => DesignApprove(true));
      _designActPanel.AddButton("GENERATE PLAN", 360, 132, 180, 50, DesignPlanGenerate);
      _taskPrevBtn = _designActPanel.AddButton("TASK <", 20, 192, 100, 50, () => CycleTask(-1), 0f, pal.Cyan);
      _taskNextBtn = _designActPanel.AddButton("TASK >", 126, 192, 100, 50, () => CycleTask(+1), 0f, pal.Cyan);
      _taskStartBtn = _designActPanel.AddButton("START", 232, 192, 100, 50, () => TaskSetStatus("running"), 0f, pal.Green);
      _taskDoneBtn = _designActPanel.AddButton("DONE", 338, 192, 100, 50, () => TaskSetStatus("done"), 0f, pal.Green);
      _taskWorkBtn = _designActPanel.AddButton("WORK ON IT", 444, 192, 116, 50, WorkOnTask, 0f, pal.Amber);
      // Rejecting sends the architecture back to draft and discards the plan generated from it (server clears it too).
      _designActPanel.AddButton("REJECT DESIGN", 20, 252, 200, 50, () => DesignApprove(false), 0f, pal.Red);

      JarvisSpatialPanel chat = AddPanel("chat", "Conversation", 440, 330, -1.12f, -0.46f, pal.Violet);
      chat.SetBodyBox(56, 220); chat.Body.fontSize = 16;
      chat.AddButton("< OLDER", 14, 280, 200, 40, () => { _chatOffset += Mathf.Max(1, _chatShown); RefreshChat(); }, 0f, pal.Violet);
      chat.AddButton("NEWER >", 226, 280, 200, 40, () => { _chatOffset = Mathf.Max(0, _chatOffset - Mathf.Max(1, _chatShown)); RefreshChat(); }, 0f, pal.Violet);
      RefreshChat();

      JarvisSpatialPanel outline = AddPanel("outline", "Outline", 440, 330, -1.12f, -0.46f, pal.Cyan);
      outline.SetBodyBox(56, 220); outline.Body.fontSize = 16;
      outline.AddButton("< PREV", 14, 280, 100, 40, () => { _outlineSel--; RefreshOutline(); }, 0f, pal.Cyan);
      outline.AddButton("NEXT >", 118, 280, 100, 40, () => { _outlineSel++; RefreshOutline(); }, 0f, pal.Cyan);
      outline.AddButton("GO TO", 222, 280, 120, 40, () => OutlineGo(false), 0f, pal.Green);
      outline.AddButton("IN MAP", 346, 280, 80, 40, () => OutlineGo(true), 0f, pal.Violet);
      RefreshOutline();

      JarvisSpatialPanel caption = AddPanel("caption", "JARVIS", 980, 190, 0.15f, -0.52f, pal.Cyan);
      caption.SetBodyBox(54, 70); caption.Body.fontSize = 26;
      _quickChange = caption.AddButton("What breaks if I change this?", 20, 128, 400, 50, () => Ask(QuickChangeQuestion()));   // label follows the selection
      caption.AddButton("Show risky paths", 430, 128, 190, 50, () => Ask("Show me the risky paths in this change."));
      caption.AddButton("Run tests", 630, 128, 170, 50, () => Ask("Run the tests for this change."));
      caption.AddButton("TYPE", 810, 128, 150, 50, OpenKeyboard);

      JarvisSpatialPanel nav = AddPanel("nav", "Navigate", 1000, 110, 0.15f, -0.80f, pal.Cyan);
      float x = 12f;
      foreach (string m in NavModes)
      {
        string mode = m;
        _navButtons[mode] = nav.AddButton(mode, x, 52, 100, 46, () => { _agentShown.Clear(); foreach (JarvisSpatialPanel pp in _panels.Values) pp.Reopen(); SetMode(mode); });
        x += 108f;
      }
      nav.AddButton("CENTER", x, 52, 100, 46, () => { Recenter(); ResetGraphView(); });
      nav.AddButton("FX", x + 108f, 52, 100, 46, CycleIsolation);

      // View tools: graph filters, rotation, runtime trace, settings, exit
      JarvisSpatialPanel tools = AddPanel("tools", "View", 900, 110, 0.15f, -0.66f, pal.Cyan);
      _kindFilterBtn = tools.AddButton("FILTER: ALL", 12, 52, 160, 46, CycleKindFilter);
      _edgeFilterBtn = tools.AddButton("EDGE: ALL", 180, 52, 160, 46, CycleEdgeFilter);
      tools.AddButton("ROT <", 348, 52, 80, 46, () => RotateGraph(-RotateStepDegrees));
      tools.AddButton("ROT >", 436, 52, 80, 46, () => RotateGraph(+RotateStepDegrees));
      tools.AddButton("TRACE", 524, 52, 100, 46, RunRuntimeTrace, 0f, pal.Violet);
      tools.AddButton("SETTINGS", 632, 52, 140, 46, OpenSettings);
      tools.AddButton("EXIT", 780, 52, 100, 46, ExitToProjects, 0f, pal.Red);

      _settingsPanel = AddPanel("settings", "Settings", 520, 330, 0.6f, 0f, pal.Cyan);
      _settingsPanel.SetBodyBox(56, 170); _settingsPanel.Body.fontSize = 18;
      _voiceBtn = _settingsPanel.AddButton("VOICE: ON", 20, 250, 120, 50, ToggleVoiceEnabled);
      _settingsPanel.AddButton("RESET LAYOUT", 146, 250, 150, 50, ResetLayout);
      _quitBtn = _settingsPanel.AddButton("QUIT APP", 302, 250, 110, 50, QuitApp, 0f, pal.Red);
      _settingsPanel.AddButton("CLOSE", 418, 250, 90, 50, () => { _settingsPanel.Show(false); _quitArmed = false; });
      _settingsPanel.Show(false);

      RefreshStatus(); RefreshRepo(); RefreshActivity(); RefreshApproval();
      BuildMenu();
    }

    private void SetMode(string mode)
    {
      if (mode != _mode && _panels.ContainsKey("menu")) _panels["menu"].Show(false);
      _mode = mode;
      if (mode == "DESIGN" && !_designRequested && _bridge != null)
      {
        _designRequested = true;
        _bridge.GetDesign(d =>
        {
          if (d != null && (d.architecture != null || d.requirements != null))
          {
            _design = d;
            RenderDesignGraph();
            RefreshDesign();
          }
        }, e => { });
      }
      foreach (KeyValuePair<string, JarvisSpatialButton> nb in _navButtons) nb.Value.Selected = nb.Key == mode;
      if (_graphRoot != null) _graphRoot.gameObject.SetActive(mode != "REPOS" && mode != "CODE");
      string[] visible = ModePanels.ContainsKey(mode) ? ModePanels[mode] : ModePanels["MAP"];
      int shown = 0;
      bool awaiting = !string.IsNullOrEmpty(_pending) || !string.IsNullOrEmpty(_lastCommitBranch);
      foreach (string key in new[] { "repo", "code", "evidence", "tests", "activity", "legend", "ghost", "approval", "impact", "design_req", "design_cmp", "design_act", "chat", "outline" })
      {
        bool on = visible.Contains(key) || _agentShown.Contains(key);
        // approval shares its slot with evidence and tests: while something is pending or a
        // committed change still awaits promotion, approval wins
        if (awaiting && key == "approval") on = true;
        if (awaiting && (key == "evidence" || key == "tests")) on = false;
        _panels[key].Show(on, on ? 0.05f * shown++ : 0f);
      }
      RefreshStatus();
      RefreshCode();
    }

    // =========================================================== graph

    private void LoadGraph(GraphDto g)
    {
      _graph = g;
      _graph.graph_type = g.graph_type;  // Preserve graph type
      _agentEvidence = null; _agentTestResults = null; _unverifiedEvidence = null;   // ids from another repository would not resolve
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
        if (!_clusters.TryGetValue(cname, out ClusterView cv)) _clusters[cname] = cv = new ClusterView { Name = cname, Collapsed = true };

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
        
        // Ensure the node collider is not a trigger so it can be raycast against
        Collider nodeCollider = body.GetComponent<Collider>();
        if (nodeCollider != null) nodeCollider.isTrigger = false;

        Color baseColor = dto.level == "module" ? pal.Amber
          : dto.level == "file" ? pal.Violet
          : dto.level == "class" ? pal.Green
          : dto.level == "layer" ? pal.Red
          : dto.kind == "external" ? pal.Gray
          : dto.kind == "test" ? pal.Violet
          : pal.Cyan;

        nv.Base = baseColor;
        body.AddComponent<JarvisGraphNode>().Initialize(dto.id, Select, DragCluster, ShowNodeMenu);
        // Invisible pinch target: the rendered node is only a few centimetres wide, which is
        // hard to hit reliably at arm's length. Parent it to Body so it grows with the pop animation.
        var hitArea = new GameObject("HitArea");
        hitArea.transform.SetParent(body.transform, false);
        hitArea.transform.localScale = Vector3.one * 2.4f;
        hitArea.AddComponent<SphereCollider>();
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
      
      // Collapse all clusters by default
      foreach (ClusterView cv in _clusters.Values)
      {
        cv.Collapsed = true;
        for (int i = 1; i < cv.Members.Count; i++)   // member 0 stays as the cluster anchor
        {
          cv.Members[i].Fx.SetShown(false);
          cv.Members[i].Label.gameObject.SetActive(false);
        }
      }
      if (_kindFilter != 0) ApplyFilters();   // a filter chosen earlier survives a graph reload
      RefreshEdgeVisibility();
    }

    // ---- edges: solid = static, dashed = inferred, dotted = ambiguous
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
    // distinct edge ids so each can be selected independently. The fallback
    // keeps file/line/column so two parallel edges without call-site ids are
    // not collapsed into one.
    private static string EdgeKey(GraphEdgeDto d)
    {
      if (!string.IsNullOrEmpty(d.edge_id))
        return "id:" + d.edge_id;

      if (!string.IsNullOrEmpty(d.callsite_id))
        return "cs:" + d.callsite_id + "|" + d.src + "|" + d.dst;

      return d.src + "|" + d.dst + "|" + d.kind + "|" + d.file + "|" + d.line + "|" + d.column;
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
      foreach (var edge in _edges)
        if (EdgeKey(edge.Dto) == edgeId) { ShowEdgeMenu(edge); return; }
      Debug.Log("Edge held: " + edgeId);
    }

    private void StyleEdge(EdgeView ev, string kind)
    {
      JarvisPalette pal = JarvisPalette.Current;
      string graphType = _graph != null ? _graph.graph_type : null;
      string edgeKind = ev.Dto != null ? ev.Dto.edge_kind : null;

      // Control-flow edge styling
      if (graphType == "control_flow" && !string.IsNullOrEmpty(edgeKind))
      {
        switch (edgeKind)
        {
          case "true":
            ev.Style = "solid";
            ev.Base = pal.Green;
            return;
          case "false":
            ev.Style = "solid";
            ev.Base = pal.Red;
            return;
          case "next":
            ev.Style = "solid";
            ev.Base = pal.Cyan;
            return;
          case "loop_back":
            ev.Style = "dashed";
            ev.Base = pal.Violet;
            return;
          case "loop_exit":
            ev.Style = "solid";
            ev.Base = pal.Amber;
            return;
          case "break":
            ev.Style = "solid";
            ev.Base = pal.Orange;
            return;
          case "continue":
            ev.Style = "dashed";
            ev.Base = pal.Violet;
            return;
          case "exception":
            ev.Style = "dotted";
            ev.Base = pal.Red;
            return;
          case "return":
            ev.Style = "solid";
            ev.Base = pal.Green;
            return;
          case "loop_exhausted":
            ev.Style = "solid";
            ev.Base = pal.Amber;
            return;
          case "finally":
            ev.Style = "dashed";
            ev.Base = pal.Violet;
            return;
          case "raise":
            ev.Style = "dotted";
            ev.Base = pal.Red;
            return;
          case "may_raise":
            ev.Style = "dashed";
            ev.Base = pal.Orange;
            return;
          case "resume":
            ev.Style = "dashed";
            ev.Base = pal.Cyan;
            return;
        }
      }

      // Data-flow edge styling
      if (graphType == "data_flow" && !string.IsNullOrEmpty(edgeKind))
      {
        switch (edgeKind)
        {
          case "operand":
            ev.Style = "solid";
            ev.Base = pal.Cyan;
            return;
          case "produces":
            ev.Style = "solid";
            ev.Base = pal.Green;
            return;
          case "reaches":
            // Check resolution field: may_reach should be dashed, must_reach solid
            string reachResolution = ev.Dto != null ? ev.Dto.resolution : null;
            if (reachResolution == "may_reach")
            {
              ev.Style = "dashed";
              ev.Base = pal.Violet;
            }
            else
            {
              ev.Style = "solid";
              ev.Base = pal.Violet;
            }
            return;
          case "may_reach":
            ev.Style = "dashed";
            ev.Base = pal.Violet;
            return;
          case "returns":
            ev.Style = "solid";
            ev.Base = pal.Amber;
            return;
        }
      }

      // Default call graph styling (legacy)
      string resolution = ev.Dto != null ? ev.Dto.resolution : null;
      string etype = ev.Dto != null ? ev.Dto.type : null;
      string style;
      if (etype == "may_call" || kind == "possible" || resolution == "polymorphic") style = "dashed";
      else if (kind == "ambiguous" || resolution == "ambiguous") style = "dotted";
      else style = kind == "inferred" || kind == "heuristic" || kind == "dashed" ? "dashed" : "solid";
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
      RefreshOutline();
      Log("selected " + _nodes[id].Dto.name);
      if (_bridge != null && !_source.ContainsKey(id) && !IsDesignNode(id))
        _bridge.GetSource(id, s => { if (s != null && s.status == "ok") { _source[id] = s; if (_selected == id) RefreshCode(); } });
      RefreshQuickButtons();
      RefreshDesignCmp();
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
      // Same behaviour as expanding a cluster from the node menu: reveal what is loaded
      // and fetch a deeper neighbourhood from the server, merged via MergeGraph.
      if (!_nodes.TryGetValue(nodeId, out NodeView n)) return;
      ClusterView cv = n.Cluster;
      if (cv.Collapsed) SetClusterCollapsed(cv, false);
      if (_bridge != null && !IsDesignNode(nodeId))
        _bridge.GetGraphWithFocus(nodeId, 2, g => { if (g != null && g.nodes != null) MergeGraph(g); },
          e => Say("Could not fetch more of the graph: " + e));
      Log("expanded node: " + nodeId);
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

    private void ToggleVoice() { if (_voice != null && _voiceEnabled) _voice.ToggleListening(); }

    private void OpenKeyboard()
    {
      if (_kb != null || (_bridge != null && _bridge.Busy)) return;
      _kb = TouchScreenKeyboard.Open("", TouchScreenKeyboardType.Default);
    }

    // Push-to-talk on the orb: hold the pinch while you speak, let go to send the message.
    private void VoiceDown()
    {
      if (_voice == null || !_voiceEnabled || _voice.Current == JarvisVoice.State.Listening) return;
      JarvisAudio.Play(JarvisAudio.Cue.SelectTick);
      _voice.StartPushToTalk();
    }
    private void VoiceUp() { if (_voice != null) _voice.StopPushToTalk(); }

    private void Ask(string text)
    {
      if (_bridge == null || string.IsNullOrEmpty(text)) return;
      if (_mode == "DESIGN") { DesignPropose(text); return; }
      AskAgent(text);
    }

    /// <summary>Send a message to the agent pipeline regardless of the current mode
    /// (used by WORK ON IT so implementation tasks are not treated as design ideas).
    /// taskId links the turn's code change back to its plan task for promotion.</summary>
    private void AskAgent(string text, string taskId = null)
    {
      _progressSeen = 0;
      Say("Thinking…");
      Log("ask: " + text);
      AddChat(true, text);
      _bridge.Ask(text, _selected, OnAnswer, err => { Say(err); Log("error: " + err); AddChat(false, "[error] " + err); _errorUntil = Time.unscaledTime + 4f; }, taskId);
    }

    // =========================================================== architecture design

    private static bool IsDesignNode(string id) { return !string.IsNullOrEmpty(id) && id.StartsWith("d:"); }
    private bool IsDesignGraph() { return _graph != null && _graph.graph_type == "architecture"; }

    private void DesignPropose(string idea)
    {
      _progressSeen = 0;
      Say("Designing architecture…");
      Log("design: " + idea);
      AddChat(true, idea);
      _bridge.DesignPropose(idea, r =>
      {
        if (r == null || r.architecture == null)
        {
          Say("Design failed: " + (r != null ? r.error : "no response"));
          AddChat(false, "[error] design failed: " + (r != null ? r.error : "no response"));
          _errorUntil = Time.unscaledTime + 4f;
          return;
        }
        _design = new DesignStateDto { requirements = r.requirements, architecture = r.architecture };
        // The response carries the provenance outside the architecture body too; keep both.
        if (string.IsNullOrEmpty(r.architecture.provenance)) r.architecture.provenance = r.provenance;
        if (string.IsNullOrEmpty(r.architecture.requirements_source)) r.architecture.requirements_source = r.requirements_source;
        _designWarning = r.warning;
        _compareStatus.Clear();
        _compareOverrides.Clear();
        _cmpAmbSel = -1; _cmpCandSel = 0;
        _qSection = 0; _questionSel = -1;
        _cycleAccepted.Clear();
        RenderDesignGraph();
        DesignCompare();   // colour components against the repository immediately
        RefreshAll();
        int n = r.architecture.components != null ? r.architecture.components.Length : 0;
        Say("Proposed " + n + " components. COMPARE, APPROVE, GENERATE PLAN in the Architecture panel.");
        AddChat(false, "Proposed " + n + " components. Review them in DESIGN mode, then COMPARE and APPROVE.");
      }, err => { Say(err); _errorUntil = Time.unscaledTime + 4f; });
    }

    /// <summary>Render the proposed architecture through the normal graph pipeline.
    /// Each component is its own cluster (named after the component) so nothing hides.</summary>
    private void RenderDesignGraph()
    {
      ArchitectureDto arch = _design != null ? _design.architecture : null;
      if (arch == null || arch.components == null) return;
      var g = new GraphDto { graph_type = "architecture" };
      foreach (ComponentDto c in arch.components)
        g.nodes.Add(new GraphNodeDto
        {
          id = "d:" + c.id, name = c.name, kind = "component", cluster = c.name,
          file = "architecture", detail = c.responsibility,
        });
      // Extra repository nodes from the last compare render as red "external" nodes.
      if (_design.compare != null && _design.compare.extra != null)
        foreach (CompareItemDto x in _design.compare.extra)
          if (!string.IsNullOrEmpty(x.node))
            g.nodes.Add(new GraphNodeDto { id = "x:" + x.node, name = x.name, kind = "external", cluster = "repo" });
      if (arch.relationships != null)
        foreach (RelationshipDto r in arch.relationships)
          g.edges.Add(new GraphEdgeDto { src = "d:" + r.src, dst = "d:" + r.dst, kind = r.kind, type = r.kind, edge_id = r.id, reason = r.label });

      string sel = _selected;
      LoadGraph(g);
      foreach (ClusterView cv in _clusters.Values) SetClusterCollapsed(cv, false);   // show every component
      ApplyCompareColors();
      if (!string.IsNullOrEmpty(sel) && _nodes.ContainsKey(sel)) Select(sel);
      else if (g.nodes.Count > 0) Select(g.nodes[0].id);
    }

    private void ApplyCompareColors()
    {
      foreach (NodeView n in _nodes.Values)
      {
        if (n.Dto.kind == "external") { n.Base = JarvisPalette.Current.Red; continue; }
        if (!IsDesignNode(n.Dto.id)) continue;
        string cid = n.Dto.id.Substring(2);
        if (_compareStatus.TryGetValue(cid, out string st))
          n.Base = st == "matched" ? JarvisPalette.Current.Green
          : st == "missing" ? JarvisPalette.Current.Amber
          : st == "ambiguous" ? JarvisPalette.Current.Cyan : n.Base;
      }
      RefreshStyles();
    }

    private void DesignCompare()
    {
      if (_bridge == null) return;
      _bridge.DesignCompare(c =>
      {
        if (c == null) return;
        if (_design != null) _design.compare = c;
        _compareStatus.Clear();
        if (c.matched != null) foreach (CompareItemDto m in c.matched) _compareStatus[m.id] = "matched";
        if (c.missing != null) foreach (CompareItemDto m in c.missing) _compareStatus[m.id] = "missing";
        if (c.ambiguous != null) foreach (CompareItemDto m in c.ambiguous) _compareStatus[m.id] = "ambiguous";
        RenderDesignGraph();
        RefreshDesignCmp();
        int nAmb = c.ambiguous != null ? c.ambiguous.Length : 0;
        Say("Compare: " + (c.matched != null ? c.matched.Length : 0) + " matched, "
          + (c.missing != null ? c.missing.Length : 0) + " missing, "
          + (c.extra != null ? c.extra.Length : 0) + " extra in repo"
          + (nAmb > 0 ? ", " + nAmb + " ambiguous (ASSIGN in the Component panel)" : "")
          + (c.stale ? " — STALE, design changed since this comparison" : "") + ".");
      }, err => Say("Compare failed: " + err),
      _compareOverrides.Count > 0 ? _compareOverrides : null);
    }

    private void DesignApprove(bool approved)
    {
      ArchitectureDto arch = _design != null ? _design.architecture : null;
      if (arch == null) { Say("No architecture to approve."); return; }
      if (approved && arch.open_questions != null && arch.open_questions.Length > 0)
      { Say("Resolve the open questions before approving."); return; }
      _bridge.DesignApprove(approved, a =>
      {
        if (a == null) { Say("Approve failed."); return; }
        _design.architecture = a;
        if (!approved) { _design.plan = null; _tasks = null; _taskSel = 0; }   // the server discards the plan with the approval
        RefreshAll();
        Say(approved ? "Architecture approved. The plan was generated: review it with TASK > in the Architecture panel." : "Design rejected. It is back in draft and the plan was discarded.");
        Log(approved ? "design approved" : "design rejected");
      }, err => Say(err));
    }

    private void DesignPlanGenerate()
    {
      _bridge.PlanGenerate(p =>
      {
        if (_design != null) _design.plan = p;
        _cycleAccepted.Clear();
        RefreshTasks();
        RefreshAll();
        Say(p != null ? "Plan generated: " + (p.tasks != null ? p.tasks.Length : 0) + " tasks." : "Plan generation failed.");
      }, err => Say(err));
    }

    // ---- design questions: open (block approval), deferred and resolved lists ----

    private string[] DesignQuestions()
    {
      if (_design?.architecture?.open_questions != null && _design.architecture.open_questions.Length > 0)
        return _design.architecture.open_questions;
      return _design?.requirements?.open_questions;
    }

    private ResolvedQuestionDto[] SectionEntries()
    {
      if (_design?.architecture == null) return null;
      return _qSection == 1 ? _design.architecture.deferred_questions
           : _qSection == 2 ? _design.architecture.resolved_questions
           : null;
    }

    private int SectionCount()
    {
      if (_qSection == 0) { string[] q = DesignQuestions(); return q != null ? q.Length : 0; }
      ResolvedQuestionDto[] e = SectionEntries();
      return e != null ? e.Length : 0;
    }

    private bool AnyQuestions()
    {
      string[] open = DesignQuestions();
      ArchitectureDto a = _design?.architecture;
      return (open != null && open.Length > 0)
        || (a != null && ((a.deferred_questions != null && a.deferred_questions.Length > 0)
                          || (a.resolved_questions != null && a.resolved_questions.Length > 0)));
    }

    private string SelectedQuestion()
    {
      if (_qSection == 0)
      {
        string[] qs = DesignQuestions();
        if (qs == null || qs.Length == 0) return null;
        _questionSel = Mathf.Clamp(_questionSel < 0 ? 0 : _questionSel, 0, qs.Length - 1);
        return qs[_questionSel];
      }
      ResolvedQuestionDto[] es = SectionEntries();
      if (es == null || es.Length == 0) return null;
      _questionSel = Mathf.Clamp(_questionSel < 0 ? 0 : _questionSel, 0, es.Length - 1);
      return es[_questionSel].question;
    }

    private void CycleQuestion(int d)
    {
      int n = SectionCount();
      if (n == 0) { Say("No " + QuestionSections[_qSection].ToLowerInvariant() + " questions."); return; }
      _questionSel = (_questionSel + d + n) % n;
      RefreshDesignReq();
    }

    private void CycleQuestionSection()
    {
      _qSection = (_qSection + 1) % QuestionSections.Length;
      _questionSel = -1;
      RefreshDesignReq();
    }

    private void ResolveQuestion()
    {
      if (_qSection != 0) { Say("Only open questions can be resolved."); return; }
      string q = SelectedQuestion();
      if (q == null) { Say("No open questions to resolve."); return; }
      _questionSel = -1;
      // Ask for an optional answer/decision rationale; submitting empty still resolves.
      _kbOp = "resolve_question"; _kbOpId = q;
      OpenKeyboard();
    }

    private void EditQuestion()
    {
      if (_qSection != 0) { Say("Only open questions can be edited."); return; }
      string q = SelectedQuestion();
      if (q == null) { Say("No open questions to edit."); return; }
      _kbOp = "update_question"; _kbOpId = q;
      OpenKeyboard();
    }

    private void DeferQuestion()
    {
      if (_qSection != 0) { Say("Only open questions can be deferred."); return; }
      string q = SelectedQuestion();
      if (q == null) { Say("No open questions to defer."); return; }
      _questionSel = -1;
      // The server requires a reason; the typed text becomes defer_question's answer field.
      _kbOp = "defer_question"; _kbOpId = q;
      OpenKeyboard();
    }

    private void ReopenQuestion()
    {
      string q = SelectedQuestion();
      if (q == null || (_qSection != 1 && _qSection != 2))
      { Say("Select a deferred or resolved question (SEC button) to reopen it."); return; }
      _questionSel = -1;
      SendDesignEdit(new[] { new DesignEditOpDto { op = "reopen_question", question = q } }, "Reopened question");
    }

    // ---- implementation plan tasks (lifecycle + hand-off to the coding workflow) ----

    private TaskDto SelectedTask()
    {
      if (_tasks == null || _tasks.Length == 0) return null;
      _taskSel = Mathf.Clamp(_taskSel, 0, _tasks.Length - 1);
      return _tasks[_taskSel];
    }

    private void CycleTask(int d)
    {
      if (_tasks == null || _tasks.Length == 0) { Say("No tasks yet. Approve the architecture and GENERATE PLAN."); return; }
      _taskSel = (_taskSel + d + _tasks.Length) % _tasks.Length;
      RefreshActivity(); RefreshDesignAct();
    }

    private void RefreshTasks()
    {
      _bridge.GetTask(tr =>
      {
        if (tr == null) return;
        _tasks = tr.tasks;
        _planCircular = tr.circular;
        if (_tasks != null && _tasks.Length > 0) _taskSel = Mathf.Clamp(_taskSel, 0, _tasks.Length - 1);
        else _taskSel = 0;
        RefreshActivity(); RefreshDesignAct();
      });
    }

    private void TaskSetStatus(string status)
    {
      TaskDto t = SelectedTask();
      if (t == null) { Say("No task selected. Generate a plan first."); return; }
      if (t.status == "done" || t.status == "completed") { Say("Task " + t.id + " is already done."); return; }
      if (status == "done")
      {
        // The server refuses DONE without evidence; collect it first.
        _kbOp = "task_done"; _kbOpId = t.id;
        OpenKeyboard();
        return;
      }
      PatchTask(t, status, null);
    }

    /// <summary>PATCH a task status. Circular-dependency tasks require a typed
    /// rationale (the server stores it as cycle_rationale) before they run.</summary>
    private void PatchTask(TaskDto t, string status, string evidence)
    {
      bool accept = _cycleAccepted.Contains(t.id);
      if (!accept && IsCyclicTask(t) && (status == "running" || status == "done"))
      {
        _cycleStatus = status; _cycleEvidence = evidence;
        _kbOp = "cycle_accept"; _kbOpId = t.id;
        OpenKeyboard();
        Say("Task " + t.id + " is in a circular dependency. Type a rationale to accept the cycle, or fix the architecture first.");
        return;
      }
      string rationale = _cycleReasons.TryGetValue(t.id, out string rr) ? rr : null;
      _bridge.PlanUpdateTask(t.id, status, ok =>
      {
        _lastTaskError = null;
        if (!ok) { Say("Task update rejected."); return; }
        RefreshTasks();
        Say("Task " + t.id + " -> " + status + ".");
      }, err => { _lastTaskError = err; Say(err); }, evidence, accept, rationale);
    }

    private bool IsCyclicTask(TaskDto t)
    {
      string[] circ = _planCircular ?? (_design != null && _design.plan != null ? _design.plan.circular : null);
      return circ != null && t != null && !string.IsNullOrEmpty(t.component_id)
        && System.Array.IndexOf(circ, t.component_id) >= 0;
    }

    /// <summary>Mark the selected task running and hand it to the agent pipeline as a
    /// code-change request, so generated tasks drive the same worktree/test/approve flow.</summary>
    private void WorkOnTask()
    {
      TaskDto t = SelectedTask();
      if (t == null) { Say("No task selected. Generate a plan first."); return; }
      if (t.status == "done" || t.status == "completed") { Say("Task " + t.id + " is already done."); return; }
      if (_bridge == null || _bridge.Busy) { Say("JARVIS is still working on the previous request."); return; }
      string prompt = "Implement this approved architecture task in the codebase: " + (t.title ?? t.id) +
        ". Acceptance criteria: " + (string.IsNullOrEmpty(t.acceptance) ? "none given" : t.acceptance) +
        ". This is component " + (string.IsNullOrEmpty(t.component_id) ? "?" : t.component_id) +
        " of the approved design. Find the relevant repository files, make the change, " +
        "run the relevant tests, and propose the patch for my approval.";
      // Only start coding after the server confirms the task may run
      // (dependency rules are enforced there); a rejection must not launch the agent.
      Action start = () => AskAgent("Implement this approved architecture task (task_id " + t.id + "). " + prompt, t.id);
      if (t.status != "running")
      {
        if (!IsCyclicTask(t) || _cycleAccepted.Contains(t.id))
        {
          string rationale = _cycleReasons.TryGetValue(t.id, out string wr) ? wr : null;
          _bridge.PlanUpdateTask(t.id, "running", ok =>
          {
            _lastTaskError = null;
            if (!ok) { Say("Task " + t.id + " could not be started."); return; }
            RefreshTasks();
            start();
          }, err => { _lastTaskError = err; Say(err); }, null, _cycleAccepted.Contains(t.id), rationale);
        }
        else
        {
          _cycleStatus = "running"; _cycleEvidence = null;
          _kbOp = "cycle_accept"; _kbOpId = t.id;
          OpenKeyboard();
          Say("Task " + t.id + " is in a circular dependency. Type a rationale to accept the cycle and proceed, or fix the architecture first.");
        }
      }
      else start();
    }

    private void SendDesignEdit(DesignEditOpDto[] ops, string what)
    {
      _bridge.DesignEdit(ops, r =>
      {
        if (r == null || !r.ok) { Say("Edit failed: " + (r != null ? r.detail : "no response")); return; }
        if (r.architecture != null && _design != null) _design.architecture = r.architecture;
        // Every design edit invalidates the repository comparison and the
        // implementation plan server-side; mirror that here so stale colours
        // and plan rows don't linger, then recompute the comparison.
        if (_design != null) { _design.compare = null; _design.plan = null; }
        _compareStatus.Clear();
        _compareOverrides.Clear();   // overrides were computed against the old revision
        _cmpAmbSel = -1; _cmpCandSel = 0;
        _tasks = null;
        _planCircular = null;
        _cycleAccepted.Clear();
        RenderDesignGraph();
        RefreshAll();
        RefreshTasks();
        DesignCompare();
        Say(what + " done.");
      }, err => Say(err));
    }

    /// <summary>Text typed for a design edit (rename / responsibility / question) instead of a chat message.</summary>
    private void ApplyDesignTextOp(string text)
    {
      if (string.IsNullOrEmpty(_kbOpId)) { Say("Nothing to send."); return; }
      if (_kbOp == "edge_label")
      {
        if (string.IsNullOrEmpty(text)) { Say("A link label cannot be empty."); return; }
        SendDesignEdit(new[] { new DesignEditOpDto { op = "update_relationship", id = _kbOpId, label = text } }, "Link label -> " + text);
        return;
      }
      if (_kbOp == "task_done")
      {
        TaskDto dt = null;
        if (_tasks != null) foreach (TaskDto x in _tasks) if (x.id == _kbOpId) dt = x;
        if (dt == null) { Say("That task no longer exists."); return; }
        if (string.IsNullOrEmpty(text)) { Say("Completion needs evidence (tests run, commit). Nothing recorded."); return; }
        PatchTask(dt, "done", text);
        return;
      }
      if (_kbOp == "cycle_accept")
      {
        if (string.IsNullOrEmpty(text)) { Say("A rationale is required to accept a cycle."); return; }
        _cycleReasons[_kbOpId] = text;
        _cycleAccepted.Add(_kbOpId);
        TaskDto ct = null;
        if (_tasks != null) foreach (TaskDto x in _tasks) if (x.id == _kbOpId) ct = x;
        if (ct != null) PatchTask(ct, _cycleStatus ?? "running", _cycleEvidence);
        return;
      }
      if (_kbOp == "reopen_question")
      {
        SendDesignEdit(new[] { new DesignEditOpDto { op = "reopen_question", question = _kbOpId } }, "Reopened question");
        return;
      }
      if (_kbOp == "defer_question")
      {
        if (string.IsNullOrEmpty(text)) { Say("A reason is required to defer a question."); return; }
        SendDesignEdit(new[] { new DesignEditOpDto { op = "defer_question", question = _kbOpId, answer = text } }, "Deferred question");
        return;
      }
      if (_kbOp == "resolve_question")
      {
        SendDesignEdit(new[] { new DesignEditOpDto { op = "resolve_question", question = _kbOpId, answer = text ?? "" } }, "Resolved question");
        return;
      }
      if (string.IsNullOrEmpty(text)) { Say("Nothing to send."); return; }
      var op = new DesignEditOpDto { op = "update_component", id = _kbOpId };
      string what;
      if (_kbOp == "rename") { op.name = text; what = "Renamed component"; }
      else if (_kbOp == "responsibility") { op.responsibility = text; what = "Updated responsibility"; }
      else if (_kbOp == "update_question") { op.op = "update_question"; op.question = _kbOpId; op.new_question = text; what = "Updated question"; }
      else { Say("Unknown edit."); return; }
      SendDesignEdit(new[] { op }, what);
    }

    private string DesignCompId(string nodeId)
    {
      return IsDesignNode(nodeId) ? nodeId.Substring(2) : null;
    }

    private ComponentDto FindComponent(string compId)
    {
      if (_design?.architecture?.components == null || compId == null) return null;
      foreach (ComponentDto c in _design.architecture.components) if (c.id == compId) return c;
      return null;
    }

    private void RefreshDesignReq()
    {
      if (_designReqPanel == null || !_panels.ContainsKey("design_req")) return;
      RequirementsDto r = _design != null ? _design.requirements : null;
      ArchitectureDto arch = _design != null ? _design.architecture : null;
      string[] open = DesignQuestions();
      ResolvedQuestionDto[] defs = arch != null ? arch.deferred_questions : null;
      ResolvedQuestionDto[] ress = arch != null ? arch.resolved_questions : null;
      int openN = open != null ? open.Length : 0;
      int defN = defs != null ? defs.Length : 0;
      int resN = ress != null ? ress.Length : 0;
      bool anyQuestions = openN + defN + resN > 0 || AnyQuestions();
      int secN = SectionCount();
      if (_qPrevBtn != null) _qPrevBtn.Interactable = secN > 0;
      if (_qNextBtn != null) _qNextBtn.Interactable = secN > 0;
      if (_qSecBtn != null) { _qSecBtn.Interactable = anyQuestions; _qSecBtn.Label.text = "SEC: " + QuestionSections[_qSection]; }
      bool openSec = _qSection == 0;
      if (_qResolveBtn != null) _qResolveBtn.Interactable = openSec && openN > 0;
      if (_qEditBtn != null) _qEditBtn.Interactable = openSec && openN > 0;
      if (_qDeferBtn != null) _qDeferBtn.Interactable = openSec && openN > 0;
      if (_qReopenBtn != null) _qReopenBtn.Interactable = (_qSection == 1 && defN > 0) || (_qSection == 2 && resN > 0);
      if (r == null && !anyQuestions) { _designReqPanel.SetBody("No requirements yet.\nType an idea in DESIGN mode or use voice."); return; }
      var sb = new StringBuilder();
      if (r != null)
      {
        AppendReqList(sb, "GOALS", r.goals);
        AppendReqList(sb, "FUNCTIONAL", r.functional);
        AppendReqList(sb, "NON-FUNCTIONAL", r.non_functional);
        AppendReqList(sb, "CONSTRAINTS", r.constraints);
        AppendReqList(sb, "ASSUMPTIONS", r.assumptions);
      }
      if (openN > 0)
      {
        sb.Append("<b>OPEN QUESTIONS</b>  <color=#").Append(Hex(JarvisPalette.Current.TextMuted))
          .Append(">block approval</color>\n");
        for (int i = 0; i < open.Length; i++)
        {
          bool sel = openSec && i == SelectedQuestionIndex();
          if (sel)
            sb.Append("<color=#").Append(Hex(JarvisPalette.Current.Amber)).Append(">» ").Append(open[i]).Append(" «</color>\n");
          else
            sb.Append("  ").Append(open[i]).Append('\n');
        }
        sb.Append('\n');
      }
      AppendQuestionSection(sb, "DEFERRED", defs, _qSection == 1);
      AppendQuestionSection(sb, "RESOLVED", ress, _qSection == 2);
      _designReqPanel.SetBody(sb.Length > 0 ? sb.ToString() : "No requirements extracted.");
    }

    private void AppendQuestionSection(StringBuilder sb, string label, ResolvedQuestionDto[] items, bool active)
    {
      if (items == null || items.Length == 0) return;
      sb.Append("<b>").Append(label).Append("</b> (").Append(items.Length).Append(")\n");
      for (int i = 0; i < items.Length; i++)
      {
        ResolvedQuestionDto e = items[i];
        bool sel = active && i == SelectedQuestionIndex();
        if (sel) sb.Append("<color=#").Append(Hex(JarvisPalette.Current.Amber)).Append(">» ");
        else sb.Append("  ");
        sb.Append(e.question ?? "?");
        string note = !string.IsNullOrEmpty(e.reason) ? e.reason : e.answer;
        if (!string.IsNullOrEmpty(note)) sb.Append(" — ").Append(note);
        if (e.revision > 0) sb.Append(" (rev ").Append(e.revision).Append(')');
        if (sel) sb.Append(" «</color>");
        sb.Append('\n');
      }
      sb.Append('\n');
    }

    private int SelectedQuestionIndex()
    {
      int n = SectionCount();
      if (n == 0) return 0;
      return Mathf.Clamp(_questionSel < 0 ? 0 : _questionSel, 0, n - 1);
    }

    private static void AppendReqList(StringBuilder sb, string label, string[] items)
    {
      if (items == null || items.Length == 0) return;
      sb.Append("<b>").Append(label).Append("</b>\n");
      foreach (string s in items) sb.Append("• ").Append(s).Append('\n');
      sb.Append('\n');
    }

    // ---- comparison: matched/missing/extra lists + ambiguous assign control ----

    private CompareItemDto[] AmbiguousItems()
    {
      return _design?.compare?.ambiguous;
    }

    private int SelectedAmbiguousIndex()
    {
      CompareItemDto[] a = AmbiguousItems();
      if (a == null || a.Length == 0) return -1;
      return Mathf.Clamp(_cmpAmbSel < 0 ? 0 : _cmpAmbSel, 0, a.Length - 1);
    }

    private void CycleAmbiguous(int d)
    {
      CompareItemDto[] a = AmbiguousItems();
      if (a == null || a.Length == 0) { Say("No ambiguous matches."); return; }
      _cmpAmbSel = (_cmpAmbSel + d + a.Length) % a.Length;
      _cmpCandSel = 0;
      RefreshDesignCmp();
    }

    private void CycleCandidate(int d)
    {
      CompareItemDto[] a = AmbiguousItems();
      int i = SelectedAmbiguousIndex();
      if (a == null || i < 0 || a[i].candidates == null || a[i].candidates.Length == 0)
      { Say("No candidates for the selected ambiguous match."); return; }
      _cmpCandSel = (_cmpCandSel + d + a[i].candidates.Length) % a[i].candidates.Length;
      RefreshDesignCmp();
    }

    /// <summary>Resolve an ambiguous match by sending override_matches {component_id: node_id}
    /// with the next compare; the server re-runs assignment with the developer's pick.</summary>
    private void AssignAmbiguousMatch()
    {
      CompareItemDto[] a = AmbiguousItems();
      int i = SelectedAmbiguousIndex();
      if (a == null || i < 0) { Say("No ambiguous matches to assign."); return; }
      CompareItemDto item = a[i];
      if (item.candidates == null || item.candidates.Length == 0) { Say(item.id + " has no candidates."); return; }
      _cmpCandSel = Mathf.Clamp(_cmpCandSel, 0, item.candidates.Length - 1);
      string node = item.candidates[_cmpCandSel].node;
      if (string.IsNullOrEmpty(node)) { Say("Selected candidate has no node id."); return; }
      _compareOverrides[item.id] = node;
      Say("Assigned " + item.name + " → " + node + ". Re-comparing…");
      DesignCompare();
    }

    private CompareItemDto FindCompareItem(string compId)
    {
      CompareDto cmp = _design?.compare;
      if (cmp == null || compId == null) return null;
      foreach (CompareItemDto[] list in new[] { cmp.matched, cmp.missing, cmp.ambiguous, cmp.extra })
        if (list != null) foreach (CompareItemDto it in list) if (it.id == compId) return it;
      return null;
    }

    private static Color CompareRelColor(string st)
    {
      JarvisPalette pal = JarvisPalette.Current;
      switch (st)
      {
        case "confirmed": return pal.Green;
        case "possible": return pal.Cyan;
        case "missing": return pal.Amber;
        case "wrong_direction":
        case "wrong_type": return pal.Red;
        default: return pal.TextMuted;
      }
    }

    private void AppendCompareSection(StringBuilder sb, string label, CompareItemDto[] items, Color col)
    {
      sb.Append("<b>").Append(label).Append("</b> (").Append(items != null ? items.Length : 0).Append(")\n");
      if (items == null) return;
      int n = Mathf.Min(items.Length, 4);
      for (int i = 0; i < n; i++)
      {
        CompareItemDto it = items[i];
        sb.Append("  <color=#").Append(Hex(col)).Append('>').Append(it.id ?? "?").Append("</color>");
        if (!string.IsNullOrEmpty(it.node)) sb.Append(" → ").Append(it.node);
        sb.Append('\n');
      }
      if (items.Length > n) sb.Append("  … +").Append(items.Length - n).Append('\n');
    }

    private void RefreshDesignCmp()
    {
      if (_designCmpPanel == null) return;
      JarvisPalette pal = JarvisPalette.Current;
      CompareDto cmp = _design != null ? _design.compare : null;
      CompareItemDto[] amb = cmp != null ? cmp.ambiguous : null;
      bool hasAmb = amb != null && amb.Length > 0;
      int ai = hasAmb ? SelectedAmbiguousIndex() : -1;
      CompareItemDto selAmb = ai >= 0 ? amb[ai] : null;
      int candN = selAmb != null && selAmb.candidates != null ? selAmb.candidates.Length : 0;
      if (_cmpAmbPrev != null) { _cmpAmbPrev.Interactable = _cmpAmbNext.Interactable = hasAmb; }
      if (_cmpCandPrev != null) { _cmpCandPrev.Interactable = _cmpCandNext.Interactable = candN > 1; }
      if (_cmpAssignBtn != null) _cmpAssignBtn.Interactable = candN > 0;
      if (cmp == null) { _designCmpPanel.SetBody("No comparison yet.\nPress COMPARE in the Architecture panel."); return; }
      var sb = new StringBuilder();
      sb.Append("repo ").Append(string.IsNullOrEmpty(cmp.repo) ? "?" : cmp.repo)
        .Append("   design rev ").Append(cmp.design_revision);
      if (cmp.stale) sb.Append("   <color=#").Append(Hex(pal.Amber)).Append(">STALE</color>");
      sb.Append('\n');
      string compId = DesignCompId(_selected);
      ComponentDto c = FindComponent(compId);
      if (c != null)
      {
        sb.Append("<b>").Append(c.name).Append("</b>  ").Append(c.kind).Append('\n');
        if (!string.IsNullOrEmpty(c.responsibility)) sb.Append(c.responsibility).Append('\n');
        string st = _compareStatus.TryGetValue(c.id, out string s) ? s : null;
        if (st == "matched") sb.Append("<color=#").Append(Hex(pal.Green)).Append(">matched in repo</color>\n");
        else if (st == "missing") sb.Append("<color=#").Append(Hex(pal.Amber)).Append(">missing from repo</color>\n");
        else if (st == "ambiguous") sb.Append("<color=#").Append(Hex(pal.Cyan)).Append(">ambiguous — assign a candidate below</color>\n");
        CompareItemDto ci = FindCompareItem(c.id);
        if (ci != null)
        {
          if (!string.IsNullOrEmpty(ci.confidence) && ci.confidence != "none")
            sb.Append("confidence: ").Append(ci.confidence).Append('\n');
          if (!string.IsNullOrEmpty(ci.evidence))
            sb.Append("<color=#").Append(Hex(pal.TextMuted)).Append('>').Append(ci.evidence).Append("</color>\n");
        }
      }
      if (_designLinkFrom != null) sb.Append("<color=#").Append(Hex(pal.Amber)).Append(">link armed: pick a target</color>\n");
      AppendCompareSection(sb, "MATCHED", cmp.matched, pal.Green);
      AppendCompareSection(sb, "MISSING", cmp.missing, pal.Amber);
      AppendCompareSection(sb, "EXTRA", cmp.extra, pal.Red);
      sb.Append("<b>AMBIGUOUS</b> (").Append(hasAmb ? amb.Length : 0).Append(") — AMB/CAND pick, ASSIGN sends override\n");
      if (hasAmb)
        for (int i = 0; i < amb.Length; i++)
        {
          bool sel = i == ai;
          if (sel) sb.Append("<color=#").Append(Hex(pal.Violet)).Append(">» ");
          else sb.Append("  ");
          sb.Append(amb[i].name ?? amb[i].id ?? "?").Append(" (").Append(amb[i].id ?? "?").Append(")");
          if (sel && amb[i].candidates != null)
          {
            sb.Append('\n');
            for (int j = 0; j < amb[i].candidates.Length; j++)
            {
              CompareCandidateDto cd = amb[i].candidates[j];
              sb.Append("    ");
              if (j == _cmpCandSel) sb.Append("<color=#").Append(Hex(pal.Green)).Append(">» ");
              sb.Append(cd.node ?? "?").Append(" (").Append(cd.score.ToString("0.00")).Append(')');
              if (j == _cmpCandSel) sb.Append("</color>");
              if (j + 1 < amb[i].candidates.Length) sb.Append("   ");
            }
          }
          if (sel) sb.Append(" «</color>");
          sb.Append('\n');
        }
      if (cmp.relationships != null && cmp.relationships.Length > 0)
      {
        sb.Append("<b>RELATIONSHIPS</b>\n");
        foreach (CompareRelDto rel in cmp.relationships)
        {
          sb.Append("  <color=#").Append(Hex(CompareRelColor(rel.status))).Append('>')
            .Append(rel.id ?? "?").Append(' ').Append(rel.src ?? "?").Append('→').Append(rel.dst ?? "?")
            .Append(' ').Append(rel.kind ?? "").Append(": ").Append(rel.status ?? "?").Append("</color>");
          if (!string.IsNullOrEmpty(rel.evidence))
            sb.Append("  <color=#").Append(Hex(pal.TextMuted)).Append('>').Append(rel.evidence).Append("</color>");
          sb.Append('\n');
        }
      }
      _designCmpPanel.SetBody(sb.ToString());
    }

    /// <summary>One provenance line. 'model' is green, 'heuristic' amber, anything else muted. Never rendered as
    /// "AI" unless the server said so.</summary>
    private static void AppendProvenance(StringBuilder sb, string what, string source)
    {
      JarvisPalette pal = JarvisPalette.Current;
      string src = string.IsNullOrEmpty(source) ? "unknown" : source;
      string label, col;
      if (src == "model") { label = "AI model"; col = Hex(pal.Green); }
      else if (src == "heuristic") { label = "heuristic fallback (not AI)"; col = Hex(pal.Amber); }
      else if (src == "stored") { label = "stored (origin not recorded)"; col = Hex(pal.TextMuted); }
      else { label = src; col = Hex(pal.TextMuted); }
      sb.Append(what).Append(": <color=#").Append(col).Append('>').Append(label).Append("</color>\n");
    }

    private void RefreshDesignAct()
    {
      if (_designActPanel == null) return;
      ArchitectureDto a = _design != null ? _design.architecture : null;
      if (a == null)
      {
        _designActPanel.SetBody("No architecture yet.\nType an idea (TYPE) or use voice in DESIGN mode to propose one.");
        return;
      }
      var sb = new StringBuilder();
      // Provenance banner: a heuristic fallback is never shown as an AI design.
      AppendProvenance(sb, "Architecture", a.provenance);
      AppendProvenance(sb, "Requirements", a.requirements_source);
      string warn = _designWarning;
      if (string.IsNullOrEmpty(warn) && (a.provenance == "heuristic" || a.requirements_source == "heuristic"))
        warn = "Part of this proposal came from the heuristic fallback, not the AI model. Review it before relying on it.";
      if (!string.IsNullOrEmpty(warn))
        sb.Append("<color=#").Append(Hex(JarvisPalette.Current.Amber)).Append(">! ").Append(warn).Append("</color>\n");
      if (a.edited_by_user) sb.Append("<color=#").Append(Hex(JarvisPalette.Current.TextMuted)).Append(">Edited by you</color>\n");
      sb.Append("v").Append(a.version).Append(" rev ").Append(a.revision).Append("  ")
        .Append(a.status == "approved"
          ? "<color=#" + Hex(JarvisPalette.Current.Green) + ">approved rev " + a.approved_revision + "</color>"
          : a.status)
        .Append('\n');
      if (!string.IsNullOrEmpty(a.approved_by)) sb.Append("by ").Append(a.approved_by).Append('\n');
      sb.Append(a.components != null ? a.components.Length : 0).Append(" components, ")
        .Append(a.relationships != null ? a.relationships.Length : 0).Append(" links\n");
      if (a.open_questions != null && a.open_questions.Length > 0)
        sb.Append("<color=#").Append(Hex(JarvisPalette.Current.Amber)).Append(">").Append(a.open_questions.Length).Append(" open questions block approval</color>\n");
      ImplementationPlanDto plan = _design?.plan;
      if (plan != null && plan.tasks != null && plan.tasks.Length > 0)
      {
        sb.Append("Plan: ").Append(plan.tasks.Length).Append(" tasks (arch rev ")
          .Append(plan.architecture_revision).Append(")");
        if (!string.IsNullOrEmpty(plan.repo)) sb.Append("  repo ").Append(plan.repo);
        if (a.status == "approved" && plan.architecture_revision != a.approved_revision)
          sb.Append("  <color=#").Append(Hex(JarvisPalette.Current.Amber)).Append(">STALE</color>");
        sb.Append('\n');
      }
      TaskDto sel = SelectedTask();
      if (sel != null)
      {
        sb.Append("\n<b>Task ").Append(sel.id).Append("</b>  ").Append(sel.status ?? "pending").Append('\n');
        if (!string.IsNullOrEmpty(sel.title)) sb.Append(sel.title).Append('\n');
        if (!string.IsNullOrEmpty(sel.description) && sel.description != sel.acceptance)
          sb.Append(sel.description).Append('\n');
        if (sel.files != null && sel.files.Length > 0)
          sb.Append("files: ").Append(string.Join(", ", sel.files)).Append('\n');
        if (sel.symbols != null && sel.symbols.Length > 0)
        {
          sb.Append("symbols: ");
          for (int si = 0; si < sel.symbols.Length && si < 6; si++)
            sb.Append(si > 0 ? ", " : "").Append(string.IsNullOrEmpty(sel.symbols[si].name) ? sel.symbols[si].id : sel.symbols[si].name);
          if (sel.symbols.Length > 6) sb.Append(" +").Append(sel.symbols.Length - 6);
          sb.Append('\n');
        }
        if (sel.confirmed_targets != null && sel.confirmed_targets.Length > 0)
          sb.Append("confirmed: ").Append(string.Join(", ", sel.confirmed_targets)).Append('\n');
        if (sel.rejected_targets != null && sel.rejected_targets.Length > 0)
        {
          sb.Append("rejected: ");
          for (int ri = 0; ri < sel.rejected_targets.Length; ri++)
            sb.Append(ri > 0 ? "; " : "").Append(sel.rejected_targets[ri].file).Append(" (").Append(sel.rejected_targets[ri].reason).Append(')');
          sb.Append('\n');
        }
        if (sel.acceptance_criteria != null && sel.acceptance_criteria.Length > 0)
          sb.Append("criteria: ").Append(string.Join(" | ", sel.acceptance_criteria)).Append('\n');
        if (!string.IsNullOrEmpty(sel.repo_match)) sb.Append("repo match: ").Append(sel.repo_match).Append('\n');
        if (sel.evidence_check != null && !string.IsNullOrEmpty(sel.evidence_check.verdict))
          sb.Append("evidence: ").Append(sel.evidence_check.verdict).Append('\n');
        if (!string.IsNullOrEmpty(sel.evidence)) sb.Append("evidence: ").Append(sel.evidence).Append('\n');
        if (!string.IsNullOrEmpty(_lastTaskError))
          sb.Append("<color=#").Append(Hex(JarvisPalette.Current.Red)).Append(">blocked: ").Append(_lastTaskError).Append("</color>\n");
        if (IsCyclicTask(sel) && sel.status != "done" && sel.status != "completed")
          sb.Append("<color=#").Append(Hex(JarvisPalette.Current.Amber))
            .Append(">")
            .Append(sel.cycle_accepted ? "cycle accepted" + (string.IsNullOrEmpty(sel.cycle_rationale) ? "" : ": " + sel.cycle_rationale) : "circular dependency — type a rationale")
            .Append("</color>\n");
      }
      string[] circ = _planCircular ?? (plan != null ? plan.circular : null);
      if (circ != null && circ.Length > 0)
        sb.Append("<color=#").Append(Hex(JarvisPalette.Current.Amber)).Append(">circular dependencies: ")
          .Append(string.Join(", ", circ)).Append("</color>\n");
      string[] cpaths = plan != null ? plan.cycle_paths : null;
      if (cpaths != null && cpaths.Length > 0)
        sb.Append("<color=#").Append(Hex(JarvisPalette.Current.TextMuted)).Append(">cycle paths: ")
          .Append(string.Join("  ", cpaths)).Append("</color>\n");
      _designActPanel.SetBody(sb.ToString());
      bool hasTasks = _tasks != null && _tasks.Length > 0;
      if (_taskPrevBtn != null) _taskPrevBtn.Interactable = hasTasks;
      if (_taskNextBtn != null) _taskNextBtn.Interactable = hasTasks;
      if (_taskStartBtn != null) _taskStartBtn.Interactable = hasTasks;
      if (_taskDoneBtn != null) _taskDoneBtn.Interactable = hasTasks;
      if (_taskWorkBtn != null) _taskWorkBtn.Interactable = hasTasks && sel != null && sel.status != "done" && sel.status != "completed";
    }

    private void RefreshDesign()
    {
      RefreshDesignReq(); RefreshDesignCmp(); RefreshDesignAct();
    }

    private void OnAnswer(AskResponse r)
    {
      if (!string.IsNullOrEmpty(r.error) && !r.error.Contains("took too long")) AddChat(false, "[error] " + r.error);
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
          Debug.LogError("[JARVIS] error: " + r.error);
          _errorUntil = Time.unscaledTime + 4f;
        }
        return;
      }
      ResetOverlay();
      _agentMode = null;
      _agentEvidence = r.evidence;
      _agentTestResults = r.test_results;
      _lastTestRun = r.test_run;
      _validated = r.validated;
      _unverifiedEvidence = r.unverified_evidence;
      bool graphChanged = false;
      if (r.scene_commands != null) foreach (SceneCommand c in r.scene_commands) graphChanged |= ApplyCommand(c);
      if (!string.IsNullOrEmpty(r.pending_approval)) _pending = r.pending_approval;
      string reply = r.reply ?? "";
      if (r.test_source == "cached") reply += "  (Test results are SIMULATED.)";
      Say(reply);
      if (!string.IsNullOrWhiteSpace(reply)) AddChat(false, reply);
      Log("JARVIS answered");
      Debug.Log("[JARVIS] reply: " + reply);
      if (_voice != null) _voice.Speak(reply);
      RefreshAll();
      if (!string.IsNullOrEmpty(_pending)) SetMode("AGENT");         // pending approval always wins
      else if (!string.IsNullOrEmpty(_agentMode))
      {
        foreach (JarvisSpatialPanel pp in _panels.Values) pp.Reopen();   // same as tapping the tab
        SetMode(_agentMode);
      }
      else if (graphChanged) SetMode("MAP");
    }

    private void RefreshAll() { RefreshStyles(); RefreshEvidence(); RefreshCode(); RefreshGhost(); RefreshApproval(); RefreshTests(); RefreshQuickButtons(); RefreshDesign(); RefreshChat(); RefreshOutline(); SetMode(_mode); }

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
            // Preserve graph_type from command
            if (!string.IsNullOrEmpty(c.graph_type))
            {
              newGraph.graph_type = c.graph_type;
            }
            LoadGraph(newGraph);
            Log("show_graph: loaded " + newGraph.nodes.Count + " nodes, " + newGraph.edges.Count + " edges" +
                (string.IsNullOrEmpty(newGraph.graph_type) ? "" : " (type: " + newGraph.graph_type + ")"));
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
          _ghostDiff = c.diff; _ghostPage = 0; _ghostSeenAll = false;
          return false;
        case "show_test_badges":
          Badge(c.passed, " [ok]"); Badge(c.failed, " [x]"); Badge(c.not_run, " [-]");
          _hasTestRun = true; _testFailed = c.failed != null && c.failed.Length > 0;
          _testFailureLines = c.failure_lines;
          _testSummary = Summarize("PASSED", c.passed) + Summarize("FAILED", c.failed) + Summarize("NOT RUN", c.not_run);
          return false;
        case "show_impact_panel":
          if (_impactPanel != null)
          {
            var sb = new System.Text.StringBuilder();
            sb.AppendLine($"CHANGE IMPACT");
            sb.AppendLine($"Changed function: {c.text ?? "Unknown"}");
            sb.AppendLine($"Risk level: {c.summary ?? "Unknown"}");
            if (!string.IsNullOrEmpty(c.test_mapping)) sb.AppendLine($"Test mapping: {c.test_mapping}");
            if (!string.IsNullOrEmpty(c.risk_basis)) sb.AppendLine($"Risk basis: {c.risk_basis}");
            sb.AppendLine();

            // Direct callers (confirmed)
            if (c.direct_callers != null && c.direct_callers.Length > 0)
            {
              sb.AppendLine($"Confirmed callers ({c.direct_callers.Length}):");
              foreach (var caller in c.direct_callers.Take(5))
                sb.AppendLine($"  - {caller}");
              if (c.direct_callers.Length > 5)
                sb.AppendLine($"  ... and {c.direct_callers.Length - 5} more");
              sb.AppendLine();
            }

            // Possible callers (inferred)
            if (c.possible_callers != null && c.possible_callers.Length > 0)
            {
              sb.AppendLine($"Possible callers ({c.possible_callers.Length}):");
              foreach (var possible in c.possible_callers.Take(5))
                sb.AppendLine($"  - {possible}");
              if (c.possible_callers.Length > 5)
                sb.AppendLine($"  ... and {c.possible_callers.Length - 5} more");
              sb.AppendLine();
            }

            // Indirect dependents
            if (c.indirect_dependents != null && c.indirect_dependents.Length > 0)
            {
              sb.AppendLine($"Indirect dependents ({c.indirect_dependents.Length}):");
              foreach (var dep in c.indirect_dependents.Take(5))
                sb.AppendLine($"  - {dep}");
              if (c.indirect_dependents.Length > 5)
                sb.AppendLine($"  ... and {c.indirect_dependents.Length - 5} more");
              sb.AppendLine();
            }

            // Import dependents
            if (c.import_dependents != null && c.import_dependents.Length > 0)
            {
              sb.AppendLine($"Import dependents ({c.import_dependents.Length}):");
              foreach (var imp in c.import_dependents.Take(5))
                sb.AppendLine($"  - {imp}");
              if (c.import_dependents.Length > 5)
                sb.AppendLine($"  ... and {c.import_dependents.Length - 5} more");
              sb.AppendLine();
            }

            // Associated tests
            sb.AppendLine($"Associated tests:");
            if (c.passed_tests != null && c.passed_tests.Length > 0)
            {
              sb.AppendLine($"  Passed ({c.passed_tests.Length}):");
              foreach (var test in c.passed_tests.Take(3))
                sb.AppendLine($"    ✓ {test}");
            }
            if (c.failed_tests != null && c.failed_tests.Length > 0)
            {
              sb.AppendLine($"  Failed ({c.failed_tests.Length}):");
              foreach (var test in c.failed_tests.Take(3))
                sb.AppendLine($"    ✗ {test}");
            }
            if (c.not_run_tests != null && c.not_run_tests.Length > 0)
            {
              sb.AppendLine($"  Not run ({c.not_run_tests.Length}):");
              foreach (var test in c.not_run_tests.Take(3))
                sb.AppendLine($"    - {test}");
            }

            _impactPanel.SetBody(sb.ToString());
          }
          return true;
        case "show_approval_prompt":
          _pending = c.summary;
          return false;
        case "set_mode":
          if (!string.IsNullOrEmpty(c.mode) && (c.mode == "REPOS" || System.Array.IndexOf(NavModes, c.mode) >= 0))
            _agentMode = c.mode;
          return false;   // false: don't let the "graph changed -> MAP" fallback fire
        case "select_node":
          if (!string.IsNullOrEmpty(c.node_id) && _nodes.ContainsKey(c.node_id)) Select(c.node_id);
          return true;
        case "move_graph":
          _graphRoot.localPosition = Vector3.ClampMagnitude(_graphRoot.localPosition + new Vector3(c.dx, c.dy, c.dz), 3f);
          return false;
        case "zoom_graph":
          _graphRoot.localScale = Vector3.one * Mathf.Clamp(c.value, 0.4f, 2.2f);
          return false;
        case "move_panel":
          if (AgentMayControl(c.panel) && _panels.TryGetValue(c.panel, out JarvisSpatialPanel mpPanel) && !mpPanel.Pinned)
            mpPanel.transform.localPosition = SlotPosition(new Vector3(c.azimuth, c.elevation, c.radius));
          return false;
        case "scale_panel":
          if (AgentMayControl(c.panel) && _panels.TryGetValue(c.panel, out JarvisSpatialPanel spPanel))
            spPanel.Anim.UserScale = Mathf.Clamp(c.value, 0.5f, 2.2f);
          return false;
        case "panel_state":
          if (AgentMayControl(c.panel) && _panels.TryGetValue(c.panel, out JarvisSpatialPanel psPanel))
          {
            switch (c.state)
            {
              case "show": _agentShown.Add(c.panel); psPanel.Reopen(); psPanel.Show(true); break;
              case "hide": if (AgentMayHide(c.panel)) { _agentShown.Remove(c.panel); psPanel.Close(); } break;
              case "pin": if (!psPanel.Pinned) psPanel.TogglePin(); break;
              case "unpin": if (psPanel.Pinned) psPanel.TogglePin(); break;
              case "minimize": psPanel.SetMinimized(true); break;
              case "restore": psPanel.SetMinimized(false); break;
            }
          }
          return false;
        case "highlight_callers":
          if (!string.IsNullOrEmpty(c.node_id)) HighlightCallers(c.node_id);
          return false;
        case "recenter":
          Recenter();
          return false;
        case "reset_layout":
          ResetLayout();
          return false;
        case "open_repo":
          // The server no longer switches on its own. Go through OpenRepo -> SelectRepo -> /repos/select,
          // which is guarded server-side and calls ResetSession() on success.
          if (!string.IsNullOrEmpty(c.repo) && _bridge != null) StartCoroutine(OpenRepoWhenIdle(c.repo));
          return false;
        case "browse_folder":
          if (!string.IsNullOrEmpty(c.repo)) _browserRepo = c.repo;
          if (_openFile != null) CloseOpenFile();
          SetMode("REPOS");
          LoadRepoFolder(c.path ?? "");
          return false;
        case "open_file":
          if (!string.IsNullOrEmpty(c.repo)) _browserRepo = c.repo;
          if (!string.IsNullOrEmpty(c.path)) { _pendingOpenLine = c.line; OpenRepoFile(c.path); }
          return false;
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
      _hot.Clear(); _keep = null; _ghostDiff = null; _ghostPage = 0; _ghostSeenAll = false;
      _hasTestRun = false; _testFailed = false; _testFailureLines = null;
      _testSummary = "No test run yet.";
      foreach (NodeView n in _nodes.Values) { n.Badge = ""; n.Label.text = n.Dto.name; }
      foreach (EdgeView e in _edges) StyleEdge(e, e.Dto.kind);
      RefreshStyles();
    }

    private void OnApprove()
    {
      if (string.IsNullOrEmpty(_pending)) { Say("Nothing is waiting for approval."); return; }
      if (_approving) return;
      if (!_hasTestRun) { Say("Run the tests before approving."); return; }
      if (_testFailed) { Say("Tests are failing. Fix them before approving."); return; }
      if (!string.IsNullOrEmpty(_ghostDiff) && !_ghostSeenAll) { Say("Page through the whole diff before approving."); return; }
      _approving = true;
      Say("Committing to the sandbox branch…"); Log("approval: approve");
      _bridge.Approve(true,
        r =>
        {
          _approving = false;
          if (r != null && r.ok)
          {
            _pending = null; _lastCommitBranch = r.branch;
            Say("Committed " + r.commit + " on " + r.branch + ". Main is untouched until you press PROMOTE.");
            Log("committed " + r.commit);
          }
          else
          {
            Say("NOT committed: " + (r != null ? r.detail : "no response") + " The proposal is still pending.");
            _errorUntil = Time.unscaledTime + 4f;
          }
          RefreshAll();
        },
        err => { _approving = false; Say(err + " The proposal is still pending."); _errorUntil = Time.unscaledTime + 4f; RefreshAll(); });
    }

    private void OnReject()
    {
      if (_approving) return;
      if (string.IsNullOrEmpty(_pending))
      {
        if (!string.IsNullOrEmpty(_lastCommitBranch)) { _lastCommitBranch = null; Say("Left on the sandbox branch. Main is untouched."); RefreshAll(); }
        return;
      }
      _approving = true;
      Say("Rejecting…"); Log("approval: reject");
      _bridge.Approve(false,
        r =>
        {
          _approving = false;
          if (r != null && r.ok) { _pending = null; _ghostDiff = null; _ghostPage = 0; Say("Change rejected. Nothing was changed."); }
          else Say("Reject failed: " + (r != null ? r.detail : "no response"));
          RefreshAll();
        },
        err => { _approving = false; Say(err); RefreshAll(); });
    }

    private void OnPromote()
    {
      if (string.IsNullOrEmpty(_lastCommitBranch)) { Say("No committed change to promote."); return; }
      if (_approving) return;
      _approving = true;
      Say("Promoting " + _lastCommitBranch + " to the main checkout and re-indexing…");
      _bridge.Promote(
        r =>
        {
          _approving = false;
          if (r != null && r.ok)
          {
            _lastCommitBranch = null; _ghostDiff = null; _ghostPage = 0;
            Say("Promoted " + r.commit + ". Graph re-indexed: " + r.nodes + " nodes, " + r.edges + " edges.");
            ReloadGraph();
            RefreshTasks();
          }
          else Say("NOT promoted: " + (r != null ? r.detail : "no response"));
          RefreshAll();
        },
        err => { _approving = false; Say(err); });
    }

    private void ReloadGraph()
    {
      _bridge.GetGraph(g =>
      {
        if (g == null || g.nodes == null) return;
        string sel = _selected;
        LoadGraph(g);
        if (!string.IsNullOrEmpty(sel) && _nodes.ContainsKey(sel)) Select(sel);
        else if (g.nodes.Count > 0) Select(g.nodes[0].id);
        RefreshStatus();
        if (_openFile != null) OpenRepoFile(_openFile.path);   // viewer shows the committed text
      });
    }

    // =========================================================== text and styling

    private static string Hex(Color c) { return ColorUtility.ToHtmlStringRGB(c); }
    private static string Esc(string s) { return s.Replace("<", "<​"); }

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
      string server = _serverOnline ? "<color=#" + Hex(pal.Green) + ">server online</color>" : "<color=#" + Hex(pal.Amber) + ">server offline</color>";
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
        OnRepoActivated(name);
      });
    }

    // Scene commands arrive inside the ask callback while the bridge is still Busy; SelectRepo refuses then.
    private IEnumerator OpenRepoWhenIdle(string name)
    {
      float until = Time.unscaledTime + 10f;
      while (_bridge != null && (_bridge.Busy || _switching) && Time.unscaledTime < until) yield return null;
      OpenRepo(name);
    }

    /// <summary>Everything that happens once the server has made `name` its active repository.</summary>
    private void OnRepoActivated(string name)
    {
      if (_repos != null) _repos.active = name;
      // Design, plan and tasks belong to the previous repository's session: drop them so DESIGN reloads
      // for the new session instead of showing (and acting on) stale data.
      _design = null; _designRequested = false; _tasks = null; _designWarning = null; _lastTaskError = null;
      _chat.Clear(); _chatOffset = 0; _validated = null; RefreshChat();   // the conversation belongs to the previous repository's session
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
        int total = (file.content ?? "").Split('\n').Length;
        int pageCount = Mathf.Max(1, Mathf.CeilToInt(total / (float)EditorLinesPerPage));
        _openFilePage = Mathf.Clamp((Mathf.Max(1, _pendingOpenLine) - 1) / EditorLinesPerPage, 0, pageCount - 1);
        _pendingOpenLine = 0;
        SetMode("CODE");
        RefreshOpenFile();
        HighlightFileNodes(path);
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
      string[] hl = JarvisSyntax.HighlightLines(_openFile.content, _openFile.path);
      int pages = Mathf.Max(1, Mathf.CeilToInt(hl.Length / (float)EditorLinesPerPage));
      int first = _openFilePage * EditorLinesPerPage;
      int last = Mathf.Min(hl.Length, first + EditorLinesPerPage);
      int width = hl.Length.ToString().Length;
      var sb = new StringBuilder();
      sb.Append("<color=#").Append(Hex(JarvisPalette.Current.TextMuted)).Append(">READ-ONLY VIEW  ·  ")
        .Append(hl.Length).Append(" lines  ·  page ").Append(_openFilePage + 1).Append('/').Append(pages).Append("</color>\n\n");
      for (int i = first; i < last; i++)
      {
        sb.Append("<color=#").Append(Hex(JarvisPalette.Current.TextMuted)).Append('>')
          .Append((i + 1).ToString().PadLeft(width)).Append("</color>  ").Append(hl[i]).Append('\n');
      }
      if (_openFile.truncated) sb.Append("\n<color=#").Append(Hex(JarvisPalette.Current.Amber)).Append(">File truncated at 512 KB.</color>");
      _codePanel.SetBody(sb.ToString());
      _codePrev.gameObject.SetActive(true); _codeClose.gameObject.SetActive(true); _codeNext.gameObject.SetActive(true);
      _codePrev.Interactable = _openFilePage > 0;
      _codeNext.Interactable = _openFilePage < pages - 1;
      RefreshOutline();
    }

    private void HighlightFileNodes(string path)
    {
      _hot.Clear();
      foreach (var kv in _nodes) if (kv.Value.Dto.file == path) _hot.Add(kv.Key);
      RefreshStyles();
    }

    private void CloseOpenFile()
    {
      _openFile = null;
      _codePrev.gameObject.SetActive(false); _codeClose.gameObject.SetActive(false); _codeNext.gameObject.SetActive(false);
      RefreshCode();
      RefreshOutline();
    }

    private void RefreshActivity()
    {
      if (!_panels.ContainsKey("activity")) return;
      var sb = new StringBuilder();
      if (_tasks != null && _tasks.Length > 0)
      {
        sb.Append("<b>TASKS</b>\n");
        var doneIds = new HashSet<string>();
        foreach (TaskDto t in _tasks)
          if (t.status == "done" || t.status == "completed") doneIds.Add(t.id);
        TaskDto sel = SelectedTask();
        foreach (TaskDto t in _tasks)
        {
          bool done = doneIds.Contains(t.id);
          bool running = t.status == "running";
          bool blocked = !done && !running && t.depends_on != null &&
            System.Array.Exists(t.depends_on, d => !doneIds.Contains(d));
          string mark = done ? "[x]" : running ? "[~]" : blocked ? "[!]" : "[ ]";
          string state = done ? "done" : running ? "in progress" : blocked ? "blocked" : "ready";
          bool isSel = sel != null && sel.id == t.id;
          sb.Append(isSel ? "<color=#" + Hex(JarvisPalette.Current.Amber) + ">" : "")
            .Append(mark).Append(' ').Append(isSel ? "» " : "").Append(t.title ?? "").Append("  ").Append(state);
          if (!string.IsNullOrEmpty(t.owner)) sb.Append(" · ").Append(t.owner);
          if (isSel) sb.Append("</color>");
          sb.Append('\n');
        }
        if (_planCircular != null && _planCircular.Length > 0)
          sb.Append("<color=#").Append(Hex(JarvisPalette.Current.Amber)).Append(">circular deps: ")
            .Append(string.Join(", ", _planCircular)).Append("</color>\n");
        sb.Append('\n');
      }
      sb.Append(string.Join("\n", _log));
      _panels["activity"].SetBody(sb.ToString());
    }

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
        int dotted = _edges.Count(e => (e.From == n || e.To == n) && e.Style == "dotted");
        if (inferred > 0) sb.Append("<color=#").Append(Hex(pal.Violet)).Append(">[inferred]</color> ").Append(inferred).Append(" links\n");
        if (dotted > 0) sb.Append("<color=#").Append(Hex(pal.Green)).Append(">[ambiguous]</color> ").Append(dotted).Append(" links\n");
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
      if (_unverifiedEvidence != null && _unverifiedEvidence.Length > 0)
        sb.Append("<color=#").Append(Hex(pal.Amber)).Append("><b>UNVERIFIED CITATIONS: ")
          .Append(_unverifiedEvidence.Length).Append("</b></color>\n");
    }

    private void RefreshCode()
    {
      if (_openFile != null) { RefreshOpenFile(); return; }
      if (_codePrev != null) { _codePrev.gameObject.SetActive(false); _codeClose.gameObject.SetActive(false); _codeNext.gameObject.SetActive(false); }
      if (!_panels.ContainsKey("code")) return;
      
      JarvisPalette pal = JarvisPalette.Current;
      if (IsDesignGraph())
      {
        ComponentDto dc = FindComponent(DesignCompId(_selected));
        _panels["code"].SetTitle("Component");
        string compBody = "Select a component node.";
        if (dc != null)
          compBody = dc.name + "  ·  " + dc.kind + "\n\n" + (dc.responsibility ?? "") + "\n\n(component " + dc.id + " - edit via the node menu)";
        _panels["code"].SetBody(compBody);
        return;
      }
      if (string.IsNullOrEmpty(_selected) || !_nodes.TryGetValue(_selected, out NodeView n))
      {
        _panels["code"].SetTitle("Code inspector");
        _panels["code"].SetBody("Select a node in the graph to view its source code.");
        return;
      }
      
      if (!_source.TryGetValue(_selected, out SourceResponse s))
      {
        _panels["code"].SetTitle("Code inspector");
        _panels["code"].SetBody(n.Dto.file + "  L" + n.Dto.start + "-" + n.Dto.end + "\n\n" + (_serverOnline ? "loading source…" : "Start the JARVIS server to see live source."));
        // Trigger source fetch if not already cached
        if (_bridge != null && !_source.ContainsKey(_selected))
        {
          string selectedId = _selected; // Capture for async callback
          _bridge.GetSource(selectedId, src => {
            if (src != null && src.status == "ok") {
              _source[selectedId] = src;
              if (_selected == selectedId) RefreshCode();
            } else if (src != null && src.status == "error") {
              // Show error in the code panel
              if (_selected == selectedId) {
                _panels["code"].SetTitle("Error");
                _panels["code"].SetBody(src.error ?? "Failed to load source");
              }
            }
          });
        }
        return;
      }
      // IDE-style header with file path and language
      string fileName = System.IO.Path.GetFileName(s.file);
      string dirPath = System.IO.Path.GetDirectoryName(s.file) ?? "";
      string ext = System.IO.Path.GetExtension(s.file).ToLower();
      string lang = ext switch
      {
        ".ts" or ".tsx" or ".js" or ".jsx" => "TypeScript",
        ".py" => "Python",
        ".cs" => "C#",
        ".java" => "Java",
        ".cpp" or ".h" or ".cc" => "C++",
        ".go" => "Go",
        ".rs" => "Rust",
        _ => ext.TrimStart('.')
      };
      _panels["code"].SetTitle($"{fileName}  ·  {lang}  ·  {dirPath}");

      string[] hl = JarvisSyntax.HighlightLines(s.source, s.file);
      int width = (s.first_line + hl.Length).ToString().Length;   // pad line numbers so code starts in one column
      var sb = new StringBuilder();
      for (int i = 0; i < hl.Length && i < MaxCodeLines; i++)
        sb.Append("<color=#").Append(Hex(pal.TextMuted)).Append('>')
          .Append((s.first_line + i).ToString().PadLeft(width)).Append("</color>  ")
          .Append(hl[i]).Append('\n');
      if (hl.Length > MaxCodeLines) sb.Append("… ").Append(hl.Length - MaxCodeLines).Append(" more lines");
      _panels["code"].SetBody(sb.ToString());
    }

    private void RefreshGhost()
    {
      if (!_panels.ContainsKey("ghost")) return;
      JarvisPalette pal = JarvisPalette.Current;
      if (string.IsNullOrEmpty(_ghostDiff)) { _panels["ghost"].SetBody("No proposed change yet. Ask JARVIS to fix something."); return; }
      string[] lines = _ghostDiff.Replace("\r", "").TrimEnd('\n').Split('\n');
      int add = 0, del = 0;
      foreach (string l in lines)
      {
        if (l.StartsWith("+") && !l.StartsWith("+++")) add++;
        else if (l.StartsWith("-") && !l.StartsWith("---")) del++;
      }
      int pages = Mathf.Max(1, Mathf.CeilToInt(lines.Length / (float)GhostLinesPerPage));
      _ghostPage = Mathf.Clamp(_ghostPage, 0, pages - 1);
      if (_ghostPage == pages - 1) _ghostSeenAll = true;
      var sb = new StringBuilder();
      sb.Append("<color=#").Append(Hex(pal.TextMuted)).Append(">+").Append(add).Append("  -").Append(del)
        .Append("   page ").Append(_ghostPage + 1).Append('/').Append(pages).Append("</color>\n");
      int from = _ghostPage * GhostLinesPerPage;
      for (int i = from; i < lines.Length && i < from + GhostLinesPerPage; i++)
      {
        string l = lines[i];
        Color c = l.StartsWith("+") ? pal.Green : l.StartsWith("-") ? pal.Red : pal.TextMuted;
        sb.Append("<color=#").Append(Hex(c)).Append('>').Append(Esc(l)).Append("</color>\n");
      }
      _panels["ghost"].SetBody(sb.ToString());
    }

    private void RefreshApproval()
    {
      if (!_panels.ContainsKey("approval")) return;
      bool pending = !string.IsNullOrEmpty(_pending);
      bool promote = !string.IsNullOrEmpty(_lastCommitBranch);
      string body;
      string blockReason = null;
      if (pending)
      {
        body = _pending;
        if (!_hasTestRun) blockReason = "Run the tests before approving.";
        else if (_testFailed) blockReason = "Tests are failing. Fix them before approving.";
        else if (!string.IsNullOrEmpty(_ghostDiff) && !_ghostSeenAll) blockReason = "Page through the whole diff first.";
        if (blockReason != null) body += "\n" + blockReason;
      }
      else if (promote)
      {
        body = "Committed on " + _lastCommitBranch + ".\nPROMOTE TO MAIN applies it. REJECT leaves it on the branch.";
      }
      else body = "Nothing is waiting for approval.";

      // One slot, two states: approve/reject while a proposal is pending, promote once it is committed.
      // SetActive respects the panel's minimized state; SetMinimized re-applies ForceHidden on restore.
      bool min = _panels["approval"].Minimized;
      if (_approveBtn != null) { _approveBtn.ForceHidden = !pending; _approveBtn.gameObject.SetActive(pending && !min); _approveBtn.Interactable = pending && blockReason == null; }
      if (_rejectBtn != null) { _rejectBtn.ForceHidden = !pending; _rejectBtn.gameObject.SetActive(pending && !min); }
      if (_promoteBtn != null) { _promoteBtn.ForceHidden = !promote; _promoteBtn.gameObject.SetActive(promote && !min); }
      _panels["approval"].SetBody(body);
    }

    private void RefreshTests()
    {
      if (!_panels.ContainsKey("tests")) return;
      JarvisPalette pal = JarvisPalette.Current;
      string verdict; Color vc;
      if (!_hasTestRun) { verdict = "UNVERIFIED: no test has run for this change"; vc = pal.Amber; }
      else if (_testFailed) { verdict = "FAILED"; vc = pal.Red; }
      else { verdict = "PASSED"; vc = pal.Green; }
      string extra = "";
      if (!string.IsNullOrWhiteSpace(_agentTestResults))   // includes command, exit_code, duration_s from the live run
      {
        string t = _agentTestResults.Trim().Replace("\r", "");
        if (t.Length > 1400) t = t.Substring(0, 1399) + "…";
        extra = "\n\n<b>Test run</b>\n" + Esc(t);
      }
      if (_testFailureLines != null && _testFailureLines.Length > 0)
      {
        extra += "\n\n<b><color=#" + Hex(pal.Red) + ">Failures</color></b>\n";
        foreach (string f in _testFailureLines) extra += "• " + Esc(f) + "\n";
      }
      extra += ValidatedBlock();
      _panels["tests"].SetBody("<b><color=#" + Hex(vc) + ">" + verdict + "</color></b>\n" + _testSummary + extra);
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
      _menu = AddPanel("menu", "Node", 380, 780, 0f, 0f, JarvisSpatialFx.Magenta);
      _menu.SetBodyBox(54, 40); _menu.Body.fontSize = 20;
      _menu.AddButton("ASK ABOUT THIS", 20, 100, 340, 50, () =>
      {
        if (_nodes.TryGetValue(_menuNode ?? "", out NodeView n)) Ask("What breaks if I change " + n.Dto.name + "?");
        _menu.Show(false);
      });
      _menu.AddButton("HIGHLIGHT CALLERS", 20, 160, 340, 50, () => HighlightCallers(_menuNode));
      _menu.AddButton("COLLAPSE / EXPAND CLUSTER", 20, 220, 340, 50, ToggleCluster);
      // Architecture-design editing (only meaningful on the DESIGN graph)
      _menuAddComp = _menu.AddButton("ADD COMPONENT", 20, 280, 340, 50, MenuAddComponent);
      _menuRename = _menu.AddButton("RENAME", 20, 340, 340, 50, () => MenuTextEdit("rename"));
      _menuResp = _menu.AddButton("EDIT RESPONSIBILITY", 20, 400, 340, 50, () => MenuTextEdit("responsibility"));
      _menuDelete = _menu.AddButton("DELETE", 20, 460, 340, 50, MenuDeleteComponent);
      _menuLink = _menu.AddButton("START LINK", 20, 520, 340, 50, MenuStartLink);
      _menuDelEdge = _menu.AddButton("DELETE EDGE", 20, 580, 340, 50, MenuDeleteEdge);
      _menuCycleKind = _menu.AddButton("CYCLE EDGE KIND", 20, 640, 340, 50, MenuCycleEdgeKind);
      _menuEditLabel = _menu.AddButton("EDIT LABEL", 20, 700, 340, 50, MenuEditEdgeLabel);
      _menu.Show(false);
    }

    private void MenuAddComponent()
    {
      if (!IsDesignGraph()) { _menu.Show(false); return; }
      int n = _design != null && _design.architecture != null && _design.architecture.components != null
        ? _design.architecture.components.Length + 1 : 1;
      SendDesignEdit(new[] { new DesignEditOpDto { op = "add_component", name = "Component " + n, component_kind = "service" } }, "Added component");
      _menu.Show(false);
    }

    private void MenuTextEdit(string kind)
    {
      string compId = DesignCompId(_menuNode);
      if (compId == null) { _menu.Show(false); return; }
      _kbOp = kind; _kbOpId = compId;
      OpenKeyboard();
      _menu.Show(false);
    }

    private void MenuDeleteComponent()
    {
      string compId = DesignCompId(_menuNode);
      if (compId == null) { _menu.Show(false); return; }
      if (!_designDeleteArmed)
      {
        _designDeleteArmed = true;
        Say("Press DELETE again to remove component " + compId + ".");
        return;
      }
      _designDeleteArmed = false;
      SendDesignEdit(new[] { new DesignEditOpDto { op = "remove_component", id = compId } }, "Deleted component");
      _menu.Show(false);
    }

    private void MenuStartLink()
    {
      string compId = DesignCompId(_menuNode);
      if (compId == null) { _menu.Show(false); return; }
      if (_designLinkFrom == compId) { _designLinkFrom = null; Say("Link cancelled."); _menu.Show(false); return; }
      _designLinkFrom = compId;
      Say("Link armed from " + compId + ". Open another component and press START LINK to complete it.");
      _menu.Show(false);
    }

    private void MenuCompleteLink(string targetCompId)
    {
      if (string.IsNullOrEmpty(_designLinkFrom) || targetCompId == null || _designLinkFrom == targetCompId)
      { _designLinkFrom = null; return; }
      string src = _designLinkFrom; _designLinkFrom = null;
      SendDesignEdit(new[] { new DesignEditOpDto { op = "add_relationship", src = src, dst = targetCompId, kind = "calls" } }, "Added link");
    }

    private void MenuDeleteEdge()
    {
      if (string.IsNullOrEmpty(_menuEdgeKey) || _design?.architecture?.relationships == null) { _menu.Show(false); return; }
      RelationshipDto rel = null;
      foreach (RelationshipDto r in _design.architecture.relationships) if (r.id == _menuEdgeKey) rel = r;
      if (rel == null) { _menu.Show(false); return; }
      SendDesignEdit(new[] { new DesignEditOpDto { op = "remove_relationship", id = rel.id } }, "Deleted link");
      _menu.Show(false);
    }

    private string RelLabel(string id)
    {
      if (string.IsNullOrEmpty(id) || _design?.architecture?.relationships == null) return null;
      foreach (RelationshipDto r in _design.architecture.relationships) if (r.id == id) return r.label;
      return null;
    }

    private void MenuEditEdgeLabel()
    {
      if (string.IsNullOrEmpty(_menuEdgeKey)) { _menu.Show(false); return; }
      _kbOp = "edge_label"; _kbOpId = _menuEdgeKey;
      OpenKeyboard();
      if (_kb == null) { _kbOp = null; _kbOpId = null; Say("The keyboard did not open (JARVIS is busy, or typing is unavailable here). Try again."); }
      _menu.Show(false);
    }

    private void MenuCycleEdgeKind()
    {
      if (string.IsNullOrEmpty(_menuEdgeKey) || _design?.architecture?.relationships == null) { _menu.Show(false); return; }
      string[] kinds = { "calls", "reads", "publishes" };
      RelationshipDto rel = null;
      foreach (RelationshipDto r in _design.architecture.relationships) if (r.id == _menuEdgeKey) rel = r;
      if (rel == null) { _menu.Show(false); return; }
      int i = System.Array.IndexOf(kinds, rel.kind);
      string next = kinds[(i + 1) % kinds.Length];
      SendDesignEdit(new[] { new DesignEditOpDto { op = "update_relationship", id = rel.id, kind = next } }, "Link kind -> " + next);
      _menu.Show(false);
    }

    /// <summary>Long pinch on a node (JarvisGraphNode.Hold).</summary>
    private void ShowNodeMenu(string id)
    {
      if (_menu == null || !_nodes.TryGetValue(id, out NodeView n)) return;
      _menuNode = id;
      _menuEdgeKey = null;
      Select(id);
      bool design = IsDesignGraph() && IsDesignNode(id);
      _menu.SetTitle(n.Dto.name);
      _menu.SetBody(n.Cluster.Name + " · " + n.Dto.kind);
      Vector3 toCam = (_cam.transform.position - n.Root.position).normalized;
      _menu.transform.position = n.Root.position + Vector3.up * 0.22f + toCam * 0.12f;
      // Design editing buttons only on architecture component nodes; edge buttons only on edges.
      foreach (JarvisSpatialButton b in new[] { _menuAddComp, _menuRename, _menuResp, _menuDelete, _menuLink })
        if (b != null) { b.ForceHidden = !design; b.gameObject.SetActive(design); }
      foreach (JarvisSpatialButton b in new[] { _menuDelEdge, _menuCycleKind, _menuEditLabel })
        if (b != null) { b.ForceHidden = true; b.gameObject.SetActive(false); }
      if (_menuLink != null)
      {
        string compId = DesignCompId(id);
        if (_designLinkFrom != null && compId != null && _designLinkFrom != compId)
        {
          _menuLink.Label.text = "COMPLETE LINK";
          _menuLink.OnClick = () => { MenuCompleteLink(compId); _menu.Show(false); };
        }
        else
        {
          _menuLink.Label.text = _designLinkFrom == compId ? "CANCEL LINK" : "START LINK";
          _menuLink.OnClick = MenuStartLink;
        }
      }
      _menu.Reopen();
      _menu.Show(true);
    }

    /// <summary>Long press on an edge: in DESIGN mode offers delete / cycle kind for architecture links.</summary>
    private void ShowEdgeMenu(EdgeView edge)
    {
      if (_menu == null || edge?.Dto == null) return;
      if (!IsDesignGraph() || string.IsNullOrEmpty(edge.Dto.edge_id)) { Debug.Log("Edge held: " + EdgeKey(edge.Dto)); return; }
      _menuEdgeKey = edge.Dto.edge_id;
      _menuNode = null;
      _menu.SetTitle("Link " + edge.Dto.src + " > " + edge.Dto.dst);
      string relLabel = RelLabel(edge.Dto.edge_id);
      _menu.SetBody("kind: " + (edge.Dto.kind ?? "?") + "  ·  " + edge.Dto.type + "\nlabel: " + (string.IsNullOrEmpty(relLabel) ? "(none)" : relLabel));
      Vector3 mid = (edge.From.Root.position + edge.To.Root.position) * 0.5f;
      Vector3 toCam = (_cam.transform.position - mid).normalized;
      _menu.transform.position = mid + Vector3.up * 0.15f + toCam * 0.12f;
      foreach (JarvisSpatialButton b in new[] { _menuAddComp, _menuRename, _menuResp, _menuDelete, _menuLink })
        if (b != null) { b.ForceHidden = true; b.gameObject.SetActive(false); }
      foreach (JarvisSpatialButton b in new[] { _menuDelEdge, _menuCycleKind, _menuEditLabel })
        if (b != null) { b.ForceHidden = false; b.gameObject.SetActive(true); }
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
      string focusId = n.Dto.id;
      _menu.Show(false);
      if (!cv.Collapsed) { SetClusterCollapsed(cv, true); return; }
      SetClusterCollapsed(cv, false);
      if (_bridge != null && !IsDesignNode(focusId))
        _bridge.GetGraphWithFocus(focusId, 2, g => { if (g != null && g.nodes != null) MergeGraph(g); },
          e => Say("Could not fetch more of the graph: " + e));
    }

    private void MergeGraph(GraphDto extra)
    {
      var haveN = new HashSet<string>(); foreach (var x in _graph.nodes) haveN.Add(x.id);
      var haveE = new HashSet<string>(); foreach (var x in _graph.edges) haveE.Add(EdgeKey(x));
      var touched = new HashSet<string>();
      int addedN = 0, addedE = 0;
      foreach (var x in extra.nodes)
        if (haveN.Add(x.id)) { _graph.nodes.Add(x); addedN++; touched.Add(string.IsNullOrEmpty(x.cluster) ? "other" : x.cluster); }
      if (extra.edges != null)
        foreach (var x in extra.edges) if (haveE.Add(EdgeKey(x))) { _graph.edges.Add(x); addedE++; }
      if (addedN + addedE == 0) { Say("Nothing more to expand here."); return; }

      var open = new HashSet<string>(touched);              // LoadGraph collapses every cluster, so remember what was open
      foreach (var kv in _clusters) if (!kv.Value.Collapsed) open.Add(kv.Key);
      var ev = _agentEvidence; var tr = _agentTestResults; var ue = _unverifiedEvidence;
      string sel = _selected;

      LoadGraph(_graph);

      _agentEvidence = ev; _agentTestResults = tr; _unverifiedEvidence = ue;   // same repository: keep them
      foreach (string name in open)
        if (_clusters.TryGetValue(name, out ClusterView c)) SetClusterCollapsed(c, false);
      if (!string.IsNullOrEmpty(sel) && _nodes.ContainsKey(sel)) Select(sel);
      RefreshAll();
      Log("expanded: +" + addedN + " nodes, +" + addedE + " edges");
    }

    private void SetClusterCollapsed(ClusterView cv, bool collapsed)
    {
      cv.Collapsed = collapsed;
      for (int i = 1; i < cv.Members.Count; i++)   // member 0 stays as the cluster anchor
      {
        bool vis = !collapsed && NodePasses(cv.Members[i].Dto);
        cv.Members[i].Fx.SetShown(vis);
        cv.Members[i].Label.gameObject.SetActive(vis);
      }
      RefreshEdgeVisibility();
    }

    // The agent may move and resize most panels, but never the approve/reject panel.
    private static bool AgentMayControl(string key) { return !string.IsNullOrEmpty(key) && key != "approval"; }
    private static bool AgentMayHide(string key) { return AgentMayControl(key) && key != "nav" && key != "status" && key != "caption"; }

    private void ResetLayout()
    {
      foreach (KeyValuePair<string, JarvisSpatialPanel> kv in _panels)
      {
        kv.Value.Reopen();
        kv.Value.SetMinimized(false);
        kv.Value.Anim.UserScale = 1f;
        if (!kv.Value.Pinned && Slots.TryGetValue(kv.Key, out Vector3 slot)) kv.Value.transform.localPosition = SlotPosition(slot);
      }
      _agentShown.Clear();
      ResetGraphView();
      Recenter();
    }

    private void RefreshEdgeVisibility()
    {
      foreach (EdgeView e in _edges)
        if (e.Line != null) e.Line.gameObject.SetActive(e.From.Fx.Shown && e.To.Fx.Shown && EdgePasses(e.Dto));
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
      var orbBtn = go.AddComponent<JarvisSpatialButton>();
      orbBtn.OnPress = VoiceDown;    // hold the orb pinch to talk; release to send
      orbBtn.OnRelease = VoiceUp;

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

    // =========================================================== conversation history

    private void AddChat(bool developer, string text)
    {
      if (string.IsNullOrWhiteSpace(text)) return;
      _chat.Add((developer ? "Y|" : "J|") + text.Trim());
      while (_chat.Count > ChatMaxEntries) _chat.RemoveAt(0);
      _chatOffset = 0;   // jump to the newest message
      RefreshChat();
    }

    private static string ChatClip(string entry)
    {
      string body = entry.Length > 2 ? entry.Substring(2).Replace("\r", "").Replace("\n", " ") : "";
      return body.Length > 280 ? body.Substring(0, 279) + "…" : body;
    }

    private void RefreshChat()
    {
      if (!_panels.ContainsKey("chat")) return;
      JarvisPalette pal = JarvisPalette.Current;
      if (_chat.Count == 0) { _panels["chat"].SetBody("No messages yet.\nPress TYPE or hold the orb and speak."); _chatShown = 0; return; }
      _chatOffset = Mathf.Clamp(_chatOffset, 0, _chat.Count - 1);
      int end = _chat.Count - _chatOffset, start = end, used = 0;
      while (start > 0)
      {
        int len = ChatClip(_chat[start - 1]).Length + 8;
        if (used + len > 600 && start < end) break;
        used += len; start--;
      }
      _chatShown = end - start;
      var sb = new StringBuilder();
      sb.Append("<color=#").Append(Hex(pal.TextMuted)).Append('>').Append(start + 1).Append('-').Append(end)
        .Append(" of ").Append(_chat.Count).Append("</color>\n");
      for (int i = start; i < end; i++)
      {
        bool dev = _chat[i].StartsWith("Y|");
        sb.Append("<b><color=#").Append(Hex(dev ? pal.Cyan : pal.Violet)).Append('>').Append(dev ? "YOU" : "JARVIS").Append("</color></b>  ")
          .Append(Esc(ChatClip(_chat[i]))).Append('\n');
      }
      _panels["chat"].SetBody(sb.ToString());
    }

    // =========================================================== file outline

    private static bool IsFunctionNode(GraphNodeDto d)
    {
      string k = d.kind ?? "";
      return k == "function" || k == "method" || (d.level == "function" && k != "object");
    }

    private static bool IsClassNode(GraphNodeDto d)
    {
      string k = d.kind ?? "";
      return k == "class" || k == "object" || d.level == "class";
    }

    /// <summary>Classes and functions of the open file (or of the selected node's file), in source order, from the loaded graph.</summary>
    private List<GraphNodeDto> OutlineSymbols(out string file)
    {
      file = _openFile != null ? _openFile.path
        : (!string.IsNullOrEmpty(_selected) && _nodes.TryGetValue(_selected, out NodeView sel) && !IsDesignNode(_selected) ? sel.Dto.file : null);
      var list = new List<GraphNodeDto>();
      if (string.IsNullOrEmpty(file) || _graph == null || _graph.nodes == null) return list;
      foreach (GraphNodeDto d in _graph.nodes)
        if (d.file == file && (IsFunctionNode(d) || IsClassNode(d))) list.Add(d);
      list.Sort((a, b) => a.start.CompareTo(b.start));
      return list;
    }

    private void RefreshOutline()
    {
      if (!_panels.ContainsKey("outline")) return;
      JarvisPalette pal = JarvisPalette.Current;
      List<GraphNodeDto> syms = OutlineSymbols(out string file);
      if (string.IsNullOrEmpty(file)) { _panels["outline"].SetBody("Open a file in the repository browser, or select a node, to list its classes and functions."); return; }
      if (syms.Count == 0) { _panels["outline"].SetBody(Esc(file) + "\n\nNo indexed classes or functions in this file."); return; }
      _outlineSel = (_outlineSel % syms.Count + syms.Count) % syms.Count;
      const int rows = 8;
      int first = (_outlineSel / rows) * rows;
      var sb = new StringBuilder();
      sb.Append("<color=#").Append(Hex(pal.TextMuted)).Append('>').Append(Esc(file)).Append("  ·  ").Append(_outlineSel + 1).Append('/').Append(syms.Count).Append("</color>\n");
      for (int i = first; i < syms.Count && i < first + rows; i++)
      {
        GraphNodeDto d = syms[i];
        string row = (IsClassNode(d) ? "class " : "fn    ") + Esc(d.name ?? "?") + "  L" + d.start;
        if (i == _outlineSel) sb.Append("<b><color=#").Append(Hex(pal.Cyan)).Append(">> ").Append(row).Append("</color></b>\n");
        else sb.Append("   ").Append(row).Append('\n');
      }
      _panels["outline"].SetBody(sb.ToString());
    }

    /// <summary>Jump to the highlighted symbol: scroll the file to its line and select its graph node; optionally open the MAP.</summary>
    private void OutlineGo(bool showInMap)
    {
      List<GraphNodeDto> syms = OutlineSymbols(out string file);
      if (syms.Count == 0) { Say("Nothing to jump to: no indexed symbols for this file."); return; }
      _outlineSel = (_outlineSel % syms.Count + syms.Count) % syms.Count;
      GraphNodeDto d = syms[_outlineSel];
      if (_openFile != null && d.start > 0) _openFilePage = Mathf.Max(0, (d.start - 1) / EditorLinesPerPage);
      Select(d.id);
      if (_openFile != null) RefreshOpenFile();
      if (showInMap) SetMode("MAP");
      Say((showInMap ? "Showing " : "Selected ") + d.name + " (line " + d.start + ").");
    }

    // =========================================================== graph filters and view

    private static readonly string[] KindFilters = { "ALL", "FILES", "FUNCTIONS", "CLASSES" };

    private bool NodePasses(GraphNodeDto d)
    {
      if (_kindFilter == 0 || d == null || IsDesignGraph()) return true;
      string k = d.kind ?? "";
      if (_kindFilter == 1) return k == "file" || k == "module";
      if (_kindFilter == 2) return IsFunctionNode(d);
      return IsClassNode(d);
    }

    private static string EdgeKindOf(GraphEdgeDto d) { return !string.IsNullOrEmpty(d.type) ? d.type : d.kind; }

    private bool EdgePasses(GraphEdgeDto d) { return _edgeFilter == null || IsDesignGraph() || EdgeKindOf(d) == _edgeFilter; }

    private void ApplyFilters()
    {
      foreach (NodeView n in _nodes.Values)
      {
        bool anchor = n.Cluster != null && n.Cluster.Members.Count > 0 && n.Cluster.Members[0] == n;
        bool vis = NodePasses(n.Dto) && (n.Cluster == null || !n.Cluster.Collapsed || anchor);
        n.Fx.SetShown(vis);
        n.Label.gameObject.SetActive(vis);
      }
      _edgesDirty = true;
      RefreshEdgeVisibility();
    }

    private void CycleKindFilter()
    {
      _kindFilter = (_kindFilter + 1) % KindFilters.Length;
      if (_kindFilterBtn != null && _kindFilterBtn.Label != null) _kindFilterBtn.Label.text = "FILTER: " + KindFilters[_kindFilter];
      ApplyFilters();
      Say("Showing " + KindFilters[_kindFilter].ToLowerInvariant() + ".");
    }

    private void CycleEdgeFilter()
    {
      var kinds = new List<string>();
      foreach (EdgeView e in _edges) { string k = EdgeKindOf(e.Dto); if (!string.IsNullOrEmpty(k) && !kinds.Contains(k)) kinds.Add(k); }
      kinds.Sort();
      int i = _edgeFilter == null ? -1 : kinds.IndexOf(_edgeFilter);
      _edgeFilter = i + 1 < kinds.Count ? kinds[i + 1] : null;
      if (_edgeFilterBtn != null && _edgeFilterBtn.Label != null)
      {
        string t = _edgeFilter ?? "ALL";
        _edgeFilterBtn.Label.text = "EDGE: " + (t.Length > 9 ? t.Substring(0, 9) : t);
      }
      RefreshEdgeVisibility();
      Say(_edgeFilter == null ? "Showing every relationship type." : "Showing only '" + _edgeFilter + "' relationships.");
    }

    private void RotateGraph(float degrees)
    {
      if (_graphRoot == null) return;
      _graphRoot.localRotation = Quaternion.Euler(0f, degrees, 0f) * _graphRoot.localRotation;
    }

    private void ResetGraphView()
    {
      if (_graphRoot == null) return;
      _graphRoot.localPosition = new Vector3(0f, 0.05f, 0f);
      _graphRoot.localScale = Vector3.one * 0.85f;
      _graphRoot.localRotation = Quaternion.identity;
    }

    // =========================================================== settings, exit, runtime trace, validation identity

    private void OpenSettings()
    {
      if (_settingsPanel == null) return;
      RefreshSettings();
      _settingsPanel.Reopen();
      _settingsPanel.Show(true);
    }

    private void RefreshSettings()
    {
      if (_settingsPanel == null) return;
      JarvisServerSettings cfg = JarvisServerSettings.Load();
      string url = cfg != null ? cfg.ServerUrl : "(no settings asset)";
      string token = cfg != null && !string.IsNullOrEmpty(cfg.Token) && cfg.Token != "dev-token" ? "set" : "MISSING or default";
      string repo = _health != null && !string.IsNullOrEmpty(_health.repo) ? _health.repo : "-";
      _settingsPanel.SetBody("Server   " + url + (_serverOnline ? "  (online)" : "  (OFFLINE)") + "\n"
        + "Token    " + token + "\n"
        + "Repo     " + repo + "\n"
        + "Mode     " + _mode + "\n"
        + "Voice    " + (_voiceEnabled ? "on" : "off") + "\n\n"
        + "URL and token are edited in Unity: JARVIS > Server.");
    }

    private void ToggleVoiceEnabled()
    {
      _voiceEnabled = !_voiceEnabled;
      if (_voiceBtn != null && _voiceBtn.Label != null) _voiceBtn.Label.text = "VOICE: " + (_voiceEnabled ? "ON" : "OFF");
      RefreshSettings();
    }

    /// <summary>Return to project selection (the repository list) without closing the app.</summary>
    private void ExitToProjects()
    {
      if (_settingsPanel != null) _settingsPanel.Show(false);
      _openFile = null;
      ReturnToRepoList();
      foreach (JarvisSpatialPanel p in _panels.Values) p.Reopen();
      SetMode("REPOS");
      Say("Back at project selection. Pick a repository to continue.");
    }

    private void QuitApp()
    {
      if (!_quitArmed)
      {
        _quitArmed = true;
        if (_quitBtn != null && _quitBtn.Label != null) _quitBtn.Label.text = "CONFIRM?";
        Say("Press QUIT APP again to close JARVIS.");
        return;
      }
#if UNITY_EDITOR
      UnityEditor.EditorApplication.isPlaying = false;
#else
      Application.Quit();
#endif
    }

    /// <summary>Runtime tracing belongs to the testing agent; this only asks for it. Results come back as the normal answer,
    /// highlighted nodes and evidence. Nothing is shown unless the trace actually returned it.</summary>
    private void RunRuntimeTrace()
    {
      if (_bridge == null) return;
      AskAgent("Use the testing agent to start a runtime trace, run the project's tests, stop the trace and report which functions executed and in what order. "
        + "Highlight the executed functions in the graph. Report only what the trace returned, and say so plainly if runtime tracing is not supported for this repository.");
    }

    private string ValidatedBlock()
    {
      if (_validated == null || (string.IsNullOrEmpty(_validated.branch) && (_validated.files == null || _validated.files.Length == 0))) return "";
      JarvisPalette pal = JarvisPalette.Current;
      var sb = new StringBuilder("\n\n<b>Validated change</b>\n");
      if (!string.IsNullOrEmpty(_validated.task_id)) sb.Append("task: ").Append(Esc(_validated.task_id)).Append('\n');
      if (!string.IsNullOrEmpty(_validated.branch)) sb.Append("branch: ").Append(Esc(_validated.branch)).Append('\n');
      sb.Append("+").Append(_validated.additions).Append(" -").Append(_validated.deletions).Append('\n');
      if (_validated.files != null)
        for (int i = 0; i < _validated.files.Length; i++)
        {
          if (i >= 6) { sb.Append("  + ").Append(_validated.files.Length - 6).Append(" more files\n"); break; }
          sb.Append("• ").Append(Esc(_validated.files[i])).Append('\n');
        }
      if (_lastTestRun != null && !string.IsNullOrEmpty(_lastTestRun.diff_hash) && !string.IsNullOrEmpty(_validated.diff_hash))
      {
        bool same = _lastTestRun.diff_hash == _validated.diff_hash;
        sb.Append("<color=#").Append(Hex(same ? pal.Green : pal.Red)).Append('>')
          .Append(same ? "tests ran on exactly this diff" : "DIFF CHANGED since the tests ran: results do not cover it").Append("</color>\n");
      }
      else sb.Append("<color=#").Append(Hex(pal.Amber)).Append(">no test run is linked to this diff</color>\n");
      return sb.ToString();
    }

    // =========================================================== loop

    private void Update()
    {
      if (_kb != null && _kb.status != TouchScreenKeyboard.Status.Visible)
      {
        if (_kb.status == TouchScreenKeyboard.Status.Done)
        {
          string t = _kb.text != null ? _kb.text.Trim() : "";
          if (_kbOp != null) { ApplyDesignTextOp(t); _kbOp = null; _kbOpId = null; }
          else if (t.Length > 0) { Ask(t); Say("Sent."); }
          else Say("Nothing to send.");
        }
        else if (_kb.status == TouchScreenKeyboard.Status.Canceled) Say("Typing cancelled.");
        _kb = null;
      }
      AnimateOrb();
      if (_edgesDirty) { RedrawEdges(); UpdateClusters(); }
      if (CurrentOrb() == OrbState.Thinking && Time.unscaledTime > _progressAt)
      {
        _progressAt = Time.unscaledTime + 1f;
        _bridge.GetProgress(_progressSeen, p => { foreach (var s in p.steps) { Log(s.agent + " working"); _progressSeen = s.i + 1; } });
      }
      if (Time.unscaledTime > _taskAt)
      {
        _taskAt = Time.unscaledTime + 2f;
        RefreshTasks();
      }
    }
  }
}
