'''
Shared model objects for every agent.

Why this exists: one user request fans out into a dozen or more model calls, and any single failed call used to fail the
whole request. This module makes each call retry on overload (HTTP 503/429/500/504) with exponential backoff and jitter,
and can pace calls so a burst does not exceed the API's requests-per-minute limit.

Environment variables (all optional):
  JARVIS_LLM_ATTEMPTS      tries per call, including the first (default 3)
  JARVIS_LLM_RETRY_DELAY   first backoff delay in seconds, doubled each retry (default 0.5)
  JARVIS_LLM_RPM           most model calls per minute across all agents; 0 = no pacing (default 10)
  JARVIS_LLM_CONCURRENCY   most model calls in flight at once; 0 = unlimited (default 0)
'''
import asyncio
import os
import time

from google.adk.models.google_llm import Gemini
from google.genai import types

RETRY = types.HttpRetryOptions(
    attempts=int(os.getenv('JARVIS_LLM_ATTEMPTS', '3')),
    initial_delay=float(os.getenv('JARVIS_LLM_RETRY_DELAY', '0.5')),
    max_delay=5.0,
    exp_base=2.0,
    jitter=1.0,
    http_status_codes=[429, 500, 503, 504],
)

# Counts every model call this process makes. Read it before and after a request to see how many calls the request cost.
stats = {'requests': 0}

_state = {'loop': None, 'pace_lock': None, 'next_at': 0.0, 'sem': None}


def _setup(rpm, concurrency):
    '''asyncio primitives belong to one event loop, so build them lazily for the running loop.'''
    loop = asyncio.get_running_loop()
    if _state['loop'] is not loop:
        _state.update(loop=loop, pace_lock=asyncio.Lock(), next_at=0.0, sem=asyncio.Semaphore(concurrency) if concurrency > 0 else None)


async def _pace(rpm):
    if rpm <= 0:
        return
    interval = 60.0 / rpm
    async with _state['pace_lock']:
        now = time.monotonic()
        wait = _state['next_at'] - now
        if wait > 0:
            await asyncio.sleep(wait)
        _state['next_at'] = max(now, _state['next_at']) + interval


class PacedGemini(Gemini):
    '''Gemini with call counting, optional pacing and an optional cap on concurrent calls. Retries come from retry_options.'''

    async def generate_content_async(self, llm_request, stream=False):
        rpm = float(os.getenv('JARVIS_LLM_RPM', '10'))  # Default to 10 RPM to avoid rate limiting
        concurrency = int(os.getenv('JARVIS_LLM_CONCURRENCY', '0'))
        _setup(rpm, concurrency)
        await _pace(rpm)
        stats['requests'] += 1
        sem = _state['sem']
        if sem is None:
            async for response in super().generate_content_async(llm_request, stream=stream):
                yield response
        else:
            async with sem:
                async for response in super().generate_content_async(llm_request, stream=stream):
                    yield response


def make_model(name, base_url=None):
    return PacedGemini(model=name, retry_options=RETRY, base_url=base_url)
