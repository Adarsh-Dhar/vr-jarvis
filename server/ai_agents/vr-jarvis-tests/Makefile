.PHONY: test unit pipelines stress soak llm dry harden

test:        ## fast offline suites (unit, pipelines, scale, concurrency, faults)
	python -m pytest tests -q

unit:
	python -m pytest tests/unit -q

pipelines:
	python -m pytest tests/pipelines tests/e2e -q

stress:
	python -m pytest tests/stress -q

soak:
	JARVIS_SOAK=1 JARVIS_SOAK_ITERATIONS=300 python -m pytest tests/stress/test_soak.py -q

llm:         ## needs model credentials
	JARVIS_RUN_LLM=1 JARVIS_TRIALS=5 python -m pytest tests/agents tests/e2e tests/stress/test_prompt_injection_llm.py -q

dry:         ## runs the real-model tests against the scripted model, to check the test code only
	JARVIS_RUN_LLM=1 JARVIS_DRY=1 JARVIS_TRIALS=1 python -m pytest tests/agents tests/e2e -q

harden:      ## copy the hardened files over ai_agents (commit first so you can diff)
	cp -r hardening/ai_agents/* ai_agents/
