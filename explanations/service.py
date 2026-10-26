"""Explicit-request-only bounded service shared by web and Pygame clients."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import uuid

from explanations import history, mechanics, schema
from explanations.packet import build_packet, digest, VERSION as PACKET_VERSION
from explanations.provider import OpenAIProvider, PROMPT_VERSION
from explanations.proposals import ProposalLog, atomic_json

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {'ready', 'failed', 'unavailable', 'cancelled'}
MESSAGES = {'queued': 'Waiting for an available explanation slot…',
            'collecting_evidence': 'Reading recorded causes…',
            'selecting_history': 'Finding a historical parallel…',
            'generating': 'Writing the explanation…', 'validating': 'Checking the explanation…',
            'ready': 'Explanation ready.', 'cancelled': 'Explanation cancelled.'}


class ExplanationService:
    def __init__(self, provider=None, cache_dir=None, proposal_dir=None):
        self.provider = provider or OpenAIProvider()
        self.cache_dir = Path(cache_dir or ROOT / 'tmp' / 'ai_explanations')
        self.proposals = ProposalLog(proposal_dir or ROOT / 'planning' / 'potential_future_mechanisms')
        self.lock = threading.RLock()
        self.jobs = {}
        self.by_key = {}
        self.executor = None
        self.closed = False

    def _key(self, captured):
        selection = dict(captured['selection'])
        if not captured.get('boundary_explicit', True):
            # A completed tick's first sample is immutable. Appending later
            # turns must not force regeneration of an earlier requested tick.
            selection.pop('boundary', None)
        context = {'selection': selection, 'scenario': captured.get('scenario'),
                   'nation': captured.get('nation'), 'era': captured.get('era')}
        # Current affordability belongs to a separate local availability check.
        # Cached prose retains its original, clearly identified action context.
        return digest({'capture': context, 'history': history.VERSION, 'mechanics': mechanics.VERSION,
                       'schema': schema.VERSION, 'prompt': PROMPT_VERSION,
                       'packet': PACKET_VERSION,
                       'model': self.provider.model})

    def request(self, captured):
        key = self._key(captured)
        with self.lock:
            if self.closed:
                raise ValueError('Explanation service is shutting down.')
            job = self.jobs.get(self.by_key.get(key))
            if job is None or job['state'] in ('failed', 'unavailable', 'cancelled'):
                active = sum(j['state'] not in TERMINAL for j in self.jobs.values())
                if active >= 4:
                    raise ValueError('Explanation queue is full. Close an explainer or retry later.')
                for ident, old in list(self.jobs.items()):
                    if len(self.jobs) > 128 and old['state'] in TERMINAL:
                        self.jobs.pop(ident)
                        if self.by_key.get(old['key']) == ident:
                            self.by_key.pop(old['key'], None)
                ident = uuid.uuid4().hex
                job = {'job_id': ident, 'key': key, 'state': 'queued', 'viewers': set(),
                       'result': None, 'error': None, 'created': time.monotonic()}
                self.jobs[ident] = job
                self.by_key[key] = ident
                if self.executor is None:
                    self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='stat-explainer')
                # The only path scheduling generation is this explicit request.
                job['future'] = self.executor.submit(self._run, ident, deepcopy(captured))
            viewer = uuid.uuid4().hex
            job['viewers'].add(viewer)
            return self._snapshot(job, viewer)

    def _snapshot(self, job, viewer):
        return {'job_id': job['job_id'], 'viewer': viewer, 'state': job['state'],
                'message': job['error'] or MESSAGES.get(job['state'], 'Explanation unavailable.'),
                'result': deepcopy(job['result'])}

    def status(self, ident, viewer):
        with self.lock:
            job = self.jobs.get(ident)
            if job is None or viewer not in job['viewers']:
                raise ValueError('Explanation request is no longer available.')
            return self._snapshot(job, viewer)

    def cancel(self, ident, viewer):
        with self.lock:
            job = self.jobs.get(ident)
            if job and viewer in job['viewers']:
                job['viewers'].discard(viewer)
                if not job['viewers'] and job['state'] not in TERMINAL:
                    job['state'] = 'cancelled'
                    job['future'].cancel()

    def _stage(self, ident, state):
        with self.lock:
            job = self.jobs[ident]
            if job['state'] == 'cancelled' or self.closed:
                raise InterruptedError()
            if time.monotonic() - job['created'] > 65:
                raise TimeoutError()
            job['state'] = state

    def _run(self, ident, captured):
        key = self.jobs[ident]['key']
        path = self.cache_dir / (key + '.json')
        try:
            self._stage(ident, 'collecting_evidence')
            try:
                result = json.loads(path.read_text())
                schema.validate(result['narrative'], result['packet'])
                if result['capture_key'] != key:
                    raise ValueError('Mismatched cache key.')
            except (OSError, ValueError, KeyError, TypeError):
                if self.provider.unavailable:
                    with self.lock:
                        self.jobs[ident].update(state='unavailable', error=self.provider.unavailable)
                    return
                packet = build_packet(captured, lambda state: self._stage(ident, state))
                self._stage(ident, 'selecting_history')
                packet['historical_candidates'] = history.candidates(packet)
                self._stage(ident, 'generating')
                narrative, metadata = self.provider.generate(packet)
                self._stage(ident, 'validating')
                schema.validate(narrative, packet)
                result = {'capture_key': key, 'packet': packet, 'narrative': narrative,
                          'generated_at': datetime.now(timezone.utc).isoformat(),
                          'metadata': metadata, 'proposal_logs': []}
            self._stage(ident, 'validating')
            # Save the validated result before attempting planning persistence.
            warnings = []
            try:
                atomic_json(path, result)
                self._retain_cache()
            except OSError:
                warnings.append('Report cache could not be saved; this result remains readable.')
            self.proposals.log_result(result)
            result['warnings'] = warnings
            with self.lock:
                if self.jobs[ident]['state'] != 'cancelled' and not self.closed:
                    self.jobs[ident].update(state='ready', result=result)
        except InterruptedError:
            pass
        except Exception as error:
            # No raw provider response, credentials, or trace inputs in errors.
            message = str(error) if isinstance(error, (ValueError, RuntimeError)) else 'Explanation failed or exceeded its time limit. Retry explicitly.'
            with self.lock:
                if self.jobs[ident]['state'] != 'cancelled':
                    self.jobs[ident].update(state='failed', error=message[:300])

    def _retain_cache(self):
        files = sorted(self.cache_dir.glob('*.json'), key=lambda p: p.stat().st_mtime)
        for path in files[:-256]:
            path.unlink(missing_ok=True)

    def retry_logging(self, ident, viewer):
        with self.lock:
            self.status(ident, viewer)
            job = self.jobs[ident]
            if job['state'] != 'ready':
                raise ValueError('Wait for a validated explanation before logging.')
            self.proposals.log_result(job['result'])
            return self._snapshot(job, viewer)

    def close(self):
        with self.lock:
            self.closed = True
            for job in self.jobs.values():
                if job['state'] not in TERMINAL:
                    job['state'] = 'cancelled'
            if self.executor:
                self.executor.shutdown(wait=False, cancel_futures=True)


_DEFAULT = None
_DEFAULT_LOCK = threading.Lock()


def default_service():
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None or _DEFAULT.closed:
            _DEFAULT = ExplanationService()
        return _DEFAULT


def close_default_service():
    """Shutdown never instantiates an unused service."""
    with _DEFAULT_LOCK:
        if _DEFAULT is not None:
            _DEFAULT.close()
