# Complete Implementation Guide for Remaining Work

This guide provides detailed instructions for completing all remaining work on the JARVIS CFG/DFG system, divided into two sections:

1. **Environment-Dependent Verification** (requires Unity Editor, Simulator, or Headset)
2. **Optional Future Development** (code-based enhancements)

---

## Part 1: Environment-Dependent Verification

### Overview

These verification steps require access to external environments not available in the current command-line setup.

---

### Section 1.1: Unity Runtime Verification

#### Prerequisites

1. **Unity Editor Installation**
   - Unity Editor version: 6000.6.7f1 (matching project version)
   - Install from Unity Hub
   - Required modules: Android Build Support, iOS Build Support (if applicable)

2. **Project Setup**
   - Unity project location: `/Users/adarsh/Documents/vr-agent/ui`
   - Open project in Unity Editor
   - Resolve any missing dependencies

#### Step 1.1.1: Graph-Type-Aware Rendering Verification

**Objective:** Verify that CFG and DFG graphs are rendered with their correct graph types in Unity.

**Detailed Steps:**

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
   - Check Console for any warnings or errors

3. **Test CFG Rendering**
   - Start the backend server if not running:
     ```bash
     cd /Users/adarsh/Documents/vr-agent/server
     python3 jarvis_server.py
     ```
   - In Unity, use the agent tool to analyze a Python function and generate a CFG
   - Example function to test:
     ```python
     def process(value):
         if value > 0:
             return value
         else:
             return -value
     ```
   - Observe the graph in the Unity workspace
   - Verify the following:
     - **Graph type is displayed as "Control Flow"**
     - **Nodes are color-coded by kind:**
       - Entry nodes: distinct color (e.g., green)
       - Exit nodes: distinct color (e.g., red)
       - Condition nodes: distinct color (e.g., blue)
       - Loop header nodes: distinct color (e.g., purple)
       - Statement nodes: distinct color (e.g., gray)
     - **Edges have correct semantic labels:**
       - True edges: labeled "true"
       - False edges: labeled "false"
       - Break edges: labeled "break"
       - Continue edges: labeled "continue"
       - Return edges: labeled "return"
       - Raise edges: labeled "raise"
     - **Source locations are visible on node hover:**
       - Hover over a node
       - Verify file path is shown
       - Verify line number is shown
       - Verify column offset is shown (if available)

4. **Test DFG Rendering**
   - Use the agent tool to analyze the same function and generate a DFG
   - Observe the graph in the Unity workspace
   - Verify the following:
     - **Graph type is displayed as "Data Flow"**
     - **Nodes are color-coded by kind:**
       - Definition nodes: distinct color (e.g., green)
       - Use nodes: distinct color (e.g., blue)
       - Operation nodes: distinct color (e.g., orange)
     - **Edges have correct semantic labels:**
       - Reaching definition edges: labeled "reaches"
       - Operand edges: labeled "operand"
       - Return relationship edges: labeled "returns"
     - **Binding keys are visible on node hover:**
       - Hover over a definition node
       - Verify binding key is shown (e.g., "test::process::value")

5. **Test Graph Type Switching**
   - Switch between CFG and DFG views for the same function
   - Verify:
     - Graph type metadata is preserved
     - Visual representation changes appropriately
     - No data is lost during the switch
     - Both graphs remain accessible

**Expected Results:**
- Both CFG and DFG graphs render correctly
- Graph types are visually distinct
- Node and edge semantics are preserved
- No generic dependency graph rendering occurs
- Source locations are accurate

**Files to Inspect:**
- `ui/Assets/ShowcaseSamples/JarvisVR/Runtime/JarvisGraphModel.cs`
- `ui/Assets/ShowcaseSamples/JarvisVR/Runtime/JarvisGraphNode.cs`
- `ui/Assets/ShowcaseSamples/JarvisVR/Runtime/JarvisGraphEdge.cs`

**Troubleshooting:**
- If graph type is not displayed: Check `JarvisGraphModel.cs` for graph_type field
- If node colors are incorrect: Check node rendering logic in `JarvisGraphNode.cs`
- If edge labels are missing: Check edge rendering logic in `JarvisGraphEdge.cs`

---

#### Step 1.1.2: Source Navigation Verification

**Objective:** Verify that graph nodes can navigate to source code and vice versa.

**Detailed Steps:**

1. **Graph-to-Code Navigation**
   - Generate a CFG or DFG for a Python function
   - Click on a graph node in Unity
   - Verify:
     - Source viewer highlights the corresponding code line
     - Correct file is displayed in the source viewer
     - Correct line number is highlighted
     - Column offset is used if available
     - Highlighting is visually distinct

2. **Test with Different Node Types**
   - Test with entry node (should highlight function definition)
   - Test with condition node (should highlight if/while condition)
   - Test with statement node (should highlight assignment or other statement)
   - Test with loop header node (should highlight for/while loop)
   - Verify each node type navigates to the correct location

