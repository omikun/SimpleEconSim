"""Disposable block-coordinate index over an append-only compact trace."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import weakref

_LOCKS = weakref.WeakValueDictionary()
_LOCK_GUARD = threading.Lock()


def _path_lock(path):
    with _LOCK_GUARD:
        key = str(path.resolve())
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _LOCKS[key] = lock
        return lock

from trace_codec import iter_storage_records, CorruptTrace
from trace_state_coverage import RULE_KINDS, context_of, expand_cell


class IndexCacheError(ValueError):
    pass


class TraceIndex:
    def __init__(self,path):
        self.path=Path(path)
        self.index_path=self.path.with_suffix(self.path.suffix+'.index.sqlite')

    def _connect(self):
        db=sqlite3.connect(self.index_path, timeout=30)
        try:
            db.execute('PRAGMA cache_size=-2048')
            db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS events(n INTEGER PRIMARY KEY,id TEXT UNIQUE,turn INTEGER,kind TEXT,metric TEXT,subject TEXT,good TEXT,block INTEGER,position INTEGER,end INTEGER,sha TEXT,class TEXT,sequence INTEGER,epoch INTEGER)')
            expected = ['n','id','turn','kind','metric','subject','good','block','position','end','sha','class','sequence','epoch']
            if [row[1] for row in db.execute('PRAGMA table_info(events)')] != expected:
                raise IndexCacheError('incompatible index schema')
            for field in ('id','turn','kind','metric','good'):
                db.execute(f'CREATE INDEX IF NOT EXISTS by_{field} ON events({field})')
            db.execute("CREATE INDEX IF NOT EXISTS by_entity_turn ON events(json_extract(subject,'$.type'),json_extract(subject,'$.id'),turn)")
            db.execute('CREATE TABLE IF NOT EXISTS coverage(n INTEGER PRIMARY KEY,prefix TEXT,min_seq INTEGER,max_seq INTEGER,turn INTEGER,subject TEXT,cells TEXT,block INTEGER,position INTEGER,end INTEGER,sha TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS coverage_by_range ON coverage(prefix,min_seq,max_seq)')
            db.execute("CREATE INDEX IF NOT EXISTS coverage_by_entity_turn ON coverage(json_extract(subject,'$.type'),json_extract(subject,'$.id'),turn)")
            db.execute('CREATE TABLE IF NOT EXISTS wilderness(n INTEGER PRIMARY KEY,id TEXT,turn INTEGER,epoch INTEGER,tiles TEXT,end INTEGER)')
            db.execute('CREATE INDEX IF NOT EXISTS wilderness_by_turn ON wilderness(turn,epoch)')
        except BaseException:
            db.close()
            raise
        return db

    def query(self, **filters):
        with _path_lock(self.index_path):
            return self._query_or_rebuild(**filters)

    def available_metrics(self, *, turn, subject, boundary=None):
        """Recorded subject/metric variants, without decoding event bodies.

        Callers freeze/publish the boundary on the simulation thread, then may
        build this disposable index on a worker. This never creates model work.
        """
        with _path_lock(self.index_path):
            indexed = self._query_or_rebuild(boundary=boundary, limit=0, _index_only=True)
            with closing(self._connect()) as db:
                rows = db.execute("""SELECT metric,subject,count(*) FROM (
                    SELECT metric,subject FROM events
                    WHERE json_extract(subject,'$.type') IS ? AND json_extract(subject,'$.id') IS ?
                    AND turn=? AND end<=? AND class NOT IN ('metadata','coverage') AND metric IS NOT NULL
                    UNION ALL
                    SELECT json_extract(j.value,'$[2]'),json_extract(j.value,'$[4]')
                    FROM coverage c,json_each(c.cells) j
                    WHERE json_extract(c.subject,'$.type') IS ? AND json_extract(c.subject,'$.id') IS ?
                    AND c.turn=? AND c.end<=?)
                    GROUP BY metric,subject ORDER BY metric,subject""",
                    (subject['type'],subject['id'],turn,indexed['boundary'])*2).fetchall()
            result=[{'metric_id': metric, 'subject': json.loads(encoded), 'count': count}
                    for metric, encoded, count in rows]
            covered=self.wilderness_status(turn=turn,subject=subject,boundary=indexed['boundary'])
            if covered:
                from wilderness_trace import FIELDS
                existing={(row['metric_id'],json.dumps(row['subject'],sort_keys=True)) for row in result}
                for metric in ['world.wilderness_state','people.residents',*[field[0] for field in FIELDS]]:
                    selected={'type':'tile','id':subject['id']}
                    if (metric,json.dumps(selected,sort_keys=True)) not in existing:
                        result.append({'metric_id':metric,'subject':selected,'count':1,'coverage':'wilderness_domain'})
            return result

    def wilderness_status(self,*,turn,subject,boundary=None,epoch=None):
        """Resolve one checked tile/domain without indexing per-tile or per-metric rows."""
        if subject.get('type')!='tile':return None
        with _path_lock(self.index_path):
            indexed=self._query_or_rebuild(boundary=boundary,limit=0,_index_only=True)
            with closing(self._connect()) as db:
                clauses=['turn=?','end<=?',"EXISTS (SELECT 1 FROM json_each(tiles) WHERE value IS ?)"]
                parameters=[turn,indexed['boundary'],subject['id']]
                if epoch is not None:clauses.append('epoch=?');parameters.append(epoch)
                found=db.execute('SELECT id FROM wilderness WHERE '+' AND '.join(clauses)+
                                 ' ORDER BY epoch,n LIMIT 1',parameters).fetchone()
            if not found:return None
            cohort=self._query_or_rebuild(event_id=found[0],boundary=indexed['boundary'],limit=1)['events'][0]
            refs=cohort['inputs']['state_refs']
            source=next((ident for ident,names in refs.items() if subject['id'] in names),None)
            if source is None:raise CorruptTrace('Wilderness state reference missing')
            page=self._query_or_rebuild(event_id=source,boundary=indexed['boundary'],limit=1)
            if not page['events']:raise CorruptTrace('Wilderness state source missing')
            state=page['events'][0]
            if (state.get('kind') not in ('wilderness_initial_state','wilderness_state_observation')
                    or state['sequence']>=cohort['sequence']
                    or (state['turn'],state.get('epoch',0))>(cohort['turn'],cohort.get('epoch',0))
                    or subject['id'] not in state.get('inputs',{}).get('states',{})):
                raise CorruptTrace('Wilderness state subject mismatch')
            return {'coverage':cohort,'source':state,'state':state['inputs']['states'][subject['id']]}

    def _query_or_rebuild(self, **filters):
        try:
            return self._query(**filters)
        except (sqlite3.DatabaseError, IndexCacheError) as error:
            if isinstance(error, sqlite3.IntegrityError):
                raise CorruptTrace('duplicate event identity in trace source') from error
            code = getattr(error, 'sqlite_errorcode', None)
            if not isinstance(error, IndexCacheError) and code not in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
                raise
            # The sidecar is derived data. Preserve the authoritative source and
            # rebuild a damaged database once; errors in the source still fail.
            self.index_path.unlink(missing_ok=True)
            return self._query(**filters)

    def _query(self,*,boundary=None,turn=None,subject=None,metric_id=None,kind=None,event_id=None,offset=0,limit=100,_index_only=False):
        if offset<0 or limit<0:raise ValueError('invalid trace page range')
        # iter_records publishes a same-process buffered writer. Obtain the
        # source identity before measuring size, otherwise a fresh reader can
        # freeze its boundary halfway through that writer's buffered block.
        records=iter_storage_records(self.path)
        try:first=next(records).payload
        finally:records.close()
        size=self.path.stat().st_size
        boundary=size if boundary is None else boundary
        if boundary>size:raise ValueError('trace boundary exceeds published data')
        with closing(self._connect()) as db, db:
            meta=dict(db.execute('SELECT key,value FROM meta'))
            identity=json.dumps([self.path.stat().st_dev,self.path.stat().st_ino,hashlib.sha256(first.encode()).hexdigest()])
            try:
                previous=int(meta.get('end','0'))
                for name in ('block','count'):
                    if name in meta:int(meta[name])
            except ValueError as error:
                raise IndexCacheError('invalid index boundary metadata') from error
            if (meta.get('identity')!=identity or previous>size
                    or (previous==size and meta.get('mtime')!=str(self.path.stat().st_mtime_ns))):
                db.execute('DELETE FROM events');db.execute('DELETE FROM coverage');db.execute('DELETE FROM wilderness');db.execute('DELETE FROM meta');meta={};previous=0
            # Index the caller's fixed published boundary. Re-read at most the
            # last block to verify coordinates before appending new rows.
            if boundary>previous:
                start=int(meta['block']) if 'block' in meta else None
                number=int(meta.get('count','0'))
                last_block=start
                for record in iter_storage_records(self.path,start_offset=start,end_offset=boundary):
                    sha=record.checksum
                    if record.end_offset<=previous:
                        old=db.execute('SELECT sha FROM events WHERE block=? AND position=?',(record.block_offset,record.record_in_block)).fetchone()
                        if old is None or old[0]!=sha:raise IndexCacheError('cached prefix differs from source')
                        continue
                    row=record.row if record.row is not None else json.loads(record.payload)
                    subject_json=json.dumps(row.get('subject',{}),sort_keys=True,separators=(',',':'))
                    db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                               (number,row.get('event_id'),row.get('turn'),row.get('kind'),row.get('metric_id'),subject_json,
                                row.get('subject',{}).get('good'),record.block_offset,record.record_in_block,record.end_offset,sha,row.get('record_class'),row.get('sequence'),row.get('epoch',0)))
                    if row.get('kind')=='wilderness_domain_coverage':
                        db.execute('INSERT INTO wilderness VALUES(?,?,?,?,?,?)',
                            (number,row['event_id'],row['turn'],row.get('epoch',0),
                             json.dumps(row['inputs']['tiles']),record.end_offset))
                    if row.get('kind') == 'state_coverage':
                        inputs = row['inputs']
                        db.execute('INSERT INTO coverage VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (number,inputs['identity_prefix'],inputs['sequence_min'],inputs['sequence_max'],row['turn'],
                             subject_json,json.dumps(inputs['cells'],sort_keys=True,separators=(',',':')),
                             record.block_offset,record.record_in_block,record.end_offset,sha))
                    number+=1;last_block=record.block_offset
                for key,value in {'identity':identity,'end':str(boundary),'block':str(last_block),'count':str(number),'mtime':str(self.path.stat().st_mtime_ns)}.items():
                    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',(key,value))
            if _index_only:
                return {'events':[],'total':0,'offset':offset,'limit':limit,'boundary':boundary}
            clauses=['class != ?','end <= ?'];parameters=['metadata',boundary]
            for column,value in [('turn',turn),('metric',metric_id),('kind',kind),('id',event_id)]:
                if value is not None:clauses.append(column+' = ?');parameters.append(value)
            for key,value in (subject or {}).items():
                if key in ('type', 'id'):
                    clauses.append(f"json_extract(subject,'$.{key}') IS ?")
                else:
                    clauses.append('json_extract(subject,?) IS ?')
                    parameters.append('$.'+json.dumps(key))
                parameters.append(json.dumps(value,sort_keys=True,separators=(',',':')) if isinstance(value,(dict,list)) else value)
            where=' AND '.join(clauses)
            # Query a covered domain inside its stored group; never populate a
            # persistent row per virtual sample. Coarse predicates prune groups
            # before json_each inspects any checked cells.
            coverage_clauses=['c.end <= ?']; coverage_parameters=[boundary]
            if turn is not None: coverage_clauses.append('c.turn = ?'); coverage_parameters.append(turn)
            for key,value in (subject or {}).items():
                if key in ('type','id'):
                    coverage_clauses.append(f"json_extract(c.subject,'$.{key}') IS ?");coverage_parameters.append(value)
            if event_id is not None:
                try:
                    prefix,sequence=event_id.rsplit(':',1);sequence=int(sequence)
                except (ValueError,AttributeError):
                    coverage_clauses.append('0')
                else:
                    coverage_clauses.extend(['c.prefix=?','c.min_seq<=?','c.max_seq>=?'])
                    coverage_parameters.extend([prefix,sequence,sequence])
            kind_case='CASE json_extract(j.value,\'$[1]\') '+ ' '.join(
                "WHEN '"+rule+"' THEN '"+value+"'" for rule,value in RULE_KINDS.items())+' END'
            class_case="CASE json_extract(j.value,'$[1]') WHEN 'checked_unchanged_snapshot.v1' THEN 'observation' WHEN 'checked_initial_snapshot.v1' THEN 'observation' WHEN 'checked_no_price_writes.v1' THEN 'audit' ELSE 'calculation' END"
            real_filter="" if event_id is not None or kind=='state_coverage' else " WHERE class != 'coverage'"
            virtual_filter=' AND '.join(coverage_clauses)
            if kind=='state_coverage':virtual_filter+=' AND 0'
            union=("SELECT id,turn,kind,metric,subject,good,block,position,end,sha,class,sequence,-1 cell FROM events"+real_filter+
                " UNION ALL SELECT c.prefix||':'||json_extract(j.value,'$[0]'),c.turn,"+kind_case+
                ",json_extract(j.value,'$[2]'),json_extract(j.value,'$[4]'),json_extract(j.value,'$[4].good'),"
                "c.block,c.position,c.end,c.sha,"+class_case+",json_extract(j.value,'$[0]'),CAST(j.key AS INTEGER) "
                "FROM coverage c,json_each(c.cells) j WHERE "+virtual_filter)
            total=db.execute('SELECT count(*) FROM ('+union+') WHERE '+where,coverage_parameters+parameters).fetchone()[0]
            selected=db.execute('SELECT block,position,sha,cell FROM ('+union+') WHERE '+where+
                ' ORDER BY sequence,id LIMIT ? OFFSET ?',coverage_parameters+parameters+[limit,offset]).fetchall()
        events=[];wanted={}
        for block,position,sha,cell in selected:wanted.setdefault(block,{})[position]=sha
        decoded={}
        for block,positions in wanted.items():
            for record in iter_storage_records(self.path,start_offset=block,end_offset=boundary):
                if record.block_offset!=block:break
                if record.record_in_block in positions:
                    if record.checksum!=positions[record.record_in_block]:
                        raise IndexCacheError('cached record differs from source')
                    decoded[block,record.record_in_block]=record.row if record.row is not None else json.loads(record.payload)
                if record.record_in_block>=max(positions):break
        for block,position,_,cell in selected:
            row=decoded[block,position]
            events.append(expand_cell(context_of(row),row['inputs']['cells'][cell]) if cell>=0 else row)
        return {'events':events,'total':total,'offset':offset,'limit':limit,'boundary':boundary}


class KnownEventIds:
    """Bounded recent identity cache with cold lookup in the source index."""
    def __init__(self,path,limit=262144):
        from collections import OrderedDict
        self.path=Path(path);self.limit=limit;self.recent=OrderedDict()

    def add(self,ident):
        self.recent[ident]=None;self.recent.move_to_end(ident)
        if len(self.recent)>self.limit:self.recent.popitem(last=False)

    def add_virtual(self,ident):
        if not hasattr(self,'virtual_ranges'):self.virtual_ranges={}
        prefix,sequence=ident.rsplit(':',1);sequence=int(sequence)
        ranges=self.virtual_ranges.setdefault(prefix,[])
        if ranges and ranges[-1][1]+1==sequence:
            ranges[-1]=(ranges[-1][0],sequence)
        else:ranges.append((sequence,sequence))
        if len(ranges)>32768:self.virtual_ranges[prefix]=ranges[-16384:]

    def __contains__(self,ident):
        if ident in self.recent:return True
        from bisect import bisect_right
        try:
            prefix,sequence=ident.rsplit(':',1);sequence=int(sequence)
            ranges=getattr(self,'virtual_ranges',{}).get(prefix,())
            location=bisect_right(ranges,(sequence,float('inf')))-1
            if (ident==prefix+':'+str(sequence) and location>=0
                    and ranges[location][0]<=sequence<=ranges[location][1]):return True
        except (ValueError,AttributeError):pass
        return bool(TraceIndex(self.path).query(event_id=ident,limit=1)['events'])

    def __len__(self):return len(self.recent)
