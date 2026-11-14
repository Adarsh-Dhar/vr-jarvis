# Unity Runtime and Device Verification Guide

This document provides detailed instructions for completing the Unity runtime verification and device testing steps that cannot be performed in the current command-line environment.

## Overview

The following verification steps require access to:
- Unity Editor (GUI application)
- Meta XR Simulator (Meta Quest Link)
- Physical Meta Quest headset

These steps are marked as **CANNOT BE DONE in Current Environment** in the implementation plan.

---

## Section 2.1: Unity Runtime Verification

### Prerequisites

1. **Unity Editor Installation**
   - Unity Editor version: 6000.6.7f1 (matching project version)
   - Install from Unity Hub
   - Required modules: Android Build Support, iOS Build Support (if applicable)

2. **Project Setup**
   - Unity project location: `/Users/adarsh/Documents/vr-agent/ui`
   - Open project in Unity Editor
   - Resolve any missing dependencies

### Verification Steps

#### 2.1.1: Graph-Type-Aware Rendering Verification

**Objective:** Verify that CFG and DFG graphs are rendered with their correct graph types in Unity.

**Steps:**

1. **Start Unity Editor**
   ```bash
   # Navigate to Unity project
   cd /Users/adarsh/Documents/vr-agent/ui
   
   # Open in Unity Editor (via Unity Hub or command line)
   /Applications/Unity/Hub/Editor/6000.6.7f1/Unity.app/Contents/MacOS/Unity \
     -projectPath /Users/adarsh/Documents/vr-agent/ui
   ```

2. **Load Test Scene**
   - Open `Assets/ShowcaseSamples/JarvisVR/Scenes/JarvisSpatialWorkspace.unity`
   - Verify scene loads without errors

3. **Test CFG Rendering**
   - Use the agent tool to analyze a Python function and generate a CFG
   - Observe the graph in the Unity workspace
   - Verify:
     - Graph type is displayed as "Control Flow"
     - Nodes are color-coded by kind (entry, exit, condition, loop_header, etc.)
     - Edges have correct semantic labels (true, false, break, continue, etc.)
     - Source locations are visible on node hover

4. **Test DFG Rendering**
   - Use the agent tool to analyze a Python function and generate a DFG
   - Observe the graph in the Unity workspace
   - Verify:
     - Graph type is displayed as "Data Flow"
     - Nodes are color-coded by kind (definition, use, operation)
     - Edges have correct semantic labels (reaches, feeds, operand, returns)
     - Binding keys are visible on node hover

5. **Test Graph Type Switching**
   - Switch between CFG and DFG views for the same function
   - Verify graph type metadata is preserved
   - Verify visual representation changes appropriately

**Expected Results:**
- Both CFG and DFG graphs render correctly
- Graph types are visually distinct
- Node and edge semantics are preserved
- No generic dependency graph rendering occurs

**Files to Inspect:**
- `ui/Assets/ShowcaseSamples/JarvisVR/Runtime/JarvisGraphModel.cs`
- `ui/Assets/ShowcaseSamples/JarvisVR/Runtime/JarvisGraphNode.cs`
- `ui/Assets/ShowcaseSamples/JarvisVR/Runtime/JarvisGraphEdge.cs`

---

#### 2.1.2: Source Navigation Verification

**Objective:** Verify that graph nodes can navigate to source code and vice versa.

**Steps:**

1. **Graph-to-Code Navigation**
   - Generate a CFG or DFG for a Python function
   - Click on a graph node in Unity
   - Verify:
     - Source viewer highlights the corresponding code line
     - Correct file is displayed
     - Correct line number is highlighted
     - Column offset is used if available

2. **Code-to-Graph Lookup**
   - If implemented, select a line in the source viewer
   - Verify corresponding graph nodes are highlighted
   - Verify all relevant CFG/DFG nodes are shown

3. **Edge Navigation**
   - Click on a graph edge
   - Verify edge semantics are displayed
   - Verify connected nodes are highlighted

**Expected Results:**
- Node selection highlights correct source location
- Source navigation works bidirectionally
- Edge semantics are visible
- Multiple node selections are supported

---

#### 2.1.3: Interaction Tests

**Objective:** Verify graph interaction features work correctly.

**Steps:**

1. **Node Selection**
   - Select individual nodes
   - Select multiple nodes (if supported)
   - Verify selection state is visual

2. **Edge Traversal**
   - Click on edges to traverse connections
   - Expand a definition's reaching uses
   - Expand a use's reaching definitions
   - Verify traversal works both directions

