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

class NewBackendFeatureTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app)
        with conn() as db:
            db.execute('DELETE FROM sessions'); db.execute('DELETE FROM checkins'); db.execute('DELETE FROM conversations'); db.execute('DELETE FROM metrics'); db.execute('DELETE FROM assignments'); db.execute('DELETE FROM users')
            for n,r,a in [('astro','astronaut','AST-A'),('astro2','astronaut','AST-B'),('medic','medic',None),('admin','admin',None)]: db.execute('INSERT INTO users(username,password_hash,role,astronaut_id) VALUES(?,?,?,?)',(n,hash_password('[REDACTED]'),r,a))
            db.execute("INSERT INTO assignments VALUES('medic','AST-A')")
        self.t={n:self.client.post('/api/auth/login',json={'username':n,'password':'[REDACTED]'}).json()['token'] for n in ('astro','astro2','medic','admin')}
    def h(self,n): return {'Authorization':'Bearer '+self.t[n]}
    def test_manual_metric_is_real_and_owner_scoped(self):
        r=self.client.post('/api/metrics',headers=self.h('astro'),json={'sleep':7.2,'heart_rate':64,'fatigue':2,'mood':4,'source':'manual','unit':'hours','recorded_at':'2026-04-02T12:00:00Z'})
        self.assertEqual(r.status_code,200); self.assertEqual(r.json()['demo'],0); self.assertEqual(r.json()['source'],'manual')
        invalid=self.client.post('/api/metrics',headers=self.h('astro'),json={'sleep':-1,'source':'manual','unit':'h','recorded_at':'2026-04-02T12:00:00Z'})
        self.assertEqual(invalid.status_code,422)
    def test_checkin_creates_owner_scoped_local_conversation_history(self):
        r=self.client.post('/api/checkins',headers=self.h('astro'),json={'fatigue':2,'mood':4,'note':'ok','language':'en'})
        self.assertEqual(r.status_code,200); self.assertEqual(r.json()['origin'],'rules_local')
        self.assertEqual(len(self.client.get('/api/conversation',headers=self.h('astro')).json()),2)
    def test_chat_uses_local_rules_persists_owner_scoped_conversation(self):
        response=self.client.post('/api/lati/chat',headers=self.h('astro'),json={'message':'How is my sleep?','language':'en'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['origin'],'rules_local')
        self.assertIn('baseline',response.json())
        history=self.client.get('/api/conversation',headers=self.h('astro')).json()
        self.assertEqual(len(history),2)
        other=self.client.get('/api/conversation',headers=self.h('astro2')).json()
        self.assertEqual(other,[])

    def test_admin_role_change_clears_or_sets_astronaut_identity_consistently(self):
        created=self.client.post('/api/admin/users',headers=self.h('admin'),json={'username':'rolechange','password':'[REDACTED]','role':'astronaut','astronaut_id':'AST-R'})
        self.assertEqual(created.status_code,200)
        changed=self.client.patch('/api/admin/users/rolechange',headers=self.h('admin'),json={'role':'medic','astronaut_id':None})
        self.assertEqual(changed.status_code,200)
        listed=self.client.get('/api/admin/users',headers=self.h('admin')).json()
        row=next(x for x in listed if x['username']=='rolechange')
        self.assertEqual(row['role'],'medic')
        self.assertIsNone(row['astronaut_id'])
        restored=self.client.patch('/api/admin/users/rolechange',headers=self.h('admin'),json={'role':'astronaut','astronaut_id':'AST-R2'})
        self.assertEqual(restored.status_code,200)
        row=next(x for x in self.client.get('/api/admin/users',headers=self.h('admin')).json() if x['username']=='rolechange')
        self.assertEqual((row['role'],row['astronaut_id']),('astronaut','AST-R2'))

    def test_admin_can_create_user_and_get_assigned_astronaut_detail(self):
        created=self.client.post('/api/admin/users',headers=self.h('admin'),json={'username':'newastro','password':'[REDACTED]','role':'astronaut','astronaut_id':'AST-N'})
        self.assertEqual(created.status_code,200)
        measured=self.client.post('/api/metrics',headers=self.h('astro'),json={'sleep':7.2,'heart_rate':64,'fatigue':2,'mood':4,'source':'manual','unit':'h','recorded_at':'2026-04-02T12:00:00Z'})
        self.assertEqual(measured.status_code,200)
        detail=self.client.get('/api/admin/astronauts/AST-A',headers=self.h('medic'))
        self.assertEqual(detail.status_code,200); self.assertIn('baseline',detail.json()); self.assertEqual(len(detail.json()['metrics']),1)
        self.assertEqual(self.client.get('/api/admin/astronauts/AST-N',headers=self.h('medic')).status_code,404)