3. **Code-to-Graph Lookup (if implemented)**
   - Select a line in the source viewer
   - Verify:
     - Corresponding graph nodes are highlighted
     - All relevant CFG/DFG nodes are shown
     - Multiple nodes are highlighted if a line maps to multiple nodes

4. **Edge Navigation**
   - Click on a graph edge
   - Verify:
     - Edge semantics are displayed (edge kind, condition if applicable)
     - Connected nodes are highlighted
     - Source locations for both endpoints are shown

5. **Test with Complex Functions**
   - Test with a function containing nested structures:
     ```python
     def complex_process(items):
         result = []
         for item in items:
             if item > 0:
                 try:
                     value = item / 2
                 except:
                     value = 0
                 result.append(value)
         return result
     ```
   - Verify navigation works correctly for all nodes
   - Verify highlighting is accurate for nested constructs

**Expected Results:**
- Node selection highlights correct source location
- Source navigation works bidirectionally
- Edge semantics are visible
- Multiple node selections are supported
- Highlighting is accurate for complex functions

**Troubleshooting:**
- If navigation doesn't work: Check agent tool integration for source location passing
- If highlighting is incorrect: Verify line/column numbers in backend serialization
- If multiple nodes not highlighted: Check if code-to-graph lookup is implemented

---

#### Step 1.1.3: Interaction Tests

**Objective:** Verify graph interaction features work correctly.

**Detailed Steps:**

1. **Node Selection**
   - Select individual nodes by clicking
   - Verify selection state is visual (e.g., node outline changes color)
   - Test with multiple nodes (if supported)
   - Verify multiple selection works correctly

2. **Edge Traversal**
   - Click on edges to traverse connections
   - Expand a definition's reaching uses:
     - Right-click on a definition node
     - Select "Show Reaching Uses" (or equivalent)
     - Verify all uses are highlighted
   - Expand a use's reaching definitions:
     - Right-click on a use node
     - Select "Show Reaching Definitions" (or equivalent)
     - Verify all definitions are highlighted
   - Verify traversal works both directions

3. **Graph Manipulation**
   - Pan the graph view:
     - Click and drag on empty space
     - Verify smooth panning
   - Zoom in/out:
     - Use mouse wheel or pinch gesture
     - Verify smooth zooming
     - Verify node labels remain readable
   - Drag nodes (if supported):
     - Click and drag a node
     - Verify node moves
     - Verify edges update accordingly
   - Verify layout is stable after manipulation

4. **Performance Test**
   - Generate a CFG/DFG for a medium-size function (50+ lines)
   - Example function:
     ```python
     def medium_process(data):
         result = []
         for item in data:
             if item > 0:
                 if item < 10:
                     result.append(item * 2)
                 elif item < 100:
                     result.append(item * 3)
                 else:
                     result.append(item * 4)
             else:
                 result.append(0)
         return result
     ```
   - Verify rendering is smooth (>30 FPS)
   - Verify interaction remains responsive
   - Check for stuttering or lag

5. **Stress Test**
   - Generate a CFG/DFG for a large function (100+ lines)
   - Verify:
     - Graph renders without crashing
     - Performance remains acceptable (>20 FPS)
     - Memory usage is reasonable
     - No memory leaks

**Expected Results:**
- All interaction features work smoothly
- Graph performance is acceptable
- No crashes or freezes occur
- Memory usage is reasonable

**Troubleshooting:**
- If performance is poor: Check graph rendering optimization
- If crashes occur: Check for memory leaks in graph management
- If interactions are unresponsive: Check event handling implementation

---

### Section 1.2: Meta XR Simulator Testing

#### Prerequisites

1. **Meta Quest Link Installation**
   - Install Meta Quest Link (PCVR application)
   - Available from Meta Quest website
   - Requires Meta account

2. **Simulator Setup**
   - Open Meta Quest Link
   - Launch XR Simulator
   - Configure simulator settings:
     - Device model: Quest 2 or Quest 3
     - Controller type: Touch controllers
     - Resolution: Default or custom

3. **Unity XR Integration**
   - Install Meta XR SDK (if not already in project)
   - Configure XR plugin management in Unity:
     - Edit > Project Settings > XR Plug-in Management
     - Enable OpenXR
     - Install required packages
   - Set up OpenXR runtime

#### Step 1.2.1: Simulator Build and Deploy

**Detailed Steps:**

1. **Build for Android (Quest)**
   - In Unity Editor:
     - File > Build Settings
     - Platform: Android
     - Switch Platform (if not already Android)
     - Wait for platform switch to complete
   - Configure build settings:
     - Texture Compression: ASTC
     - Graphics APIs: OpenGLES3
     - Minimum API Level: 29 (Android 10)
     - Target API Level: 33 (Android 13)
   - Click "Build and Run"

2. **Deploy to Simulator**
   - Launch Meta XR Simulator
   - In Unity, select "Build and Run"
   - Verify:
     - Build completes successfully
     - App deploys to simulator
     - App launches without errors
     - No build warnings

