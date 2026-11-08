# Unity Runtime Visualization Verification Guide

## Purpose
This guide provides step-by-step instructions to verify the runtime visualization implementation in Unity after the code changes have been completed.

## Prerequisites
- Unity Editor 6000.6.7f1 (or compatible version) is open with the vr-agent project
- Python server is running
- All Python tests have passed (19/19 tests passed successfully)

## Files Modified

### C# Files
1. `ui/Assets/ShowcaseSamples/JarvisVR/Runtime/JarvisBridge.cs`
   - Added `exception_type` and `exception_id` to `RuntimeEventDto`
   - Added `runtime_limitations` string array to `SceneCommand`

2. `ui/Assets/ShowcaseSamples/JarvisVR/Runtime/JarvisSpatialWorkspace.cs`
   - Enhanced `show_runtime_panel` handler to display:
     - Exception events with type, file, line, function
     - All limitations from `runtime_limitations` array
     - Partial warning even when not truncated
     - Both elapsed time and duration for function calls
     - Fixed omitted-event count logic (compares received vs total)

### Python Files
1. `server/ai_agents/runtime_trace_runner.py`
   - Fixed argument forwarding (split at `--`, exclude sys.argv[0])
   - Fixed exception deduplication (instance identity with object retention)
   - Fixed multiple unsupported limitation reporting
   - Added proper sys.path, working directory, and sys.argv handling

2. `server/ai_agents/tools/visualization_spatial_tools.py`
   - Added `runtime_limitations` to show_runtime_panel command

3. `server/tests/test_runtime_tracing.py`
   - Replaced weak tests with real fixture-based tests
   - Added 4 new tests for comprehensive coverage

## Verification Steps

### Step 1: Verify Unity Compilation
1. In Unity Editor, check the Console for any compilation errors
2. Expected: No compilation errors related to `JarvisBridge.cs` or `JarvisSpatialWorkspace.cs`
3. If errors appear, check:
   - `RuntimeEventDto` has the new fields: `exception_type`, `exception_id`
   - `SceneCommand` has the new field: `runtime_limitations`
   - `show_runtime_panel` case handler matches the updated implementation

### Step 2: Start Python Server
1. Navigate to the server directory:
   ```bash
   cd /Users/adarsh/Documents/vr-agent/server
   ```
2. Start the server:
   ```bash
   python3 jarvis_server.py
   ```
3. Verify server starts successfully and is listening on port 8000

### Step 3: Load JARVIS Workspace Scene
1. In Unity Project window, navigate to: `Assets/ShowcaseSamples/JarvisVR/Scenes/`
2. Open the JARVIS workspace scene (e.g., `JarvisWorkspace.unity`)
3. Enter Play Mode

### Step 4: Connect to Server
1. In the VR workspace, the system should automatically connect to the server
2. Verify the status indicator shows "Online" or green
3. If not connected, check:
   - Server is running on http://127.0.0.1:8000
   - JARVIS_TOKEN matches between Unity and server
   - No firewall blocking the connection

### Step 5: Launch Sample Application
1. Use voice command or text input to ask JARVIS:
   ```
   Launch the sample application for runtime tracing
   ```
2. Alternatively, use the Runtime Intelligence agent to start the application:
   - Application ID: `test_app`
   - Entrypoint: `jarvis-tests/fixtures/integration-test-infrastructure/runtime/sample_app.py`
   - Timeout: 10 seconds

### Step 6: Collect Execution Trace
1. Ask JARVIS:
   ```
   Collect the execution trace for the sample application
   ```
2. Wait for the application to complete (should take ~2-3 seconds)
3. Verify the trace collection succeeds

### Step 7: Visualize Execution Flow
1. Ask JARVIS:
   ```
   Visualize the execution flow
   ```
2. Expected results:
   - A runtime graph appears with individual function invocation nodes
   - Edges show parent-child relationships between function calls
   - The graph uses dotted green edges for runtime-observed edges
   - Multiple nodes should be visible (sample_app has ~10-15 function calls)

### Step 8: Verify Runtime Panel
1. The runtime panel should automatically open in the right-side panel area
2. Verify the panel displays:
   - **Application name**: "sample_app" or similar
   - **Trace ID**: First 8 characters of trace ID
   - **Status**: "COMPLETED" or "PARTIAL"
   - **Duration**: Total execution time in milliseconds
   - **Trace events**: Total number of events captured
   - **Execution timeline**: First 30 events with:
     - Function name with indentation showing call depth
     - Elapsed time (when function was called)
     - Duration (how long the function took)
   - **Provenance**: "RUNTIME OBSERVED"

