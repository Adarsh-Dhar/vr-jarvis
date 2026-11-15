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
      _editVerifyBtn, _editReviewBtn, _editRunBtn, _editSelBtn, _editSubmitBtn,
      _editIdeBtn, _editBreakBtn, _editDebugBtn, _editContBtn, _editStepBtn, _editStopBtn;
    // IDE-change polling: token from /workspace/changes; a change means the
    // file was edited in VS Code, so the viewer reloads it.
    private string _lastChangesToken;
    private Coroutine _changesPoll;
    // Live diagnostics: line -> checker item, refreshed (debounced) after edits.
    private readonly Dictionary<int, WsDiagItem> _diagByLine = new Dictionary<int, WsDiagItem>();
    private int _diagGen;
    // Debugger: breakpoints are 1-based lines of the file being edited.
    private readonly HashSet<int> _bpLines = new HashSet<int>();
    private string _bpPath;
    private bool _debugActive;
    private WsDebugStateDto _debugState;
    private Coroutine _debugPoll;
    // range selection: LINE ^/v move the end while SEL is on; EDIT LINE / DELETE LINE
    // then operate on [SelLo..SelHi] instead of the single cursor line.
    private bool _editSelMode;
    private int _editSelStart, _editSelEnd;   // 1-based inclusive; 0 = no anchor yet
    private bool _runBusy;
    private readonly StringBuilder _runOutput = new StringBuilder();
    // Demo mode (server JARVIS_DEMO_MODE=1, reported via /health demo_mode):
    // editing, running, debugging and IDE routes all return 404, so the whole
    // edit panel is hidden and its polling coroutines never start.
    private bool _demoMode;

    private sealed class UndoEntry
    {
      public string Path, Op, OldText, NewText;
      public int Start, End;
    }

    // =========================================================== panel

    private void BuildEditPanel()
    {
      JarvisPalette pal = JarvisPalette.Current;
      _editPanel = AddPanel("edit", "Edit", 560, 720, 1.18f, 0.20f, pal.Green);
      _editPanel.SetBodyBox(56, 120); _editPanel.UseMono(15);
      _editPanel.SetBody("Open a file in the repository browser, then press EDIT: ON.");

      const float w = 262f, x0 = 14f, x1 = 284f, h = 44f;
      float[] ys = { 150f, 202f, 254f, 306f, 358f, 410f, 462f, 514f, 566f, 618f };
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
      _editRunBtn   = _editPanel.AddButton("RUN",            x0, ys[5], w,  h, EditRun);
      _editSelBtn   = _editPanel.AddButton("SEL: OFF",       x1, ys[5], w,  h, ToggleEditSel);
      _editSubmitBtn= _editPanel.AddButton("SUBMIT",         x0, ys[6], 532f, h, EditSubmit, 0f, pal.Amber);
      _editIdeBtn   = _editPanel.AddButton("IDE",            x0, ys[7], w,  h, EditOpenIde, 0f, pal.Cyan);
      _editBreakBtn = _editPanel.AddButton("BREAK",          x1, ys[7], w,  h, EditToggleBreakpoint, 0f, pal.Orange);
      _editDebugBtn = _editPanel.AddButton("DEBUG",          x0, ys[8], w,  h, EditDebugStart, 0f, pal.Violet);
      _editContBtn  = _editPanel.AddButton("CONT",           x1, ys[8], w,  h, EditDebugControl("continue"));
      _editStepBtn  = _editPanel.AddButton("STEP",           x0, ys[9], w,  h, EditDebugControl("next"));
      _editStopBtn  = _editPanel.AddButton("STOP",           x1, ys[9], w,  h, EditDebugStop, 0f, pal.Red);
      RefreshEdit();
    }

    /// <summary>Called once /health reports demo_mode. Hides every edit-panel
    /// button (ForceHidden survives minimize/restore) and stops the polling
    /// coroutines so nothing calls the disabled routes.</summary>
    private void ApplyDemoMode()
    {
      if (_demoMode) return;
      _demoMode = true;
      if (_changesPoll != null) { StopCoroutine(_changesPoll); _changesPoll = null; }
      if (_debugPoll != null) { StopCoroutine(_debugPoll); _debugPoll = null; }
      _debugActive = false;
      _editMode = false;
      HideDemo(_editRunBtn); HideDemo(_editIdeBtn); HideDemo(_editBreakBtn);
      HideDemo(_editDebugBtn); HideDemo(_editContBtn); HideDemo(_editStepBtn);
      HideDemo(_editStopBtn);
      // The server 404s every write/verify route in demo mode, so the editing
      // controls are hidden too — judges see analysis and the 3D graph only.
      HideDemo(_editModeBtn); HideDemo(_editPrevBtn); HideDemo(_editNextBtn);
      HideDemo(_editLineBtn); HideDemo(_editAddBtn); HideDemo(_editDelBtn);
      HideDemo(_editUndoBtn); HideDemo(_editRevertBtn); HideDemo(_editVerifyBtn);
      HideDemo(_editReviewBtn); HideDemo(_editSubmitBtn); HideDemo(_editSelBtn);
      ShowDemoQuestions();
      RefreshEdit();
    }

    private static void HideDemo(JarvisSpatialButton b)
    {
      if (b == null) return;
      b.ForceHidden = true;
      b.Interactable = false;
      b.gameObject.SetActive(false);
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
      if (_demoMode) { Say("Editing is disabled in this demo build."); return; }
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
          _diagByLine.Clear(); _bpLines.Clear(); _bpPath = _editPath;
          _debugState = null; _debugActive = false;
          RefreshOpenFile(); RefreshEdit();
          PollEditStatus();
          StartChangesPoll();
          StartDebugPoll();
          ScheduleDiagnostics();
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
      _editSelMode = false; _editSelStart = _editSelEnd = 0;
      _undo.Clear();
      _diagByLine.Clear(); _diagGen++;
      _bpLines.Clear(); _bpPath = null;
      _lastChangesToken = null;
      if (_changesPoll != null) { StopCoroutine(_changesPoll); _changesPoll = null; }
      if (_debugPoll != null) { StopCoroutine(_debugPoll); _debugPoll = null; }
      if (_debugActive && _bridge != null)
      {
        _debugActive = false;
        _bridge.DebugControl("stop", r => { }, e => { });
      }
      _debugState = null;
      RefreshEdit();
    }

    private void EditLineDelta(int d)
    {
      int n = Mathf.Max(1, EditLineCount());
      if (_editSelMode)
      {
        if (_editSelStart <= 0) _editSelStart = _editSelEnd = Mathf.Clamp(_editLine, 1, n);
        _editSelEnd = Mathf.Clamp(_editSelEnd + d, 1, n);
        _editLine = _editSelEnd;
      }
      else _editLine = Mathf.Clamp(_editLine + d, 1, n);
      RefreshOpenFile(); RefreshEdit();
    }

    // =========================================================== range selection

    private bool HasEditSel
    {
      get { return _editSelMode && _editSelStart > 0 && _editSelEnd > 0; }
    }
    private int SelLo { get { return Mathf.Min(_editSelStart, _editSelEnd); } }
    private int SelHi { get { return Mathf.Max(_editSelStart, _editSelEnd); } }

    private void ToggleEditSel()
    {
      if (!EditReady()) return;
      _editSelMode = !_editSelMode;
      if (_editSelMode) _editSelStart = _editSelEnd = Mathf.Clamp(_editLine, 1, Mathf.Max(1, EditLineCount()));
      else _editSelStart = _editSelEnd = 0;
      RefreshEdit();
    }

    /// <summary>The current text of the selected line range, for undo bookkeeping.</summary>
    private string SelText()
    {
      var lines = FileLines(_openFile != null ? _openFile.content : "");
      var sb = new StringBuilder();
      for (int i = SelLo; i <= Mathf.Min(SelHi, lines.Count); i++)
      {
        if (sb.Length > 0) sb.Append('\n');
        sb.Append(lines[i - 1]);
      }
      return sb.ToString();
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
      if (HasEditSel)
      {
        SendEdit("replace", SelLo, SelHi, text ?? "", SelText());
        return;
      }
      int start = Mathf.Clamp(_editLine, 1, Mathf.Max(1, EditLineCount()));
      SendEdit("replace", start, start, text, CurrentEditLine());
    }

    private void EditDeleteLine()
    {
      if (!EditReady()) return;
      if (HasEditSel)
      {
        SendEdit("delete", SelLo, SelHi, "", SelText());
        return;
      }
      var lines = FileLines(_openFile.content);
      if (_editLine < 1 || _editLine > lines.Count) { Say("No line " + _editLine + " to delete."); return; }
      SendEdit("delete", _editLine, _editLine, "", lines[_editLine - 1]);
    }

    /// <summary>One line-range edit. end is always concrete (JsonUtility has no int?).</summary>
    private void SendEdit(string op, int start, int end, string newText, string undoOldText,
                          bool recordUndo = true)
    {
      if (_bridge == null || _openFile == null) return;
      if (_debugState != null && _debugState.status == "stopped")
        Say("Program is stopped at a breakpoint — line numbers may have shifted.");
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
      _editSelStart = _editSelEnd = 0;   // the range it described no longer exists
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
      ScheduleDiagnostics();
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

    // =========================================================== run

    /// <summary>POST /workspace/run with a fixed allowlisted argv: pytest in the
    /// worktree. Output accumulates in _runOutput and shows in the panel body.</summary>
    private void EditRun()
    {
      if (_bridge == null || _runBusy) return;
      if (!_wsReady) { Say("No sandbox worktree yet — turn EDIT on for a file first."); return; }
      _runOutput.Length = 0;
      _runBusy = true;
      RefreshEdit();
      Say("Running pytest in the worktree…");
      string[] argv = { "python3", "-m", "pytest", "-x", "-q" };
      _bridge.WorkspaceRun(argv,
        line => { RunOut(line); RefreshEdit(); },
        code =>
        {
          _runBusy = false;
          RunOut("[exit " + code + "]\n");
          RefreshEdit();
          PollEditStatus();
        },
        err =>
        {
          _runBusy = false;
          RunOut("[error] " + (err ?? "failed") + "\n");
          RefreshEdit();
          Say("Run failed: " + err);
        }, 110);
    }

    private void RunOut(string s)
    {
      _runOutput.Append(s ?? "");
      if (_runOutput.Length > 8000)
        _runOutput.Remove(0, _runOutput.Length - 8000);
    }

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

    // =========================================================== IDE link

    /// <summary>Open the session worktree in the IDE configured on the server
    /// (JARVIS_IDE_COMMAND). The server runs it, so this works tethered or not.</summary>
    private void EditOpenIde()
    {
      if (_bridge == null) return;
      if (!_wsReady) { Say("No sandbox worktree yet — turn EDIT on for a file first."); return; }
      Say("Opening the worktree in the IDE…");
      _bridge.WorkspaceOpenIde(o =>
      {
        if (o == null || !o.ok) { Say("IDE open failed: " + (o != null ? o.detail : "no response")); return; }
        Say("Worktree opened in the IDE. Edits there show up here within a few seconds.");
      }, err => Say("IDE open failed: " + err));
    }

    /// <summary>Poll /workspace/changes while edit mode is on; a new token means
    /// a file changed on disk (IDE or external tool), so reload and re-check.</summary>
    private void StartChangesPoll()
    {
      if (_changesPoll != null) StopCoroutine(_changesPoll);
      _changesPoll = StartCoroutine(PollWorkspaceChanges());
    }

    private IEnumerator PollWorkspaceChanges()
    {
      var wait = new WaitForSeconds(2f);
      while (_editMode && _bridge != null)
      {
        yield return wait;
        if (!_editMode || _bridge == null) yield break;
        _bridge.WorkspaceChanges(c =>
        {
          if (c == null || !_editMode) return;
          if (_lastChangesToken == null) { _lastChangesToken = c.token; return; }
          if (c.token == _lastChangesToken) return;
          _lastChangesToken = c.token;
          ReloadEditFile();
          AfterWorkspaceChange();
          Say("File changed outside the editor. Reloaded.");
        }, e => { });
      }
      _changesPoll = null;
    }

    // =========================================================== diagnostics

    private WsDiagItem DiagForLine(int lineNo)
    {
      WsDiagItem it;
      return _diagByLine.TryGetValue(lineNo, out it) ? it : null;
    }

    /// <summary>Debounced: run diagnostics 1.5s after the last edit/change.</summary>
    private void ScheduleDiagnostics()
    {
      _diagGen++;
      int gen = _diagGen;
      StartCoroutine(DiagAfterDelay(gen));
    }

    private IEnumerator DiagAfterDelay(int gen)
    {
      yield return new WaitForSeconds(1.5f);
      if (gen != _diagGen || !_editMode || _bridge == null || string.IsNullOrEmpty(_editPath)) yield break;
      string path = _editPath;
      _bridge.WorkspaceDiagnostics(path, d =>
      {
        if (d == null || !d.ok || !d.supported || path != _editPath) return;
        _diagByLine.Clear();
        if (d.items != null)
          foreach (WsDiagItem it in d.items)
            if (it != null && it.line > 0) _diagByLine[it.line] = it;
        RefreshOpenFile(); RefreshEdit();
      }, e => { });
    }

    // =========================================================== debugger

    private void EditToggleBreakpoint()
    {
      if (!EditReady()) return;
      int line = Mathf.Clamp(_editLine, 1, Mathf.Max(1, EditLineCount()));
      if (_bpPath != _editPath) { _bpPath = _editPath; _bpLines.Clear(); }
      if (!_bpLines.Add(line)) _bpLines.Remove(line);
      RefreshEdit();
    }

    private void EditDebugStart()
    {
      if (_bridge == null || _debugActive) return;
      if (!EditReady()) return;
      if (_editPath == null || !_editPath.EndsWith(".py"))
      { Say("Debug needs a .py file — open one and turn EDIT on."); return; }
      if (_bpPath != _editPath) { _bpPath = _editPath; _bpLines.Clear(); }
      var bps = new List<WsDebugBpDto>();
      foreach (int l in _bpLines) bps.Add(new WsDebugBpDto { path = _editPath, line = l });
      bps.Sort((a, b) => a.line.CompareTo(b.line));
      Say("Starting debugger" + (bps.Count > 0 ? " with " + bps.Count + " breakpoint(s)" : "") + "…");
      _bridge.DebugStart(_editPath, new string[0], bps.ToArray(), r =>
      {
        if (r == null || !r.ok) { Say("Debug start failed: " + (r != null ? r.detail : "no response")); return; }
        _debugActive = true;
        _debugState = null;
        StartDebugPoll();
        RefreshEdit();
      }, err => Say("Debug start failed: " + err));
    }

    private Action EditDebugControl(string action)
    {
      return () => DebugSend(action);
    }

    private void EditDebugStop()
    {
      DebugSend("stop");
    }

    private void DebugSend(string action)
    {
      if (_bridge == null) return;
      _bridge.DebugControl(action, r =>
      {
        if (r == null || !r.ok) Say("Debug " + action + " failed: " + (r != null ? r.detail : "no response"));
        if (action == "stop") { _debugActive = false; _debugState = null; }
        RefreshEdit();
      }, err => Say("Debug " + action + " failed: " + err));
    }

    private void StartDebugPoll()
    {
      if (_debugPoll != null) StopCoroutine(_debugPoll);
      _debugPoll = StartCoroutine(PollDebugState());
    }

    private IEnumerator PollDebugState()
    {
      var wait = new WaitForSeconds(1f);
      while (_debugActive && _bridge != null)
      {
        yield return wait;
        if (!_debugActive || _bridge == null) yield break;
        _bridge.DebugState(s =>
        {
          if (s == null || !_debugActive) return;
          _debugState = s;
          if (s.status == "none" || s.status == "exited" || s.status == "error")
          {
            _debugActive = false;
            if (s.status == "error" && !string.IsNullOrEmpty(s.error)) Say("Debug error: " + s.error);
            else if (s.status == "exited") Say("Program finished.");
          }
          else if (s.status == "stopped") RefreshOpenFile();
          RefreshEdit();
        }, e => { });
      }
      _debugPoll = null;
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
      if (_demoMode)
      {
        _editPanel.SetBody("Editing is disabled in this demo build.\nAsk JARVIS a question, or pinch a node to read its code.");
        return;
      }
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
      if (_editRunBtn != null) _editRunBtn.Interactable = _wsReady && !_runBusy;
      if (_editSelBtn != null) { _editSelBtn.Interactable = mode; _editSelBtn.Label.text = _editSelMode ? "SEL: ON" : "SEL: OFF"; }
      if (_editSubmitBtn != null) _editSubmitBtn.Interactable = mode && AllEvidenceFresh();
      bool isPy = mode && _editPath != null && _editPath.EndsWith(".py");
      if (_editIdeBtn != null) _editIdeBtn.Interactable = _wsReady;
      if (_editBreakBtn != null)
      {
        _editBreakBtn.Interactable = isPy;
        _editBreakBtn.Label.text = _bpLines.Count > 0 ? "BREAK (" + _bpLines.Count + ")" : "BREAK";
      }
      if (_editDebugBtn != null) _editDebugBtn.Interactable = isPy && !_debugActive;
      bool dbgStopped = _debugState != null && _debugState.status == "stopped";
      if (_editContBtn != null) _editContBtn.Interactable = _debugActive && dbgStopped;
      if (_editStepBtn != null) _editStepBtn.Interactable = _debugActive && dbgStopped;
      if (_editStopBtn != null) _editStopBtn.Interactable = _debugActive;

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
        .Append("  ·  ").Append(_undo.Count).Append(" undo");
      if (HasEditSel)
        sb.Append("  ·  sel ").Append(SelLo).Append('-').Append(SelHi);
      sb.Append('\n');
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
      if (_runBusy)
        sb.Append("<color=#").Append(Hex(pal.Cyan)).Append(">running pytest…</color>\n");
      if (_runOutput.Length > 0)
      {
        sb.Append("<color=#").Append(Hex(pal.Cyan)).Append("RUN OUTPUT:</color>\n");
        string[] runLines = _runOutput.ToString().Replace("\r", "").Split('\n');
        int shown0 = Mathf.Max(0, runLines.Length - 10);
        for (int i = shown0; i < runLines.Length; i++)
          sb.Append("  ").Append(Esc(runLines[i])).Append('\n');
      }
      WsDiagItem curDiag = DiagForLine(_editLine);
      if (curDiag != null && !string.IsNullOrEmpty(curDiag.message))
      {
        bool warn = curDiag.severity == "warning";
        sb.Append("<color=#").Append(Hex(warn ? pal.Orange : pal.Red)).Append(">L")
          .Append(_editLine).Append(' ').Append(Esc(curDiag.message)).Append("</color>\n");
      }
      if (_bpPath == _editPath && _bpLines.Count > 0)
      {
        var bps = new List<int>(_bpLines); bps.Sort();
        sb.Append("breakpoints: ");
        foreach (int b in bps) sb.Append(b).Append(' ');
        sb.Append('\n');
      }
      if (_debugActive || _debugState != null)
      {
        sb.Append("<color=#").Append(Hex(pal.Violet)).Append(">debug: ")
          .Append(_debugState != null ? _debugState.status : "starting").Append("</color>\n");
        if (dbgStopped && _debugState != null)
        {
          sb.Append("  stopped ").Append(Esc(_debugState.file ?? "")).Append(':')
            .Append(_debugState.line).Append('\n');
          if (_debugState.variables != null)
          {
            int shown = 0;
            foreach (WsDebugVarDto v in _debugState.variables)
            {
              if (v == null || shown >= 8) continue;
              sb.Append("    ").Append(Esc(v.name)).Append(" = ").Append(Esc(v.value)).Append('\n');
              shown++;
            }
          }
        }
        if (_debugState != null && _debugState.output != null && _debugState.output.Length > 0)
        {
          int shown1 = Mathf.Max(0, _debugState.output.Length - 6);
          for (int i = shown1; i < _debugState.output.Length; i++)
            sb.Append("  ").Append(Esc(_debugState.output[i])).Append('\n');
        }
      }
      sb.Append("\nEDIT LINE replaces ").Append(HasEditSel ? "lines " + SelLo + "-" + SelHi : "line " + _editLine)
        .Append(HasEditSel ? "" : " · ADD LINE BELOW inserts after it")
        .Append("\nVERIFY → REVIEW → SUBMIT, then approve.");
      _editPanel.SetBody(sb.ToString());
    }
  }
}