3. **Graph Manipulation**
   - Pan the graph view
   - Zoom in/out
   - Drag nodes (if supported)
   - Verify layout is stable

4. **Performance Test**
   - Generate a CFG/DFG for a medium-size function (50+ lines)
   - Verify rendering is smooth (>30 FPS)
   - Verify interaction remains responsive

**Expected Results:**
- All interaction features work smoothly
- Graph performance is acceptable
- No crashes or freezes occur

---

## Section 2.2: Meta XR Simulator Testing

### Prerequisites

1. **Meta Quest Link Installation**
   - Install Meta Quest Link (PCVR application)
   - Available from Meta Quest website
   - Requires Meta account

2. **Simulator Setup**
   - Open Meta Quest Link
   - Launch XR Simulator
   - Configure simulator settings (device model, controllers)

3. **Unity XR Integration**
   - Install Meta XR SDK (if not already in project)
   - Configure XR plugin management in Unity
   - Set up OpenXR runtime

### Verification Steps

#### 2.2.1: Simulator Build and Deploy

**Steps:**

1. **Build for Android (Quest)**
   ```bash
   # In Unity Editor:
   # File > Build Settings
   # Platform: Android
   # Switch Platform
   # Build and Run
   ```

2. **Deploy to Simulator**
   - Launch Meta XR Simulator
   - In Unity, select "Build and Run"
   - Verify app deploys to simulator
   - Verify app launches without errors

3. **Test Graph Visualization in Simulator**
   - Navigate to the graph visualization feature
   - Generate a CFG for a test function
   - Verify graph renders in VR
   - Verify node selection works with controllers
   - Verify source navigation works

**Expected Results:**
- App builds successfully for Android
- App deploys to simulator
- Graph visualization works in VR
- Controller interactions work correctly

---

## Section 2.3: Physical Quest Headset Testing

### Prerequisites

1. **Meta Quest Headset**
   - Quest 2, Quest 3, or Quest Pro
   - Updated to latest firmware
   - Developer mode enabled

2. **USB Connection**
   - USB-C cable
   - Oculus Link or Air Link enabled

3. **Meta Quest Link**
   - PCVR application installed
   - Headset paired with PC

### Verification Steps

#### 2.3.1: Physical Device Build and Deploy

**Steps:**

1. **Connect Headset**
   - Connect Quest headset to PC via USB-C
   - Enable Oculus Link or Air Link
   - Verify connection in Meta Quest Link

2. **Build and Deploy**
   ```bash
   # In Unity Editor:
   # File > Build Settings
   # Platform: Android
   # Build and Run (select headset as target)
   ```

3. **Test on Physical Device**
   - Navigate to graph visualization in VR
   - Generate CFG/DFG for test functions
   - Verify rendering quality
   - Verify performance on actual hardware
   - Test controller interactions
   - Test source navigation

4. **Performance Testing**
   - Test with large graphs (100+ nodes)
   - Verify frame rate remains acceptable
   - Verify memory usage is reasonable
   - Check for thermal throttling

**Expected Results:**
- App runs on physical headset
- Graph visualization is performant
- Controller interactions are intuitive
- No major performance issues

---

## Section 2.4: Regression Testing in Unity

### Automated Tests

**Unity Test Runner:**

1. **EditMode Tests**
   ```bash
   # In Unity Editor:
   # Window > General > Test Runner
   # Run EditMode tests
   ```
   - Verify all EditMode tests pass
   - Check for serialization tests
   - Check for graph model tests

2. **PlayMode Tests**
   ```bash
   # In Unity Editor:
   # Window > General > Test Runner
   # Run PlayMode tests
   ```
   - Verify all PlayMode tests pass
   - Check for integration tests
   - Check for UI interaction tests

### Manual Test Checklist

**CFG Visualization:**
- [ ] Graph renders with correct node types
- [ ] Entry/exit nodes are distinct
- [ ] Condition nodes have true/false edges
- [ ] Loop headers have loop_back edges
- [ ] Break/continue edges are labeled
- [ ] Return/raise edges are labeled
- [ ] Finally routing is visible
- [ ] Source locations are accurate

**DFG Visualization:**
- [ ] Graph renders with correct node types
- [ ] Definitions are distinct from uses
- [ ] Operations are visible
- [ ] Reaching definition edges are labeled
- [ ] Operand edges are labeled
- [ ] Return relationships are visible
- [ ] Binding keys are visible
- [ ] Source locations are accurate

**Interaction:**
- [ ] Node selection works
- [ ] Edge selection works
- [ ] Source navigation works
- [ ] Graph type switching works
- [ ] Zoom/pan works
- [ ] Performance is acceptable

