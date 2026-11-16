import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _db_isolation import configure_isolated_test_db

configure_isolated_test_db()

import app.database as database
import app.main as main
from fastapi.testclient import TestClient
from app.main import app, conn


class SecurityTests(unittest.TestCase):
    def setUp(self):
        from app.main import hash_password
        with conn() as db:
            db.execute('DELETE FROM sessions')
            db.execute('DELETE FROM assignments')
            db.execute('DELETE FROM users')
            db.execute("INSERT INTO users(username,password_hash,role,astronaut_id) VALUES('astro',?, 'astronaut','AST-T')", (hash_password('[REDACTED]'),))
        self.client = TestClient(app)

    def test_fresh_database_has_no_code_embedded_demo_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            old_db=database.DB
            old_main_db=main.DB
            database.DB=main.DB=Path(temp)/'fresh.sqlite3'
            try:
                with patch.dict(os.environ, {'LATIRA_DEMO_PASSWORD':''}):
                    main.init()
                    with conn() as db:
                        users=db.execute('SELECT username FROM users').fetchall()
                self.assertEqual(users,[])
            finally:
                database.DB=old_db
                main.DB=old_main_db

    def test_password_hash_uses_unique_random_salt(self):
        from app.main import hash_password
        first, second = hash_password('[REDACTED]'), hash_password('[REDACTED]')
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith('pbkdf2_sha256$'))

    def test_database_connection_closes_on_context_exit(self):
        with conn() as db:
            db.execute('SELECT 1')
        with self.assertRaises(Exception):
            db.execute('SELECT 1')

    def test_session_can_be_revoked_by_logout(self):
        from app.main import hash_password
        with conn() as db:
            db.execute("UPDATE users SET password_hash=? WHERE username='astro'", (hash_password('[REDACTED]'),))
        token = self.client.post('/api/auth/login', json={'username':'astro','password':'[REDACTED]'}).json()['token']
        headers = {'Authorization': f'Bearer {token}'}
        self.assertEqual(self.client.post('/api/auth/logout', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/api/me', headers=headers).status_code, 401)



if __name__ == '__main__':
    unittest.main()
