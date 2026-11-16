import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(PROJECT_ROOT / 'backend' / 'tests'), str(PROJECT_ROOT / 'backend')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from _db_isolation import configure_isolated_test_db

configure_isolated_test_db()

from fastapi import FastAPI
from fastapi.testclient import TestClient
import app.database as database
import app.main as main
from app.main import conn, hash_password
from app.routers.pose import router


class PoseRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_tmp = tempfile.TemporaryDirectory()
        cls.old_db = database.DB
        database.DB = Path(cls.database_tmp.name) / 'pose-tests.sqlite3'
        main.DB = database.DB
        main.init()

    @classmethod
    def tearDownClass(cls):
        database.DB = cls.old_db
        main.DB = cls.old_db
        cls.database_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / 'history.sqlite3'
        with conn() as db:
            db.execute('DELETE FROM sessions'); db.execute('DELETE FROM assignments'); db.execute('DELETE FROM users')
            db.execute("INSERT INTO users(username,password_hash,role,astronaut_id) VALUES('astro',?,'astronaut','AST-T')", (hash_password('[REDACTED]'),))
            db.execute("INSERT INTO users(username,password_hash,role,astronaut_id) VALUES('medic',?,'medic',NULL)", (hash_password('[REDACTED]'),))
            db.execute("INSERT INTO users(username,password_hash,role,astronaut_id) VALUES('other',?,'astronaut','AST-O')", (hash_password('[REDACTED]'),))
        self.app = FastAPI(); self.app.include_router(router)
        self.client = TestClient(self.app)
        self.token = '[REDACTED]'
        with conn() as db:
            db.execute("INSERT INTO sessions(token,username,expires) VALUES(?,?,?)", (self.token, 'astro', '2999-01-01T00:00:00+00:00'))
        self.headers = {'Authorization': f'Bearer {self.token}'}
        self.upload_url = '/api/pose/process'
        self.env = patch.dict(os.environ, {'POSE_STORAGE_DIR':str(self.root/'files'), 'POSE_HISTORY_DB':str(self.db), 'POSE_MAX_UPLOAD_BYTES':'16'})
        self.env.start()

    def tearDown(self):
        self.env.stop(); self.tmp.cleanup()

    def test_upload_requires_authentication(self):
        r = self.client.post(self.upload_url, files={'file':('clip.mp4',b'x','video/mp4')})
        self.assertEqual(r.status_code, 401)

    def test_rejects_unsupported_extension(self):
        r = self.client.post(self.upload_url, headers=self.headers, files={'file':('clip.txt',b'x','text/plain')})
        self.assertEqual(r.status_code, 400)

    def test_rejects_oversized_upload(self):
        r = self.client.post(self.upload_url, headers=self.headers, files={'file':('clip.mp4',b'x'*17,'video/mp4')})
        self.assertEqual(r.status_code, 413)

    def test_missing_yolo_returns_503_without_fabricated_history(self):
        with patch('app.routers.pose.process_video', side_effect=RuntimeError('YOLO processing requires optional dependencies')):
            r = self.client.post(self.upload_url, headers=self.headers, files={'file':('clip.mp4',bytes.fromhex('000000186674797069736f6d00000000'),'video/mp4')})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.client.get('/api/pose/history', headers=self.headers).json(), [])

    def test_history_and_download_are_owner_scoped(self):
        import sqlite3, json
        output = self.root/'files'/'owned.mp4'; output.parent.mkdir(parents=True); output.write_bytes(b'annotated')
        db = sqlite3.connect(self.db)
        try:
            db.execute('CREATE TABLE pose_analysis_history(id TEXT PRIMARY KEY, owner TEXT NOT NULL, created_at TEXT NOT NULL, input_name TEXT NOT NULL, output_path TEXT NOT NULL, measurements_json TEXT NOT NULL)')
            db.execute('INSERT INTO pose_analysis_history VALUES(?,?,?,?,?,?)', ('id1','astro','now','clip.mp4',str(output),json.dumps({'frames_processed':1})))
            db.execute('INSERT INTO pose_analysis_history VALUES(?,?,?,?,?,?)', ('id2','other','now','clip.mp4',str(output),json.dumps({'frames_processed':1})))
            db.commit()
        finally:
            db.close()
        self.assertEqual(len(self.client.get('/api/pose/history', headers=self.headers).json()), 1)
        self.assertEqual(self.client.get('/api/pose/history/id2/video', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get('/api/pose/history/id1/video', headers=self.headers).content, b'annotated')


if __name__ == '__main__': unittest.main()
