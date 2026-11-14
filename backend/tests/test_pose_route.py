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

from fastapi.testclient import TestClient
import app.database as database
import app.main as main
from app.main import app, conn, hash_password

class PoseRouteIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='latira_pose_test_')
        cls.old_db=database.DB
        database.DB=Path(cls.temp.name)/'pose-test.sqlite3'
        main.DB=database.DB
        main.init()
        with conn() as db:
            db.execute("INSERT INTO users(username,password_hash,role,astronaut_id,active) VALUES('pose_astro',?,'astronaut','POSE-1',1)",(hash_password('[REDACTED]'),))

    @classmethod
    def tearDownClass(cls):
        database.DB=cls.old_db
        main.DB=cls.old_db
        cls.temp.cleanup()

    def setUp(self):
        self.client=TestClient(app)
        login=self.client.post('/api/auth/login',json={'username':'pose_astro','password':'[REDACTED]'})
        self.assertEqual(login.status_code,200)
        self.headers={'Authorization':'Bearer '+login.json()['token']}

    def test_authenticated_video_processing_route_is_mounted(self):
        paths = app.openapi()['paths']
        self.assertIn('/api/pose/process', paths)
        self.assertIn('/api/pose/history', paths)

    def test_upload_requires_authenticated_user(self):
        response=self.client.post('/api/pose/process',files={'file':('clip.mp4',b'not-real-video','video/mp4')})
        self.assertEqual(response.status_code,401)

    def test_upload_rejects_unapproved_extension(self):
        response=self.client.post('/api/pose/process',headers=self.headers,files={'file':('clip.txt',b'x','text/plain')})
        self.assertEqual(response.status_code,400)

    def test_upload_rejects_mismatched_content_signature(self):
        response=self.client.post('/api/pose/process',headers=self.headers,files={'file':('clip.mp4',b'not an mp4 container','video/mp4')})
        self.assertEqual(response.status_code,415)

    def test_successful_processing_returns_protected_video_and_persists_history(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as work:
            root=Path(work)
            def fake_process(source, output_dir):
                output_dir.mkdir(parents=True,exist_ok=True)
                rendered=output_dir/'annotated.mp4'
                rendered.write_bytes(b'processed')
                return {'output_video':str(rendered),'frames_processed':2,'model':'unit-test','measurements':[],'notice':'geometric detections only'}
            with patch('app.routers.pose._settings',return_value=(root/'storage',root/'history.sqlite3',1024)), patch('app.routers.pose.process_video',side_effect=fake_process):
                response=self.client.post('/api/pose/process',headers=self.headers,files={'file':('clip.mp4',bytes.fromhex('000000186674797069736f6d00000000'),'video/mp4')})
                self.assertEqual(response.status_code,200,response.text)
                payload=response.json()
                self.assertEqual(payload['video_url'],f"/api/pose/history/{payload['id']}/video")
                self.assertEqual(self.client.get(payload['video_url'],headers=self.headers).content,b'processed')
                history=self.client.get('/api/pose/history',headers=self.headers).json()
                self.assertEqual(history[0]['id'],payload['id'])

    def test_optional_model_unavailable_returns_service_error_not_fake_result(self):
        with patch('app.routers.pose.process_video',side_effect=RuntimeError('YOLO processing requires optional dependencies: pip install -r ai/requirements.txt')):
            response=self.client.post('/api/pose/process',headers=self.headers,files={'file':('clip.mp4',bytes.fromhex('000000186674797069736f6d00000000'),'video/mp4')})
        self.assertEqual(response.status_code,503)
        self.assertIn('unavailable',response.json()['detail'].lower())

    def test_pose_status_live_frame_validation_and_live_complete_rbac(self):
        # Status endpoint requires auth and reports model status
        self.assertEqual(self.client.get('/api/pose/status').status_code, 401)
        st = self.client.get('/api/pose/status', headers=self.headers)
        self.assertEqual(st.status_code, 200)
        self.assertIn('status', st.json())

        # /api/pose/frame validates auth and image signature
        self.assertEqual(self.client.post('/api/pose/frame', files={'file': ('f.jpg', b'x', 'image/jpeg')}).status_code, 401)
        self.assertEqual(self.client.post('/api/pose/frame', headers=self.headers, files={'file': ('f.jpg', b'not-an-image', 'image/jpeg')}).status_code, 415)

        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        with patch('app.routers.pose.process_frame_bytes', side_effect=RuntimeError('YOLO processing requires optional dependencies')):
            unavail = self.client.post('/api/pose/frame', headers=self.headers, files={'file': ('f.jpg', jpeg_header, 'image/jpeg')})
        self.assertEqual(unavail.status_code, 503)

        mock_frame = {
            'model': 'yolo11n-pose.pt',
            'width': 640,
            'height': 480,
            'person_count': 1,
            'visible_keypoints': 12,
            'mean_confidence': 0.88,
            'trunk_inclination_deg': 6.0,
            'shoulder_tilt_deg': 2.0,
            'hip_tilt_deg': 1.5,
            'regions': {'head_visible': True, 'upper_body_visible': True, 'torso_visible': True, 'lower_body_visible': True},
            'persons': [],
            'skeleton': [[5, 6]],
            'notice': 'geometric only',
        }
        with patch('app.routers.pose.process_frame_bytes', return_value=mock_frame):
            ok = self.client.post('/api/pose/frame', headers=self.headers, files={'file': ('f.jpg', jpeg_header, 'image/jpeg')})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['visible_keypoints'], 12)

        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as work:
            root = Path(work)
            with patch('app.routers.pose._settings', return_value=(root/'storage', root/'history.sqlite3', 1024*1024)):
                done = self.client.post('/api/pose/live/complete', headers=self.headers, json={
                    'model': 'yolo11n-pose.pt',
                    'duration_seconds': 2.0,
                    'input_name': 'Sesión en vivo',
                    'frames': [
                        {'frame': 1, 'timestamp_s': 0.0, 'visible_keypoints': 12, 'mean_confidence': 0.85, 'trunk_inclination_deg': 5.0, 'shoulder_tilt_deg': 1.5, 'hip_tilt_deg': 1.0, 'person_count': 1, 'regions': {'upper_body_visible': True, 'lower_body_visible': True}},
                        {'frame': 2, 'timestamp_s': 0.5, 'visible_keypoints': 12, 'mean_confidence': 0.87, 'trunk_inclination_deg': 6.0, 'shoulder_tilt_deg': 2.0, 'hip_tilt_deg': 1.0, 'person_count': 1, 'regions': {'upper_body_visible': True, 'lower_body_visible': True}},
                    ],
                    'representative_frames': [],
                })
                self.assertEqual(done.status_code, 200, done.text)
                created_id = done.json()['id']
                self.assertIn('interpretation', done.json())
                self.assertIn('summary', done.json()['interpretation'])

                # Another astronaut cannot access or delete pose_astro's session
                with conn() as db:
                    db.execute("INSERT OR IGNORE INTO users(username,password_hash,role,astronaut_id,active) VALUES('pose_other',?,'astronaut','POSE-2',1)", (hash_password('[REDACTED]'),))
                    db.execute("INSERT OR IGNORE INTO users(username,password_hash,role,astronaut_id,active) VALUES('pose_medic',?,'medic',NULL,1)", (hash_password('[REDACTED]'),))
                    db.execute("INSERT OR IGNORE INTO assignments(medic_username,astronaut_id) VALUES('pose_medic','POSE-1')")
                other_token = self.client.post('/api/auth/login', json={'username': 'pose_other', 'password': '[REDACTED]'}).json()['token']
                medic_token = self.client.post('/api/auth/login', json={'username': 'pose_medic', 'password': '[REDACTED]'}).json()['token']

                self.assertEqual(self.client.get('/api/pose/history', headers={'Authorization': 'Bearer ' + other_token}).json(), [])
                self.assertEqual(self.client.delete(f'/api/pose/history/{created_id}', headers={'Authorization': 'Bearer ' + other_token}).status_code, 404)

                # Assigned medic can view assigned astronaut's pose history, but cannot delete another user's analysis
                medic_hist = self.client.get('/api/pose/history', headers={'Authorization': 'Bearer ' + medic_token}).json()
                self.assertTrue(any(item['id'] == created_id for item in medic_hist))

                # Owner can delete cleanly
                self.assertEqual(self.client.delete(f'/api/pose/history/{created_id}', headers=self.headers).status_code, 200)
                self.assertEqual(self.client.get('/api/pose/history', headers=self.headers).json(), [])

if __name__ == '__main__':
    unittest.main()
