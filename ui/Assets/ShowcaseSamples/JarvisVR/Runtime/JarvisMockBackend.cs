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
    void Ask(string text, string selection, Action<AskResponse> ok, Action<string> fail);
    void Approve(bool approved, Action<ApproveResponse> ok, Action<string> fail);
    void GetSource(string nodeId, Action<SourceResponse> ok);
    void GetHealth(Action<HealthDto> ok, Action<string> fail);
    void GetGraph(Action<GraphDto> ok);
    void GetRepos(Action<ReposDto> ok, Action<string> fail);
    void GetTree(string repo, string path, Action<RepoTreeDto> ok, Action<string> fail);
    void GetFile(string repo, string path, Action<RepoFileDto> ok, Action<string> fail);
    void SelectRepo(string name, Action<bool> done);
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

    public void Ask(string text, string selection, Action<AskResponse> ok, Action<string> fail)
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
