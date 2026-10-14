"""Owner-scoped local autosave and bounded immutable revision snapshots."""
from pathlib import Path
import datetime as dt
import hashlib
import sqlite3
import core

def connect(path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=10)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS workspaces (owner TEXT, id TEXT, payload BLOB, hash TEXT, updated TEXT, PRIMARY KEY(owner,id))')
    db.execute('CREATE TABLE IF NOT EXISTS revisions (owner TEXT, id TEXT, revision INTEGER PRIMARY KEY AUTOINCREMENT, payload BLOB, hash TEXT, updated TEXT)')
    return db

def save(path,owner,workspace):
    if not owner: raise ValueError('Workspace owner is required.')
    payload=core.workspace_bytes(workspace); digest=hashlib.sha256(payload).hexdigest(); wid=workspace['workspace_id']
    with connect(path) as db:
        old=db.execute('SELECT hash FROM workspaces WHERE owner=? AND id=?',(owner,wid)).fetchone()
        if old and old[0]==digest: return
        now=dt.datetime.now(dt.timezone.utc).isoformat()
        db.execute('INSERT OR REPLACE INTO workspaces VALUES (?,?,?,?,?)',(owner,wid,payload,digest,now))
        db.execute('INSERT INTO revisions(owner,id,payload,hash,updated) VALUES (?,?,?,?,?)',(owner,wid,payload,digest,now))
        db.execute('DELETE FROM revisions WHERE owner=? AND id=? AND revision NOT IN (SELECT revision FROM revisions WHERE owner=? AND id=? ORDER BY revision DESC LIMIT 10)',(owner,wid,owner,wid))

def latest(path,owner):
    with connect(path) as db:
        row=db.execute('SELECT payload,hash FROM workspaces WHERE owner=? ORDER BY updated DESC LIMIT 1',(owner,)).fetchone()
    if not row: return None
    if hashlib.sha256(row[0]).hexdigest()!=row[1]: raise ValueError('Autosave integrity check failed.')
    return core.load_workspace(row[0],trusted_local=True)

def list_workspaces(path,owner):
    with connect(path) as db:
        return db.execute('SELECT id,updated FROM workspaces WHERE owner=? ORDER BY updated DESC',(owner,)).fetchall()

def load(path,owner,wid):
    with connect(path) as db:
        row=db.execute('SELECT payload,hash FROM workspaces WHERE owner=? AND id=?',(owner,wid)).fetchone()
    if not row: raise ValueError('Workspace unavailable for this owner.')
    if hashlib.sha256(row[0]).hexdigest()!=row[1]: raise ValueError('Autosave integrity check failed.')
    return core.load_workspace(row[0],trusted_local=True)
