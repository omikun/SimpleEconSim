"""Atomic versioned JSON saves, exact journal replay, no pickle or world globals."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from .model import Session, VERSION, digest, state_digest
from .scenario import SCENARIO, validate, content_digest


def save(session, path):
    validate(session.state)
    payload = session.payload()
    # Include a digest to detect accidental edits/truncation, not as an authenticity claim.
    envelope = dict(payload=payload, checksum=digest(payload))
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,encoding='utf-8') as stream:
            temp = stream.name
            json.dump(envelope,stream,sort_keys=True,allow_nan=False,separators=(',',':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def load(path):
    try:
        envelope = json.loads(Path(path).read_text())
        p = envelope['payload']
        if digest(p) != envelope['checksum']:
            raise ValueError('Save checksum does not match')
        if p['version'] not in (VERSION,3) or p['version']!=p['state']['version']:
            raise ValueError('Unsupported save version')
        expected = content_digest(p['state'].get('ruleset','classic'))
        if p['state']['content_digest'] != expected or p['initial']['content_digest'] != expected:
            raise ValueError('Scenario content changed; start a new laboratory run')
        from .terrain import load_terrain
        if p['state']['terrain_digest'] != digest(load_terrain()):
            raise ValueError('Terrain fixture changed; start a new laboratory run')
        validate(p['decision_start'])
        validate(p['state'])
        validate(p['initial'])
        for entry in p['history']:
            validate(entry['before'])
            validate(entry['after'])
            if state_digest(entry['after']) != entry['digest']:
                raise ValueError('Invalid history checkpoint')
        return Session(**{k:p[k] for k in ('state','initial','events','history','journal','tracing','decision_start')})
    except (KeyError,TypeError,json.JSONDecodeError,OverflowError) as exc:
        raise ValueError('Invalid laboratory save; current session was not replaced') from exc


def replay(session):
    from .engine import command, step, set_availability
    result = Session(deepcopy(session.initial),deepcopy(session.initial))
    def apply(c):
        if c['issuer'] == 'scenario':
            set_availability(result,**c['params'])
        else:
            command(result,c['issuer'],c['kind'],**c['params'])
    for round_record in session.journal:
        for c in round_record['commands']:
            apply(c)
        step(result,rival=False)
        if state_digest(result.state) != round_record['digest']:
            raise ValueError(f"Replay diverged at round {result.state['round']}")
    for c in session.state['actions']:
        apply(c)
    if state_digest(result.state) != state_digest(session.state):
        raise ValueError('Replay diverged in pending decisions')
    return result
