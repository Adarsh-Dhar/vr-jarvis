'''A deterministic stand-in for the model. It lets every pipeline, loop and guard run offline.

Each agent is scripted as a few tool-call steps followed by a final text. The model call is the only
fake part: tools, state, callbacks, routing and workflow agents are the real ADK and jarvis code.
'''
import asyncio
import json
import re
import uuid
from typing import Any

from google.adk.models import BaseLlm, LlmResponse
from google.genai import types

from .context import DEFAULT_DIFF
from .jsonutil import ids_in_text

SELECTED_RE = re.compile(r'(?:selected|selection) \(may be empty\):[ \t]*(\S*)')
NAME_RE = re.compile(r'internal name is "([^"]+)"')


class Ctx:
    def __init__(self, agent, system_text, contents):
        self.agent = agent
        self.system = system_text
        self.contents = contents
        m = SELECTED_RE.search(system_text)
        sel = m.group(1) if m else ''
        self.selected = '' if sel in ('', 'None') else sel
        self.user_text = self._user_text()
        blocks = []
        for c in reversed(contents):
            parts = c.parts or []
            if any(p.function_response for p in parts):
                blocks.append([(p.function_response.name, p.function_response.response)
                               for p in parts if p.function_response])
            elif parts and all(p.function_call for p in parts):
                continue
            else:
                break
        self.blocks = list(reversed(blocks))
        self.step = len(self.blocks)
        self.last = self.blocks[-1] if self.blocks else []
        self.all_responses = [r for b in self.blocks for r in b]

    def _user_text(self):
        for c in reversed(self.contents):
            if c.role != 'user':
                continue
            for p in c.parts or []:
                if p.text and not p.text.startswith('For context'):
                    return p.text
        return ''

    def resp(self, name):
        for n, r in reversed(self.all_responses):
            if n == name:
                return r
        return {}


def j(obj):
    return json.dumps(obj)


