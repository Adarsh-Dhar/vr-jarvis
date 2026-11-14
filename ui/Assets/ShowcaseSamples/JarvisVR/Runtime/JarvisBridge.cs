using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace JarvisVR
{
  // Field names match the server JSON exactly (JsonUtility is case-sensitive and ignores unknown fields).
  [Serializable] public class SceneCommand
  {
    public string type, color, node_id, src, dst, style, diff, summary, mode;
    public string repo, path, panel, state;
    public string[] node_ids, keep_ids, passed, failed, not_run, failure_lines;
    public int depth, line;
    public float dx, dy, dz, value, azimuth, elevation, radius;
    public bool collapsed;
    public string text;
    public GraphNodeDto[] nodes;
    public GraphEdgeDto[] edges;
    public string graph_type;
    public string title;
    public string test_mapping, risk_basis;
    // Impact panel fields
    public string[] direct_callers, indirect_dependents, possible_callers, import_dependents;
    public string[] passed_tests, failed_tests, not_run_tests;
  }
  /// <summary>The exact change a test/review run was about (server reads it from the sandbox worktree).</summary>
  [Serializable] public class ValidatedDto { public string task_id, branch, diff_hash; public string[] files; public int additions, deletions; }
  [Serializable] public class AskResponse
  {
    public string reply, error, pending_approval, test_results, test_source;
    public bool approved, duplicate;
    public List<SceneCommand> scene_commands;
    public string[] evidence;
    public string[] unverified_evidence;
    public string[] tool_errors;
    public string task_id, proposal_status;
    public ValidatedDto validated;
    public EvidenceItemDto[] evidence_items;
    public ActiveTaskDto active_task;
    public TestRunDto test_run;
  }
  [Serializable] public class EvidenceItemDto
  {
    public string node_id, file, kind;
    public int first_line, last_line;
  }
  [Serializable] public class ActiveTaskDto
  {
    public string id, title, description, component_id, repo, repo_match;
    public string[] files, acceptance_criteria, depends_on, symbols_flat;
    public int design_revision;
    public bool needs_investigation;
  }
  [Serializable] public class TestRunDto
  {
    public string status, source, runner, command, error, diff_hash, head;
    public int exit_code;
    public float duration_s;
    public string[] passed, failed_ids, skipped, checks_not_run;
  }
  [Serializable] public class ProgressStep { public int i; public string agent, kind; }
  [Serializable] public class ProgressDto { public bool busy; public List<ProgressStep> steps; }
  [Serializable] internal class TranscribeRequest { public string audio_base64, mime; }
  [Serializable] internal class TranscribeResponse { public string text, error; }
  [Serializable] public class SourceResponse { public string status, id, file, source, error; public int first_line; }
  [Serializable] public class ApproveResponse { public bool ok; public string branch, commit, detail; }
  [Serializable] public class PromoteResponse { public bool ok, graph_refreshed; public string commit, detail; public int nodes, edges; }
  [Serializable] internal class PromoteRequest { public string session_id, repo; }
  [Serializable] public class SymbolDto { public string id, name, file; }
  [Serializable] public class EvidenceCheckItemDto { public string claim, status, detail; }
  [Serializable] public class EvidenceCheckDto { public string verdict; public EvidenceCheckItemDto[] checks; }
  [Serializable] public class TaskDto
  {
    public string id, title, status;
    public string[] depends_on;
    public string component_id, acceptance, owner, evidence;
    public string[] files, acceptance_criteria, suggested_files, confirmed_targets;
    public RejectedTargetDto[] rejected_targets;
    public SymbolDto[] symbols;
    public string repo_match, description;
    public EvidenceCheckDto evidence_check;
    public int design_revision;
    public bool cycle_accepted, needs_investigation, modifies_existing;
    public string cycle_rationale;
    public string[] new_files;
  }
  [Serializable] public class RejectedTargetDto { public string file, reason; }
  [Serializable] public class TaskCompletionDto
  {
    public string branch, commit, typecheck, diff_hash;
    public int design_revision;
    public TestRunDto test_run;
  }

  // ---- architecture design workflow (server /design and /plan endpoints)
  [Serializable] public class RequirementsDto
  {
    public string[] goals, functional, non_functional, constraints, assumptions, open_questions;
  }
  [Serializable] public class ComponentDto
  {
    public string id, name, responsibility, kind;
    public string[] requirement_ids;
  }
  [Serializable] public class RelationshipDto { public string id, src, dst, kind, label; }
  [Serializable] public class ResolvedQuestionDto { public string question, answer, reason; public int revision; }
  [Serializable] public class ArchitectureDto
  {
    public int version, revision, approved_version, approved_revision;
    public string status, approved_by, provenance, requirements_source;   // 'model' | 'heuristic' | 'unknown' | 'stored'
    public bool edited_by_user;
    public ComponentDto[] components;
    public RelationshipDto[] relationships;
    public string[] open_questions, deferred_questions_flat;
    public ResolvedQuestionDto[] resolved_questions, deferred_questions;
  }
  [Serializable] public class CompareCandidateDto { public string node; public float score; }
  [Serializable] public class CompareItemDto
  {
    public string id, name, node, evidence;
    public float score;
    public string confidence;
    public bool ambiguous;
    public CompareCandidateDto[] candidates;
  }
  [Serializable] public class CompareRelDto { public string id, src, dst, kind, status, evidence; }
  [Serializable] public class CompareDto
  {
    public string status, repo;
    public int design_revision;
    public bool stale;
    public CompareItemDto[] matched, missing, ambiguous, extra;
    public CompareRelDto[] relationships;
  }
  [Serializable] public class ImplementationPlanDto
  {
    public int architecture_version, architecture_revision;
    public string status, repo;
    public TaskDto[] tasks;
    public string[] circular;        // component ids whose dependencies form a cycle
    public string[] cycle_paths;     // ordered paths like "c3>c5>c3"
  }
  [Serializable] public class DesignStateDto
  {
    public RequirementsDto requirements;
    public ArchitectureDto architecture;
    public CompareDto compare;
    public ImplementationPlanDto plan;
  }
  [Serializable] public class DesignProposeResponse
  {
    public string status, error, provenance, requirements_source, warning;
    public RequirementsDto requirements;
    public ArchitectureDto architecture;
  }
  [Serializable] public class DesignEditResponse { public bool ok; public string detail; public ArchitectureDto architecture; }
  [Serializable] public class DesignEditOpDto
  {
    public string op, id, src, dst, kind, label, name, responsibility, component_kind;
    public string[] requirement_ids;
    public string question, new_question, answer;   // open-question ops: resolve/update/add
  }
  [Serializable] internal class DesignSessionRequest { public string session_id; public string idea_text; }
  [Serializable] internal class DesignEditRequest { public string session_id; public DesignEditOpDto[] ops; }
  [Serializable] internal class DesignApproveRequest { public string session_id; public bool approved; public string approved_by; }
  [Serializable] internal class PlanSessionRequest { public string session_id; }
  [Serializable] internal class PlanTaskPatchRequest { public string status, title, evidence, cycle_rationale, request_id; public bool accept_cycles; }
  [Serializable] public class AgentResultDto { public string agent, summary, status; public float confidence; }
  [Serializable] public class TaskResponse { public bool busy; public string plan_summary; public TaskDto[] tasks; public string[] circular; public AgentResultDto[] agent_results; public string[] findings; }
  [Serializable] internal class SessionResponse { public string session_id; }
  [Serializable] internal class AskRequest { public string session_id, text, selection, repo, task_id, request_id; }
  [Serializable] internal class ApproveRequest { public string session_id; public bool approved; public string repo, request_id; }

  // Field names match ai_agents/data/graph.json and the server's /health JSON.
  // Call-graph fields (callsite_id, resolution, confidence, ...) are optional:
  // graphs emitted before schema v3 simply leave them null/0.
  // Control-flow and data-flow fields (node_kind, variable, expression, ast_kind, edge_kind, condition, evidence) are optional.
  [Serializable] public class GraphNodeDto
  {
    public string id, name, file, cluster, kind, level, parent, type, detail;
    public string qualname, class_name, language, signature;
    public int start, end, count;
    // Control-flow and data-flow metadata (optional)
    public string node_kind, variable, expression, ast_kind, function_id;
    public int column;
    // Graph-analysis metadata (optional)
    public string severity, confidence, evidence;
    public int line;
  }
  [Serializable] public class GraphEdgeDto
  {
    public string src, dst, type, kind, file;
    public int line;
    // schema v3 call-graph metadata (all optional)
    public string callsite_id, resolution, resolution_method, reason, call_type;
    public string edge_id;
    public int column;
    public float confidence;
    public string[] candidates;
    // Control-flow and data-flow metadata (optional)
    public string edge_kind, condition;
    public string evidence;  // JSON string of evidence dict
  }
  [Serializable] public class GraphDto
  {
    public System.Collections.Generic.List<GraphNodeDto> nodes = new System.Collections.Generic.List<GraphNodeDto>();
    public System.Collections.Generic.List<GraphEdgeDto> edges = new System.Collections.Generic.List<GraphEdgeDto>();
    public string graph_type;
  }
  [Serializable] public class RepoInfoDto { public string name, branch; public int files; }
  [Serializable] public class ReposDto { public string active; public System.Collections.Generic.List<RepoInfoDto> repos = new System.Collections.Generic.List<RepoInfoDto>(); }
  [Serializable] public class RepoTreeEntryDto { public string name, path, type; public long size; }
  [Serializable] public class RepoTreeDto
  {
    public string repo, path;
    public System.Collections.Generic.List<RepoTreeEntryDto> entries = new System.Collections.Generic.List<RepoTreeEntryDto>();
  }
  [Serializable] public class RepoFileDto
  {
    public string status, repo, path, content, error;
    public long size;
    public int total_lines;
    public bool truncated;
  }

  [Serializable] internal class RepoSelectRequest { public string name; }
  [Serializable] internal class RepoSelectResponse { public string active; public bool session_reset_required; }
  [Serializable] public class HealthDto { public bool ok, cached_tests; public string repo, branch; public int changed; }

  // ---- workspace editing: human edits inside the sandbox worktree ----
  // Field names match the /workspace/* JSON exactly (snake_case).
  [Serializable] public class SyntaxErrorDto { public int line, col; public string message; }
  [Serializable] public class WsSymbolDto { public string name, kind, file, signature; public int start, end, line; }
  [Serializable] public class WsOpenDto { public bool ok, dirty; public string worktree_name, branch, detail; }
  [Serializable] public class WsFileDto
  {
    public string status, path, content, hash, source, error;
    public bool truncated;
    public long size;
    public int total_lines;
  }
  [Serializable] public class WsEditResponse
  {
    public bool ok, duplicate, conflict, reverted;
    public string hash, detail, current_hash, current_content, verification;
    public int lines, size;
    public SyntaxErrorDto[] syntax_errors;
    public WsSymbolDto[] symbols;
  }
  [Serializable] public class WsVerificationDto { public string tests, typecheck, review, security; }
  [Serializable] public class WsStatusDto
  {
    public bool ok, busy, worktree, dirty;
    public string[] files;
    public string diff_hash, head;
    public WsVerificationDto verification;
  }
  [Serializable] public class WsDiffDto
  {
    public bool ok, worktree;
    public string diff, branch, diff_hash;
    public string[] files;
    public int additions, deletions;
  }
  [Serializable] public class WsTypecheckDto
  {
    public string status, typecheck, command, source, checker, language, note, diff_hash, head;
    public int exit_code;
    public string[] errors;
  }
  [Serializable] public class WsSecurityFindingDto
  {
    public string rule_id, category, severity, file, title, evidence, description, remediation, confidence;
    public int line;
    public bool introduced_by_current_change;
  }
  [Serializable] public class WsSecurityDto
  {
    public string status, scanner, scanner_version, ruleset_version, error, diff_hash;
    public int files_scanned;
    public WsSecurityFindingDto[] findings;
  }
  [Serializable] public class WsVerifyDto
  {
    public bool ok, duplicate;
    public TestRunDto test_run;
    public WsTypecheckDto typecheck;
    public WsSecurityDto security_scan;
    public WsVerificationDto verification;
    public string detail;
  }
  [Serializable] public class WsReviewDto
  {
    public bool ok, duplicate;
    public string source, verdict, summary;
    public string[] blockers;
    public string detail;
  }
  [Serializable] public class WsSubmitDto
  {
    public bool ok, duplicate;
    public string pending_approval, detail;
    public string[] blockers;
    public WsDiffDto review;
  }
  [Serializable] internal class WsSessionRequest { public string session_id, repo; }
  [Serializable] internal class WsSubmitRequest { public string session_id, repo, request_id; }
  [Serializable] internal class WsPathRequest { public string session_id, path, repo, request_id; }
  [Serializable] internal class WsEditRequest
  {
    public string session_id, path, op, text, base_hash, repo, request_id;
    public int start, end;
  }
  [Serializable] internal class WsVerifyRequest
  {
    public string session_id, repo, request_id;
    public string[] steps, test_files;
  }

  /// <summary>What the spatial workspace needs from a backend. Implemented by JarvisBridge.</summary>
  public interface IJarvisBackend
  {
    bool Busy { get; }
    void Ask(string text, string selection, Action<AskResponse> ok, Action<string> fail, string taskId = null);
    void Approve(bool approved, Action<ApproveResponse> ok, Action<string> fail);
    void Promote(Action<PromoteResponse> ok, Action<string> fail);
    void GetTask(Action<TaskResponse> ok);
    void GetSource(string nodeId, Action<SourceResponse> ok);
    void GetHealth(Action<HealthDto> ok, Action<string> fail);
    void GetGraph(Action<GraphDto> ok);
    void GetGraphWithFocus(string focusId, int depth, Action<GraphDto> ok, Action<string> fail);
    void GetRepos(Action<ReposDto> ok, Action<string> fail);
    void GetTree(string repo, string path, Action<RepoTreeDto> ok, Action<string> fail);
    void GetFile(string repo, string path, Action<RepoFileDto> ok, Action<string> fail);
    void SelectRepo(string name, Action<bool> done);
    void GetProgress(int since, Action<ProgressDto> ok);
    void Transcribe(byte[] wav, Action<string> ok, Action<string> fail);
    void DesignPropose(string ideaText, Action<DesignProposeResponse> ok, Action<string> fail);
    void GetDesign(Action<DesignStateDto> ok, Action<string> fail);
    void DesignEdit(DesignEditOpDto[] ops, Action<DesignEditResponse> ok, Action<string> fail);
    void DesignCompare(Action<CompareDto> ok, Action<string> fail, Dictionary<string, string> overrideMatches = null);
    void DesignApprove(bool approved, Action<ArchitectureDto> ok, Action<string> fail);
    void PlanGenerate(Action<ImplementationPlanDto> ok, Action<string> fail);
    void PlanUpdateTask(string taskId, string status, Action<bool> ok, Action<string> fail,
                        string evidence = null, bool acceptCycles = false, string cycleRationale = null);
    void WorkspaceOpen(Action<WsOpenDto> ok, Action<string> fail);
    void WorkspaceGetFile(string path, Action<WsFileDto> ok, Action<string> fail);
    void WorkspaceEditLines(string path, string op, int start, int end, string text, string baseHash,
                            Action<WsEditResponse> ok, Action<string> fail);
    void WorkspaceRevert(string path, Action<WsEditResponse> ok, Action<string> fail);
    void WorkspaceDiff(Action<WsDiffDto> ok, Action<string> fail);
    void WorkspaceStatus(Action<WsStatusDto> ok, Action<string> fail);
    void WorkspaceVerify(string[] testFiles, Action<WsVerifyDto> ok, Action<string> fail);
    void WorkspaceReview(Action<WsReviewDto> ok, Action<string> fail);
    void WorkspaceSubmit(Action<WsSubmitDto> ok, Action<string> fail);
  }

  /// <summary>HTTP client for server/jarvis_server.py. On a Quest, 127.0.0.1 is the headset itself:
  /// set the PC's LAN IP via PlayerPrefs key "jarvis.server" (or DefaultServerUrl) and use the same token as JARVIS_TOKEN.</summary>
  public sealed class JarvisBridge : MonoBehaviour, IJarvisBackend
  {
    public static string DefaultServerUrl = "http://127.0.0.1:8000";
    public string Token = "";
    public int TimeoutSeconds = 180;   // keep above JARVIS_ASK_TIMEOUT (170) on the server

    private string _session;
    private int _reqSeq;
    private string NewRequestId() => "u" + (++_reqSeq) + "-" + DateTime.UtcNow.Ticks.ToString("x");
    /// <summary>Active repository name, kept in sync from /repos and /repos/select. Sent with ask/approve so the
    /// server can reject calls made against a stale repository (409).</summary>
    public string ActiveRepo = "";
    public bool Busy { get; private set; }
    private static JarvisServerSettings _settings;
    private static JarvisServerSettings Settings
    {
      get { if (_settings == null) _settings = JarvisServerSettings.Load(); return _settings; }
    }

    /// <summary>Server address. Order: PlayerPrefs "jarvis.server" (Editor override) > JarvisServerSettings asset > DefaultServerUrl.</summary>
    public static string ResolveUrl()
    {
      string v = PlayerPrefs.GetString("jarvis.server", "");
      if (string.IsNullOrEmpty(v)) v = Settings != null && !string.IsNullOrEmpty(Settings.ServerUrl) ? Settings.ServerUrl : DefaultServerUrl;
      return v.TrimEnd('/');
    }

    /// <summary>Shared secret. Order: PlayerPrefs "jarvis.token" > JarvisServerSettings asset. Must equal JARVIS_TOKEN on the server.</summary>
    public static string ResolveToken()
    {
      string t = PlayerPrefs.GetString("jarvis.token", "");
      if (!string.IsNullOrEmpty(t)) return t;
      return Settings != null && Settings.Token != null ? Settings.Token : "";
    }

    private string Url => ResolveUrl();

    public void Ask(string text, string selection, Action<AskResponse> ok, Action<string> fail, string taskId = null)
    {
      if (Busy) { fail("JARVIS is still working on the previous request."); return; }
      StartCoroutine(AskRoutine(text, selection, taskId, ok, fail));
    }

    public void Approve(bool approved, Action<ApproveResponse> ok, Action<string> fail) =>
      StartCoroutine(ApproveRoutine(approved, ok, fail));

    public void GetSource(string nodeId, Action<SourceResponse> ok) => StartCoroutine(SourceRoutine(nodeId, ok));

    public void GetHealth(Action<HealthDto> ok, Action<string> fail) =>
      StartCoroutine(Send("GET", "/health", null, b => ok(JsonUtility.FromJson<HealthDto>(b)), fail));

    public void GetRepos(Action<ReposDto> ok, Action<string> fail) =>
      StartCoroutine(Send("GET", "/repos", null, b =>
      {
        var r = JsonUtility.FromJson<ReposDto>(b);
        if (r != null) ActiveRepo = r.active ?? "";
        ok(r);
      }, fail));

    public void GetTree(string repo, string path, Action<RepoTreeDto> ok, Action<string> fail)
    {
      string url = "/repos/" + UnityWebRequest.EscapeURL(repo) + "/tree";
      if (!string.IsNullOrEmpty(path)) url += "?path=" + UnityWebRequest.EscapeURL(path);
      StartCoroutine(Send("GET", url, null, b =>
      {
        try { ok(JsonUtility.FromJson<RepoTreeDto>(b)); }
        catch (Exception ex) { fail("Invalid repository tree response: " + ex.Message); }
      }, fail));
    }

    public void GetFile(string repo, string path, Action<RepoFileDto> ok, Action<string> fail)
    {
      string url = "/repos/" + UnityWebRequest.EscapeURL(repo) + "/file?path=" + UnityWebRequest.EscapeURL(path);
      StartCoroutine(Send("GET", url, null, b =>
      {
        try { ok(JsonUtility.FromJson<RepoFileDto>(b)); }
        catch (Exception ex) { fail("Invalid file response: " + ex.Message); }
      }, fail));
    }

    /// <summary>Sessions are bound to one repository on the server. Drop ours so the next call opens a fresh
    /// session for the active repository instead of failing with HTTP 409.</summary>
    public void ResetSession() { _session = null; }

    public void SelectRepo(string name, Action<bool> done)
    {
      if (Busy) { Debug.LogWarning("JARVIS select repo: an ask is running."); done(false); return; }
      StartCoroutine(Send("POST", "/repos/select", JsonUtility.ToJson(new RepoSelectRequest { name = name }),
        b =>
        {
          ActiveRepo = name;
          ResetSession();   // the server refused the switch if work was unfinished, so this one is safe to drop
          done(true);
        },
        e => { Debug.LogWarning("JARVIS select repo: " + e); done(false); }));
    }

    /// <summary>Speech to text on the server. wav = 16 kHz mono 16-bit PCM WAV bytes.</summary>
    public void Transcribe(byte[] wav, Action<string> ok, Action<string> fail)
    {
      string body = JsonUtility.ToJson(new TranscribeRequest { audio_base64 = Convert.ToBase64String(wav), mime = "audio/wav" });
      StartCoroutine(Send("POST", "/transcribe", body, b =>
      {
        var r = JsonUtility.FromJson<TranscribeResponse>(b);
        if (r != null && !string.IsNullOrEmpty(r.error)) fail(r.error); else ok(r != null ? r.text : "");
      }, e => fail(e)));
    }

    public void GetGraph(Action<GraphDto> ok) =>
      StartCoroutine(Send("GET", "/graph", null, b => ok(JsonUtility.FromJson<GraphDto>(b)), e => Debug.LogWarning("JARVIS graph: " + e)));

    public void GetGraphWithFocus(string focusId, int depth, Action<GraphDto> ok, Action<string> fail)
    {
      string url = "/graph?focus=" + UnityWebRequest.EscapeURL(focusId) + "&depth=" + depth;
      StartCoroutine(Send("GET", url, null, b => ok(JsonUtility.FromJson<GraphDto>(b)), fail));
    }

    public void GetProgress(int since, Action<ProgressDto> ok) =>
      StartCoroutine(Send("GET", "/progress/" + _session + "?since=" + since, null,
        b => ok(JsonUtility.FromJson<ProgressDto>(b)), e => { }));

    private IEnumerator EnsureSession(Action<string> fail)
    {
      if (!string.IsNullOrEmpty(_session)) yield break;
      string body = null;
      yield return Send("POST", "/session", "{}", b => body = b, fail);
      if (body != null) _session = JsonUtility.FromJson<SessionResponse>(body).session_id;
    }

    private IEnumerator AskRoutine(string text, string selection, string taskId, Action<AskResponse> ok, Action<string> fail)
    {
      Busy = true;
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (!failed)
      {
        string json = JsonUtility.ToJson(new AskRequest { session_id = _session, text = text, selection = selection ?? "", repo = ActiveRepo, task_id = taskId ?? "", request_id = NewRequestId() });
        yield return Send("POST", "/ask", json, b =>
        {
          try { ok(JsonUtility.FromJson<AskResponse>(b)); }
          catch (Exception ex) { fail("Bad response: " + ex.Message); }
        }, fail);
      }
      Busy = false;
    }

    private IEnumerator ApproveRoutine(bool approved, Action<ApproveResponse> ok, Action<string> fail)
    {
      if (string.IsNullOrEmpty(_session)) { fail("No active session."); yield break; }
      string json = JsonUtility.ToJson(new ApproveRequest { session_id = _session, approved = approved, repo = ActiveRepo, request_id = NewRequestId() });
      yield return Send("POST", "/approve", json, b => ok(JsonUtility.FromJson<ApproveResponse>(b)), fail);
    }

    public void Promote(Action<PromoteResponse> ok, Action<string> fail) => StartCoroutine(PromoteRoutine(ok, fail));

    private IEnumerator PromoteRoutine(Action<PromoteResponse> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new PromoteRequest { session_id = _session, repo = ActiveRepo });
      yield return Send("POST", "/promote", json, b => ok(JsonUtility.FromJson<PromoteResponse>(b)), fail);
    }

    public void GetTask(Action<TaskResponse> ok)
    {
      if (string.IsNullOrEmpty(_session)) { ok(null); return; }
      StartCoroutine(Send("GET", "/task/" + _session, null, b => ok(JsonUtility.FromJson<TaskResponse>(b)), e => { }));
    }

    // ---- architecture design workflow

    public void DesignPropose(string ideaText, Action<DesignProposeResponse> ok, Action<string> fail) =>
      StartCoroutine(DesignProposeRoutine(ideaText, ok, fail));

    private IEnumerator DesignProposeRoutine(string ideaText, Action<DesignProposeResponse> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new DesignSessionRequest { session_id = _session, idea_text = ideaText ?? "" });
      yield return Send("POST", "/design/propose", json, b => ok(JsonUtility.FromJson<DesignProposeResponse>(b)), fail);
    }

    public void GetDesign(Action<DesignStateDto> ok, Action<string> fail) =>
      StartCoroutine(DesignGetRoutine(ok, fail));

    private IEnumerator DesignGetRoutine(Action<DesignStateDto> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      yield return Send("GET", "/design/" + _session, null, b => ok(JsonUtility.FromJson<DesignStateDto>(b)), fail);
    }

    public void DesignEdit(DesignEditOpDto[] ops, Action<DesignEditResponse> ok, Action<string> fail) =>
      StartCoroutine(DesignEditRoutine(ops, ok, fail));

    private IEnumerator DesignEditRoutine(DesignEditOpDto[] ops, Action<DesignEditResponse> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new DesignEditRequest { session_id = _session, ops = ops ?? new DesignEditOpDto[0] });
      yield return Send("POST", "/design/" + _session + "/edit", json, b => ok(JsonUtility.FromJson<DesignEditResponse>(b)), fail);
    }

    public void DesignCompare(Action<CompareDto> ok, Action<string> fail, Dictionary<string, string> overrideMatches = null) =>
      StartCoroutine(DesignCompareRoutine(ok, fail, overrideMatches));

    private IEnumerator DesignCompareRoutine(Action<CompareDto> ok, Action<string> fail, Dictionary<string, string> overrideMatches)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      // override_matches is a bare JSON object {component_id: node_id}; repo picks the graph to compare against.
      string url = "/design/" + _session + "/compare";
      if (!string.IsNullOrEmpty(ActiveRepo)) url += "?repo=" + UnityWebRequest.EscapeURL(ActiveRepo);
      yield return Send("POST", url, OverridesJson(overrideMatches), b => ok(JsonUtility.FromJson<CompareDto>(b)), fail);
    }

    private static string OverridesJson(Dictionary<string, string> m)
    {
      if (m == null || m.Count == 0) return "{}";
      var sb = new StringBuilder("{");
      bool first = true;
      foreach (KeyValuePair<string, string> kv in m)
      {
        if (!first) sb.Append(',');
        first = false;
        sb.Append(JsonUtility.ToJson(kv.Key)).Append(':').Append(JsonUtility.ToJson(kv.Value ?? ""));
      }
      return sb.Append('}').ToString();
    }

    public void DesignApprove(bool approved, Action<ArchitectureDto> ok, Action<string> fail) =>
      StartCoroutine(DesignApproveRoutine(approved, ok, fail));

    private IEnumerator DesignApproveRoutine(bool approved, Action<ArchitectureDto> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new DesignApproveRequest { session_id = _session, approved = approved, approved_by = "quest-user" });
      yield return Send("POST", "/design/" + _session + "/approve", json,
        b => { var r = JsonUtility.FromJson<DesignEditResponse>(b); ok(r != null ? r.architecture : null); }, fail);
    }

    public void PlanGenerate(Action<ImplementationPlanDto> ok, Action<string> fail) =>
      StartCoroutine(PlanGenerateRoutine(ok, fail));

    private IEnumerator PlanGenerateRoutine(Action<ImplementationPlanDto> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new PlanSessionRequest { session_id = _session });
      yield return Send("POST", "/plan/generate", json, b => ok(JsonUtility.FromJson<ImplementationPlanDto>(b)), fail);
    }

    public void PlanUpdateTask(string taskId, string status, Action<bool> ok, Action<string> fail,
                               string evidence = null, bool acceptCycles = false, string cycleRationale = null)
    {
      if (string.IsNullOrEmpty(_session)) { fail("No active session."); return; }
      StartCoroutine(PlanUpdateRoutine(taskId, status, evidence, acceptCycles, cycleRationale, ok, fail));
    }

    private IEnumerator PlanUpdateRoutine(string taskId, string status, string evidence, bool acceptCycles,
                                          string cycleRationale, Action<bool> ok, Action<string> fail)
    {
      string json = JsonUtility.ToJson(new PlanTaskPatchRequest
        { status = status, title = null, evidence = evidence, accept_cycles = acceptCycles,
          cycle_rationale = cycleRationale ?? "", request_id = NewRequestId() });
      yield return Send("PATCH", "/plan/" + _session + "/tasks/" + UnityWebRequest.EscapeURL(taskId), json,
        b => ok(true), fail);
    }

    // ---- workspace editing: human edits inside the sandbox worktree ----

    public void WorkspaceOpen(Action<WsOpenDto> ok, Action<string> fail) =>
      StartCoroutine(WsOpenRoutine(ok, fail));

    private IEnumerator WsOpenRoutine(Action<WsOpenDto> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new WsSessionRequest { session_id = _session, repo = ActiveRepo });
      yield return Send("POST", "/workspace/open", json, b => ok(JsonUtility.FromJson<WsOpenDto>(b)), fail);
    }

    public void WorkspaceGetFile(string path, Action<WsFileDto> ok, Action<string> fail)
    {
      StartCoroutine(WsGetRoutine("/workspace/file", "path", path, ok, fail));
    }

    public void WorkspaceEditLines(string path, string op, int start, int end, string text, string baseHash,
                                  Action<WsEditResponse> ok, Action<string> fail) =>
      StartCoroutine(WsEditRoutine(path, op, start, end, text, baseHash, ok, fail));

    private IEnumerator WsEditRoutine(string path, string op, int start, int end, string text, string baseHash,
                                      Action<WsEditResponse> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      // end is a plain int: callers pass end == start for single-line ops
      // (JsonUtility cannot send a null/absent field the way int? would need).
      string json = JsonUtility.ToJson(new WsEditRequest
      {
        session_id = _session, path = path ?? "", op = op ?? "", start = start, end = end,
        text = text ?? "", base_hash = baseHash ?? "", repo = ActiveRepo,
        request_id = NewRequestId()
      });
      yield return Send("POST", "/workspace/edit", json,
        b => ok(JsonUtility.FromJson<WsEditResponse>(b)), fail);
    }

    public void WorkspaceRevert(string path, Action<WsEditResponse> ok, Action<string> fail) =>
      StartCoroutine(WsRevertRoutine(path, ok, fail));

    private IEnumerator WsRevertRoutine(string path, Action<WsEditResponse> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new WsPathRequest
      { session_id = _session, path = path ?? "", repo = ActiveRepo, request_id = NewRequestId() });
      yield return Send("POST", "/workspace/revert", json,
        b => ok(JsonUtility.FromJson<WsEditResponse>(b)), fail);
    }

    public void WorkspaceDiff(Action<WsDiffDto> ok, Action<string> fail) =>
      StartCoroutine(WsGetRoutine("/workspace/diff", null, null, ok, fail));

    public void WorkspaceStatus(Action<WsStatusDto> ok, Action<string> fail) =>
      StartCoroutine(WsGetRoutine("/workspace/status", null, null, ok, fail));

    public void WorkspaceVerify(string[] testFiles, Action<WsVerifyDto> ok, Action<string> fail) =>
      StartCoroutine(WsVerifyRoutine(testFiles, ok, fail));

    private IEnumerator WsVerifyRoutine(string[] testFiles, Action<WsVerifyDto> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new WsVerifyRequest
      {
        session_id = _session, repo = ActiveRepo, request_id = NewRequestId(),
        steps = null, test_files = testFiles ?? new string[0]
      });
      yield return Send("POST", "/workspace/verify", json,
        b => ok(JsonUtility.FromJson<WsVerifyDto>(b)), fail);
    }

    public void WorkspaceReview(Action<WsReviewDto> ok, Action<string> fail) =>
      StartCoroutine(WsReviewRoutine(ok, fail));

    private IEnumerator WsReviewRoutine(Action<WsReviewDto> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new WsPathRequest
      { session_id = _session, path = null, repo = ActiveRepo, request_id = NewRequestId() });
      yield return Send("POST", "/workspace/review", json,
        b => ok(JsonUtility.FromJson<WsReviewDto>(b)), fail);
    }

    public void WorkspaceSubmit(Action<WsSubmitDto> ok, Action<string> fail) =>
      StartCoroutine(WsSubmitRoutine(ok, fail));

    private IEnumerator WsSubmitRoutine(Action<WsSubmitDto> ok, Action<string> fail)
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string json = JsonUtility.ToJson(new WsSubmitRequest
      { session_id = _session, repo = ActiveRepo, request_id = NewRequestId() });
      yield return Send("POST", "/workspace/submit", json,
        b => ok(JsonUtility.FromJson<WsSubmitDto>(b)), fail);
    }

    /// <summary>GET a /workspace/* endpoint. extraParam/extraValue add one query
    /// parameter (e.g. path=...) when the route needs it.</summary>
    private IEnumerator WsGetRoutine<T>(string route, string extraParam, string extraValue,
                                        Action<T> ok, Action<string> fail) where T : class
    {
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (failed) yield break;
      string url = route + "?session_id=" + UnityWebRequest.EscapeURL(_session ?? "");
      if (!string.IsNullOrEmpty(ActiveRepo)) url += "&repo=" + UnityWebRequest.EscapeURL(ActiveRepo);
      if (!string.IsNullOrEmpty(extraParam))
        url += "&" + extraParam + "=" + UnityWebRequest.EscapeURL(extraValue ?? "");
      yield return Send("GET", url, null,
        b => { try { ok(JsonUtility.FromJson<T>(b)); } catch (Exception ex) { fail("Bad response: " + ex.Message); } },
        fail);
    }

    private IEnumerator SourceRoutine(string nodeId, Action<SourceResponse> ok)
    {
      yield return Send("GET", "/source/" + UnityWebRequest.EscapeURL(nodeId), null,
        b => ok(JsonUtility.FromJson<SourceResponse>(b)), e => Debug.LogWarning("JARVIS source: " + e));
    }

    private IEnumerator Send(string method, string path, string json, Action<string> ok, Action<string> fail)
    {
      using (var req = new UnityWebRequest(Url + path, method))
      {
        if (json != null) { req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)); req.SetRequestHeader("Content-Type", "application/json"); }
        req.downloadHandler = new DownloadHandlerBuffer();
        string token = !string.IsNullOrEmpty(Token) ? Token : ResolveToken();
        if (!string.IsNullOrEmpty(token)) req.SetRequestHeader("Authorization", "Bearer " + token);
        req.timeout = TimeoutSeconds;
        yield return req.SendWebRequest();
        if (req.result != UnityWebRequest.Result.Success)
        {
          string detail = req.downloadHandler != null && req.downloadHandler.text != null ? req.downloadHandler.text : "";
          if (detail.Length > 300) detail = detail.Substring(0, 300);
          if (req.responseCode == 401)
            fail("Unauthorized: the token must equal JARVIS_TOKEN on the server (Resources/JarvisServerSettings).");
          else if (req.responseCode >= 400)
            fail("JARVIS " + req.responseCode + ": " + detail);
          else
            fail("Cannot reach JARVIS at " + Url + " (" + req.error + ")");
        }
        else ok(req.downloadHandler.text);
      }
    }
  }
}