3. **Test Graph Visualization in Simulator**
   - Navigate to the graph visualization feature in VR
   - Generate a CFG for a test function
   - Verify:
     - Graph renders in VR
     - Nodes are visible and distinguishable
     - Edges are visible
     - Text labels are readable
   - Test node selection with controllers:
     - Point controller at a node
     - Press trigger to select
     - Verify selection is visual
   - Test source navigation:
     - Select a node
     - Verify source code is displayed
     - Verify highlighting is visible
   - Test graph manipulation:
     - Use thumbstick to pan
     - Use grip buttons to grab/drag
     - Verify smooth interaction

4. **Test Different Graph Types**
   - Generate a DFG for the same function
   - Verify:
     - Graph type switches correctly
     - Different node colors are visible
     - Different edge labels are visible
   - Test with complex graphs:
     - Generate graphs for functions with 50+ lines
     - Verify performance in VR
     - Verify text remains readable

**Expected Results:**
- App builds successfully for Android
- App deploys to simulator
- Graph visualization works in VR
- Controller interactions work correctly
- Performance is acceptable in VR

**Troubleshooting:**
- If build fails: Check Android SDK installation
- If deployment fails: Check Meta XR Simulator connection
- If graph doesn't render: Check Unity VR camera setup
- If text is unreadable: Check text scaling in VR

---

### Section 1.3: Physical Quest Headset Testing

#### Prerequisites

1. **Meta Quest Headset**
   - Quest 2, Quest 3, or Quest Pro
   - Updated to latest firmware
   - Developer mode enabled (Meta Quest Developer Hub)

2. **USB Connection**
   - USB-C cable (USB 3.0 recommended)
   - Oculus Link or Air Link enabled

3. **Meta Quest Link**
   - PCVR application installed
   - Headset paired with PC

#### Step 1.3.1: Physical Device Build and Deploy

**Detailed Steps:**

1. **Connect Headset**
   - Connect Quest headset to PC via USB-C
   - Enable Oculus Link in headset settings
     - Settings > Quick Settings > Oculus Link
   - Or enable Air Link:
     - Settings > Experimental > Air Link
   - Verify connection in Meta Quest Link:
     - Headset should appear as connected
     - Connection quality should be "Good" or better

2. **Build and Deploy**
   - In Unity Editor:
     - File > Build Settings
     - Platform: Android
     - Ensure settings match simulator configuration
     - Click "Build and Run"
     - Select headset as target (if multiple devices available)
   - Verify:
     - Build completes successfully
     - App installs on headset
     - App launches on headset

3. **Test on Physical Device**
   - Put on headset
   - Navigate to the JARVIS app
   - Launch the app
   - Navigate to graph visualization feature
   - Generate CFG/DFG for test functions
   - Verify:
     - Graph rendering quality is good
     - Node colors are distinct
     - Text is readable
     - No visual artifacts

4. **Test Controller Interactions**
   - Test node selection:
     - Point controller at node
     - Press trigger
     - Verify selection feedback
   - Test graph manipulation:
     - Use thumbstick to pan
     - Use grip to grab
     - Verify smooth interactions
   - Test source navigation:
     - Select a node
     - Verify source panel appears
     - Verify text is readable

5. **Performance Testing**
   - Test with large graphs (100+ nodes):
     - Generate CFG for complex function
     - Verify frame rate remains acceptable (>30 FPS)
     - Check for stuttering
   - Test memory usage:
     - Monitor headset performance
     - Verify no out-of-memory errors
     - Check for memory leaks after extended use
   - Test thermal performance:
     - Use app for 10+ minutes
     - Check for thermal throttling
     - Verify performance remains stable

6. **Comfort Testing**
   - Test text readability at different distances
   - Test with different lighting conditions
   - Verify comfortable viewing experience
   - Check for motion sickness (graph manipulation)

**Expected Results:**
- App runs on physical headset
- Graph visualization is performant
- Controller interactions are intuitive
- No major performance issues
- Comfortable viewing experience

**Troubleshooting:**
- If connection fails: Check USB cable quality
- If app crashes: Check log files in headset
- If performance is poor: Optimize graph rendering
- If text is unreadable: Adjust text scaling

---

## Part 2: Optional Future Development

These are code-based enhancements that can be implemented in the current environment but are not required for P0/P1 completion.

---

### Section 2.1: Full Async Semantics (Phase 4.5)

**Current Status:** Basic node dispatch only

**Goal:** Model async iteration, suspension, and resumption

**Implementation Steps:**

1. **File:** `server/ai_agents/intelligence/controlflow/python_cfg.py`

2. **Enhance AsyncFor CFG Construction**
   ```python
   def _build_async_for(self, statement, cfg, ctx) -> FlowResult:
       """Build CFG for async for loops with suspension points."""
       # Create suspension node before iteration
       suspension_id = ctx.generate_node_id()
       suspension_node = CFGNode(
           id=suspension_id,
           kind='suspension',
           label='await iter',
           function_id=ctx.function_id,
           file=ctx.file,
           start_line=statement.lineno,
           end_line=statement.lineno,
           ast_kind='AsyncFor',
           metadata={'suspension_point': 'async_iteration'}
       )
       cfg.add_node(suspension_node)
       
       # Build rest of for loop with suspension points
       # ... existing for loop logic ...
       
       # Add suspension edges
       self._add_edge(cfg, ctx, suspension_id, loop_header_id, 'resume')
   ```

