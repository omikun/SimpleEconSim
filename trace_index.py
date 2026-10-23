"""Disposable block-coordinate index over an append-only compact trace."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from trace_codec import iter_records, CorruptTrace


class TraceIndex:
    def __init__(self,path):
        self.path=Path(path)
        self.index_path=self.path.with_suffix(self.path.suffix+'.index.sqlite')

    def _connect(self):
        db=sqlite3.connect(self.index_path)
        db.execute('PRAGMA cache_size=-2048')
        db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS events(n INTEGER PRIMARY KEY,id TEXT UNIQUE,turn INTEGER,kind TEXT,metric TEXT,subject TEXT,good TEXT,block INTEGER,position INTEGER,end INTEGER,sha TEXT,class TEXT)')
        for field in ('id','turn','kind','metric','good'):
            db.execute(f'CREATE INDEX IF NOT EXISTS by_{field} ON events({field})')
        return db

    def query(self, **filters):
        try:
            return self._query(**filters)
        except sqlite3.DatabaseError as error:
            if isinstance(error, sqlite3.IntegrityError):
                raise CorruptTrace('duplicate event identity in trace source') from error
            # The sidecar is derived data. Preserve the authoritative source and
            # rebuild a damaged database once; errors in the source still fail.
            self.index_path.unlink(missing_ok=True)
            return self._query(**filters)

    def _query(self,*,boundary=None,turn=None,subject=None,metric_id=None,kind=None,event_id=None,offset=0,limit=100):
        if offset<0 or limit<0:raise ValueError('invalid trace page range')
        size=self.path.stat().st_size
        boundary=size if boundary is None else boundary
        if boundary>size:raise ValueError('trace boundary exceeds published data')
        with closing(self._connect()) as db, db:
            meta=dict(db.execute('SELECT key,value FROM meta'))
            records=iter_records(self.path)
            try:first=next(records).payload
            finally:records.close()
            identity=json.dumps([self.path.stat().st_dev,self.path.stat().st_ino,hashlib.sha256(first.encode()).hexdigest()])
            previous=int(meta.get('end','0'))
            if meta.get('identity')!=identity or previous>size:
                db.execute('DELETE FROM events');db.execute('DELETE FROM meta');meta={};previous=0
            # Index the caller's fixed published boundary. Re-read at most the
            # last block to verify coordinates before appending new rows.
            if boundary>previous:
                start=int(meta['block']) if 'block' in meta else None
                number=int(meta.get('count','0'))
                last_block=start
                for record in iter_records(self.path,start_offset=start,end_offset=boundary):
                    sha=hashlib.sha256(record.payload.encode()).hexdigest()
                    if record.end_offset<=previous:
                        old=db.execute('SELECT sha FROM events WHERE block=? AND position=?',(record.block_offset,record.record_in_block)).fetchone()
                        if old is None or old[0]!=sha:raise CorruptTrace('indexed source prefix changed')
                        continue
                    row=json.loads(record.payload);subject_json=json.dumps(row.get('subject',{}),sort_keys=True,separators=(',',':'))
                    db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                               (number,row.get('event_id'),row.get('turn'),row.get('kind'),row.get('metric_id'),subject_json,
                                row.get('subject',{}).get('good'),record.block_offset,record.record_in_block,record.end_offset,sha,row.get('record_class')))
                    number+=1;last_block=record.block_offset
                for key,value in {'identity':identity,'end':str(boundary),'block':str(last_block),'count':str(number)}.items():
                    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',(key,value))
            clauses=['class != ?','end <= ?'];parameters=['metadata',boundary]
            for column,value in [('turn',turn),('metric',metric_id),('kind',kind),('id',event_id)]:
                if value is not None:clauses.append(column+' = ?');parameters.append(value)
            for key,value in (subject or {}).items():
                clauses.append('json_extract(subject,?) IS ?')
                parameters.extend(['$.'+json.dumps(key),json.dumps(value,sort_keys=True,separators=(',',':')) if isinstance(value,(dict,list)) else value])
            where=' AND '.join(clauses)
            total=db.execute('SELECT count(*) FROM events WHERE '+where,parameters).fetchone()[0]
            selected=db.execute('SELECT block,position,sha FROM events WHERE '+where+' ORDER BY n LIMIT ? OFFSET ?',parameters+[limit,offset]).fetchall()
        events=[];wanted={}
        for block,position,sha in selected:wanted.setdefault(block,{})[position]=sha
        decoded={}
        for block,positions in wanted.items():
            for record in iter_records(self.path,start_offset=block,end_offset=boundary):
                if record.block_offset!=block:break
                if record.record_in_block in positions:
                    if hashlib.sha256(record.payload.encode()).hexdigest()!=positions[record.record_in_block]:
                        raise CorruptTrace('indexed record differs from source')
                    decoded[block,record.record_in_block]=json.loads(record.payload)
                if record.record_in_block>=max(positions):break
        for block,position,_ in selected:events.append(decoded[block,position])
        return {'events':events,'total':total,'offset':offset,'limit':limit,'boundary':boundary}


class KnownEventIds:
    """Bounded recent identity cache with cold lookup in the source index."""
    def __init__(self,path,limit=4096):
        from collections import OrderedDict
        self.path=Path(path);self.limit=limit;self.recent=OrderedDict()

    def add(self,ident):
        self.recent[ident]=None;self.recent.move_to_end(ident)
        if len(self.recent)>self.limit:self.recent.popitem(last=False)

    def __contains__(self,ident):
        if ident in self.recent:return True
        return bool(TraceIndex(self.path).query(event_id=ident,limit=1)['events'])

    def __len__(self):return len(self.recent)
