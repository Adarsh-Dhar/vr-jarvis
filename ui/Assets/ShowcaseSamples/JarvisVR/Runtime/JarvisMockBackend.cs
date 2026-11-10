using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace JarvisVR
{
  /// <summary>What the spatial workspace needs from a backend. Implemented by JarvisBridge (real server) and JarvisMockBackend (UI-only).</summary>
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
    void DesignCompare(Action<CompareDto> ok, Action<string> fail);
    void DesignApprove(bool approved, Action<ArchitectureDto> ok, Action<string> fail);
    void PlanGenerate(Action<ImplementationPlanDto> ok, Action<string> fail);
    void PlanUpdateTask(string taskId, string status, Action<bool> ok, Action<string> fail,
                        string evidence = null, bool acceptCycles = false);
  }

  /// <summary>Local, network-free backend with scripted answers for UI development. Uses the ids of JarvisGraphModel.Sample().</summary>
  public sealed class JarvisMockBackend : MonoBehaviour, IJarvisBackend
  {
    public bool Busy { get; private set; }

    private static readonly Dictionary<string, SourceResponse> Sources = new Dictionary<string, SourceResponse>
    {
      { "route.delete", Src("route.delete", "routes/account.ts", 12,
        "router.delete('/account/:id', requireAuth, async (req, res) => {\n  await deleteAccount(req.params.id, req.user);\n  res.status(204).end();\n});") },
      { "auth.require", Src("auth.require", "auth/requireAuth.ts", 4,
        "export function requireAuth(req, res, next) {\n  if (!req.user) return res.status(401).end();\n  next();\n}") },
      { "service.delete", Src("service.delete", "services/account.ts", 30,
        "export async function deleteAccount(id, actor) {\n  // TODO: checkOwner(actor, id) is not called here\n  await users.delete(id);\n  await audit.log('account.delete', id);\n}") },
      { "auth.owner", Src("auth.owner", "auth/owner.ts", 8,
        "export function checkOwner(actor, id) {\n  return actor.id === id || actor.role === 'admin';\n}") },
      { "db.delete", Src("db.delete", "db/users.repo.ts", 44,
        "async delete(id) {\n  return this.db.run('DELETE FROM users WHERE id = ?', [id]);\n}") },
      { "db.repo", Src("db.repo", "db/users.repo.ts", 1,
        "export const users = {\n  find, insert, delete: del,\n};") },
      { "test.own-account", Src("test.own-account", "tests/account.test.ts", 5,
        "it('deletes own account', async () => {\n  const res = await api.delete('/account/' + me.id);\n  expect(res.status).toBe(204);\n});") },
    };

    private static SourceResponse Src(string id, string file, int first, string code)
    {
      return new SourceResponse { status = "ok", id = id, file = file, first_line = first, source = code };
    }

    public void GetHealth(Action<HealthDto> ok, Action<string> fail)
    {
      StartCoroutine(After(0.15f, () => ok(new HealthDto { ok = true, cached_tests = true, repo = "demo-repo (mock)", branch = "main", changed = 3 })));
    }

    public void GetRepos(Action<ReposDto> ok, Action<string> fail)
    {
      var r = new ReposDto { active = "demo-repo (mock)" };
      r.repos.Add(new RepoInfoDto { name = "demo-repo (mock)", branch = "main", files = 7 });
      StartCoroutine(After(0.1f, () => ok(r)));
    }

    public void SelectRepo(string name, Action<bool> done) { StartCoroutine(After(0.1f, () => done(true))); }

    public void Transcribe(byte[] wav, Action<string> ok, Action<string> fail)
    {
      StartCoroutine(After(0.4f, () => ok("What breaks if I change deleteAccount?")));   // scripted: the mock graph is the demo repo
    }

    public void GetTree(string repo, string path, Action<RepoTreeDto> ok, Action<string> fail)
    {
      var tree = new RepoTreeDto { repo = repo, path = path ?? "" };
      string folder = (path ?? "").Trim('/');
      if (folder == "")
      {
        AddDir(tree, "auth"); AddDir(tree, "db"); AddDir(tree, "routes"); AddDir(tree, "services"); AddDir(tree, "tests");
        AddFile(tree, "README.md", 650);
      }
      else if (folder == "auth") { AddFile(tree, "requireAuth.ts", 320); AddFile(tree, "owner.ts", 250); }
      else if (folder == "db") { AddFile(tree, "users.repo.ts", 410); }
      else if (folder == "routes") { AddFile(tree, "account.ts", 720); }
      else if (folder == "services") { AddFile(tree, "account.ts", 540); }
      else if (folder == "tests") { AddFile(tree, "account.test.ts", 380); }
      else { fail("Folder not found in mock repository: " + folder); return; }
      StartCoroutine(After(0.08f, () => ok(tree)));
    }

    private static void AddDir(RepoTreeDto tree, string name) => tree.entries.Add(new RepoTreeEntryDto
      { name = name, path = string.IsNullOrEmpty(tree.path) ? name : tree.path + "/" + name, type = "directory" });
    private static void AddFile(RepoTreeDto tree, string name, long size) => tree.entries.Add(new RepoTreeEntryDto
      { name = name, path = string.IsNullOrEmpty(tree.path) ? name : tree.path + "/" + name, type = "file", size = size });

    public void GetFile(string repo, string path, Action<RepoFileDto> ok, Action<string> fail)
    {
      string normalized = (path ?? "").Replace('\\', '/');
      SourceResponse source = null;
      foreach (SourceResponse candidate in Sources.Values)
        if (candidate.file == normalized) { source = candidate; break; }
      string content = source != null ? source.source : normalized == "README.md"
        ? "# Demo repository\n\nThis is a read-only mock file browser.\n\nOpen a source file from the repository tree to inspect it."
        : null;
      if (content == null) { fail("Mock file not found: " + normalized); return; }
      StartCoroutine(After(0.08f, () => ok(new RepoFileDto
      {
        status = "ok", repo = repo, path = normalized, content = content,
        size = content.Length, total_lines = content.Split('\n').Length, truncated = false
      })));
    }

    public void GetGraph(Action<GraphDto> ok) { StartCoroutine(After(0.2f, () => ok(JarvisGraphModel.Sample()))); }

    public void GetGraphWithFocus(string focusId, int depth, Action<GraphDto> ok, Action<string> fail)
    {
      // For mock, just return the sample graph filtered by focus
      var sample = JarvisGraphModel.Sample();
      var filtered = new GraphDto();
      
      // Find the focus node
      GraphNodeDto focusNode = null;
      foreach (var node in sample.nodes)
      {
        if (node.id == focusId || node.name == focusId)
        {
          focusNode = node;
          break;
        }
      }
      
      if (focusNode == null)
      {
        fail("Node not found: " + focusId);
        return;
      }
      
      // Add focus node
      filtered.nodes.Add(focusNode);
      
      // Add connected nodes up to depth
      var includedIds = new HashSet<string> { focusNode.id };
      var currentDepth = new Dictionary<string, int> { { focusNode.id, 0 } };
      var frontier = new HashSet<string> { focusNode.id };
      
      for (int d = 0; d < depth; d++)
      {
        var nextFrontier = new HashSet<string>();
        foreach (var edge in sample.edges)
        {
          string otherId = null;
          if (edge.src == focusNode.id || includedIds.Contains(edge.src))
          {
            otherId = edge.dst;
          }
          else if (edge.dst == focusNode.id || includedIds.Contains(edge.dst))
          {
            otherId = edge.src;
          }
          
          if (otherId != null && !includedIds.Contains(otherId))
          {
            includedIds.Add(otherId);
            currentDepth[otherId] = currentDepth.GetValueOrDefault(edge.src, 0) + 1;
            nextFrontier.Add(otherId);
            filtered.edges.Add(edge);
            
            // Add the node
            foreach (var node in sample.nodes)
            {
              if (node.id == otherId)
              {
                filtered.nodes.Add(node);
                break;
              }
            }
          }
        }
        frontier = nextFrontier;
      }
      
      StartCoroutine(After(0.2f, () => ok(filtered)));
    }

    public void GetProgress(int since, Action<ProgressDto> ok)
    {
      var dto = new ProgressDto { busy = Busy, steps = new List<ProgressStep>() };
      if (since < 2)
      {
        dto.steps.Add(new ProgressStep { i = 0, agent = "jarvis_orchestrator", kind = "start" });
        dto.steps.Add(new ProgressStep { i = 1, agent = "investigate_pipeline", kind = "start" });
      }
      StartCoroutine(After(0.05f, () => ok(dto)));
    }

    public void GetSource(string nodeId, Action<SourceResponse> ok)
    {
      StartCoroutine(After(0.1f, () => { if (Sources.TryGetValue(nodeId, out SourceResponse s)) ok(s); }));
    }

    public void Approve(bool approved, Action<ApproveResponse> ok, Action<string> fail)
    {
      StartCoroutine(After(0.6f, () => ok(approved
        ? new ApproveResponse { ok = true, branch = "jarvis/mock-sandbox", commit = "a1b2c3d" }
        : new ApproveResponse { ok = true, detail = "rejected" })));
    }

    public void Promote(Action<PromoteResponse> ok, Action<string> fail)
    {
      StartCoroutine(After(0.6f, () => ok(new PromoteResponse { ok = true, graph_refreshed = true, commit = "a1b2c3d", nodes = 7, edges = 6 })));
    }

    public void GetTask(Action<TaskResponse> ok)
    {
      StartCoroutine(After(0.05f, () => ok(new TaskResponse
      {
        busy = Busy, plan_summary = "", tasks = _designPlan != null ? _designPlan.tasks : new TaskDto[0],
        agent_results = new AgentResultDto[0], findings = new string[0]
      })));
    }

    // ---- scripted architecture design workflow

    private ArchitectureDto _designArch;
    private RequirementsDto _designReq;
    private ImplementationPlanDto _designPlan;

    private static ArchitectureDto SampleArchitecture()
    {
      return new ArchitectureDto
      {
        version = 3, revision = 1, status = "draft", approved_by = "", approved_version = 0, approved_revision = 0,
        open_questions = new[] { "Should export include archived accounts?" },
        components = new[]
        {
          new ComponentDto { id = "c1", name = "Export API", responsibility = "Accept export requests and stream results", kind = "service" },
          new ComponentDto { id = "c2", name = "Query Builder", responsibility = "Build filtered queries over user data", kind = "service" },
          new ComponentDto { id = "c3", name = "CSV Writer", responsibility = "Serialize rows to CSV format", kind = "library" },
        },
        relationships = new[]
        {
          new RelationshipDto { id = "e1", src = "c1", dst = "c2", kind = "calls", label = "" },
          new RelationshipDto { id = "e2", src = "c2", dst = "c3", kind = "calls", label = "" },
        },
      };
    }

    public void DesignPropose(string ideaText, Action<DesignProposeResponse> ok, Action<string> fail)
    {
      StartCoroutine(After(0.5f, () =>
      {
        _designReq = new RequirementsDto
        {
          goals = new[] { ideaText ?? "Export user data" },
          functional = new[] { "Stream CSV export for large accounts" },
          non_functional = new[] { "Must handle one million rows" },
          constraints = new string[0], assumptions = new string[0],
          open_questions = new[] { "Should export include archived accounts?" },
        };
        _designArch = SampleArchitecture();
        _designArch.open_questions = _designReq.open_questions;
        _designPlan = null;
        ok(new DesignProposeResponse { status = "ok", requirements = _designReq, architecture = _designArch });
      }));
    }

    public void GetDesign(Action<DesignStateDto> ok, Action<string> fail)
    {
      StartCoroutine(After(0.1f, () => ok(new DesignStateDto
      {
        requirements = _designReq, architecture = _designArch, compare = null, plan = _designPlan,
      })));
    }

    public void DesignEdit(DesignEditOpDto[] ops, Action<DesignEditResponse> ok, Action<string> fail)
    {
      StartCoroutine(After(0.1f, () =>
      {
        if (_designArch == null) { fail("No architecture proposal."); return; }
        var comps = new List<ComponentDto>(_designArch.components ?? new ComponentDto[0]);
        var rels = new List<RelationshipDto>(_designArch.relationships ?? new RelationshipDto[0]);
        var questions = new List<string>(_designArch.open_questions ?? new string[0]);
        bool questionsChanged = false;
        string err = null;
        foreach (DesignEditOpDto op in ops ?? new DesignEditOpDto[0])
        {
          switch (op.op)
          {
            case "resolve_question":
            case "update_question":
            case "add_question":
            {
              string text = op.op == "add_question" ? (op.question ?? op.new_question) : op.question;
              int qi = questions.FindIndex(q => q == text || q.Equals(text ?? "", StringComparison.OrdinalIgnoreCase));
              if (qi < 0 && !string.IsNullOrEmpty(text))
                qi = questions.FindIndex(q => (q ?? "").IndexOf(text, StringComparison.OrdinalIgnoreCase) >= 0);
              if (op.op == "add_question")
              {
                if (string.IsNullOrEmpty(text)) { err = "add_question requires question text"; break; }
                if (!questions.Contains(text)) questions.Add(text);
                questionsChanged = true;
              }
              else if (qi < 0) { err = "open question not found: " + text; }
              else if (op.op == "resolve_question") { questions.RemoveAt(qi); questionsChanged = true; }
              else
              {
                if (string.IsNullOrEmpty(op.new_question)) { err = "update_question requires new_question text"; break; }
                questions[qi] = op.new_question; questionsChanged = true;
              }
              break;
            }
            case "add_component":
              comps.Add(new ComponentDto { id = op.id ?? ("c" + (comps.Count + 1)), name = op.name, responsibility = op.responsibility, kind = op.component_kind ?? "service" });
              break;
            case "remove_component":
              if (rels.Exists(r => r.src == op.id || r.dst == op.id)) { err = "component has relationships"; break; }
              comps.RemoveAll(c => c.id == op.id);
              break;
            case "update_component":
              foreach (ComponentDto c in comps)
                if (c.id == op.id)
                {
                  if (!string.IsNullOrEmpty(op.name)) c.name = op.name;
                  if (!string.IsNullOrEmpty(op.responsibility)) c.responsibility = op.responsibility;
                  if (!string.IsNullOrEmpty(op.component_kind)) c.kind = op.component_kind;
                }
              break;
            case "add_relationship":
              if (!comps.Exists(c => c.id == op.src) || !comps.Exists(c => c.id == op.dst)) { err = "unknown component"; break; }
              rels.Add(new RelationshipDto { id = op.id ?? ("e" + (rels.Count + 1)), src = op.src, dst = op.dst, kind = op.kind ?? "calls", label = op.label });
              break;
            case "remove_relationship":
              rels.RemoveAll(r => r.id == op.id || (op.src == r.src && op.dst == r.dst));
              break;
            case "update_relationship":
              foreach (RelationshipDto r in rels)
                if (r.id == op.id)
                {
                  if (!string.IsNullOrEmpty(op.kind)) r.kind = op.kind;
                  if (op.label != null) r.label = op.label;
                }
              break;
            default: err = "unknown op: " + op.op; break;
          }
          if (err != null) break;
        }
        if (err != null) { fail(err); return; }
        _designArch.components = comps.ToArray();
        _designArch.relationships = rels.ToArray();
        if (questionsChanged)
        {
          _designArch.open_questions = questions.ToArray();
          if (_designReq != null) _designReq.open_questions = questions.ToArray();
        }
        _designArch.revision++;
        if (_designArch.status == "approved") { _designArch.status = "draft"; _designArch.approved_by = ""; _designArch.approved_version = 0; _designArch.approved_revision = 0; }
        _designPlan = null;
        ok(new DesignEditResponse { ok = true, architecture = _designArch });
      }));
    }

    public void DesignCompare(Action<CompareDto> ok, Action<string> fail)
    {
      StartCoroutine(After(0.2f, () => ok(new CompareDto
      {
        status = "ok",
        matched = new[] { new CompareItemDto { id = "c1", name = "Export API", node = "route.export", evidence = "routes/export.ts" } },
        missing = new[] { new CompareItemDto { id = "c2", name = "Query Builder", node = "", evidence = "no graph node matches" } },
        extra = new CompareItemDto[0],
      })));
    }

    public void DesignApprove(bool approved, Action<ArchitectureDto> ok, Action<string> fail)
    {
      StartCoroutine(After(0.2f, () =>
      {
        if (_designArch == null) { fail("No architecture proposal."); return; }
        if (approved && _designArch.open_questions != null && _designArch.open_questions.Length > 0)
        { fail("Cannot approve: unresolved open questions."); return; }
        _designArch.status = approved ? "approved" : "draft";
        _designArch.approved_by = approved ? "quest-user" : "";
        _designArch.approved_version = approved ? _designArch.version : 0;
        _designArch.approved_revision = approved ? _designArch.revision : 0;
        ok(_designArch);
      }));
    }

    public void PlanGenerate(Action<ImplementationPlanDto> ok, Action<string> fail)
    {
      StartCoroutine(After(0.2f, () =>
      {
        if (_designArch == null || _designArch.status != "approved") { fail("Architecture must be approved first."); return; }
        _designPlan = new ImplementationPlanDto
        {
          architecture_version = _designArch.version, architecture_revision = _designArch.revision,
          status = "active",
          tasks = new[]
          {
            new TaskDto { id = "t1", title = "Implement Export API", status = "pending", component_id = "c1", depends_on = new string[0], acceptance = "Accept export requests and stream results", owner = "developer" },
            new TaskDto { id = "t2", title = "Implement Query Builder", status = "pending", component_id = "c2", depends_on = new[] { "t1" }, acceptance = "Build filtered queries over user data", owner = "developer" },
            new TaskDto { id = "t3", title = "Implement CSV Writer", status = "pending", component_id = "c3", depends_on = new[] { "t2" }, acceptance = "Serialize rows to CSV format", owner = "developer" },
          },
        };
        ok(_designPlan);
      }));
    }

    public void PlanUpdateTask(string taskId, string status, Action<bool> ok, Action<string> fail,
                               string evidence = null, bool acceptCycles = false)
    {
      StartCoroutine(After(0.05f, () =>
      {
        if (_designPlan?.tasks == null) { fail("No plan."); return; }
        string norm = status == "completed" ? "done"
          : (status == "in_progress" || status == "in-progress") ? "running" : status;
        if (norm != "pending" && norm != "running" && norm != "done") { fail("Invalid task status."); return; }
        foreach (TaskDto t in _designPlan.tasks)
          if (t.id == taskId)
          {
            if (norm == "running" || norm == "done")
            {
              var done = new HashSet<string>();
              foreach (TaskDto d in _designPlan.tasks)
                if (d.status == "done" || d.status == "completed") done.Add(d.id);
              if (t.depends_on != null && System.Array.Exists(t.depends_on, x => !done.Contains(x)))
              { fail("Task is blocked by unfinished dependencies."); return; }
              if ((_designPlan.circular != null && System.Array.IndexOf(_designPlan.circular, t.component_id) >= 0)
                  && !acceptCycles)
              { fail("Task is part of a circular dependency; resubmit with accept_cycles=true."); return; }
            }
            if (norm == "done" && t.status != "done" && string.IsNullOrEmpty(evidence))
            { fail("Marking a task done requires evidence."); return; }
            t.status = norm;
            if (norm == "done" && !string.IsNullOrEmpty(evidence)) t.evidence = evidence;
            ok(true); return;
          }
        fail("Task not found.");
      }));
    }

    public void Ask(string text, string selection, Action<AskResponse> ok, Action<string> fail, string taskId = null)
    {
      if (Busy) { fail("JARVIS is still working on the previous request."); return; }
      StartCoroutine(AskRoutine(text ?? "", ok));
    }

    private IEnumerator AskRoutine(string text, Action<AskResponse> ok)
    {
      Busy = true;
      yield return new WaitForSecondsRealtime(1.1f);   // long enough to see the Thinking orb
      ok(Script(text.ToLowerInvariant()));
      Busy = false;
    }

    private IEnumerator After(float seconds, Action a)
    {
      yield return new WaitForSecondsRealtime(seconds);
      a();
    }

    private static SceneCommand Path(params string[] ids) { return new SceneCommand { type = "highlight_path", node_ids = ids }; }

    private static AskResponse Script(string t)
    {
      var r = new AskResponse { scene_commands = new List<SceneCommand>(), test_source = "cached" };
      if (t.Contains("fix") || t.Contains("patch") || t.Contains("propose"))
      {
        const string summary = "Add checkOwner(actor, id) to deleteAccount (services/account.ts). 1 file, +2 lines.";
        r.reply = "deleteAccount never checks ownership. I propose calling checkOwner before the delete. Hold to approve when you are ready.";
        r.scene_commands.Add(Path("route.delete", "service.delete", "auth.owner"));
        r.scene_commands.Add(new SceneCommand
        {
          type = "show_ghost_diff",
          diff = "--- a/services/account.ts\n+++ b/services/account.ts\n@@ -30,3 +30,5 @@\n export async function deleteAccount(id, actor) {\n-  // TODO: checkOwner(actor, id) is not called here\n+  if (!checkOwner(actor, id)) throw new Forbidden();\n   await users.delete(id);\n+  // audit stays after the delete\n   await audit.log('account.delete', id);"
        });
        r.scene_commands.Add(new SceneCommand { type = "show_approval_prompt", summary = summary });
        r.pending_approval = summary;
      }
      else if (t.Contains("test"))
      {
        r.reply = "Ran the account tests. One passes, checkOwner has no test yet.";
        r.scene_commands.Add(new SceneCommand { type = "show_test_badges", passed = new[] { "test.own-account" }, failed = new string[0], not_run = new[] { "auth.owner" } });
      }
      else if (t.Contains("risk"))
      {
        r.reply = "Two risky spots: the route depends on requireAuth only, and checkOwner has no callers at all.";
        r.scene_commands.Add(Path("route.delete", "auth.require"));
        r.scene_commands.Add(new SceneCommand { type = "focus_camera", node_id = "auth.owner" });
      }
      else
      {
        r.reply = "Changing deleteAccount affects the DELETE route, the users repository and one test.";
        r.scene_commands.Add(Path("route.delete", "service.delete", "db.repo", "db.delete"));
        r.scene_commands.Add(new SceneCommand { type = "dim_unrelated", keep_ids = new[] { "route.delete", "service.delete", "db.repo", "db.delete", "test.own-account" } });
        r.scene_commands.Add(new SceneCommand { type = "show_test_badges", passed = new[] { "test.own-account" }, failed = new string[0], not_run = new string[0] });
      }
      return r;
    }
  }
}