3. **Enhance AsyncWith CFG Construction**
   ```python
   def _build_async_with(self, statement, cfg, ctx) -> FlowResult:
       """Build CFG for async with with async context manager."""
       # Create suspension node for __aenter__
       enter_suspension_id = ctx.generate_node_id()
       enter_suspension_node = CFGNode(
           id=enter_suspension_id,
           kind='suspension',
           label='await __aenter__',
           function_id=ctx.function_id,
           file=ctx.file,
           start_line=statement.lineno,
           end_line=statement.lineno,
           ast_kind='AsyncWith',
           metadata={'suspension_point': 'async_enter'}
       )
       cfg.add_node(enter_suspension_node)
       
       # Create suspension node for __aexit__
       exit_suspension_id = ctx.generate_node_id()
       exit_suspension_node = CFGNode(
           id=exit_suspension_id,
           kind='suspension',
           label='await __aexit__',
           function_id=ctx.function_id,
           file=ctx.file,
           start_line=statement.lineno,
           end_line=statement.lineno,
           ast_kind='AsyncWith',
           metadata={'suspension_point': 'async_exit'}
       )
       cfg.add_node(exit_suspension_node)
   ```

4. **Add Await Suspension Points**
   ```python
   def _build_await(self, node, cfg, ctx) -> FlowResult:
       """Build CFG for await expressions."""
       await_id = ctx.generate_node_id()
       await_node = CFGNode(
           id=await_id,
           kind='suspension',
           label='await',
           function_id=ctx.function_id,
           file=ctx.file,
           start_line=node.lineno,
           end_line=node.lineno,
           ast_kind='Await',
           metadata={'suspension_point': 'await_expression'}
       )
       cfg.add_node(await_node)
       
       # Continue after suspension
       return FlowResult(entry_nodes=[await_id], normal_exits=[await_id], abrupt_exits=[])
   ```

5. **Add Tests**
   - File: `tests/unit/controlflow/test_async_semantics.py`
   - Test async for loop suspension
   - Test async with suspension
   - Test await suspension points
   - Test nested async constructs

**Acceptance Criteria:**
- All async constructs have explicit suspension nodes
- Suspension points are labeled with their purpose
- CFG clearly shows where execution may be suspended
- DFG can track values across suspension points

---

### Section 2.2: Full Generator Semantics (Phase 4.6)

**Current Status:** Basic node dispatch only

**Goal:** Model yield suspension/resumption and yield from

**Implementation Steps:**

1. **File:** `server/ai_agents/intelligence/controlflow/python_cfg.py`

2. **Enhance Yield CFG Construction**
   ```python
   def _build_yield(self, node, cfg, ctx) -> FlowResult:
       """Build CFG for yield statements."""
       yield_id = ctx.generate_node_id()
       yield_node = CFGNode(
           id=yield_id,
           kind='suspension',
           label='yield',
           function_id=ctx.function_id,
           file=ctx.file,
           start_line=node.lineno,
           end_line=node.lineno,
           ast_kind='Yield',
           metadata={
               'suspension_point': 'yield',
               'yielded_value': ast.unparse(node.value) if node.value else None
           }
       )
       cfg.add_node(yield_node)
       
       # Yield is an abrupt completion that suspends the generator
       completion = Completion(
           node_id=yield_id,
           kind='yield',
           intended_target=ctx.function_id,  # Generator will resume at caller
           source_metadata={'line': node.lineno, 'file': ctx.file},
           completion_id=ctx.generate_completion_id()
       )
       
       return FlowResult(entry_nodes=[yield_id], normal_exits=[], abrupt_exits=[completion])
   ```

3. **Enhance YieldFrom CFG Construction**
   ```python
   def _build_yield_from(self, node, cfg, ctx) -> FlowResult:
       """Build CFG for yield from statements."""
       yield_from_id = ctx.generate_node_id()
       yield_from_node = CFGNode(
           id=yield_from_id,
           kind='suspension',
           label='yield from',
           function_id=ctx.function_id,
           file=ctx.file,
           start_line=node.lineno,
           end_line=node.lineno,
           ast_kind='YieldFrom',
           metadata={
               'suspension_point': 'yield_from',
               'delegated_generator': ast.unparse(node.value)
           }
       )
       cfg.add_node(yield_from_node)
       
       # Yield from delegates to another generator
       completion = Completion(
           node_id=yield_from_id,
           kind='yield',
           intended_target=ctx.function_id,
           source_metadata={'line': node.lineno, 'file': ctx.file},
           completion_id=ctx.generate_completion_id(),
           metadata={'delegated': True}
       )
       
       return FlowResult(entry_nodes=[yield_from_id], normal_exits=[], abrupt_exits=[completion])
   ```

4. **Add Tests**
   - File: `tests/unit/controlflow/test_generator_semantics.py`
   - Test simple yield
   - Test yield from
   - Test yield in loops
   - Test yield with try/finally