class Policy:
    '''Default scripts for every agent in the reference system, written for the tiny graph.'''

    def __init__(self):
        self.marker = 'MARK-' + uuid.uuid4().hex[:8]
        self.repair_count = 0

    def route(self, text):
        t = text.lower()
        if not t.strip():
            return 'clarify'
        if 'commit' in t:
            return 'approval'
        if any(w in t for w in ('brief', 'status', "what's new", 'what is new')):
            return 'briefing_pipeline'
        if any(w in t for w in ('what breaks', 'affected', 'impact', 'risk')):
            return 'impact_pipeline'
        if any(t.startswith(w) for w in ('add ', 'fix ', 'implement ', 'patch ', 'change ')):
            return 'fix_pipeline'
        if any(w in t for w in ('cricket', 'weather', 'recipe')):
            return 'none'
        return 'investigate_pipeline'

    def plan(self, ctx):
        '''Return (steps, final_text). A step is a list of (tool, args) calls issued together.'''
        a = ctx.agent
        ids = ids_in_text(ctx.system) or ['auth.validateSession']
        sel = ctx.selected or 'auth.validateSession'
        if a == 'jarvis_orchestrator':
            r = self.route(ctx.user_text)
            if r == 'approval':
                return [[('request_approval', {'action_summary': 'Commit the proposed patch'})]], 'Waiting for your approval.'
            if r == 'none':
                return [], 'I can only help with understanding and changing code.'
            if r == 'clarify':
                return [], 'What would you like to look at?'
            return [[('transfer_to_agent', {'agent_name': r})]], ''
        if a == 'investigator_agent':
            callers = [c['id'] for c in ctx.resp('get_callers').get('callers', [])]
            claim_ids = [sel] + callers
            return ([[('search_symbols', {'query': sel.split('.')[-1]})],
                     [('get_callers', {'node_id': sel, 'depth': 1}), ('get_source', {'node_id': sel})]],
                    j({'answer': '%s has %d callers.' % (sel, len(callers)),
                       'claims': [{'text': 'callers of ' + sel, 'node_ids': claim_ids, 'confidence': 'confirmed'}],
                       'evidence_nodes': claim_ids}))
        if a.endswith('_critic'):
            return ([[('verify_citations', {'node_ids': ids})]],
                    j({'verdict': 'pass', 'answer': 'Verified. ' + ' '.join(ids[:3]),
                       'claims': [{'text': 'verified', 'node_ids': ids, 'confidence': 'confirmed'}],
                       'changes_made': []}))
        if a.endswith('_scene'):
            steps = [[('highlight_path', {'node_ids': ids}), ('dim_unrelated', {'keep_ids': ids})]]
            second = [('open_code_panel', {'node_id': ids[0]}), ('focus_camera', {'node_id': ids[0]})]
            if len(ids) > 1:
                second.append(('set_edge_style', {'src': ids[0], 'dst': ids[1], 'style': 'dashed'}))
            steps.append(second)
            if a == 'fix_scene':
                steps.append([('show_ghost_diff', {'node_id': ids[0], 'diff': DEFAULT_DIFF}),
                              ('show_test_badges', {'passed_ids': [], 'failed_ids': [], 'not_run_ids': ids[:1]})])
            return steps, 'Two paths depend on this code. One of them has no tests.'
        if a == 'change_loader_agent':
            return ([[('list_changed_nodes', {}), ('get_diff', {}), ('get_node', {'node_id': sel})]],
                    j({'source': 'diff', 'branch': 'feature/session-timeout',
                       'changed_nodes': ctx.resp('list_changed_nodes').get('changed_nodes', [sel]),
                       'diff_summary': 'Session timeout changed.'}))
        if a == 'static_impact_agent':
            n = ids[0]
            deps = ctx.resp('get_dependents').get('dependents', [])
            return ([[('get_dependents', {'node_id': n, 'max_depth': 4}), ('get_callers', {'node_id': n, 'depth': 2})]],
                    j({'confirmed': [d['id'] for d in deps if d['edge_kind'] == 'confirmed'],
                       'unresolved': [d['id'] for d in deps if d['edge_kind'] != 'confirmed'],
                       'counts': {'confirmed': len(deps)}}))
        if a == 'test_mapper_agent':
            n = ids[0]
            return ([[('get_callers', {'node_id': n, 'depth': 2}), ('find_tests_for_node', {'node_id': n}),
                      ('get_coverage', {'node_id': n})]],
                    j({'tests': ctx.resp('find_tests_for_node').get('tests', []),
                       'untested_nodes': [n] if ctx.resp('find_tests_for_node').get('untested') else [],
                       'low_coverage_nodes': []}))
        if a == 'impact_synthesizer_agent':
            return [], j({'summary': 'Impact summary ' + self.marker, 'risk_level': 'medium',
                          'affected': [{'id': i, 'risk': 'medium', 'edge_kind': 'confirmed', 'reason': 'caller',
                                        'untested': False} for i in ids[:3]],
                          'inferred_links': [], 'recommended_tests': [],
                          'claims': [{'text': 'affected', 'node_ids': ids[:3], 'confidence': 'confirmed'}]})
        if a == 'briefing_agent':
            return ([[('load_project_memory', {}), ('get_branch_info', {}), ('list_changed_nodes', {})]],
                    j({'summary': 'One change touches session validation. ' + self.marker,
                       'risky_nodes': ['auth.validateSession'], 'unfinished_work': [],
                       'claims': [{'text': 'changed', 'node_ids': ['auth.validateSession'],
                                   'confidence': 'confirmed'}]}))
        if a == 'patch_agent':
            diff = ctx.resp('get_worktree_diff').get('diff', '')
            return ([[('create_worktree', {'branch_name': 'jarvis/fix'})],
                     [('apply_patch_to_worktree', {'diff': DEFAULT_DIFF})],
                     [('get_worktree_diff', {})]],
                    j({'summary': 'Adds a regression test.', 'files': ['tests/ratelimit.test.ts'], 'diff': diff,
                       'tests_added': ['tests/ratelimit.test.ts'], 'assumptions': [],
                       'claims': [{'text': 'adds test', 'node_ids': ['auth.validateSession'],
                                   'confidence': 'confirmed'}]}))
        if a == 'verifier_agent':
            status = ctx.resp('run_tests').get('status', 'not_run')
            tc = ctx.resp('run_typecheck').get('typecheck', 'not_run')
            steps = [[('run_tests', {'test_files': ['tests/ratelimit.test.ts']})], [('run_typecheck', {})]]
            if status == 'passed' and tc == 'passed':
                steps.append([('exit_loop', {})])
            return steps, j({'status': status, 'passed': ctx.resp('run_tests').get('passed', []),
                             'failed': ctx.resp('run_tests').get('failed', []), 'not_run': [], 'typecheck': tc})
        if a == 'patch_repair_agent':
            self.repair_count += 1
            name = 'tests/repair%d.test.ts' % self.repair_count
            diff = DEFAULT_DIFF.replace('tests/ratelimit.test.ts', name)
            return ([[('apply_patch_to_worktree', {'diff': diff})], [('get_worktree_diff', {})]],
                    j({'summary': 'Repaired.', 'files': [name], 'diff': ctx.resp('get_worktree_diff').get('diff', ''),
                       'tests_added': [name], 'assumptions': [], 'claims': []}))
        return [], 'ok'


