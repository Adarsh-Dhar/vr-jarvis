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
  }
  [Serializable] public class AskResponse
  {
    public string reply, error, pending_approval, test_results, test_source;
    public bool approved;
    public List<SceneCommand> scene_commands;
    public string[] evidence;
  }
  [Serializable] public class SourceResponse { public string status, id, file, source, error; public int first_line; }
  [Serializable] public class ApproveResponse { public bool ok; public string branch, commit, detail; }
  [Serializable] internal class SessionResponse { public string session_id; }
  [Serializable] internal class AskRequest { public string session_id, text, selection; }
  [Serializable] internal class ApproveRequest { public string session_id; public bool approved; }

  // Field names match ai_agents/data/graph.json and the server's /health JSON.
  [Serializable] public class GraphNodeDto { public string id, name, file, cluster, kind; public int start, end; }
  [Serializable] public class GraphEdgeDto { public string src, dst, type, kind; }
  [Serializable] public class GraphDto
  {
    public System.Collections.Generic.List<GraphNodeDto> nodes = new System.Collections.Generic.List<GraphNodeDto>();
    public System.Collections.Generic.List<GraphEdgeDto> edges = new System.Collections.Generic.List<GraphEdgeDto>();
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
    public int TimeoutSeconds = 120;   // keep above JARVIS_ASK_TIMEOUT (110) on the server

    private string _session;
    public bool Busy { get; private set; }
    private string Url => PlayerPrefs.GetString("jarvis.server", DefaultServerUrl).TrimEnd('/');

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

    public void GetGraph(Action<GraphDto> ok) =>
      StartCoroutine(Send("GET", "/graph", null, b => ok(JsonUtility.FromJson<GraphDto>(b)), e => Debug.LogWarning("JARVIS graph: " + e)));

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
        if (!string.IsNullOrEmpty(Token)) req.SetRequestHeader("Authorization", "Bearer " + Token);
        req.timeout = TimeoutSeconds;
        yield return req.SendWebRequest();
        if (req.result != UnityWebRequest.Result.Success)
          fail(req.responseCode == 401 ? "Unauthorized: token mismatch." : "Cannot reach JARVIS at " + Url + " (" + req.error + ")");
        else ok(req.downloadHandler.text);
      }
    }
  }
}
