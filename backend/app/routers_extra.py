from datetime import datetime, timezone
from pathlib import Path
import csv, io, sys
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from .main import conn, auth, need, audit, hash_password, calculate_baseline, create_deviation_alert

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from ai.nasa_sources import answer_scientific_query

router=APIRouter()
class ManualMetric(BaseModel):
    sleep:float|None=Field(default=None,ge=0,le=24); heart_rate:float|None=Field(default=None,ge=20,le=240); fatigue:int|None=Field(default=None,ge=1,le=5); mood:int|None=Field(default=None,ge=1,le=5)
    source:str=Field(min_length=1,max_length=100); unit:str=Field(min_length=1,max_length=40); recorded_at:datetime
    @model_validator(mode='after')
    def require_value(self):
        if all(getattr(self,k) is None for k in ('sleep','heart_rate','fatigue','mood')):
            raise ValueError('At least one monitoring value is required')
        return self
class UserCreate(BaseModel):
    username:str; password:str=Field(min_length=8); role:str; astronaut_id:str|None=None
class UserUpdate(BaseModel):
    active:bool|None=None; password:str|None=Field(default=None,min_length=8); role:str|None=None; astronaut_id:str|None=None
class ChatCheckin(BaseModel):
    fatigue:int=Field(ge=1,le=5); mood:int=Field(ge=1,le=5); note:str=''; language:str='en'
class ChatMessage(BaseModel):
    message:str=Field(min_length=1,max_length=1000)
    language:str='en'

@router.post('/api/metrics')
def create_metric(data:ManualMetric,authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'astronaut')
    if not u.get('astronaut_id'):
        raise HTTPException(400,'Astronaut identity required')
    with conn() as c:
        cur=c.execute('INSERT INTO metrics(astronaut_id,recorded_at,sleep,heart_rate,fatigue,mood,source,demo,unit) VALUES(?,?,?,?,?,?,?,0,?)',(u['astronaut_id'],data.recorded_at.isoformat(),data.sleep,data.heart_rate,data.fatigue,data.mood,data.source,data.unit))
        create_deviation_alert(c, cur.lastrowid)
        row=dict(c.execute('SELECT * FROM metrics WHERE id=?',(cur.lastrowid,)).fetchone())
    audit(u['username'],'manual_metric_create'); return row