**Acceptance Criteria:**
- Yield statements create suspension nodes
- Yield from delegates to sub-generators
- CFG shows generator suspension/resumption points
- DFG can track yielded values

---

### Section 2.3: Exception Groups (Phase 4.7)

**Current Status:** Not implemented

**Goal:** Support TryStar and except* (Python 3.11+)

**Implementation Steps:**

1. **Check Python Version Support**
   ```python
   import sys
   if sys.version_info >= (3, 11):
       # Exception groups are supported
   else:
       # Mark as unsupported
   ```

2. **File:** `server/ai_agents/intelligence/controlflow/python_cfg.py`

3. **Add TryStar Support**
   ```python
   def _build_trystar(self, statement, cfg, ctx) -> FlowResult:
       """Build CFG for try* statements (exception groups)."""
       try_star_id = ctx.generate_node_id()
       try_star_node = CFGNode(
           id=try_star_id,
           kind='statement',
           label='try*',
           function_id=ctx.function_id,
           file=ctx.file,
           start_line=statement.lineno,
           end_line=statement.lineno,
           ast_kind='TryStar',
           metadata={'exception_group': True}
       )
       cfg.add_node(try_star_node)
       
       # Build try body
       body_result = self._build_suite(statement.body, cfg, ctx)
       
       # Build except* handlers (exception group handlers)
       handler_join_id = ctx.generate_node_id()
       for handler in statement.excepthandlers:
           handler_id = ctx.generate_node_id()
           handler_node = CFGNode(
               id=handler_id,
               kind='exception_dispatch',
               label='except*',
               function_id=ctx.function_id,
               file=ctx.file,
               start_line=handler.lineno if hasattr(handler, 'lineno') else statement.lineno,
               end_line=handler.lineno if hasattr(handler, 'lineno') else statement.lineno,
               ast_kind='ExceptStar',
               metadata={'exception_group_handler': True}
           )
           cfg.add_node(handler_node)
           
           # Connect try to handler
           self._add_edge(cfg, ctx, try_star_id, handler_id, 'exception_group')
           
           # Build handler body
           handler_result = self._build_suite(handler.body, cfg, ctx)
           for handler_exit in handler_result.normal_exits:
               self._add_edge(cfg, ctx, handler_exit, handler_join_id, 'next')
       
       return FlowResult(entry_nodes=[try_star_id], normal_exits=[handler_join_id], abrupt_exits=[])
   ```

4. **Add Diagnostic for Unsupported Python Version**
   ```python
   if not self._supports_exception_groups():
       ctx.add_diagnostic(
           "exception_groups_unsupported",
           statement.lineno,
           "Exception groups (try*/except*) require Python 3.11+",
           "warning"
       )
   ```

5. **Add Tests**
   - File: `tests/unit/controlflow/test_exception_groups.py`
   - Test basic exception group
   - Test multiple exception handlers
   - Test partial exception matching
   - Test unsupported version diagnostic

**Acceptance Criteria:**
- TryStar creates correct CFG structure
- Except* handlers are modeled
- Unsupported versions emit diagnostics
- Partial exception matching is represented

---

### Section 2.4: Full Nested Expression Operations (Phase 7.3)

**Current Status:** Partial - basic structure

**Goal:** Represent complete input/output relationships for nested expressions

**Implementation Steps:**

1. **File:** `server/ai_agents/intelligence/dataflow/python_extractor.py`

2. **Implement ExpressionResult Helper**
   ```python
   from dataclasses import dataclass
   from typing import List, Optional

   @dataclass
   class ExpressionResult:
       """Result of analyzing an expression."""
       use_ids: List[str]
       operation_ids: List[str]
       result_id: Optional[str]
       cfg_node_ids: List[str]
       binding_key: Optional[str]
   ```

3. **Implement analyze_expression Method**
   ```python
   def analyze_expression(self, node: ast.AST) -> ExpressionResult:
       """Recursively analyze an expression and return complete operation graph."""
       if isinstance(node, ast.BinOp):
           return self._analyze_binary_op(node)
       elif isinstance(node, ast.UnaryOp):
           return self._analyze_unary_op(node)
       elif isinstance(node, ast.Compare):
           return self._analyze_comparison(node)
       elif isinstance(node, ast.Call):
           return self._analyze_call(node)
       elif isinstance(node, ast.Name):
           return self._analyze_name(node)
       else:
           return ExpressionResult([], [], None, [], None)
   ```

