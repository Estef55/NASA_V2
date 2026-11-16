from datetime import datetime, timezone
import os, secrets
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .database import DB, conn
from .security import auth, need, hash_password, verify_password
from .services.health_baseline import calculate_baseline, create_deviation_alert
from .services.lati_ai import get_lati_llm_status, verify_lati_llm_connection

app = FastAPI(title='LÁTIRA 2.0 API', version='2.0.0', description='Demo académica; no es dispositivo médico.')
_raw_cors = os.getenv('LATIRA_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
_cors_origins = [origin.strip() for origin in _raw_cors.split(',') if origin.strip() and origin.strip() != '*']
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins or ['http://localhost:5173','http://127.0.0.1:5173'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

DEMO_PROFILE_SPECS = (
    {
        'profile': 'astronaut',
        'username': 'astro_demo',
        'role': 'astronaut',
        'astronaut_id': 'AST-001',
        'label_es': 'Astronauta',
        'label_en': 'Astronaut',
        'summary_es': 'Tripulante asignado (AST-001): resumen, chequeo diario, registro real, LÁTI y análisis de movimiento.',
        'summary_en': 'Assigned crew member (AST-001): overview, daily check-in, real monitoring, LÁTI, and pose analysis.',
    },
    {
        'profile': 'medic',
        'username': 'medic_demo',
        'role': 'medic',
        'astronaut_id': None,
        'label_es': 'Médico',
        'label_en': 'Medical officer',
        'summary_es': 'Personal médico con acceso exclusivo a tripulación asignada (AST-001), alertas, seguimientos y reportes.',
        'summary_en': 'Medical officer scoped exclusively to assigned crew (AST-001), clinical alerts, follow-ups, and reports.',
    },
    {
        'profile': 'admin',
        'username': 'admin_demo',
        'role': 'admin',
        'astronaut_id': None,
        'label_es': 'Administrador',
        'label_en': 'Administrator',
        'summary_es': 'Administración del sistema con aislamiento clínico RBAC: cuentas, asignaciones e integraciones.',
        'summary_en': 'RBAC-isolated system administration: accounts, assignments, and integrations.',
    },
)
DEMO_PROFILE_MAP = {spec['profile']: spec for spec in DEMO_PROFILE_SPECS}


def is_demo_auth_enabled() -> bool:
    env = os.getenv('LATIRA_ENV', 'production').strip().lower()
    flag = os.getenv('LATIRA_DEMO_LOGIN', '').strip().lower()
    if flag in ('0', 'false', 'no', 'off'):
        return False
    return env == 'demo'


def ensure_demo_accounts(c) -> None:
    demo_mode = is_demo_auth_enabled()
    demo_password = os.getenv('LATIRA_DEMO_PASSWORD')
    if demo_mode:
        seed_secret = demo_password or secrets.token_urlsafe(32)
        for spec in DEMO_PROFILE_SPECS:
            exists = c.execute('SELECT 1 FROM users WHERE username=?', (spec['username'],)).fetchone()
            if not exists:
                c.execute(
                    'INSERT INTO users(username,password_hash,role,astronaut_id) VALUES(?,?,?,?)',
                    (spec['username'], hash_password(seed_secret), spec['role'], spec['astronaut_id']),
                )
        c.execute(
            "INSERT OR IGNORE INTO assignments(medic_username,astronaut_id) "
            "SELECT 'medic_demo','AST-001' "
            "WHERE EXISTS(SELECT 1 FROM users WHERE username='medic_demo' AND role='medic') "
            "AND EXISTS(SELECT 1 FROM users WHERE astronaut_id='AST-001' AND role='astronaut')"
        )
    elif not c.execute('SELECT 1 FROM users LIMIT 1').fetchone() and demo_password:
        for spec in DEMO_PROFILE_SPECS:
            c.execute(
                'INSERT INTO users(username,password_hash,role,astronaut_id) VALUES(?,?,?,?)',
                (spec['username'], hash_password(demo_password), spec['role'], spec['astronaut_id']),
            )
        c.execute("INSERT OR IGNORE INTO assignments(medic_username,astronaut_id) SELECT 'medic_demo','AST-001' WHERE EXISTS(SELECT 1 FROM users WHERE username='medic_demo')")


def init():
    with conn() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL, astronaut_id TEXT, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY, astronaut_id TEXT NOT NULL, day INTEGER, recorded_at TEXT NOT NULL, sleep REAL, heart_rate REAL, fatigue INTEGER, mood INTEGER, source TEXT NOT NULL, demo INTEGER DEFAULT 0, unit TEXT);
        CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY, astronaut_id TEXT, created_at TEXT, fatigue INTEGER, mood INTEGER, note TEXT, demo INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, astronaut_id TEXT, metric_id INTEGER, created_at TEXT, priority TEXT, reason TEXT, status TEXT DEFAULT 'pending', demo INTEGER DEFAULT 0, UNIQUE(metric_id,reason));
        CREATE TABLE IF NOT EXISTS followups(id INTEGER PRIMARY KEY, alert_id INTEGER REFERENCES alerts(id), author TEXT, note TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor TEXT, action TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, username TEXT, expires TEXT);
        CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY,astronaut_id TEXT NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,origin TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assignments(medic_username TEXT NOT NULL REFERENCES users(username), astronaut_id TEXT NOT NULL, PRIMARY KEY(medic_username, astronaut_id));
        CREATE TABLE IF NOT EXISTS demo_state(id INTEGER PRIMARY KEY CHECK(id=1), day INTEGER DEFAULT 0, active INTEGER DEFAULT 0); INSERT OR IGNORE INTO demo_state(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS demo_owner_state(astronaut_id TEXT PRIMARY KEY, day INTEGER DEFAULT 0, active INTEGER DEFAULT 0);''')
        ensure_demo_accounts(c)
        if 'unit' not in [r['name'] for r in c.execute('PRAGMA table_info(metrics)')]: c.execute('ALTER TABLE metrics ADD COLUMN unit TEXT')
        conv_cols = {r['name'] for r in c.execute('PRAGMA table_info(conversations)')}
        if 'input_mode' not in conv_cols:
            c.execute("ALTER TABLE conversations ADD COLUMN input_mode TEXT DEFAULT 'text'")
        if 'context_source' not in conv_cols:
            c.execute("ALTER TABLE conversations ADD COLUMN context_source TEXT DEFAULT 'rules_local'")
        if 'model' not in conv_cols:
            c.execute('ALTER TABLE conversations ADD COLUMN model TEXT')
        if 'client_message_id' not in conv_cols:
            c.execute('ALTER TABLE conversations ADD COLUMN client_message_id TEXT')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_client_msg ON conversations(astronaut_id, role, client_message_id) WHERE client_message_id IS NOT NULL')
init()

class Login(BaseModel): username:str; password:str
class DemoLogin(BaseModel):
    model_config = {'extra': 'forbid'}
    profile: str
class Checkin(BaseModel): fatigue:int=Field(ge=1,le=5); mood:int=Field(ge=1,le=5); note:str=''; language:str='es'
class Followup(BaseModel): note:str=Field(min_length=1,max_length=2000)

def audit(actor,action):
    with conn() as c:c.execute('INSERT INTO audit(actor,action,created_at) VALUES(?,?,?)',(actor,action,datetime.now(timezone.utc).isoformat()))
@app.get('/api/health')
def health():
    from .routers.nasa import get_nasa_runtime_overview
    try:
        nasa_status = get_nasa_runtime_overview().get('status', 'catalogued_reference_only')
    except Exception:
        nasa_status = 'catalogued_reference_only'
    return {'status':'ok','database':'connected','demo_mode':'separate demo flag','medical_device':False,'nasa_source':nasa_status}
def _issue_session(c, username: str) -> str:
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc).timestamp() + int(os.getenv('LATIRA_SESSION_TTL_SECONDS', '43200'))
    exp = datetime.fromtimestamp(expiry, timezone.utc).isoformat()
    c.execute('INSERT INTO sessions VALUES(?,?,?)', (token, username, exp))
    return token


@app.get('/api/auth/demo-profiles')
def demo_profiles():
    if not is_demo_auth_enabled():
        env = os.getenv('LATIRA_ENV', 'production').strip().lower() or 'production'
        return {'enabled': False, 'environment': 'demo_disabled' if env == 'demo' else env, 'profiles': []}
    with conn() as c:
        ensure_demo_accounts(c)
        profiles = []
        for spec in DEMO_PROFILE_SPECS:
            row = c.execute(
                'SELECT username, role, astronaut_id, active FROM users WHERE username=?',
                (spec['username'],),
            ).fetchone()
            if row and row['active'] == 1 and row['role'] == spec['role']:
                profiles.append({
                    'profile': spec['profile'],
                    'role': row['role'],
                    'astronaut_id': row['astronaut_id'],
                    'label_es': spec['label_es'],
                    'label_en': spec['label_en'],
                    'summary_es': spec['summary_es'],
                    'summary_en': spec['summary_en'],
                })
    return {'enabled': True, 'environment': 'demo', 'profiles': profiles}


@app.post('/api/auth/demo-login')
def demo_login(data: DemoLogin):
    if not is_demo_auth_enabled():
        raise HTTPException(403, 'El acceso de demostración sin contraseña solo está habilitado en entorno demo')
    spec = DEMO_PROFILE_MAP.get(data.profile.strip().lower())
    if not spec:
        raise HTTPException(400, 'Perfil de demostración inválido')
    with conn() as c:
        ensure_demo_accounts(c)
        row = c.execute('SELECT * FROM users WHERE username=? AND active=1', (spec['username'],)).fetchone()
        if not row or row['role'] != spec['role']:
            raise HTTPException(403, 'Cuenta de demostración no disponible')
        if spec['role'] == 'astronaut' and not row['astronaut_id']:
            raise HTTPException(403, 'Cuenta de astronauta sin identidad asignada')
        token = _issue_session(c, row['username'])
    audit(row['username'], f"demo_login:{spec['profile']}")
    return {'token': token, 'role': row['role'], 'astronaut_id': row['astronaut_id'], 'username': row['username']}


@app.post('/api/auth/login')
def login(data:Login):
    with conn() as c: row=c.execute('SELECT * FROM users WHERE username=? AND active=1',(data.username,)).fetchone()
    if not row: raise HTTPException(401,'Credenciales inválidas')
    if not verify_password(data.password, row['password_hash']): raise HTTPException(401,'Credenciales inválidas')
    if '$' not in row['password_hash']:
        with conn() as c: c.execute('UPDATE users SET password_hash=? WHERE username=?',(hash_password(data.password),data.username))
    with conn() as c:
        token = _issue_session(c, data.username)
    audit(data.username,'login'); return {'token':token,'role':row['role'],'astronaut_id':row['astronaut_id'],'username':row['username']}
@app.get('/api/me')
def me(authorization:str|None=Header(None)):
    u=auth(authorization); return {k:u[k] for k in ('username','role','astronaut_id')}
@app.post('/api/auth/logout')
def logout(authorization:str|None=Header(None)):
    u=auth(authorization); token=authorization.removeprefix('Bearer ').strip()
    with conn() as c:c.execute('DELETE FROM sessions WHERE token=?',(token,))
    audit(u['username'],'logout'); return {'ok':True}

def _demo_target_aid(u):
    return u.get('astronaut_id') or 'AST-001'

def _get_owner_demo_row(c, aid: str):
    row = c.execute('SELECT day,active FROM demo_owner_state WHERE astronaut_id=?', (aid,)).fetchone()
    if row is None:
        if aid == 'AST-001':
            legacy = c.execute('SELECT day,active FROM demo_state WHERE id=1').fetchone()
            day, active = (legacy['day'], legacy['active']) if legacy else (0, 0)
        else:
            day, active = (0, 0)
        c.execute('INSERT OR IGNORE INTO demo_owner_state(astronaut_id,day,active) VALUES(?,?,?)', (aid, day, active))
        return {'day': day, 'active': active}
    return {'day': row['day'], 'active': row['active']}

def _set_owner_demo_state(c, aid: str, day: int, active: int):
    c.execute(
        'INSERT INTO demo_owner_state(astronaut_id,day,active) VALUES(?,?,?) '
        'ON CONFLICT(astronaut_id) DO UPDATE SET day=excluded.day, active=excluded.active',
        (aid, day, active),
    )
    if aid == 'AST-001':
        c.execute('UPDATE demo_state SET day=?, active=? WHERE id=1', (day, active))

def _clear_demo_scenario(c, aid: str) -> None:
    c.execute(
        'DELETE FROM followups WHERE alert_id IN (SELECT id FROM alerts WHERE demo=1 AND astronaut_id=?)',
        (aid,),
    )
    c.execute('DELETE FROM alerts WHERE demo=1 AND astronaut_id=?', (aid,))
    c.execute('DELETE FROM metrics WHERE demo=1 AND astronaut_id=?', (aid,))
    c.execute('DELETE FROM checkins WHERE demo=1 AND astronaut_id=?', (aid,))


@app.post('/api/demo/start')
def demo_start(authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'astronaut','admin')
    aid=_demo_target_aid(u)
    with conn() as c:
        _clear_demo_scenario(c, aid)
        _set_owner_demo_state(c, aid, 1, 1)
        add_demo_day(c, 1, aid)
    audit(u['username'],'demo_start'); return demo_status(aid)

def add_demo_day(c, d, astronaut_id='AST-001'):
    rows=[(7.5,66,2,4),(7,67,2,4),(6,70,3,3),(5.5,74,3,3),(5,77,4,2)]
    sl,hr,fa,mo=rows[d-1]
    cur=c.execute('INSERT INTO metrics(astronaut_id,day,recorded_at,sleep,heart_rate,fatigue,mood,source,demo) VALUES(?,?,?,?,?,?,?,?,1)',(astronaut_id,d,datetime.now(timezone.utc).isoformat(),sl,hr,fa,mo,'DEMO ficticio'))
    create_deviation_alert(c, cur.lastrowid)

@app.get('/api/baseline')
def baseline(demo:bool|None=None,authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'astronaut')
    aid=u['astronaut_id']
    if aid is None: raise HTTPException(400,'Astronaut identity required')
    with conn() as c:
        if demo is None:
            latest=c.execute('SELECT demo FROM metrics WHERE astronaut_id=? ORDER BY id DESC LIMIT 1',(aid,)).fetchone()
            use_demo=bool(latest['demo']) if latest else False
        else:
            use_demo=bool(demo)
        return calculate_baseline(c,aid,use_demo)
@app.post('/api/demo/next')
def demo_next(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'astronaut','admin')
    aid=_demo_target_aid(u)
    with conn() as c:
        d=_get_owner_demo_row(c, aid)
        if not d['active']: raise HTTPException(409,'Inicia el escenario primero')
        if d['day']>=5: raise HTTPException(409,'Escenario completado; reinícialo para repetir')
        day=d['day']+1
        _set_owner_demo_state(c, aid, day, 1)
        add_demo_day(c, day, aid)
    audit(u['username'],'demo_next'); return demo_status(aid)
@app.post('/api/demo/reset')
def demo_reset(authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'astronaut','admin')
    aid=_demo_target_aid(u)
    with conn() as c:
        _clear_demo_scenario(c, aid)
        _set_owner_demo_state(c, aid, 0, 0)
    audit(u['username'],'demo_reset'); return demo_status(aid)
def demo_status(astronaut_id='AST-001'):
    with conn() as c:
        state=_get_owner_demo_row(c, astronaut_id)
        rows=[dict(r) for r in c.execute('SELECT day,sleep,heart_rate,fatigue,mood,source FROM metrics WHERE demo=1 AND astronaut_id=? ORDER BY day',(astronaut_id,))]
    return {'state':state,'records':rows}
@app.get('/api/demo')
def get_demo(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'astronaut','medic','admin'); return demo_status(_demo_target_aid(u))
@app.post('/api/checkins')
def checkin(data:Checkin,authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'astronaut'); aid=u['astronaut_id']
    if aid is None: raise HTTPException(400,'Astronaut identity required')
    lang = 'en' if data.language.lower().startswith('en') else 'es'
    with conn() as c:
        owner_demo = _get_owner_demo_row(c, aid)
        latest = c.execute('SELECT demo FROM metrics WHERE astronaut_id=? ORDER BY id DESC LIMIT 1', (aid,)).fetchone()
        demo = 1 if (owner_demo['active'] and (latest is None or latest['demo'] == 1)) else 0
        stamp=datetime.now(timezone.utc).isoformat()
        clean_note = data.note.strip()
        c.execute('INSERT INTO checkins(astronaut_id,created_at,fatigue,mood,note,demo) VALUES(?,?,?,?,?,?)',(aid,stamp,data.fatigue,data.mood,clean_note,demo))
        high_strain = data.fatigue >= 4 or data.mood <= 2
        if lang == 'en':
            if high_strain:
                answer = f'Check-in saved (fatigue {data.fatigue}/5, mood {data.mood}/5). You reported elevated fatigue or low mood — prioritize hydration, rest, and low-demand pacing if possible. This is not a diagnosis; contact your care team if discomfort persists.'
            else:
                answer = f'Thank you for completing the check-in (fatigue {data.fatigue}/5, mood {data.mood}/5). Signals look steady in your self-report. This is not a diagnosis; contact the medical team if you need help.'
            user_entry = f'[Daily check-in: fatigue={data.fatigue}/5, mood={data.mood}/5]' + (f' {clean_note}' if clean_note else '')
        else:
            if high_strain:
                answer = f'Chequeo guardado (fatiga {data.fatigue}/5, ánimo {data.mood}/5). Reportaste fatiga elevada o ánimo bajo: prioriza descanso, hidratación y tareas de menor exigencia si es posible. No es un diagnóstico; contacta al equipo médico si el malestar continúa.'
            else:
                answer = f'Gracias por completar el chequeo (fatiga {data.fatigue}/5, ánimo {data.mood}/5). Tus valores autorreportados se mantienen estables. No es un diagnóstico; contacta al equipo médico si necesitas ayuda.'
            user_entry = f'[Chequeo diario: fatiga={data.fatigue}/5, ánimo={data.mood}/5]' + (f' {clean_note}' if clean_note else '')
        c.execute(
            'INSERT INTO conversations(astronaut_id,role,content,origin,created_at,input_mode,context_source) VALUES(?,?,?,?,?,?,?)',
            (aid, 'user', user_entry, 'rules_local', stamp, 'text', 'authenticated_astronaut_records'),
        )
        c.execute(
            'INSERT INTO conversations(astronaut_id,role,content,origin,created_at,input_mode,context_source) VALUES(?,?,?,?,?,?,?)',
            (aid, 'assistant', answer, 'rules_local', stamp, 'text', 'authenticated_astronaut_records'),
        )
    audit(u['username'],'daily_checkin'); return {'message':'Chequeo guardado','assistant':answer,'origin':'rules_local','demo':demo}

@app.get('/api/checkins')
def list_checkins(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'astronaut','medic')
    with conn() as c:
        if u['role']=='astronaut':
            rows=c.execute('SELECT * FROM checkins WHERE astronaut_id=? ORDER BY id DESC',(u['astronaut_id'],)).fetchall()
        else:
            rows=c.execute('SELECT k.* FROM checkins k JOIN assignments a ON a.astronaut_id=k.astronaut_id WHERE a.medic_username=? ORDER BY k.id DESC',(u['username'],)).fetchall()
    return [dict(r) for r in rows]

@app.get('/api/metrics')
def metrics(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'astronaut','medic')
    with conn() as c:
        if u['role']=='astronaut': rows=c.execute('SELECT * FROM metrics WHERE astronaut_id=? ORDER BY id',(u['astronaut_id'],)).fetchall()
        else: rows=c.execute('SELECT m.* FROM metrics m JOIN assignments a ON a.astronaut_id=m.astronaut_id WHERE a.medic_username=? ORDER BY m.id',(u['username'],)).fetchall()
    return [dict(r) for r in rows]
@app.get('/api/alerts')
def alerts(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'astronaut','medic')
    with conn() as c:
        if u['role']=='astronaut': rows=c.execute('SELECT * FROM alerts WHERE astronaut_id=? ORDER BY id DESC',(u['astronaut_id'],)).fetchall()
        else: rows=c.execute('SELECT x.* FROM alerts x JOIN assignments a ON a.astronaut_id=x.astronaut_id WHERE a.medic_username=? ORDER BY x.id DESC',(u['username'],)).fetchall()
        alert_list = [dict(r) for r in rows]
        if alert_list:
            ids = [a['id'] for a in alert_list]
            placeholders = ','.join('?' for _ in ids)
            frows = c.execute(f'SELECT * FROM followups WHERE alert_id IN ({placeholders}) ORDER BY id DESC', ids).fetchall()
            by_alert: dict[int, list[dict]] = {}
            for fr in frows:
                by_alert.setdefault(fr['alert_id'], []).append(dict(fr))
            for a in alert_list:
                a['followups'] = by_alert.get(a['id'], [])
    return alert_list
@app.post('/api/alerts/{alert_id}/followups')
def followup(alert_id:int,data:Followup,authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'medic')
    with conn() as c:
        alert=c.execute('SELECT id FROM alerts WHERE id=? AND astronaut_id IN (SELECT astronaut_id FROM assignments WHERE medic_username=?)',(alert_id,u['username'])).fetchone()
        if not alert: raise HTTPException(404,'Alerta no encontrada')
        c.execute('INSERT INTO followups(alert_id,author,note,created_at) VALUES(?,?,?,?)',(alert_id,u['username'],data.note,datetime.now(timezone.utc).isoformat()));c.execute("UPDATE alerts SET status='review' WHERE id=?",(alert_id,))
    audit(u['username'],f'followup_alert_{alert_id}'); return {'ok':True}
@app.get('/api/admin/users')
def users(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'admin')
    with conn() as c:return [dict(r) for r in c.execute('SELECT id,username,role,astronaut_id,active FROM users')]

class Assignment(BaseModel):
    medic_username:str
    astronaut_id:str

@app.get('/api/admin/assignments')
def list_assignments(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'admin')
    with conn() as c:return [dict(r) for r in c.execute('SELECT medic_username,astronaut_id FROM assignments ORDER BY medic_username,astronaut_id')]

@app.post('/api/admin/assignments')
def add_assignment(data:Assignment,authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'admin')
    with conn() as c:
        medic=c.execute("SELECT 1 FROM users WHERE username=? AND role='medic'",(data.medic_username,)).fetchone()
        astronaut=c.execute("SELECT 1 FROM users WHERE astronaut_id=? AND role='astronaut'",(data.astronaut_id,)).fetchone()
        if not medic or not astronaut: raise HTTPException(404,'Medic or astronaut not found')
        c.execute('INSERT OR IGNORE INTO assignments(medic_username,astronaut_id) VALUES(?,?)',(data.medic_username,data.astronaut_id))
    audit(u['username'],'assignment_add'); return {'ok':True}

@app.delete('/api/admin/assignments/{medic_username}/{astronaut_id}')
def remove_assignment(medic_username:str,astronaut_id:str,authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'admin')
    with conn() as c:c.execute('DELETE FROM assignments WHERE medic_username=? AND astronaut_id=?',(medic_username,astronaut_id))
    audit(u['username'],'assignment_remove'); return {'ok':True}
def _pose_integration_status():
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from ai.setup_yolo import get_yolo_runtime_status
    return get_yolo_runtime_status(verify_inference=False)

def _lati_llm_status():
    return get_lati_llm_status()

@app.get('/api/lati/status')
def lati_status(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'astronaut','medic','admin')
    return get_lati_llm_status()

@app.post('/api/integrations/lati/verify')
def verify_lati_integration(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'admin')
    status = verify_lati_llm_connection()
    audit(u['username'], f"lati_llm_verify:{status.get('verification_status', 'unknown')}")
    return status

@app.get('/api/integrations')
def integrations(authorization:str|None=Header(None)):
    u=auth(authorization); need(u,'medic','admin')
    from .routers.nasa import get_nasa_runtime_overview
    return {
        'thermography':{'status':'not_connected','reason':'No camera, SDK or credentials provided.'},
        'nasa':get_nasa_runtime_overview(),
        'pose':_pose_integration_status(),
        'lati_llm':_lati_llm_status(),
    }

from .routers_extra import router as extra_router
app.include_router(extra_router)
try:
    from .routers.pose import router as pose_router
    app.include_router(pose_router)
except ImportError:
    pass
from .routers.thermography import router as thermography_router
app.include_router(thermography_router)
from .routers.nasa import router as nasa_router
app.include_router(nasa_router)
