import os
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


class ApiRegressionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        with conn() as db:
            db.execute('DELETE FROM sessions')
            db.execute('DELETE FROM followups')
            db.execute('DELETE FROM alerts')
            db.execute('DELETE FROM metrics')
            db.execute('DELETE FROM assignments')
            db.execute('DELETE FROM users')
            for name, role, aid in [('astro1','astronaut','AST-001'), ('astro2','astronaut','AST-002'), ('medic','medic',None), ('admin','admin',None)]:
                db.execute('INSERT INTO users(username,password_hash,role,astronaut_id) VALUES(?,?,?,?)', (name, hash_password('[REDACTED]'), role, aid))
        self.tokens = {name: self.client.post('/api/auth/login', json={'username':name,'password':'[REDACTED]'}).json()['token'] for name in ('astro1','astro2','medic','admin')}

    def headers(self, role):
        return {'Authorization': 'Bearer ' + self.tokens[role]}

    def test_baseline_endpoint_reports_insufficient_then_sufficient_samples(self):
        one = self.client.post('/api/demo/start', headers=self.headers('astro1'))
        self.assertEqual(one.status_code, 200)
        response = self.client.get('/api/baseline', headers=self.headers('astro1'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['sufficient'])
        for _ in range(2):
            self.client.post('/api/demo/next', headers=self.headers('astro1'))
        response = self.client.get('/api/baseline', headers=self.headers('astro1'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['sufficient'])
        self.assertEqual(response.json()['sample_count'], 3)

    def test_baseline_tracks_sample_sufficiency_per_indicator(self):
        with conn() as db:
            for i in range(3):
                db.execute('INSERT INTO metrics(astronaut_id,recorded_at,sleep,source,demo) VALUES(?,?,?,?,0)',('AST-001',f'2026-03-0{i+1}T00:00:00+00:00',7+i/10,'manual'))
        baseline=self.client.get('/api/baseline',headers=self.headers('astro1')).json()
        self.assertEqual(baseline['metric_samples']['sleep'],3)
        self.assertEqual(baseline['metric_samples']['heart_rate'],0)
        self.assertTrue(baseline['metric_sufficiency']['sleep'])
        self.assertFalse(baseline['metric_sufficiency']['heart_rate'])
        self.assertEqual(set(baseline['values']),{'sleep'})

    def test_alerts_are_created_from_baseline_deviation_explanation(self):
        self.client.post('/api/demo/start', headers=self.headers('astro1'))
        for _ in range(4):
            self.client.post('/api/demo/next', headers=self.headers('astro1'))
        alerts = self.client.get('/api/alerts', headers=self.headers('astro1')).json()
        self.assertTrue(alerts)
        self.assertTrue(all('deviation' in row['reason'].lower() for row in alerts))
        self.assertTrue(all(row['demo'] == 1 for row in alerts))

    def test_medic_metrics_and_alerts_are_limited_to_assigned_astronauts(self):
        with conn() as db:
            db.execute("INSERT INTO assignments(medic_username,astronaut_id) VALUES('medic','AST-001')")
            for aid in ('AST-001','AST-002'):
                db.execute('INSERT INTO metrics(astronaut_id,day,recorded_at,source,demo) VALUES(?,1,?,?,0)', (aid,'2026-01-01T00:00:00+00:00','test'))
                db.execute('INSERT INTO alerts(astronaut_id,created_at,priority,reason,demo) VALUES(?,?,?, ?,0)', (aid,'2026-01-01T00:00:00+00:00','review','test',))
        metrics = self.client.get('/api/metrics', headers=self.headers('medic')).json()
        self.assertEqual({r['astronaut_id'] for r in metrics}, {'AST-001'})
        alerts = self.client.get('/api/alerts', headers=self.headers('medic')).json()
        self.assertEqual({r['astronaut_id'] for r in alerts}, {'AST-001'})

    def test_medic_cannot_add_followup_to_unassigned_astronaut_alert(self):
        with conn() as db:
            db.execute("INSERT INTO assignments(medic_username,astronaut_id) VALUES('medic','AST-001')")
            cur = db.execute("INSERT INTO alerts(astronaut_id,created_at,priority,reason,demo) VALUES('AST-002','2026-01-01','review','test',0)")
            alert_id = cur.lastrowid
        response = self.client.post(f'/api/alerts/{alert_id}/followups', headers=self.headers('medic'), json={'note':'review'})
        self.assertEqual(response.status_code, 404)

    def test_medic_report_can_be_filtered_to_assigned_astronaut_only(self):
        with conn() as db:
            db.execute("INSERT INTO assignments(medic_username,astronaut_id) VALUES('medic','AST-001')")
            for aid in ('AST-001','AST-002'):
                db.execute('INSERT INTO metrics(astronaut_id,recorded_at,source,demo) VALUES(?,?,?,0)',(aid,f'2026-01-0{1 if aid=="AST-001" else 2}T00:00:00Z','real-source'))
            db.execute('INSERT INTO metrics(astronaut_id,recorded_at,source,demo) VALUES(?,?,?,1)',('AST-001','2026-01-03T00:00:00Z','demo-source'))
        report=self.client.get('/api/admin/reports/astronauts.csv?astronaut_id=AST-001&demo=false',headers=self.headers('medic'))
        self.assertEqual(report.status_code,200)
        self.assertIn('AST-001',report.text)
        self.assertIn('real-source',report.text)
        self.assertNotIn('AST-002',report.text)
        self.assertNotIn('demo-source',report.text)
        demo_report=self.client.get('/api/admin/reports/astronauts.csv?astronaut_id=AST-001&demo=true',headers=self.headers('medic'))
        self.assertIn('demo-source',demo_report.text)
        self.assertNotIn('real-source',demo_report.text)
        forbidden=self.client.get('/api/admin/reports/astronauts.csv?astronaut_id=AST-002',headers=self.headers('medic'))
        self.assertEqual(forbidden.status_code,404)

    def test_only_admin_can_manage_assignments(self):
        forbidden = self.client.post('/api/admin/assignments', headers=self.headers('medic'), json={'medic_username':'medic','astronaut_id':'AST-002'})
        self.assertEqual(forbidden.status_code, 403)
        created = self.client.post('/api/admin/assignments', headers=self.headers('admin'), json={'medic_username':'medic','astronaut_id':'AST-002'})
        self.assertEqual(created.status_code, 200)
        listed = self.client.get('/api/admin/assignments', headers=self.headers('admin'))
        self.assertEqual(listed.status_code, 200)
        self.assertIn({'medic_username':'medic','astronaut_id':'AST-002'}, listed.json())

    def test_admin_does_not_get_automatic_clinical_access(self):
        with conn() as db:
            db.execute("INSERT INTO metrics(astronaut_id,recorded_at,sleep,source,demo) VALUES('AST-001','2026-01-01T00:00:00Z',7.0,'manual',0)")
            cur = db.execute("INSERT INTO alerts(astronaut_id,created_at,priority,reason,demo) VALUES('AST-001','2026-01-01','review','test',0)")
            alert_id = cur.lastrowid
        for path in ('/api/metrics', '/api/alerts', '/api/baseline', '/api/admin/astronauts/AST-001', '/api/admin/reports/astronauts.csv', '/api/thermography/history', '/api/thermography/image/nonexistent'):
            res = self.client.get(path, headers=self.headers('admin'))
            self.assertEqual(res.status_code, 403, f'{path} returned {res.status_code}')
        fup = self.client.post(f'/api/alerts/{alert_id}/followups', headers=self.headers('admin'), json={'note': 'admin note'})
        self.assertEqual(fup.status_code, 403)

    def test_astronaut_cannot_access_other_astronaut_records(self):
        self.client.post('/api/metrics', headers=self.headers('astro1'), json={'sleep': 7.5, 'source': 'manual', 'unit': 'h', 'recorded_at': '2026-04-01T00:00:00Z'})
        self.client.post('/api/lati/chat', headers=self.headers('astro1'), json={'message': 'How is my sleep?', 'language': 'en'})
        metrics_other = self.client.get('/api/metrics', headers=self.headers('astro2')).json()
        self.assertEqual(metrics_other, [])
        conv_other = self.client.get('/api/conversation', headers=self.headers('astro2')).json()
        self.assertEqual(conv_other, [])
        reply = self.client.post('/api/lati/chat', headers=self.headers('astro1'), json={'message': 'sleep?', 'language': 'en'}).json()['reply']
        self.assertIn('N/A', reply)
        self.assertNotIn('None', reply)


if __name__ == '__main__':
    unittest.main()