@router.post('/api/lati/chat')
def lati_chat(data:ChatMessage,authorization:str|None=Header(default=None)):
    user=auth(authorization); need(user,'astronaut')
    language=data.language.lower()
    if language not in ('en','es'): raise HTTPException(422,'language must be en or es')
    aid=user['astronaut_id']; stamp=datetime.now(timezone.utc).isoformat(); question=data.message.strip()
    if not question: raise HTTPException(422,'message cannot be blank')
    qfold=question.casefold()
    with conn() as c:
        latest=c.execute('SELECT * FROM metrics WHERE astronaut_id=? AND demo=0 ORDER BY id DESC LIMIT 1',(aid,)).fetchone()
        baseline=calculate_baseline(c,aid,False)
        sci = answer_scientific_query(question, language)
        if sci is not None:
            answer = sci['reply']
            c.execute('INSERT INTO conversations(astronaut_id,role,content,origin,created_at) VALUES(?,?,?,?,?)',(aid,'user',question,'rules_local',stamp))
            c.execute('INSERT INTO conversations(astronaut_id,role,content,origin,created_at) VALUES(?,?,?,?,?)',(aid,'assistant',answer,'rules_local',stamp))
            c.execute('INSERT INTO audit(actor,action,created_at) VALUES(?,?,?)',(user['username'],'lati_chat',stamp))
            return {
                'reply': answer,
                'origin': 'rules_local',
                'baseline': baseline,
                'context_source': sci['context_source'],
                'citations': sci['citations'],
            }
        if any(w in qfold for w in ('alert','alerta','warning','aviso')):
            alerts_open=c.execute("SELECT id,reason,status FROM alerts WHERE astronaut_id=? AND demo=0 AND status!='closed' ORDER BY id DESC LIMIT 3",(aid,)).fetchall()
            if alerts_open:
                joined=' | '.join(f"#{row['id']}: {row['reason']}" for row in alerts_open)
                answer=(('Existing system alert: ' if language=='en' else 'Alerta vigente del sistema: ')+joined+' '+('This is not a diagnosis; contact your care team for review.' if language=='en' else 'No es un diagnóstico; contacta al equipo médico para revisión.'))
            else:
                answer='There are no open alerts in your real records.' if language=='en' else 'No hay alertas abiertas en tus registros reales.'
        elif any(w in qfold for w in ('baseline','línea base','linea base','patrón','patron')):
            if baseline['sufficient']:
                vals=', '.join(f"{k.replace('_',' ')}={v:.2f}" for k,v in baseline['values'].items())
                answer=(
                    f"Your personal real-data baseline is calculated from {baseline['sample_count']} records (threshold {int(baseline['relative_deviation_threshold']*100)}%): {vals}. This compares against your own pattern and is not a diagnosis."
                    if language=='en'
                    else f"Tu línea base personal con datos reales se calculó con {baseline['sample_count']} registros (umbral {int(baseline['relative_deviation_threshold']*100)}%): {vals}. Compara tus registros contra tu propio patrón y no es un diagnóstico."
                )
            else:
                answer=(
                    f"Your real-data baseline has {baseline['sample_count']} record(s); at least {baseline['minimum_samples']} are needed per indicator before reliable comparison."
                    if language=='en'
                    else f"Tu línea base real tiene {baseline['sample_count']} registro(s); se necesitan al menos {baseline['minimum_samples']} por indicador para una comparación confiable."
                )
        elif any(w in qfold for w in ('checkin','check-in','chequeo')):
            last_ck=c.execute('SELECT fatigue,mood,note,created_at FROM checkins WHERE astronaut_id=? AND demo=0 ORDER BY id DESC LIMIT 1',(aid,)).fetchone()
            if last_ck:
                note_part=f" ({last_ck['note']})" if last_ck['note'] else ''
                answer=(
                    f"Your latest real daily check-in recorded fatigue={last_ck['fatigue']}/5 and mood={last_ck['mood']}/5{note_part}. This is a wellbeing self-report, not a medical diagnosis."
                    if language=='en'
                    else f"Tu último chequeo diario real registró fatiga={last_ck['fatigue']}/5 y ánimo={last_ck['mood']}/5{note_part}. Es un autorreporte de bienestar, no un diagnóstico médico."
                )
            else:
                answer='No real daily check-ins have been recorded for your profile yet.' if language=='en' else 'Aún no hay chequeos diarios reales registrados en tu perfil.'
        elif any(w in qfold for w in ('sleep','sueño','heart','corazón','fatigue','fatiga','mood','ánimo')):
            if latest:
                fmt=lambda v,u='': f"{v}{u}" if v is not None else ('N/A' if language=='en' else 'n/d')
                summary=f"sleep={fmt(latest['sleep'],' h')}, heart rate={fmt(latest['heart_rate'],' bpm')}, fatigue={fmt(latest['fatigue'],'/5')}, mood={fmt(latest['mood'],'/5')}"
                if language=='en':
                    answer=f"Your latest saved record: {summary}. " + (f"Your individual baseline has {baseline['sample_count']} records." if baseline['sufficient'] else f"There are {baseline['sample_count']} baseline records; at least {baseline['minimum_samples']} are needed. No reliable comparison is available yet.")
                else:
                    answer=f"Tu último registro guardado: sueño={fmt(latest['sleep'],' h')}, frecuencia cardíaca={fmt(latest['heart_rate'],' lpm')}, fatiga={fmt(latest['fatigue'],'/5')}, ánimo={fmt(latest['mood'],'/5')}. " + (f"Tu línea base individual tiene {baseline['sample_count']} registros." if baseline['sufficient'] else f"Hay {baseline['sample_count']} registros; se necesitan al menos {baseline['minimum_samples']}. Aún no hay comparación confiable.")
            else:
                answer='No real monitoring records are available for your profile yet.' if language=='en' else 'Aún no hay registros reales de monitoreo en tu perfil.'
        else:
            answer=('I can review your saved health indicators, baseline, open alerts, check-ins, and verified NASA/CSA scientific references. I cannot diagnose or prescribe. If you feel unsafe or need medical help, contact your care team.' if language=='en' else 'Puedo revisar tus indicadores guardados, línea base, alertas abiertas, chequeos y referencias científicas verificadas de NASA/CSA. No puedo diagnosticar ni prescribir. Si no te sientes a salvo o necesitas atención, contacta al equipo médico.')
        c.execute('INSERT INTO conversations(astronaut_id,role,content,origin,created_at) VALUES(?,?,?,?,?)',(aid,'user',question,'rules_local',stamp))
        c.execute('INSERT INTO conversations(astronaut_id,role,content,origin,created_at) VALUES(?,?,?,?,?)',(aid,'assistant',answer,'rules_local',stamp))
        c.execute('INSERT INTO audit(actor,action,created_at) VALUES(?,?,?)',(user['username'],'lati_chat',stamp))
    return {'reply':answer,'origin':'rules_local','baseline':baseline,'context_source':'authenticated_astronaut_records'}

@router.get('/api/conversation')
def conversation(authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'astronaut')
    with conn() as c: return [dict(x) for x in c.execute('SELECT * FROM conversations WHERE astronaut_id=? ORDER BY id',(u['astronaut_id'],))]
