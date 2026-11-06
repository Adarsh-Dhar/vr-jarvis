#!/bin/bash
# Automated release gates for CFG and DFG analysis

set -e

echo "=== Running Critical Release Gates for CFG and DFG Analysis ==="

# Gate 1: Python imports
echo "Gate 1: Python imports..."
python3 -c 'from ai_agents.intelligence.controlflow import PythonCFGBuilder, validate_cfg; from ai_agents.intelligence.dataflow import PythonDefUseExtractor, ReachingDefinitionsAnalyzer, DataFlowGraphBuilder; print("✓ All analysis modules import successfully")'

# Gate 2: Compilation
echo "Gate 2: Compilation check..."
python3 -m compileall -q ai_agents
echo "✓ Zero syntax errors"

# Gate 3: Basic CFG construction
echo "Gate 3: Basic CFG construction..."
python3 -c 'from ai_agents.intelligence.controlflow import PythonCFGBuilder; import ast; code = "def process(value): return value * 2"; tree = ast.parse(code); func = tree.body[0]; cfg = PythonCFGBuilder().build_function(func, "test::process", code, "test.py"); assert len(cfg.nodes) > 0; assert len(cfg.edges) > 0; assert cfg.entry_node_id is not None; assert cfg.exit_node_id is not None; print("✓ CFG construction works")'

# Gate 4: Basic DFG construction
echo "Gate 4: Basic DFG construction..."
python3 -c 'from ai_agents.intelligence.controlflow import PythonCFGBuilder; from ai_agents.intelligence.dataflow import PythonDefUseExtractor; import ast; code = "def process(value): return value * 2"; tree = ast.parse(code); func = tree.body[0]; cfg = PythonCFGBuilder().build_function(func, "test::process", code, "test.py"); facts = PythonDefUseExtractor().extract_function(func, "test::process", code, cfg, "test.py"); assert len(facts.definitions) > 0; assert len(facts.uses) > 0; print("✓ DFG construction works")'

# Gate 5: Unity format conversion
echo "Gate 5: Unity format conversion..."
python3 -c 'from ai_agents.intelligence.controlflow import cfg_to_dict; from ai_agents.intelligence.controlflow import PythonCFGBuilder; import ast; code = "def process(value): return value * 2"; tree = ast.parse(code); func = tree.body[0]; cfg = PythonCFGBuilder().build_function(func, "test::process", code, "test.py"); cfg_dict = cfg_to_dict(cfg); assert "nodes" in cfg_dict; assert "edges" in cfg_dict; print("✓ Unity format conversion verified")'

echo ""
echo "=== All Critical Release Gates Passed ==="
echo "System is functional for CFG and DFG analysis"
