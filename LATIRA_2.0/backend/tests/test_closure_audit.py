"""Regression and closure audit tests for LÁTIRA 2.0 core flow, isolation, and LÁTI rules."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _db_isolation import configure_isolated_test_db

configure_isolated_test_db()

from fastapi.testclient import TestClient
from app.main import app, conn, hash_password


class ClosureAuditTests(unittest.TestCase):
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
            for uname, role, aid in [
                ('astro1', 'astronaut', 'AST-001'),
                ('astro2', 'astronaut', 'AST-002'),
                ('medic', 'medic', None),
                ('admin', 'admin', None),
            ]:
                db.execute(
                    'INSERT INTO users(username,password_hash,role,astronaut_id) VALUES(?,?,?,?)',
                    (uname, hash_password('[REDACTED]'), role, aid),
                )
            db.execute("INSERT INTO assignments(medic_username,astronaut_id) VALUES('medic','AST-001')")
        self.tokens = {
            name: self.client.post('/api/auth/login', json={'username': name, 'password': '[REDACTED]'}).json()['token']
            for name in ('astro1', 'astro2', 'medic', 'admin')
        }

    def h(self, user: str) -> dict[str, str]:
        return {'Authorization': f'Bearer {self.tokens[user]}'}

    def test_real_metrics_build_baseline_then_trigger_explainable_alert_on_deviation(self):
        # First 3 real records build personal baseline without generating false alerts
        for day_idx, (sleep, hr) in enumerate([(8.0, 62.0), (7.8, 63.0), (8.2, 64.0)], start=1):
            res = self.client.post(
                '/api/metrics',
                headers=self.h('astro1'),
                json={
                    'sleep': sleep,
                    'heart_rate': hr,
                    'fatigue': 2,
                    'mood': 4,
                    'source': 'manual',
                    'unit': 'mixed',
                    'recorded_at': f'2026-05-0{day_idx}T08:00:00Z',
                },
            )
            self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get('/api/alerts', headers=self.h('astro1')).json(), [])

        # 4th real record has major drop in sleep (8.0 -> 5.0 = -37.5%) and spike in HR (63 -> 85 = +34.9%)
        dev = self.client.post(
            '/api/metrics',
            headers=self.h('astro1'),
            json={
                'sleep': 5.0,
                'heart_rate': 85.0,
                'fatigue': 4,
                'mood': 2,
                'source': 'manual',
                'unit': 'mixed',
                'recorded_at': '2026-05-04T08:00:00Z',
            },
        )
        self.assertEqual(dev.status_code, 200)
        alerts = self.client.get('/api/alerts', headers=self.h('astro1')).json()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['demo'], 0)
        self.assertIn('personal baseline deviation', alerts[0]['reason'].lower())
        self.assertIn('not a diagnosis', alerts[0]['reason'].lower())

    def test_baseline_switches_from_demo_to_real_after_real_metric_recorded(self):
        self.client.post('/api/demo/start', headers=self.h('astro1'))
        self.client.post('/api/demo/next', headers=self.h('astro1'))
        self.client.post('/api/demo/next', headers=self.h('astro1'))
        demo_base = self.client.get('/api/baseline', headers=self.h('astro1')).json()
        self.assertTrue(demo_base['sufficient'])
        self.assertEqual(demo_base['sample_count'], 3)

        # Now astronaut logs 1 real measurement -> latest metric is demo=0 -> /api/baseline switches to real
        self.client.post(
            '/api/metrics',
            headers=self.h('astro1'),
            json={'sleep': 7.5, 'heart_rate': 65, 'source': 'manual', 'unit': 'mixed', 'recorded_at': '2026-05-01T08:00:00Z'},
        )
        real_base = self.client.get('/api/baseline', headers=self.h('astro1')).json()
        self.assertFalse(real_base['sufficient'])
        self.assertEqual(real_base['sample_count'], 1)
        # Explicit ?demo=true still reads demo baseline cleanly
        explicit_demo = self.client.get('/api/baseline?demo=true', headers=self.h('astro1')).json()
        self.assertTrue(explicit_demo['sufficient'])

    def test_demo_scenarios_are_isolated_per_astronaut(self):
        s1 = self.client.post('/api/demo/start', headers=self.h('astro1')).json()
        self.assertEqual(s1['state']['day'], 1)
        s2 = self.client.post('/api/demo/start', headers=self.h('astro2')).json()
        self.assertEqual(s2['state']['day'], 1)
        self.client.post('/api/demo/next', headers=self.h('astro2'))

        # astro1 should still have 1 demo record in AST-001, astro2 should have 2 in AST-002
        m1 = [r for r in self.client.get('/api/metrics', headers=self.h('astro1')).json() if r['demo'] == 1]
        m2 = [r for r in self.client.get('/api/metrics', headers=self.h('astro2')).json() if r['demo'] == 1]
        self.assertEqual(len(m1), 1)
        self.assertEqual(m1[0]['astronaut_id'], 'AST-001')
        self.assertEqual(len(m2), 2)
        self.assertEqual(m2[0]['astronaut_id'], 'AST-002')

    def test_alerts_endpoint_includes_medical_followups(self):
        with conn() as db:
            cur = db.execute(
                "INSERT INTO alerts(astronaut_id,created_at,priority,reason,demo) VALUES('AST-001','2026-05-01T00:00:00Z','review','Deviation test',0)"
            )
            aid = cur.lastrowid
        res = self.client.post(f'/api/alerts/{aid}/followups', headers=self.h('medic'), json={'note': 'Reviewed sleep schedule'})
        self.assertEqual(res.status_code, 200)
        astro_alerts = self.client.get('/api/alerts', headers=self.h('astro1')).json()
        self.assertEqual(len(astro_alerts), 1)
        self.assertEqual(astro_alerts[0]['status'], 'review')
        self.assertEqual(len(astro_alerts[0]['followups']), 1)
        self.assertEqual(astro_alerts[0]['followups'][0]['note'], 'Reviewed sleep schedule')
        self.assertEqual(astro_alerts[0]['followups'][0]['author'], 'medic')

    def test_admin_user_update_revokes_existing_sessions(self):
        # astro1 token works initially
        self.assertEqual(self.client.get('/api/me', headers=self.h('astro1')).status_code, 200)
        # Admin updates astro1 password -> existing token must be revoked immediately
        upd = self.client.patch(
            '/api/admin/users/astro1',
            headers=self.h('admin'),
            json={'password': 'NewSecurePassword123!'},
        )
        self.assertEqual(upd.status_code, 200)
        self.assertEqual(self.client.get('/api/me', headers=self.h('astro1')).status_code, 401)
        # Login with new password succeeds
        relogin = self.client.post('/api/auth/login', json={'username': 'astro1', 'password': 'NewSecurePassword123!'})
        self.assertEqual(relogin.status_code, 200)

    def test_lati_word_boundaries_baseline_checkin_and_audit(self):
        # Record a check-in with elevated fatigue
        ck = self.client.post(
            '/api/checkins',
            headers=self.h('astro1'),
            json={'fatigue': 5, 'mood': 2, 'note': 'tired after EVA prep', 'language': 'en'},
        )
        self.assertEqual(ck.status_code, 200)
        self.assertIn('fatigue 5/5', ck.json()['assistant'])

        # Check-in history endpoint returns scoped check-in for astronaut & assigned medic only
        self.assertEqual(len(self.client.get('/api/checkins', headers=self.h('astro1')).json()), 1)
        self.assertEqual(len(self.client.get('/api/checkins', headers=self.h('astro2')).json()), 0)
        self.assertEqual(len(self.client.get('/api/checkins', headers=self.h('medic')).json()), 1)

        # Query containing "mission" and "missing" must NOT falsely hijack to NASA/CSA
        r_sleep = self.client.post(
            '/api/lati/chat',
            headers=self.h('astro1'),
            json={'message': 'I am missing sleep data on this mission', 'language': 'en'},
        )
        self.assertEqual(r_sleep.status_code, 200)
        self.assertEqual(r_sleep.json()['context_source'], 'authenticated_astronaut_records')

        # Baseline query returns dedicated baseline rule
        r_base = self.client.post(
            '/api/lati/chat',
            headers=self.h('astro1'),
            json={'message': '¿Cómo va mi línea base?', 'language': 'es'},
        )
        self.assertEqual(r_base.status_code, 200)
        self.assertEqual(r_base.json()['context_source'], 'authenticated_astronaut_records')
        self.assertIn('línea base', r_base.json()['reply'].lower())

        # Check-in query returns saved check-in summary
        r_ck = self.client.post(
            '/api/lati/chat',
            headers=self.h('astro1'),
            json={'message': 'Show my latest check-in', 'language': 'en'},
        )
        self.assertEqual(r_ck.status_code, 200)
        self.assertIn('fatigue=5/5', r_ck.json()['reply'])

        # Audit log recorded lati_chat
        audits = self.client.get('/api/admin/audit', headers=self.h('admin')).json()
        self.assertTrue(any(a['action'] == 'lati_chat' and a['actor'] == 'astro1' for a in audits))

        # Integrations reports honest LLM status
        integ = self.client.get('/api/integrations', headers=self.h('admin')).json()
        self.assertEqual(integ['lati_llm']['status'], 'not_configured')
        self.assertEqual(integ['lati_llm']['mode'], 'rules_local')


if __name__ == '__main__':
    unittest.main()