4. **Implement Binary Op Analysis**
   ```python
   def _analyze_binary_op(self, node: ast.BinOp) -> ExpressionResult:
       """Analyze binary operation with nested expression graph."""
       # Analyze left operand
       left_result = self.analyze_expression(node.left)
       
       # Analyze right operand
       right_result = self.analyze_expression(node.right)
       
       # Create operation node for this binary op
       op_id = self._generate_operation_id()
       self.facts.operations.append(ExpressionFact(
           id=op_id,
           function_id=self.function_id,
           file=self.file,
           line=node.lineno,
           column=node.col_offset if hasattr(node, 'col_offset') else 0,
           cfg_node_ids=self._get_cfg_node_ids(node),
           expression=ast.unparse(node),
           operation=type(node.op).__name__,
           input_use_ids=left_result.use_ids + right_result.use_ids,
           input_operation_ids=left_result.operation_ids + right_result.operation_ids,
           output_definition_ids=[],
           metadata={'nested': True}
       ))
       
       return ExpressionResult(
           use_ids=left_result.use_ids + right_result.use_ids,
           operation_ids=left_result.operation_ids + right_result.operation_ids + [op_id],
           result_id=op_id,
           cfg_node_ids=self._get_cfg_node_ids(node),
           binding_key=None
       )
   ```

5. **Link Assignment to Operation**
   ```python
   def visit_Assign(self, node: ast.Assign) -> None:
       """Visit assignment statements with operation linking."""
       # Analyze the value expression
       value_result = self.analyze_expression(node.value)
       
       # Extract target definitions
       for target in node.targets:
           binding_key = f"{self.function_id}::{self._get_binding_name(target)}"
           cfg_node_ids = self._get_cfg_node_ids(node)
           
           def_id = self._generate_def_id(self._get_binding_name(target))
           self.facts.definitions.append(Definition(
               id=def_id,
               variable=self._get_binding_name(target),
               function_id=self.function_id,
               file=self.file,
               line=node.lineno,
               column=target.col_offset if hasattr(target, 'col_offset') else 0,
               kind='assignment',
               cfg_node_ids=cfg_node_ids,
               binding_key=binding_key,
               expression=ast.unparse(node),
               metadata={}
           ))
           
           # Link the operation's output to this definition
           if value_result.operation_ids:
               last_op_id = value_result.operation_ids[-1]
               # Update the operation's output_definition_ids
               for op in self.facts.operations:
                   if op.id == last_op_id:
                       op.output_definition_ids.append(def_id)
                       break
   ```

6. **Add Tests**
   - File: `tests/unit/dataflow/test_nested_expression_graph.py`
   - Test nested binary operations (a + b) * c
   - Test nested comparisons a < b < c
   - Test call with nested arguments
   - Verify complete operation graph structure

**Acceptance Criteria:**
- Nested expressions create connected operation graph
- Each operation references its input operations
- Final operation links to assignment definition
- No disconnected operation nodes

---

### Section 2.5: Full Side-Effect Modeling (Phase 7.10)

**Current Status:** Partial - unknown call side effects marked

**Goal:** Model known direct mutations and mark unknown side effects

**Implementation Steps:**

1. **File:** `server/ai_agents/intelligence/dataflow/python_extractor.py`

2. **Track Known Mutations**
   ```python
   def visit_Call(self, node: ast.Call) -> None:
       """Visit function calls with side-effect tracking."""
       # Analyze function being called
       if isinstance(node.func, ast.Attribute):
           # Known mutation methods
           mutation_methods = ['append', 'extend', 'insert', 'remove', 'pop', 
                            'clear', 'sort', 'reverse', 'update', 'add', 'discard']
           if node.func.attr in mutation_methods:
               # This is a known mutation
               metadata = {
                   'side_effect': 'known_mutation',
                   'mutation_kind': node.func.attr,
                   'receiver': ast.unparse(node.func.value)
               }
           else:
               # Unknown side effect
               metadata = {
                   'side_effect': 'unknown',
                   'confidence': 'low'
               }
       else:
           # Unknown function, conservatively mark as unknown side effect
           metadata = {
               'side_effect': 'unknown',
               'confidence': 'low'
           }
       
       # Create operation with side-effect metadata
       op_id = self._generate_operation_id()
       self.facts.operations.append(ExpressionFact(
           id=op_id,
           function_id=self.function_id,
           file=self.file,
           line=node.lineno,
           column=node.col_offset if hasattr(node, 'col_offset') else 0,
           cfg_node_ids=self._get_cfg_node_ids(node),
           expression=ast.unparse(node),
           operation="Call",
           input_use_ids=[],
           output_definition_ids=[],
           metadata=metadata
       ))
   ```

3. **Model Attribute Write Mutations**
   ```python
   def visit_Attribute(self, node: ast.Attribute) -> None:
       """Visit attribute access with write tracking."""
       # Check if this is in a write context (assignment target)
       # This requires context tracking
       
       # Track as potential mutation
       if self._is_write_context(node):
           metadata = {
               'access_type': 'write',
               'mutation': True,
               'attribute': node.attr,
               'receiver': ast.unparse(node.value)
           }
       else:
           metadata = {
               'access_type': 'read',
               'mutation': False,
               'attribute': node.attr,
               'receiver': ast.unparse(node.value)
           }
   ```

4. **Add Tests**
   - File: `tests/unit/dataflow/test_side_effects.py`
   - Test known mutation methods (list.append)
   - Test unknown function calls
   - Test attribute writes
   - Verify side-effect metadata

**Acceptance Criteria:**
- Known mutations are explicitly marked
- Unknown side effects are marked with low confidence
- Attribute writes are tracked
- No invented definitions for unknown state