@router.post('/api/admin/users')
def create_user(data:UserCreate,authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'admin')
    clean_username=data.username.strip()
    clean_aid=data.astronaut_id.strip() if data.astronaut_id else None
    if not clean_username:
        raise HTTPException(400,'Username cannot be empty')
    if data.role not in ('astronaut','medic','admin') or (data.role=='astronaut') != bool(clean_aid): raise HTTPException(400,'Invalid role or astronaut identity')
    try:
        with conn() as c:c.execute('INSERT INTO users(username,password_hash,role,astronaut_id) VALUES(?,?,?,?)',(clean_username,hash_password(data.password),data.role,clean_aid))
    except Exception as e: raise HTTPException(409,'User already exists or invalid') from e
    audit(u['username'],'user_create'); return {'ok':True,'username':clean_username}
@router.patch('/api/admin/users/{username}')
def update_user(username:str,data:UserUpdate,authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'admin')
    with conn() as c:
        row=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if not row: raise HTTPException(404,'User not found')
        role=data.role if data.role is not None else row['role']
        astronaut_id=data.astronaut_id if 'astronaut_id' in data.model_fields_set else row['astronaut_id']
        if isinstance(astronaut_id, str):
            astronaut_id = astronaut_id.strip() or None
        if role not in ('astronaut','medic','admin') or (role=='astronaut') != bool(astronaut_id): raise HTTPException(400,'Invalid role or astronaut identity')
        revoke_sessions=False
        if data.active is not None:
            c.execute('UPDATE users SET active=? WHERE username=?',(int(data.active),username))
            revoke_sessions=True
        if data.role is not None:
            c.execute('UPDATE users SET role=? WHERE username=?',(role,username))
            revoke_sessions=True
        if 'astronaut_id' in data.model_fields_set:
            c.execute('UPDATE users SET astronaut_id=? WHERE username=?',(astronaut_id,username))
            revoke_sessions=True
        if data.password:
            c.execute('UPDATE users SET password_hash=? WHERE username=?',(hash_password(data.password),username))
            revoke_sessions=True
        if revoke_sessions:
            c.execute('DELETE FROM sessions WHERE username=?',(username,))
    audit(u['username'],'user_update'); return {'ok':True}
@router.get('/api/admin/astronauts')
def assigned_astronauts(authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'admin','medic')
    with conn() as c:
        q="SELECT DISTINCT astronaut_id FROM assignments WHERE medic_username=?" if u['role']=='medic' else "SELECT astronaut_id FROM users WHERE role='astronaut'"
        args=(u['username'],) if u['role']=='medic' else ()
        return [dict(x) for x in c.execute(q,args)]
@router.get('/api/admin/astronauts/{astronaut_id}')
def astronaut_detail(astronaut_id:str,authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'medic')
    with conn() as c:
        if not c.execute('SELECT 1 FROM assignments WHERE medic_username=? AND astronaut_id=?',(u['username'],astronaut_id)).fetchone(): raise HTTPException(404,'Astronaut not found')
        metrics=[dict(x) for x in c.execute('SELECT * FROM metrics WHERE astronaut_id=? ORDER BY id',(astronaut_id,))]
        demo=bool(metrics and metrics[-1]['demo'])
        baselines={'real':calculate_baseline(c,astronaut_id,False),'demo':calculate_baseline(c,astronaut_id,True)}
        baseline=baselines['demo' if demo else 'real']
        alerts=[dict(x) for x in c.execute('SELECT * FROM alerts WHERE astronaut_id=? ORDER BY id DESC',(astronaut_id,))]
        fups=[dict(x) for x in c.execute('SELECT f.* FROM followups f JOIN alerts a ON a.id=f.alert_id WHERE a.astronaut_id=? ORDER BY f.id DESC',(astronaut_id,))]
    return {'astronaut_id':astronaut_id,'metrics':metrics,'baseline':baseline,'baselines':baselines,'alerts':alerts,'followups':fups}
@router.get('/api/admin/reports/astronauts.csv')
def astronaut_report(authorization:str|None=Header(default=None),astronaut_id:str|None=None,demo:bool|None=None):
    u=auth(authorization); need(u,'medic')
    with conn() as c:
        if astronaut_id and not c.execute('SELECT 1 FROM assignments WHERE medic_username=? AND astronaut_id=?',(u['username'],astronaut_id)).fetchone(): raise HTTPException(404,'Astronaut not found')
        q='SELECT m.* FROM metrics m JOIN assignments a ON a.astronaut_id=m.astronaut_id WHERE a.medic_username=?'
        args=[u['username']]
        if astronaut_id:
            q+=' AND m.astronaut_id=?'; args.append(astronaut_id)
        if demo is not None:
            q+=' AND m.demo=?'; args.append(int(demo))
        q+=' ORDER BY m.id'
        rows=c.execute(q,args).fetchall()
    out=io.StringIO(); w=csv.writer(out); w.writerow(rows[0].keys() if rows else ['id','astronaut_id','recorded_at','source','unit']); [w.writerow(tuple(r)) for r in rows]
    from fastapi.responses import Response
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="astronaut-report.csv"'})
@router.get('/api/admin/audit')
def audit_records(authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'admin')
    with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC')]