---

## Section 2.5: Known Limitations and Future Work

### Current Limitations

1. **Unity Editor Access**
   - Current environment is command-line only
   - Unity Editor requires GUI access
   - Remote/headless Unity builds possible but not configured

2. **Device Access**
   - No physical Quest headset available
   - Meta XR Simulator not installed
   - PCVR environment not configured

3. **Test Infrastructure**
   - Unity automated tests not yet implemented
   - No CI/CD integration for Unity tests
   - No automated VR testing framework

### Future Enhancements

1. **Headless Unity Builds**
   - Configure Unity for batch mode builds
   - Set up automated build pipeline
   - Integrate with CI/CD

2. **Automated VR Testing**
   - Implement Unity Test Runner integration
   - Add PlayMode tests for graph visualization
   - Consider automated screenshot comparison

3. **Remote Device Testing**
   - Set up remote Quest device testing
   - Use Quest over Wi-Fi for testing
   - Implement telemetry collection

---

## Section 2.6: Verification Reporting

### Test Report Template

After completing Unity/device verification, create a report with:

**Environment:**
- Unity Editor version: [version]
- Meta XR SDK version: [version]
- Quest headset model: [model]
- PC specifications: [CPU, GPU, RAM]

**Test Results:**
- Unity build: [PASS/FAIL]
- EditMode tests: [X/X passing]
- PlayMode tests: [X/X passing]
- Simulator tests: [PASS/FAIL]
- Physical device tests: [PASS/FAIL]

**Performance Metrics:**
- Build time: [seconds]
- App startup time: [seconds]
- Graph rendering FPS: [FPS]
- Memory usage: [MB]

**Known Issues:**
- [List any issues found]

**Recommendations:**
- [List any improvements needed]

---

## Conclusion

This guide provides complete instructions for completing the Unity runtime and device verification steps. These steps are essential for the final release gate but cannot be performed in the current command-line environment due to the requirement for Unity Editor GUI access and physical device access.

Once these steps are completed, the JARVIS CFG/DFG system will meet the full "Implemented — Basic" or better status for both control-flow and data-flow visualization in VR.

---

## Workspace Edit Loop (VR line editing → verify → review → submit → approve → promote)

The Edit panel (CODE mode, right side) edits files inside the sandbox worktree. Every write goes through `POST /workspace/edit` with `base_hash` conflict detection — never whole-file PUT, so a truncated view cannot corrupt a file.

### Steps to verify in the headset

1. **Open a file**: REPOS → pick a repository → open a small source file.
2. **EDIT: ON**: press EDIT ON in the Edit panel. The file reloads from the worktree (`source == "worktree"`). Truncated files refuse edit mode.
3. **Line edits**: LINE ^ / LINE v moves the cursor (amber `»` gutter, page follows). EDIT LINE opens the keyboard prefilled with the line — leading whitespace is preserved. ADD LINE BELOW inserts after the cursor. DELETE LINE removes it. UNDO reverses the last op (inverse line edits only).
4. **Conflict handling**: if the file changes in an IDE, the next edit returns 409 and the panel reloads automatically.
5. **Syntax feedback**: per-edit `syntax_errors` mark bad lines red with the message.
6. **VERIFY**: runs `/workspace/verify` (tests + typecheck + security, live — refused when `JARVIS_CACHED_TESTS=1`). The TESTS panel shows the same run shape as an agent turn.
7. **REVIEW**: runs `/workspace/review` — the independent `code_reviewer` agent on the worktree diff. With `JARVIS_ALLOW_HUMAN_REVIEW=1` the server records a human acceptance instead (off by default).
8. **Status polling**: the Edit panel polls `/workspace/status` every 2 s; all four evidence keys must read `fresh` before SUBMIT enables. An IDE edit makes them `stale`/`missing` again.
9. **SUBMIT**: calls `/workspace/submit`, which runs the same `verification_blockers` gate as `/approve` and sets `pending_approval`. On 409 the blockers are shown via the status poll.
10. **Approve/promote**: unchanged — HOLD 2s TO APPROVE commits to the sandbox branch, PROMOTE TO MAIN merges and re-indexes.

### Server routes added

- `POST /workspace/verify` — `{session_id, steps?, test_files?, repo?, request_id?}`
- `POST /workspace/review` — `{session_id, repo?, request_id?}`
- `POST /workspace/submit` — `{session_id, repo?, request_id?}`

### Tests

`server/tests/test_workspace_verify.py` covers evidence recording, cached-mode and busy-turn refusal, submit gating on all four fresh evidence keys, `pending_approval`, and staleness after a new edit.