---

### Section 2.6: May/Must Separation (Phase 8.8)

**Current Status:** Not implemented - may only

**Goal:** Separate may-reach and must-reach analysis

**Implementation Steps:**

1. **File:** `server/ai_agents/intelligence/dataflow/reaching_definitions.py`

2. **Add Must Analysis**
   ```python
   def analyze_must_reach(
       self,
       cfg: ControlFlowGraph,
       facts: DefUseFacts
   ) -> Dict[str, Any]:
       """
       Perform must-reaching definitions analysis.
       
       Unlike may-reaching (union of predecessor OUT sets),
       must-reaching uses intersection of predecessor OUT sets.
       A definition must-reach a use only if it reaches on ALL paths.
       """
       # Initialize sets
       must_in_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}
       must_out_sets: Dict[str, Set[str]] = {node.id: set() for node in cfg.nodes}
       
       # Build node_defs and node_uses (reuse from may analysis)
       node_defs, node_uses = self._build_node_maps(cfg, facts)
       
       # Calculate GEN for must analysis (definitions that must occur)
       gen = {}
       for node_id in node_defs:
           gen[node_id] = set(d.id for d in node_defs[node_id])
       
       # Calculate KILL (same as may analysis)
       kill = {}
       for node_id in node_defs:
           kill[node_id] = set()
           for definition in node_defs[node_id]:
               key = definition.binding_key
               if key in binding_defs:
                   for def_id in binding_defs[key]:
                       if def_id != definition.id:
                           kill[node_id].add(def_id)
       
       # Worklist algorithm with intersection instead of union
       worklist = list(node.id for node in cfg.nodes)
       
       while worklist:
           node_id = worklist.pop(0)
           
           # Calculate IN[B] = intersection of OUT[P] for all predecessors P
           predecessors = self._get_predecessors(cfg, node_id)
           if predecessors:
               new_in = set(must_out_sets[pred_id] for pred_id in predecessors)
               # Use intersection for must analysis
               if len(new_in) > 1:
                   new_in = set.intersection(*new_in)
               else:
                   new_in = new_in.pop() if new_in else set()
           else:
               new_in = set()
           
           # Calculate OUT[B] = GEN[B] union (IN[B] - KILL[B])
           new_out = gen[node_id].union(new_in - kill[node_id])
           
           # If changed, add successors to worklist
           if new_out != must_out_sets[node_id]:
               must_out_sets[node_id] = new_out
                 must_in_sets[node_id] = new_in
                 successors = self._get_successors(cfg, node_id)
                 worklist.extend(successors)
       
       return {
           'must_in_sets': must_in_sets,
           'must_out_sets': must_out_sets,
           'diagnostics': []
       }
   ```

3. **Integrate with Dependency Builder**
   ```python
   def build_dfg(self, cfg, facts):
       """Build DFG with both may and must edges."""
       # Run may-reaching analysis
       may_result = self.reaching_analyzer.analyze(cfg, facts)
       
       # Run must-reaching analysis
       must_result = self.reaching_analyzer.analyze_must_reach(cfg, facts)
       
       # Create may-reach edges
       for use in facts.uses:
           for cfg_node_id in use.cfg_node_ids:
               may_reaching = may_result['out_sets'].get(cfg_node_id, set())
               for def_id in may_reaching:
                   if def_id in may_result['node_defs'].get(cfg_node_id, set()):
                       edge = DataFlowEdge(
                           id=self._generate_edge_id(),
                           source=def_id,
                           target=use.id,
                           kind='may_reach',
                           evidence={'cfg_node': cfg_node_id}
                       )
                       graph.edges.append(edge)
       
       # Create must-reach edges
       for use in facts.uses:
           for cfg_node_id in use.cfg_node_ids:
               must_reaching = must_result['must_out_sets'].get(cfg_node_id, set())
               for def_id in must_reaching:
                   if def_id in must_result['node_defs'].get(cfg_node_id, set()):
                       edge = DataFlowEdge(
                           id=self._generate_edge_id(),
                           source=def_id,
                           target=use.id,
                           kind='must_reach',
                           evidence={'cfg_node': cfg_node_id}
                       )
                       graph.edges.append(edge)
   ```

4. **Add Tests**
   - File: `tests/unit/dataflow/test_must_must_reaching.py`
   - Test must-reach in straight-line code
   - Test may-reach vs must-reach in branches
   - Test loop-carried must definitions
   - Verify must edges are subset of may edges

**Acceptance Criteria:**
- Must analysis uses intersection of predecessor sets
- Must-reach edges are labeled separately from may-reach
- Must edges are always a subset of may edges
- Branch conditions correctly affect must analysis

---

### Section 2.7: Metamorphic Tests (Phase 12.6)

**Current Status:** Not implemented

**Goal:** Test invariants to ensure correctness

**Implementation Steps:**

1. **File:** `tests/unit/controlflow/test_metamorphic_invariants.py`

