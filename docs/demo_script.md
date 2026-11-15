# JARVIS demo script

The questions the competition demo and video use. Each must pass 5 of 5 runs
against the real agents before its answer is recorded into
`server/demo_answers.json` (see `JARVIS_RECORD_DEMO` in the server README
section). Keep this list in sync with the three suggestion buttons in the VR
app (`DemoQuestions` in `JarvisSpatialWorkspace.cs`).

Demo repository: `repository/demo-account-service` (put ONLY this folder in
`JARVIS_REPOSITORY_DIR` for the judged build).

| # | Question (as asked in VR) | What it shows |
|---|----------------------------|---------------|
| 1 | What does this repository do? | Repository overview, grounded in the graph |
| 2 | Who calls deleteAccount? | Call-graph traversal (services/account.ts -> routes/account.ts) |
| 3 | What breaks if I change verifyToken? | Change-impact analysis (lib/token.ts -> auth/requireAuth.ts -> routes) |
| 4 | How does authentication work? | Cross-file explanation (verifyToken, requireAuth, checkOwner) |
| 5 | Which tests cover the account service? | Test discovery (tests/account.test.ts) |
| 6 | Show me the risky paths in this change. | Risk/path scene commands in the 3D graph |

## Recording answers

1. Start the server with `JARVIS_DEMO_MODE=1 JARVIS_RECORD_DEMO=1` and the demo
   repo as the only entry in `JARVIS_REPOSITORY_DIR`.
2. Ask each question above 5 times; keep only questions that are correct and
   grounded every time (fix the prompt/tool or swap the question otherwise).
3. Run with `JARVIS_RECORD_DEMO=1` once more per question; each real `/ask`
   response is appended to `server/demo_answers.json` keyed by the normalized
   question text.
4. Restart with `JARVIS_RECORD_DEMO=0`: scripted questions now answer
   instantly from the file; anything else still goes through the real agents.

## Pre-warming

Start the server once against the demo repo and let it build `data/index` and
the graph caches before deploying, so the first `/ask` after a restart does not
rebuild anything.
