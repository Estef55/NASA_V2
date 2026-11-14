from datetime import datetime, timezone
import os
import sys
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from ..database import conn
from ..security import auth, need
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from ai.thermography import analyze_thermal_image

router = APIRouter(prefix='/api/thermography', tags=['thermography'])
ROOT = Path(__file__).resolve().parents[3]
MAX_BYTES = 10 * 1024 * 1024
SIGNATURES = {
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.tif': (b'II*\x00', b'MM\x00*'),
    '.tiff': (b'II*\x00', b'MM\x00*'),
}


def storage_dir():
    path = Path(os.getenv('LATIRA_THERMAL_DIR', ROOT / 'data' / 'uploads' / 'thermography')).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_table():
    with conn() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS thermal_images(
            id TEXT PRIMARY KEY, astronaut_id TEXT NOT NULL, owner_username TEXT NOT NULL,
            filename TEXT NOT NULL, stored_name TEXT NOT NULL, media_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL, demo INTEGER NOT NULL DEFAULT 0)''')


ensure_table()


@router.post('/upload')
async def upload_thermal(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    user = auth(authorization)
    need(user, 'astronaut')
    if not user.get('astronaut_id'):
        raise HTTPException(400, 'Astronaut identity required')
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in SIGNATURES:
        raise HTTPException(415, 'Unsupported thermal image format')
    payload = await file.read(MAX_BYTES + 1)
    if not payload:
        raise HTTPException(400, 'Thermal image is empty')
    if len(payload) > MAX_BYTES:
        raise HTTPException(413, 'Thermal image exceeds the 10 MiB limit')
    if not any(payload.startswith(signature) for signature in SIGNATURES[suffix]):
        raise HTTPException(415, 'Image content does not match the file extension')
    try:
        analysis = analyze_thermal_image(payload, Path(file.filename).name)
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    image_id = uuid4().hex
    stored_name = f'{image_id}{suffix}'
    (storage_dir() / stored_name).write_bytes(payload)
    media_type = {'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','tif':'image/tiff','tiff':'image/tiff'}[suffix[1:]]
    try:
        with conn() as db:
            db.execute('INSERT INTO thermal_images(id,astronaut_id,owner_username,filename,stored_name,media_type,size_bytes,created_at,demo) VALUES(?,?,?,?,?,?,?,?,0)',
                       (image_id, user['astronaut_id'], user['username'], Path(file.filename).name, stored_name, media_type, len(payload), datetime.now(timezone.utc).isoformat()))
    except Exception:
        (storage_dir() / stored_name).unlink(missing_ok=True)
        raise
    return {
        'id': image_id, 'astronaut_id': user['astronaut_id'], 'filename': Path(file.filename).name,
        'size_bytes': len(payload), 'created_at': datetime.now(timezone.utc).isoformat(),
        'source': 'user_uploaded_image', 'analysis': analysis, 'core_temperature_inferred': False,
        'notice': 'Image stored for review only. No core-temperature estimate or medical diagnosis is produced.'
    }


@router.get('/history')
def thermal_history(authorization: str | None = Header(default=None)):
    user = auth(authorization)
    need(user, 'astronaut', 'medic')
    with conn() as db:
        if user['role'] == 'astronaut':
            rows = db.execute('SELECT id,astronaut_id,filename,media_type,size_bytes,created_at,demo FROM thermal_images WHERE astronaut_id=? ORDER BY created_at DESC', (user['astronaut_id'],)).fetchall()
        else:
            rows = db.execute('SELECT t.id,t.astronaut_id,t.filename,t.media_type,t.size_bytes,t.created_at,t.demo FROM thermal_images t JOIN assignments a ON a.astronaut_id=t.astronaut_id WHERE a.medic_username=? ORDER BY t.created_at DESC', (user['username'],)).fetchall()
    return [dict(row) for row in rows]


@router.get('/image/{image_id}')
def get_thermal_image(image_id: str, authorization: str | None = Header(default=None)):
    user = auth(authorization)
    need(user, 'astronaut', 'medic')
    with conn() as db:
        row = db.execute('SELECT * FROM thermal_images WHERE id=?', (image_id,)).fetchone()
        if row and user['role'] == 'astronaut' and row['astronaut_id'] != user['astronaut_id']:
            row = None
        if row and user['role'] == 'medic' and not db.execute('SELECT 1 FROM assignments WHERE medic_username=? AND astronaut_id=?', (user['username'], row['astronaut_id'])).fetchone():
            row = None
    if not row:
        raise HTTPException(404, 'Thermal image not found')
    path = storage_dir() / row['stored_name']
    if not path.is_file():
        raise HTTPException(410, 'Thermal image file is no longer available')
    return FileResponse(path, media_type=row['media_type'], filename=row['filename'])