2. **Test Variable Renaming Invariant**
   ```python
   def test_rename_variable_preserves_cfg():
       """Renaming a variable changes binding identity but not CFG topology."""
       source1 = """
   def process(value):
       if value > 0:
           return value
       return 0
   """
       source2 = """
   def process(x):
       if x > 0:
           return x
       return 0
   """
       
       cfg1 = build_cfg(source1)
       cfg2 = build_cfg(source2)
       
       # CFG topology should be identical
       assert len(cfg1.nodes) == len(cfg2.nodes)
       assert len(cfg1.edges) == len(cfg2.edges)
       
       # Binding keys should differ
       facts1 = extract_dfg(source1)
       facts2 = extract_dfg(source2)
       binding_keys1 = {d.binding_key for d in facts1.definitions}
       binding_keys2 = {d.binding_key for d in facts2.definitions}
       assert binding_keys1 != binding_keys2
   ```

3. **Test Unreachable Statement Invariant**
   ```python
   def test_unreachable_statement_no_path():
       """Adding unreachable statement doesn't create reachable path."""
       source1 = """
   def process():
       return 1
   """
       source2 = """
   def process():
       return 1
       x = 2  # Unreachable
   """
       
       cfg1 = build_cfg(source1)
       cfg2 = build_cfg(source2)
       
       # CFG should mark x=2 as unreachable
       # No edge should connect return to x=2
       return_nodes = [n for n in cfg2.nodes if n.kind == 'return']
       for ret_node in return_nodes:
           outgoing = cfg2.get_edges_from(ret_node.id)
           assert len(outgoing) == 0  # No edges from return
   ```

4. **Test Reassignment Invariant**
   ```python
   def test_reassignment_kills_previous():
       """Adding second assignment kills first on straight-line path."""
       source = """
   def process():
       x = 1
       x = 2
       return x
   """
       
       facts = extract_dfg(source)
       reach = analyze_reaching_definitions(source)
       
       # Only second definition should reach return
       return_uses = [u for u in facts.uses if u.kind == 'return']
       for use in return_uses:
           reaching_defs = get_reaching_definitions(use, reach)
           assert len(reaching_defs) == 1
           assert reaching_defs[0].expression == 'x = 2'
   ```

5. **Test Finally Invariant**
   ```python
   def test_finally_preserves_completion():
       """Finally block preserves original completion if it completes normally."""
       source1 = """
   def process():
       return 1
   """
       source2 = """
   def process():
       try:
           return 1
       finally:
           pass
   """
       
       cfg1 = build_cfg(source1)
       cfg2 = build_cfg(source2)
       
       # Both should have same number of return completions
       # Finally should not add extra return paths
       returns1 = [n for n in cfg1.nodes if n.kind == 'return']
       returns2 = [n for n in cfg2.nodes if n.kind == 'return']
       assert len(returns1) == len(returns2)
   ```

6. **Add More Invariant Tests**
   - Test branch completion changes
   - Test loop structure preservation
   - Test exception handling structure
   - Test comprehension scope isolation

**Acceptance Criteria:**
- All invariants pass
- Regression fails when invariant is broken
- Tests cover critical correctness properties
- Tests are automated and repeatable

---

## Summary

### Immediate Action Required (External Environments)

1. **Unity Runtime Verification**
   - Requires Unity Editor 6000.6.7f1
   - Follow Part 1.1 of this guide
   - Estimated time: 2-4 hours

2. **Meta XR Simulator Testing**
   - Requires Meta Quest Link and XR Simulator
   - Follow Part 1.2 of this guide
   - Estimated time: 1-2 hours

3. **Physical Quest Headset Testing**
   - Requires Quest headset and USB-C cable
   - Follow Part 1.3 of this guide
   - Estimated time: 2-3 hours

### Optional Future Development (Code-Based)

1. **Full Async Semantics** (Section 2.1)
   - Estimated time: 4-6 hours
   - Priority: Low

2. **Full Generator Semantics** (Section 2.2)
   - Estimated time: 3-4 hours
   - Priority: Low

3. **Exception Groups** (Section 2.3)
   - Estimated time: 2-3 hours
   - Priority: Low

4. **Full Nested Expression Operations** (Section 2.4)
   - Estimated time: 6-8 hours
   - Priority: Medium

5. **Full Side-Effect Modeling** (Section 2.5)
   - Estimated time: 3-4 hours
   - Priority: Low

6. **May/Must Separation** (Section 2.6)
   - Estimated time: 4-6 hours
   - Priority: Medium

7. **Metamorphic Tests** (Section 2.7)
   - Estimated time: 4-6 hours
   - Priority: Medium

### Completion Criteria

The JARVIS CFG/DFG system will be considered **fully complete** when:

1. ✅ All code-based work from the original plan is done (100% complete)
2. ✅ Unity runtime verification is completed
3. ✅ Meta XR Simulator testing is completed
4. ✅ Physical Quest headset testing is completed
5. ⚠️ Optional future development is implemented (optional, not required for P0/P1)

The system currently meets "Implemented — Intermediate" status for both control-flow and data-flow visualization. Full completion requires the environment-dependent verification steps.