class ScriptedLlm(BaseLlm):
    model: str = 'scripted'
    policy: Any = None
    fault: Any = None        # callable(agent, step) -> None | 'raise' | 'empty' | 'garbage' | 'loop' | 'hang'
    hooks: Any = None        # list of callables(agent, step) run before each model call
    calls: Any = None        # list of (agent, step)
    seen: Any = None         # list of (agent, system_instruction_text)
    sizes: Any = None        # prompt size in characters for each model call

    def __init__(self, **kw):
        super().__init__(model='scripted', **kw)
        self.policy = self.policy or Policy()
        self.hooks = self.hooks or []
        self.calls = []
        self.seen = []
        self.sizes = []

    @classmethod
    def supported_models(cls):
        return ['scripted']

    async def generate_content_async(self, llm_request, stream=False):
        sys_parts = llm_request.config.system_instruction
        if isinstance(sys_parts, str):
            system = sys_parts
        elif sys_parts is not None and getattr(sys_parts, 'parts', None):
            system = '\n'.join(p.text or '' for p in sys_parts.parts)
        else:
            system = str(sys_parts or '')
        m = NAME_RE.search(system)
        agent = m.group(1) if m else 'unknown'
        ctx = Ctx(agent, system, llm_request.contents)
        self.calls.append((agent, ctx.step))
        self.seen.append((agent, system))
        self.sizes.append(len(system) + len(str(llm_request.contents)))
        for hook in self.hooks:
            hook(agent, ctx.step)
        fault = self.fault(agent, ctx.step) if self.fault else None
        if fault == 'raise':
            raise RuntimeError('injected model failure in ' + agent)
        if fault == 'hang':
            await asyncio.sleep(3600)
        if fault == 'empty':
            yield LlmResponse(content=types.Content(role='model', parts=[types.Part(text='')]))
            return
        if fault == 'garbage':
            yield LlmResponse(content=types.Content(role='model', parts=[types.Part(text='lorem {not json')]))
            return
        if fault == 'loop':
            call = types.Part(function_call=types.FunctionCall(name='get_node', args={'node_id': 'auth.validateSession'}))
            yield LlmResponse(content=types.Content(role='model', parts=[call]))
            return
        steps, final = self.policy.plan(ctx)
        if ctx.step < len(steps):
            parts = [types.Part(function_call=types.FunctionCall(name=n, args=a)) for n, a in steps[ctx.step]]
        else:
            parts = [types.Part(text=final)]
        yield LlmResponse(content=types.Content(role='model', parts=parts))
