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
    public string type, color, node_id, src, dst, style, diff, summary;
    public string[] node_ids, keep_ids, passed, failed, not_run;
    public int depth;
    public string scope;
    public string group_id;
    public string text;
    public string label;
    public string node_id1, node_id2;
    public GraphNodeDto[] nodes;
    public GraphEdgeDto[] edges;
    public string graph_type;
    public string title;
    // Impact panel fields
    public string[] direct_callers, indirect_dependents, possible_callers, import_dependents;
    public string[] passed_tests, failed_tests, not_run_tests;
    // Security panel fields
    public SecurityFindingDto[] findings;
    public TaintPathDto[] taint_paths;
  }

  [Serializable] public class SecurityFindingDto
  {
    public string id, type, severity, file, evidence, confidence;
    public int line;
  }

  [Serializable] public class TaintPathDto
  {
    public string id, kind;
    public TaintSourceDto source;
    public TaintSinkDto sink;
  }

  [Serializable] public class TaintSourceDto
  {
    public int line;
    public string call, kind, variable;
  }

  [Serializable] public class TaintSinkDto
  {
    public int line;
    public string call, kind;
    public string[] tainted_variables;
  }
  [Serializable] public class AskResponse
  {
    public string reply, error, pending_approval, test_results, test_source;
    public bool approved;
    public List<SceneCommand> scene_commands;
    public string[] evidence;
  }
  [Serializable] public class ProgressStep { public int i; public string agent, kind; }
  [Serializable] public class ProgressDto { public bool busy; public List<ProgressStep> steps; }
  [Serializable] internal class TranscribeRequest { public string audio_base64, mime; }
  [Serializable] internal class TranscribeResponse { public string text, error; }
  [Serializable] public class SourceResponse { public string status, id, file, source, error; public int first_line; }
  [Serializable] public class ApproveResponse { public bool ok; public string branch, commit, detail; }
  [Serializable] internal class SessionResponse { public string session_id; }
  [Serializable] internal class AskRequest { public string session_id, text, selection; }
  [Serializable] internal class ApproveRequest { public string session_id; public bool approved; }

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
  [Serializable] public class HealthDto { public bool ok, cached_tests; public string repo, branch; public int changed; }

  /// <summary>HTTP client for server/jarvis_server.py. On a Quest, 127.0.0.1 is the headset itself:
  /// set the PC's LAN IP via PlayerPrefs key "jarvis.server" (or DefaultServerUrl) and use the same token as JARVIS_TOKEN.</summary>
  public sealed class JarvisBridge : MonoBehaviour, IJarvisBackend
  {
    public static string DefaultServerUrl = "http://127.0.0.1:8000";
    public string Token = "";
    public int TimeoutSeconds = 180;   // keep above JARVIS_ASK_TIMEOUT (170) on the server

    private string _session;
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

    public void Ask(string text, string selection, Action<AskResponse> ok, Action<string> fail)
    {
      if (Busy) { fail("JARVIS is still working on the previous request."); return; }
      StartCoroutine(AskRoutine(text, selection, ok, fail));
    }

    public void Approve(bool approved, Action<ApproveResponse> ok, Action<string> fail) =>
      StartCoroutine(ApproveRoutine(approved, ok, fail));

    public void GetSource(string nodeId, Action<SourceResponse> ok) => StartCoroutine(SourceRoutine(nodeId, ok));

    public void GetHealth(Action<HealthDto> ok, Action<string> fail) =>
      StartCoroutine(Send("GET", "/health", null, b => ok(JsonUtility.FromJson<HealthDto>(b)), fail));

    public void GetRepos(Action<ReposDto> ok, Action<string> fail) =>
      StartCoroutine(Send("GET", "/repos", null, b => ok(JsonUtility.FromJson<ReposDto>(b)), fail));

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

    public void SelectRepo(string name, Action<bool> done) =>
      StartCoroutine(Send("POST", "/repos/select", JsonUtility.ToJson(new RepoSelectRequest { name = name }), b => done(true),
        e => { Debug.LogWarning("JARVIS select repo: " + e); done(false); }));

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

    private IEnumerator AskRoutine(string text, string selection, Action<AskResponse> ok, Action<string> fail)
    {
      Busy = true;
      bool failed = false;
      yield return EnsureSession(e => { failed = true; fail(e); });
      if (!failed)
      {
        string json = JsonUtility.ToJson(new AskRequest { session_id = _session, text = text, selection = selection ?? "" });
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
      string json = JsonUtility.ToJson(new ApproveRequest { session_id = _session, approved = approved });
      yield return Send("POST", "/approve", json, b => ok(JsonUtility.FromJson<ApproveResponse>(b)), fail);
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
          fail(req.responseCode == 401 ? "Unauthorized: the token must equal JARVIS_TOKEN on the server (Resources/JarvisServerSettings)." : "Cannot reach JARVIS at " + Url + " (" + req.error + ")");
        else ok(req.downloadHandler.text);
      }
    }
  }
}
