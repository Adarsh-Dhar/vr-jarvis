using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace JarvisVR
{
  /// <summary>
  /// Human line editing inside the sandbox worktree (partial of JarvisSpatialWorkspace).
  /// Every write goes through POST /workspace/edit with base_hash conflict detection —
  /// never PUT /workspace/file, so a truncated view can never corrupt the file.
  /// Each edit clears the four verification evidence keys server-side; VERIFY, REVIEW
  /// and SUBMIT then run the same gates an agent patch faces before /approve.
  /// </summary>
  public sealed partial class JarvisSpatialWorkspace
  {
    // ---- edit state ----
    private JarvisSpatialPanel _editPanel;
    private bool _editMode;
    private int _editLine = 1;
    private string _editBase = "";          // hash of the file text the next edit is based on
    private string _editPath;               // worktree-relative path being edited
    private SyntaxErrorDto[] _editSyntax;
    private WsSymbolDto[] _editSymbols;
    private WsStatusDto _editStatus;
    private bool _wsReady;                  // server reports a sandbox worktree
    private float _editPollAt;
    private readonly List<UndoEntry> _undo = new List<UndoEntry>();
    private JarvisSpatialButton _editModeBtn, _editPrevBtn, _editNextBtn, _editLineBtn,
      _editAddBtn, _editDelBtn, _editUndoBtn, _editRevertBtn,
      _editVerifyBtn, _editReviewBtn, _editSubmitBtn;

    private sealed class UndoEntry
    {
      public string Path, Op, OldText, NewText;
      public int Start, End;
    }

    // =========================================================== panel

    private void BuildEditPanel()
    {
      JarvisPalette pal = JarvisPalette.Current;
      _editPanel = AddPanel("edit", "Edit", 560, 520, 1.18f, 0.20f, pal.Green);
      _editPanel.SetBodyBox(56, 120); _editPanel.UseMono(15);
      _editPanel.SetBody("Open a file in the repository browser, then press EDIT: ON.");

      const float w = 262f, x0 = 14f, x1 = 284f, h = 46f;
      float[] ys = { 150f, 204f, 258f, 312f, 366f, 420f };
      _editModeBtn  = _editPanel.AddButton("EDIT: OFF",      x0, ys[0], w,  h, ToggleEditMode);
      _editPrevBtn  = _editPanel.AddButton("LINE ^",         x1, ys[0], w,  h, () => EditLineDelta(-1));
      _editNextBtn  = _editPanel.AddButton("LINE v",         x0, ys[1], w,  h, () => EditLineDelta(+1));
      _editLineBtn  = _editPanel.AddButton("EDIT LINE",      x1, ys[1], w,  h, EditCurrentLine);
      _editAddBtn   = _editPanel.AddButton("ADD LINE BELOW", x0, ys[2], w,  h, EditAddLineBelow);
      _editDelBtn   = _editPanel.AddButton("DELETE LINE",    x1, ys[2], w,  h, EditDeleteLine);
      _editUndoBtn  = _editPanel.AddButton("UNDO",           x0, ys[3], w,  h, EditUndo);
      _editRevertBtn= _editPanel.AddButton("REVERT FILE",    x1, ys[3], w,  h, EditRevertFile);
      _editVerifyBtn= _editPanel.AddButton("VERIFY",         x0, ys[4], w,  h, EditVerify, 0f, pal.Violet);
      _editReviewBtn= _editPanel.AddButton("REVIEW",         x1, ys[4], w,  h, EditReview, 0f, pal.Violet);
      _editSubmitBtn= _editPanel.AddButton("SUBMIT",         x0, ys[5], 532f, h, EditSubmit, 0f, pal.Amber);
      RefreshEdit();
    }

    // =========================================================== helpers

    /// <summary>splitlines() semantics: a trailing newline does not add a line.</summary>
    private static List<string> FileLines(string content)
    {
      var list = new List<string>((content ?? "").Replace("\r\n", "\n").Split('\n'));
      if (list.Count > 0 && list[list.Count - 1].Length == 0) list.RemoveAt(list.Count - 1);
      if (list.Count == 0 && !string.IsNullOrEmpty(content)) list.Add("");
      return list;
    }

    private int EditLineCount() { return _openFile != null ? FileLines(_openFile.content).Count : 0; }

    private bool EditReady()
    {
      if (!_editMode || _openFile == null || string.IsNullOrEmpty(_editPath))
      { Say("Turn EDIT on for an open file first."); return false; }
      return true;
    }

    private string CurrentEditLine()
    {
      var lines = FileLines(_openFile != null ? _openFile.content : "");
      if (lines.Count == 0) return "";
      return lines[Mathf.Clamp(_editLine, 1, lines.Count) - 1];
    }

    private bool HasEditSyntaxError(int lineNo)
    {
      if (_editSyntax == null) return false;
      foreach (SyntaxErrorDto se in _editSyntax)
        if (se != null && se.line == lineNo) return true;
      return false;
    }

    private static string VerStatus(string s)
    {
      if (s == "fresh") return "fresh";
      if (s == "stale") return "STALE";
      return "missing";
    }

    private bool AllEvidenceFresh()
    {
      WsVerificationDto v = _editStatus != null ? _editStatus.verification : null;
      return v != null && v.tests == "fresh" && v.typecheck == "fresh"
        && v.review == "fresh" && v.security == "fresh";
    }

    /// <summary>Fold a /workspace/file response into the viewer's RepoFileDto.</summary>
    private static RepoFileDto ToRepoFile(WsFileDto wf, string fallbackPath)
    {
      string content = wf.content ?? "";
      return new RepoFileDto
      {
        status = "ok",
        path = string.IsNullOrEmpty(wf.path) ? fallbackPath : wf.path,
        content = content,
        size = wf.size,
        total_lines = FileLines(content).Count,
        truncated = wf.truncated
      };
    }

    // =========================================================== edit mode

    private void ToggleEditMode()
    {
      if (_editMode) { ExitEditMode(); Say("Edit mode off."); return; }
      if (_openFile == null) { Say("Open a file in the repository browser first."); return; }
      if (_openFile.truncated) { Say("This file is truncated; edit it in an IDE instead."); return; }
      if (_bridge == null) return;
      Say("Opening the sandbox…");
      _bridge.WorkspaceOpen(o =>
      {
        if (o == null || !o.ok) { Say("Could not open the sandbox: " + (o != null ? o.detail : "no response")); return; }
        _wsReady = true;
        _bridge.WorkspaceGetFile(_openFile.path, wf =>
        {
          if (wf == null || string.IsNullOrEmpty(wf.hash)) { Say("Could not read " + _openFile.path + " from the sandbox."); return; }
          if (wf.source != "worktree") { Say("No sandbox copy of this file yet."); return; }
          _openFile = ToRepoFile(wf, _openFile.path);
          _editMode = true;
          _editPath = wf.path;
          _editBase = wf.hash;
          _editLine = Mathf.Clamp(_openFilePage * EditorLinesPerPage + 1, 1, Mathf.Max(1, EditLineCount()));
          _undo.Clear();
          _editSyntax = null; _editSymbols = null;
          RefreshOpenFile(); RefreshEdit();
          PollEditStatus();
          Say("EDIT ON — LINE ^/v picks a line, EDIT LINE replaces it. VERIFY → REVIEW → SUBMIT when done.");
          Log("edit mode on: " + _editPath);
        }, err => Say("Sandbox read failed: " + err));
      }, err => Say("Sandbox open failed: " + err));
    }

    private void ExitEditMode()
    {
      _editMode = false;
      _editLine = 1; _editBase = ""; _editPath = null;
      _editSyntax = null; _editSymbols = null;
      _undo.Clear();
      RefreshEdit();
    }

    private void EditLineDelta(int d)
    {
      int n = Mathf.Max(1, EditLineCount());
      _editLine = Mathf.Clamp(_editLine + d, 1, n);
      RefreshOpenFile(); RefreshEdit();
    }

    // =========================================================== edits

    /// <summary>Typed text for an edit_* keyboard op: replace the cursor line or insert below it.</summary>
    private void ApplyEditTextOp(string text)
    {
      if (!EditReady()) return;
      if (_kbOp == "edit_insert") { EditInsertBelow(text ?? ""); return; }
      EditReplaceLine(text ?? "");
    }

    private void EditCurrentLine()
    {
      if (!EditReady()) return;
      _kbOp = "edit_replace"; _kbOpId = _editPath;
      OpenKeyboard(CurrentEditLine());
      if (_kb == null) { _kbOp = null; _kbOpId = null; Say("The keyboard did not open (JARVIS is busy). Try again."); }
    }

    private void EditAddLineBelow()
    {
      if (!EditReady()) return;
      _kbOp = "edit_insert"; _kbOpId = _editPath;
      OpenKeyboard("");
      if (_kb == null) { _kbOp = null; _kbOpId = null; Say("The keyboard did not open (JARVIS is busy). Try again."); }
    }

    private void EditInsertBelow(string text)
    {
      int start = Mathf.Clamp(_editLine, 1, Mathf.Max(1, EditLineCount()));
      SendEdit("insert_after", start, start, text ?? "", "");
    }

    private void EditReplaceLine(string text)
    {
      int start = Mathf.Clamp(_editLine, 1, Mathf.Max(1, EditLineCount()));
      SendEdit("replace", start, start, text, CurrentEditLine());
    }

    private void EditDeleteLine()
    {
      if (!EditReady()) return;
      var lines = FileLines(_openFile.content);
      if (_editLine < 1 || _editLine > lines.Count) { Say("No line " + _editLine + " to delete."); return; }
      SendEdit("delete", _editLine, _editLine, "", lines[_editLine - 1]);
    }

    /// <summary>One line-range edit. end is always concrete (JsonUtility has no int?).</summary>
    private void SendEdit(string op, int start, int end, string newText, string undoOldText,
                          bool recordUndo = true)
    {
      if (_bridge == null || _openFile == null) return;
      string path = _editPath ?? _openFile.path;
      _bridge.WorkspaceEditLines(path, op, start, end, newText, _editBase,
        r => OnEditApplied(r, op, start, end, newText, undoOldText, recordUndo),
        OnEditFailed);
    }

    private void OnEditApplied(WsEditResponse r, string op, int start, int end,
                               string newText, string undoOldText, bool recordUndo)
    {
      if (r == null) { Say("Edit failed: no response"); return; }
      if (!r.ok)
      {
        if (r.conflict) { Say("File changed outside the editor. Reloaded."); ReloadEditFile(); return; }
        Say("Edit rejected: " + (r.detail ?? "unknown error"));
        return;
      }
      if (recordUndo)
        _undo.Add(new UndoEntry { Path = _editPath, Op = op, Start = start, End = end,
                                OldText = undoOldText ?? "", NewText = newText ?? "" });
      _editBase = r.hash ?? _editBase;
      _editSyntax = r.syntax_errors;
      _editSymbols = r.symbols;
      AfterWorkspaceChange();
      ReloadEditFile();
      FetchEditDiff();
      RefreshEdit();
    }

    private void OnEditFailed(string err)
    {
      // Send truncates 4xx bodies; a 409 means the file changed outside the
      // editor, so reload through /workspace/file to get current text + hash.
      if (err != null && err.StartsWith("JARVIS 409"))
      {
        Say("File changed outside the editor. Reloaded.");
        ReloadEditFile();
        return;
      }
      Say("Edit failed: " + (err ?? "no response"));
      _errorUntil = Time.unscaledTime + 4f;
    }

    /// <summary>Every successful workspace write invalidates the same evidence an agent patch does.</summary>
    private void AfterWorkspaceChange()
    {
      _hasTestRun = false; _testFailed = false; _testFailureLines = null;
      _testSummary = "No test run yet.";
      _pending = null;
      _ghostSeenAll = false; _ghostDiff = null; _ghostPage = 0;
      RefreshTests(); RefreshApproval(); RefreshGhost();
      PollEditStatus();
    }

    private void ReloadEditFile()
    {
      if (_bridge == null || _openFile == null) return;
      string path = _editPath ?? _openFile.path;
      _bridge.WorkspaceGetFile(path, wf =>
      {
        if (wf == null) return;
        _openFile = ToRepoFile(wf, path);
        if (!string.IsNullOrEmpty(wf.hash)) _editBase = wf.hash;
        int lines = EditLineCount();
        _editLine = Mathf.Clamp(_editLine, 1, Mathf.Max(1, lines));
        int pages = Mathf.Max(1, Mathf.CeilToInt(lines / (float)EditorLinesPerPage));
        _openFilePage = Mathf.Clamp(_openFilePage, 0, pages - 1);
        RefreshOpenFile(); RefreshOutline();
      }, err => { });
    }

    private void FetchEditDiff()
    {
      if (_bridge == null) return;
      _bridge.WorkspaceDiff(d =>
      {
        if (d != null && d.ok) { _ghostDiff = d.diff; _ghostPage = 0; _ghostSeenAll = false; }
        RefreshGhost();
      }, e => { });
    }

    // =========================================================== undo

    /// <summary>Inverse line edits only (never PUT). Deleting line 1 is undone by
    /// replacing the new first line with the deleted text plus that line —
    /// apply_line_edit cannot insert before line 1 directly.</summary>
    private void EditUndo()
    {
      if (!EditReady()) return;
      if (_undo.Count == 0) { Say("Nothing to undo."); return; }
      UndoEntry u = _undo[_undo.Count - 1];
      _undo.RemoveAt(_undo.Count - 1);
      var cur = FileLines(_openFile.content);

      if (u.Op == "insert_after")
      {
        int n = Mathf.Max(1, FileLines(u.NewText).Count);
        SendEdit("delete", u.Start + 1, u.Start + n, "", null, false);
        return;
      }
      if (u.Op == "delete" || FileLines(u.NewText).Count == 0)
      {
        // Restore deleted lines: insert_after before the gap, or the
        // replace-line-1 trick when the deletion was at the top.
        if (u.Start <= 1)
        {
          if (cur.Count == 0) SendEdit("insert_after", 1, 1, u.OldText, null, false);
          else SendEdit("replace", 1, 1, u.OldText + "\n" + cur[0], null, false);
        }
        else SendEdit("insert_after", u.Start - 1, u.Start - 1, u.OldText, null, false);
        return;
      }
      // replace: overwrite the inserted span with the original line(s)
      int ins = FileLines(u.NewText).Count;
      SendEdit("replace", u.Start, u.Start + ins - 1, u.OldText, null, false);
    }

    // =========================================================== revert / verify / review / submit

    private void EditRevertFile()
    {
      if (!EditReady()) return;
      _bridge.WorkspaceRevert(_editPath, r =>
      {
        if (r == null || !r.ok) { Say("Revert failed: " + (r != null ? r.detail : "no response")); return; }
        _undo.Clear();
        _editBase = r.hash ?? "";
        _editSyntax = null; _editSymbols = null;
        AfterWorkspaceChange();
        ReloadEditFile();
        FetchEditDiff();
        RefreshEdit();
        Say("File reverted to HEAD.");
      }, OnEditFailed);
    }

    private void EditVerify()
    {
      if (_bridge == null) return;
      Say("Running verification…");
      _bridge.WorkspaceVerify(null, r =>
      {
        if (r == null) { Say("Verify failed: no response"); return; }
        ApplyTestRun(r.test_run);
        RefreshTests(); RefreshEdit();
        WsVerificationDto v = r.verification;
        Say("Verify — tests: " + VerStatus(v != null ? v.tests : null)
          + ", typecheck: " + VerStatus(v != null ? v.typecheck : null)
          + ", review: " + VerStatus(v != null ? v.review : null)
          + ", security: " + VerStatus(v != null ? v.security : null) + ".");
      }, err => Say("Verify failed: " + err));
    }

    private void EditReview()
    {
      if (_bridge == null) return;
      Say("Requesting independent review…");
      _bridge.WorkspaceReview(r =>
      {
        if (r == null) { Say("Review failed: no response"); return; }
        if (r.ok) Say("Review " + (r.verdict ?? "done") + (r.source == "human" ? " (human)" : "")
          + (string.IsNullOrEmpty(r.summary) ? "" : " — " + r.summary));
        else Say("Review blockers: " + string.Join("; ", r.blockers ?? new string[0]));
        PollEditStatus(); RefreshEdit();
      }, err => Say("Review failed: " + err));
    }

    private void EditSubmit()
    {
      if (_bridge == null) return;
      if (!AllEvidenceFresh()) { Say("VERIFY tests/typecheck/security and REVIEW must all be fresh before SUBMIT."); PollEditStatus(); return; }
      Say("Submitting for approval…");
      _bridge.WorkspaceSubmit(r =>
      {
        if (r == null) { Say("Submit failed: no response"); return; }
        if (r.ok)
        {
          _pending = r.pending_approval;
          if (r.review != null && !string.IsNullOrEmpty(r.review.diff))
          { _ghostDiff = r.review.diff; _ghostPage = 0; _ghostSeenAll = false; }
          RefreshApproval(); RefreshGhost();
          SetMode("AGENT");   // pending approval always wins
          Say("Submitted. Page the diff, then HOLD 2s TO APPROVE.");
          Log("workspace edit submitted");
        }
        else Say("Submit rejected: " + (r.detail ?? "unknown"));
      }, err =>
      {
        if (err != null && err.StartsWith("JARVIS 409"))
        {
          Say("Submit blocked — verification is stale or missing. Re-run VERIFY.");
          PollEditStatus();
        }
        else Say("Submit failed: " + err);
      });
    }

    // =========================================================== status and refresh

    private void PollEditStatus()
    {
      if (_bridge == null) return;
      _bridge.WorkspaceStatus(s =>
      {
        if (s == null) return;
        _editStatus = s;
        if (s.worktree) _wsReady = true;
        RefreshEdit();
      }, e => { });
    }

    /// <summary>Test fields shared by /ask responses and /workspace/verify so the
    /// TESTS panel looks identical whichever path produced the run.</summary>
    private void ApplyTestRun(TestRunDto tr)
    {
      _lastTestRun = tr;
      if (tr == null || string.IsNullOrEmpty(tr.status)) return;
      _hasTestRun = tr.status == "passed" || tr.status == "failed";
      _testFailed = tr.status == "failed"
        || (tr.failed_ids != null && tr.failed_ids.Length > 0);
      int passed = tr.passed != null ? tr.passed.Length : 0;
      int failed = tr.failed_ids != null ? tr.failed_ids.Length : 0;
      int skipped = tr.skipped != null ? tr.skipped.Length : 0;
      _testSummary = "status " + tr.status
        + "  ·  " + passed + " passed, " + failed + " failed, " + skipped + " skipped"
        + (string.IsNullOrEmpty(tr.runner) ? "" : "  ·  " + tr.runner)
        + (string.IsNullOrEmpty(tr.source) ? "" : "  ·  " + tr.source);
      _testFailureLines = tr.failed_ids;
    }

    private void RefreshEdit()
    {
      if (_editPanel == null) return;
      bool open = _openFile != null;
      bool mode = _editMode && open;
      JarvisPalette pal = JarvisPalette.Current;

      if (_editModeBtn != null) { _editModeBtn.Label.text = mode ? "EDIT: ON" : "EDIT: OFF"; _editModeBtn.Interactable = open; }
      int n = EditLineCount();
      if (_editPrevBtn != null) { _editPrevBtn.Interactable = mode && n > 1; }
      if (_editNextBtn != null) { _editNextBtn.Interactable = mode && n > 1; }
      if (_editLineBtn != null) _editLineBtn.Interactable = mode;
      if (_editAddBtn != null) _editAddBtn.Interactable = mode;
      if (_editDelBtn != null) _editDelBtn.Interactable = mode && _editLine >= 1 && _editLine <= n;
      if (_editUndoBtn != null) _editUndoBtn.Interactable = mode && _undo.Count > 0;
      if (_editRevertBtn != null) _editRevertBtn.Interactable = mode;
      if (_editVerifyBtn != null) _editVerifyBtn.Interactable = mode;
      if (_editReviewBtn != null) _editReviewBtn.Interactable = mode;
      if (_editSubmitBtn != null) _editSubmitBtn.Interactable = mode && AllEvidenceFresh();

      if (!open)
      {
        _editPanel.SetBody("Open a file in the repository browser, then press EDIT: ON.");
        return;
      }
      var sb = new StringBuilder();
      sb.Append("<b>").Append(Esc(_editPath ?? _openFile.path)).Append("</b>\n");
      if (!mode)
      {
        sb.Append("press EDIT: ON to edit in the sandbox worktree");
        _editPanel.SetBody(sb.ToString());
        return;
      }
      sb.Append("line ").Append(_editLine).Append('/').Append(n)
        .Append("  ·  ").Append(_undo.Count).Append(" undo").Append('\n');
      WsVerificationDto v = _editStatus != null ? _editStatus.verification : null;
      sb.Append("verify  tests ").Append(VerStatus(v != null ? v.tests : null))
        .Append("  typecheck ").Append(VerStatus(v != null ? v.typecheck : null))
        .Append("  review ").Append(VerStatus(v != null ? v.review : null))
        .Append("  security ").Append(VerStatus(v != null ? v.security : null)).Append('\n');
      if (_editStatus != null && _editStatus.dirty)
        sb.Append("worktree dirty: ").Append(_editStatus.files != null ? _editStatus.files.Length : 0).Append(" file(s)\n");
      int errCount = _editSyntax != null ? _editSyntax.Length : 0;
      if (errCount > 0)
      {
        sb.Append("<color=#").Append(Hex(pal.Red)).Append(errCount).Append(" syntax error(s):</color>\n");
        int shown = 0;
        foreach (SyntaxErrorDto se in _editSyntax)
        {
          if (se == null || shown >= 4) continue;
          sb.Append("  L").Append(se.line).Append(": ").Append(Esc(se.message ?? "")).Append('\n');
          shown++;
        }
      }
      else if (_editSyntax != null)
        sb.Append("syntax: clean\n");
      sb.Append("\nEDIT LINE replaces line ").Append(_editLine)
        .Append(" · ADD LINE BELOW inserts after it\nVERIFY → REVIEW → SUBMIT, then approve.");
      _editPanel.SetBody(sb.ToString());
    }
  }
}
