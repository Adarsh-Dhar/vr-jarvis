# Phase 5: Metrics and Performance Targets

**Status:** ⏳ Planning  
**Date:** 2026-11-01  
**Score Impact:** +5.1 points (to 34.5%)  
**Estimated Effort:** S (2 weeks)

## Overview

Phase 5 implements the 15 metrics from the plan, each with a definition, source, and threshold. The plan also includes performance targets and benchmarks.

## The 15 Metrics (from plan)

### 1. Tool Correctness
**Definition:** Verified-spec pass rate
**Source:** Verified tool tests that pass against real tools and fail against stubs
**Threshold:** ≥ 80% of tools verified

### 2. Tool Completeness
**Definition:** Percentage of tools with at least one verified spec
**Source:** tool_completion_status.json
**Threshold:** ≥ 90% of tools have verified specs

### 3. Precision
**Definition:** True Positives / (True Positives + False Positives)
**Source:** Ground truth engine comparison against manifests
**Threshold:** ≥ 0.95 for direct edges, ≥ 0.90 overall

### 4. Recall
**Definition:** True Positives / (True Positives + False Negatives)
**Source:** Ground truth engine comparison against manifests
**Threshold:** ≥ 0.90 for direct edges, ≥ 0.85 overall

### 5. Schema Validity
**Definition:** Percentage of tool outputs that pass JSON Schema validation
**Source:** validate_spec_schema.py on tool outputs
**Threshold:** 100% of tool outputs valid

### 6. Agent Task Success
**Definition:** Percentage of agent tasks that complete successfully
**Source:** Agent evaluator task completion rate
**Threshold:** ≥ 85% of agent tasks succeed

### 7. Tool Selection
**Definition:** Percentage of agent tool selections that match expected tools
**Source:** Agent evaluator tool selection score
**Threshold:** ≥ 80% correct tool selection

### 8. Evidence Accuracy
**Definition:** Percentage of agent claims that cite a real tool result
**Source:** Agent evaluator evidence score
**Threshold**: ≥ 90% of claims have evidence

### 9. Hallucination Rate
**Definition:** Percentage of agent claims without supporting evidence
**Source:** Agent evaluator hallucination score
**Threshold:** ≤ 10% hallucination rate

### 10. Investigation Completeness
**Definition:** Percentage of required investigation steps performed
**Source:** Scenario manifest completion tracking
**Threshold:** ≥ 90% of required steps completed

### 11. Latency (P50)
**Definition:** 50th percentile tool execution time
**Source:** Performance monitor percentiles
**Threshold:** Tool-specific (see below)

### 12. Latency (P95)
**Definition:** 95th percentile tool execution time
**Source:** Performance monitor percentiles
**Threshold:** Tool-specific (see below)

### 13. Throughput
**Definition:** Requests per second under load
**Source:** Load generator capacity report
**Threshold:** ≥ 100 req/s for core tools

### 14. Resource Consumption
**Definition:** CPU, memory, disk usage during runs
**Source:** Performance monitor resource metrics
**Threshold:** CPU ≤ 80%, Memory ≤ 4GB per run

### 15. Failure Recovery
**Definition:** Time to recover from chaos/failure scenarios
**Source:** Chaos controller recovery time
**Threshold:** ≤ 30 seconds to recover

## Performance Targets (from plan)

| Tool/Operation | P95 Target | P99 Target |
|----------------|-----------|-----------|
| Symbol lookup | 100ms | 200ms |
| Indexed search | 300ms | 500ms |
| Direct call graph query | 500ms | 1000ms |
| Small repository indexing | 30s | 60s |
| Incremental indexing | 5s | 10s |
| Basic agent response | 5s | 10s |
| File read (small) | 50ms | 100ms |
| File write (small) | 100ms | 200ms |
| Parse source code | 500ms | 1000ms |
| Graph query (simple) | 200ms | 500ms |

## Implementation Strategy

### Step 1: Create Metrics Collector
**File:** `metrics_collector.py`

Collects all 15 metrics from various sources:
- Verified tool test results
- Ground truth engine precision/recall
- Agent evaluator scores
- Performance monitor data
- Load generator reports
- Chaos controller recovery times

### Step 2: Create Metrics Report
**File:** `metrics_report.py`

Generates a comprehensive metrics report showing:
- Current value for each metric
- Target threshold
- Pass/fail status
- Trend over time
- Comparison to baseline

### Step 3: Wire into Scoreboard
**File:** Update `score_plan.py`

Add metrics section to scoreboard:
- Calculate metrics score (0.7 → 5.0 points)
- Weight each metric appropriately
- Fail gate if critical metrics miss thresholds

### Step 4: Add Performance Benchmarks
**Directory:** `benchmarks/`

Create benchmark scripts for:
- Symbol lookup latency
- Indexed search latency
- Repository indexing time
- Graph query performance

### Step 5: CI Integration
Add to workflows:
- Run metrics collection on every build
- Generate metrics report
- Fail build if critical metrics miss targets
- Store metrics history for trend analysis

## Metrics Calculation

### Metric Weights
From plan: 5 points total for 15 metrics

**Critical metrics (2.5 points):**
- Tool correctness (0.5)
- Precision (0.5)
- Recall (0.5)
- P95 latency (0.5)
- P99 latency (0.5)

**Important metrics (1.5 points):**
- Tool completeness (0.3)
- Schema validity (0.3)
- Agent task success (0.3)
- Evidence accuracy (0.3)
- Investigation completeness (0.3)

**Supporting metrics (1.0 points):**
- Tool selection (0.2)
- Hallucination rate (0.2)
- Throughput (0.2)
- Resource consumption (0.2)
- Failure recovery (0.2)

## Implementation Files to Create

1. `metrics_collector.py` - Collects all 15 metrics
2. `metrics_report.py` - Generates metrics report
3. `benchmarks/` - Performance benchmark scripts
4. Update `score_plan.py` - Add metrics scoring
5. Update CI workflows - Run metrics collection

## Next Steps

**Immediate:**
1. Create metrics_collector.py
2. Define metric calculation logic
3. Create metrics_report.py

**Short-term:**
4. Wire into scoreboard
5. Create benchmark scripts
6. Set performance targets

**Medium-term:**
7. CI integration
8. Trend analysis
9. Alert configuration

## Success Metrics

- All 15 metrics defined and collected
- All metrics have targets and thresholds
- Metrics score increases from 0.7 to 5.0 points
- Performance targets enforced in CI
- Benchmark baselines established

## Conclusion

Phase 5 requires defining and implementing 15 metrics with targets. The infrastructure for many of these already exists (performance monitor, agent evaluator, ground truth engine, load generator, chaos controller). The work is primarily:
1. Creating a unified metrics collector
2. Calculating metric scores
3. Setting and enforcing targets
4. Wiring into scoreboard and CI

This is a smaller phase compared to Phase 3, estimated at 2 weeks.