### Step 9: Test Exception Display
1. Create or use the exception fixture:
   ```
   Launch test_exception_fixture.py for runtime tracing
   ```
2. Collect trace and visualize
3. Verify the runtime panel shows:
   - Exception events in the timeline
   - Exception type (e.g., "ValueError")
   - File and line number where exception occurred
   - Function name where exception was raised
   - Multiple exceptions should be shown separately (not duplicates)

### Step 10: Test Event Limit Display
1. Launch the limits fixture with event limit:
   ```
   Launch test_limits_fixture.py with argument --event-limit 20
   ```
2. Configure max_events to 10 in the runner
3. Collect trace and visualize
4. Verify the runtime panel shows:
   - WARNING: "Trace was truncated at event limit"
   - "Showing X of Y events" where X < Y
   - Limitations section mentions truncation

### Step 11: Test Partial Status Display
1. Launch the multiple unsupported fixture:
   ```
   Launch test_multiple_unsupported_fixture.py
   ```
2. Collect trace and visualize
3. Verify the runtime panel shows:
   - Status: "PARTIAL"
   - WARNING: "Trace is partial (limitations detected)"
   - LIMITATIONS section with multiple entries:
     - "generator_function" or "coroutine_function"
     - "background_thread_execution"

### Step 12: Verify in Meta XR Simulator (Optional but Recommended)
1. Switch Unity to Meta XR Simulator platform
2. Enter Play Mode
3. Repeat steps 5-11 in the simulator
4. Verify:
   - Runtime graph renders correctly in VR
   - Runtime panel is readable in VR
   - Text is legible at the correct distance
   - Panel positioning is comfortable for viewing

## Expected Test Results

### Python Backend Tests (Already Passed)
```
19 passed, 21 warnings in 11.49s
```

All tests should pass:
- Basic execution with real fixture
- Exception capture and deduplication
- Recursive function calls with distinct IDs
- Event limit truncation
- Duration limit enforcement
- Function returns matching calls
- CLI argument forwarding
- Local imports from sibling files
- Multiple unsupported features reported

### Unity Verification Checklist
- [ ] No C# compilation errors
- [ ] Server connects successfully
- [ ] Sample application launches
- [ ] Trace collection succeeds
- [ ] Runtime graph appears with nodes and edges
- [ ] Runtime panel opens with correct data
- [ ] Function calls show elapsed time and duration
- [ ] Exceptions display type, file, line, function
- [ ] Partial status shows warning and limitations
- [ ] Event truncation shows correct counts
- [ ] Multiple limitations all displayed
- [ ] Meta XR Simulator renders correctly (if tested)

## Troubleshooting

### Compilation Errors
If Unity shows compilation errors:
1. Check that all C# fields are properly named (case-sensitive)
2. Verify `RuntimeEventDto` has both new fields
3. Verify `SceneCommand` has `runtime_limitations` array
4. Check for syntax errors in the `show_runtime_panel` case

### Server Connection Issues
If Unity cannot connect to the server:
1. Verify server is running: `curl http://127.0.0.1:8000/health`
2. Check JARVIS_TOKEN in Unity Settings matches server environment
3. Verify no firewall blocking port 8000

### Trace Collection Issues
If trace collection fails:
1. Check server logs for errors
2. Verify the fixture file exists in the worktree
3. Check that the worktree path is correctly configured
4. Verify the trace runner script is executable

### Panel Display Issues
If the runtime panel doesn't display correctly:
1. Check that `runtime_limitations` is being sent from Python
2. Verify the panel handler receives all expected fields
3. Check Unity Console for JSON parsing errors
4. Verify the panel text formatting doesn't overflow

## Success Criteria

The implementation is considered complete when:
1. All 19 Python tests pass ✅ (Already completed)
2. Unity compiles without errors
3. Runtime graph appears with function invocations and parent-child edges
4. Runtime panel displays execution summary, timeline, exceptions, and limitations
5. Exception events show type, file, line, and function
6. Partial traces show warnings and list all limitations
7. Event limit truncation shows correct displayed vs total counts
8. Meta XR Simulator renders correctly (optional but recommended)

## Next Steps After Verification

Once verification is complete:
1. If all checks pass, the implementation is ready for "Implemented — basic" status
2. Update the capability report to reflect the completed implementation
3. Consider the next milestone: Quest headset build and testing for actual headset rendering validation
