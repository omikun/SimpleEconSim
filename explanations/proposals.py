"""Fixed-directory, atomic, deduplicated planning proposals. No game mutations."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import tempfile
import threading

from explanations.packet import digest

_LOCK = threading.RLock()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ProposalLog:
    def __init__(self, directory):
        self.directory = Path(directory)

    def record(self, proposal, packet):
        # Hashes are filenames. Neither model text nor client fields become paths.
        ident = digest({'capability': proposal['capability'], 'scenario': packet.get('scenario'),
                        'client': packet['selection']['client']})[:24]
        now = datetime.now(timezone.utc).isoformat()
        occurrence = {'selection_id': packet['selection_id'], 'selection': packet['selection'],
                      'evidence_ids': proposal['evidence_ids'], 'source_ids': proposal['source_ids']}
        with _LOCK:
            self.directory.mkdir(parents=True, exist_ok=True)
            with (self.directory / '.writer.lock').open('a') as lockfile:
                fcntl.flock(lockfile, fcntl.LOCK_EX)
                path = self.directory / (ident + '.json')
                if path.exists():
                    record = json.loads(path.read_text())
                else:
                    record = {'id': ident, 'status': 'proposed', 'created_at': now,
                              'review_notes': '', 'proposal': proposal,
                              'catalog_coverage': packet['catalog_coverage'], 'occurrences': []}
                if not any(o['selection_id'] == occurrence['selection_id'] for o in record['occurrences']):
                    record['occurrences'].append(occurrence)
                record['updated_at'] = now
                # Existing proposal content, status, and reviewer decisions survive.
                atomic_json(path, record)
        return {'id': ident, 'status': 'logged', 'path': 'planning/potential_future_mechanisms/' + ident + '.json'}

    def log_result(self, result):
        statuses = []
        for proposal in result['narrative']['future_mechanics']:
            try:
                statuses.append(self.record(proposal, result['packet']))
            except (OSError, ValueError, KeyError, TypeError):
                statuses.append({'status': 'not_logged', 'message': 'Could not write the planning log. Retry logging without regenerating.'})
        result['proposal_logs'] = statuses
        return result
