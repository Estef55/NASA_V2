"""Tests for environment-gated passwordless demo profile login and RBAC preservation."""
from __future__ import annotations

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
from app.main import app, conn, hash_password


class DemoLoginTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        with conn() as db:
            db.execute('DELETE FROM audit')
            db.execute('DELETE FROM sessions')
            db.execute('DELETE FROM followups')
            db.execute('DELETE FROM alerts')
            db.execute('DELETE FROM checkins')
            db.execute('DELETE FROM conversations')
            db.execute('DELETE FROM metrics')
            db.execute('DELETE FROM assignments')
            db.execute('DELETE FROM demo_owner_state')
            db.execute('UPDATE demo_state SET day=0, active=0 WHERE id=1')
            db.execute('DELETE FROM users')

    def test_demo_login_is_disabled_in_production_and_when_explicitly_off(self):
        for env_patch in (
            {'LATIRA_ENV': 'production', 'LATIRA_DEMO_LOGIN': ''},
            {'LATIRA_ENV': 'production', 'LATIRA_DEMO_LOGIN': 'true'},
            {'LATIRA_ENV': 'demo', 'LATIRA_DEMO_LOGIN': 'false'},
            {'LATIRA_ENV': '', 'LATIRA_DEMO_LOGIN': ''},
        ):
            with patch.dict(os.environ, env_patch):
                cfg = self.client.get('/api/auth/demo-profiles')
                self.assertEqual(cfg.status_code, 200)
                self.assertFalse(cfg.json()['enabled'])
                self.assertEqual(cfg.json()['profiles'], [])

                res = self.client.post('/api/auth/demo-login', json={'profile': 'astronaut'})
                self.assertEqual(res.status_code, 403)

    def test_missing_demo_accounts_seeded_safely_without_erasing_existing_data(self):
        with conn() as db:
            db.execute(
                "INSERT INTO users(username,password_hash,role,astronaut_id) VALUES('existing_astro', ?, 'astronaut', 'AST-002')",
                (hash_password('ExistingPass123!'),),
            )
            db.execute(
                "INSERT INTO metrics(astronaut_id,recorded_at,sleep,source,demo) VALUES('AST-002','2026-06-01T08:00:00Z',7.5,'manual',0)"
            )

        with patch.dict(os.environ, {'LATIRA_ENV': 'demo', 'LATIRA_DEMO_LOGIN': ''}):
            main.init()
            with conn() as db:
                usernames = {r['username'] for r in db.execute('SELECT username FROM users').fetchall()}
                self.assertIn('existing_astro', usernames)
                self.assertIn('astro_demo', usernames)
                self.assertIn('medic_demo', usernames)
                self.assertIn('admin_demo', usernames)
                metric = db.execute("SELECT sleep FROM metrics WHERE astronaut_id='AST-002'").fetchone()
                self.assertIsNotNone(metric)
                self.assertEqual(metric['sleep'], 7.5)
                assignment = db.execute(
                    "SELECT 1 FROM assignments WHERE medic_username='medic_demo' AND astronaut_id='AST-001'"
                ).fetchone()
                self.assertIsNotNone(assignment)

    def test_passwordless_demo_login_for_all_three_profiles_and_rbac_enforcement(self):
        with patch.dict(os.environ, {'LATIRA_ENV': 'demo', 'LATIRA_DEMO_LOGIN': ''}):
            cfg = self.client.get('/api/auth/demo-profiles')
            self.assertEqual(cfg.status_code, 200)
            body = cfg.json()
            self.assertTrue(body['enabled'])
            self.assertEqual([p['profile'] for p in body['profiles']], ['astronaut', 'medic', 'admin'])
            self.assertEqual([p['label_es'] for p in body['profiles']], ['Astronauta', 'Médico', 'Administrador'])

            # Seed an unassigned astronaut AST-002 to verify medic scope restriction
            with conn() as db:
                db.execute(
                    "INSERT INTO users(username,password_hash,role,astronaut_id) VALUES('astro_other', ?, 'astronaut', 'AST-002')",
                    (hash_password('OtherPass123!'),),
                )
                db.execute(
                    "INSERT INTO metrics(astronaut_id,recorded_at,sleep,heart_rate,source,demo) VALUES('AST-001','2026-06-01T08:00:00Z',7.4,63,'manual',0)"
                )
                db.execute(
                    "INSERT INTO metrics(astronaut_id,recorded_at,sleep,heart_rate,source,demo) VALUES('AST-002','2026-06-01T08:00:00Z',6.0,78,'manual',0)"
                )
                cur_a1 = db.execute(
                    "INSERT INTO alerts(astronaut_id,created_at,priority,reason,demo) VALUES('AST-001','2026-06-01T08:00:00Z','review','AST-001 alert',0)"
                )
                alert_ast1 = cur_a1.lastrowid
                cur_a2 = db.execute(
                    "INSERT INTO alerts(astronaut_id,created_at,priority,reason,demo) VALUES('AST-002','2026-06-01T08:00:00Z','review','AST-002 alert',0)"
                )
                alert_ast2 = cur_a2.lastrowid

            # 1. Astronaut passwordless login
            r_astro = self.client.post('/api/auth/demo-login', json={'profile': 'astronaut'})
            self.assertEqual(r_astro.status_code, 200)
            astro_data = r_astro.json()
            self.assertEqual(astro_data['role'], 'astronaut')
            self.assertEqual(astro_data['astronaut_id'], 'AST-001')
            h_astro = {'Authorization': f"Bearer {astro_data['token']}"}
            self.assertEqual(self.client.get('/api/me', headers=h_astro).json()['role'], 'astronaut')
            self.assertEqual(self.client.get('/api/metrics', headers=h_astro).status_code, 200)
            self.assertEqual(
                {m['astronaut_id'] for m in self.client.get('/api/metrics', headers=h_astro).json()},
                {'AST-001'},
            )
            self.assertEqual(self.client.get('/api/admin/users', headers=h_astro).status_code, 403)
            self.assertEqual(self.client.get('/api/integrations', headers=h_astro).status_code, 403)
            self.assertEqual(
                self.client.post(f'/api/alerts/{alert_ast1}/followups', headers=h_astro, json={'note': 'nope'}).status_code,
                403,
            )

            # 2. Medic passwordless login
            r_medic = self.client.post('/api/auth/demo-login', json={'profile': 'medic'})
            self.assertEqual(r_medic.status_code, 200)
            medic_data = r_medic.json()
            self.assertEqual(medic_data['role'], 'medic')
            self.assertIsNone(medic_data['astronaut_id'])
            h_medic = {'Authorization': f"Bearer {medic_data['token']}"}
            self.assertEqual(self.client.get('/api/me', headers=h_medic).json()['role'], 'medic')
            medic_metrics = self.client.get('/api/metrics', headers=h_medic).json()
            self.assertEqual({m['astronaut_id'] for m in medic_metrics}, {'AST-001'})
            self.assertEqual(self.client.get('/api/admin/astronauts/AST-001', headers=h_medic).status_code, 200)
            self.assertEqual(self.client.get('/api/admin/astronauts/AST-002', headers=h_medic).status_code, 404)
            self.assertEqual(
                self.client.post(f'/api/alerts/{alert_ast2}/followups', headers=h_medic, json={'note': 'forbidden'}).status_code,
                404,
            )
            self.assertEqual(
                self.client.post(f'/api/alerts/{alert_ast1}/followups', headers=h_medic, json={'note': 'ok'}).status_code,
                200,
            )
            self.assertEqual(self.client.get('/api/admin/users', headers=h_medic).status_code, 403)

            # 3. Admin passwordless login
            r_admin = self.client.post('/api/auth/demo-login', json={'profile': 'admin'})
            self.assertEqual(r_admin.status_code, 200)
            admin_data = r_admin.json()
            self.assertEqual(admin_data['role'], 'admin')
            self.assertIsNone(admin_data['astronaut_id'])
            h_admin = {'Authorization': f"Bearer {admin_data['token']}"}
            self.assertEqual(self.client.get('/api/admin/users', headers=h_admin).status_code, 200)
            self.assertEqual(self.client.get('/api/admin/assignments', headers=h_admin).status_code, 200)
            self.assertEqual(self.client.get('/api/integrations', headers=h_admin).status_code, 200)
            for clinical_path in ('/api/metrics', '/api/alerts', '/api/baseline', '/api/admin/astronauts/AST-001', '/api/thermography/history'):
                self.assertEqual(self.client.get(clinical_path, headers=h_admin).status_code, 403)

            # Audit trail recorded all demo logins
            audits = self.client.get('/api/admin/audit', headers=h_admin).json()
            actions = {a['action'] for a in audits}
            self.assertTrue({'demo_login:astronaut', 'demo_login:medic', 'demo_login:admin'}.issubset(actions))

            # Logout revokes session
            for hdr in (h_astro, h_medic, h_admin):
                self.assertEqual(self.client.post('/api/auth/logout', headers=hdr).status_code, 200)
                self.assertEqual(self.client.get('/api/me', headers=hdr).status_code, 401)

    def test_demo_login_rejects_role_tampering_invalid_profiles_and_inactive_users(self):
        with patch.dict(os.environ, {'LATIRA_ENV': 'demo', 'LATIRA_DEMO_LOGIN': ''}):
            # Extra fields attempting privilege escalation must fail validation
            tampered = self.client.post('/api/auth/demo-login', json={'profile': 'astronaut', 'role': 'admin'})
            self.assertEqual(tampered.status_code, 422)

            unknown = self.client.post('/api/auth/demo-login', json={'profile': 'commander'})
            self.assertEqual(unknown.status_code, 400)

            # Deactivating astro_demo prevents demo login for that account
            main.init()
            with conn() as db:
                db.execute("UPDATE users SET active=0 WHERE username='astro_demo'")
            inactive = self.client.post('/api/auth/demo-login', json={'profile': 'astronaut'})
            self.assertEqual(inactive.status_code, 403)

    def test_fresh_db_in_demo_mode_without_password_env_seeds_demo_accounts_with_random_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            old_db = database.DB
            old_main_db = main.DB
            database.DB = main.DB = Path(temp) / 'demo_fresh.sqlite3'
            try:
                with patch.dict(os.environ, {'LATIRA_ENV': 'demo', 'LATIRA_DEMO_PASSWORD': ''}):
                    main.init()
                    with conn() as db:
                        rows = db.execute('SELECT username, role, password_hash FROM users ORDER BY username').fetchall()
                self.assertEqual([(r['username'], r['role']) for r in rows], [
                    ('admin_demo', 'admin'),
                    ('astro_demo', 'astronaut'),
                    ('medic_demo', 'medic'),
                ])
                self.assertTrue(all(r['password_hash'].startswith('pbkdf2_sha256$') for r in rows))
            finally:
                database.DB = old_db
                main.DB = old_main_db


if __name__ == '__main__':
    unittest.main()
