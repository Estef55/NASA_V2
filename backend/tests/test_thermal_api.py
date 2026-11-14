import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _db_isolation import configure_isolated_test_db

configure_isolated_test_db()

from fastapi.testclient import TestClient
import app.database as database
import app.main as main
from app.main import app, conn, hash_password
from app.routers.thermography import ensure_table

PNG_FIXTURE = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p/8AAAAASUVORK5CYII=')

class ThermographyApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='latira_thermal_test_')
        cls.old_db=database.DB
        database.DB=Path(cls.temp.name)/'thermal-test.sqlite3'
        main.DB=database.DB
        cls.old_thermal=os.environ.get('LATIRA_THERMAL_DIR')
        os.environ['LATIRA_THERMAL_DIR']=str(Path(cls.temp.name)/'thermal')
        main.init();ensure_table()
        with conn() as db:
            db.execute("INSERT INTO users(username,password_hash,role,astronaut_id,active) VALUES('thermal_astro',?,'astronaut','THERMAL-1',1)",(hash_password('[REDACTED]'),))

    @classmethod
    def tearDownClass(cls):
        database.DB=cls.old_db
        main.DB=cls.old_db
        if cls.old_thermal is None: os.environ.pop('LATIRA_THERMAL_DIR',None)
        else: os.environ['LATIRA_THERMAL_DIR']=cls.old_thermal
        cls.temp.cleanup()

    def setUp(self):
        self.client=TestClient(app)
        login=self.client.post('/api/auth/login',json={'username':'thermal_astro','password':'[REDACTED]'})
        self.headers={'Authorization':'Bearer '+login.json()['token']}

    def test_authenticated_thermal_image_is_saved_and_listed_without_core_temp(self):
        response=self.client.post('/api/thermography/upload',headers=self.headers,files={'file':('sample.png',PNG_FIXTURE,'image/png')})
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()['core_temperature_inferred'])
        self.assertEqual(response.json()['analysis']['status'],'user_image_received')
        history=self.client.get('/api/thermography/history',headers=self.headers)
        self.assertEqual(history.status_code,200)
        self.assertTrue(any(item['id']==response.json()['id'] for item in history.json()))

    def test_thermal_upload_requires_login(self):
        response=self.client.post('/api/thermography/upload',files={'file':('sample.png',PNG_FIXTURE,'image/png')})
        self.assertEqual(response.status_code,401)

if __name__=='__main__':
    unittest.main()
