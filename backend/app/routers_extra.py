from datetime import datetime, timezone
from pathlib import Path
import csv, io, sys
from typing import Literal
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from .main import conn, auth, need, audit, hash_password, calculate_baseline, create_deviation_alert
from .services.lati_ai import LatiExternalAiError, generate_lati_reply, get_lati_ai_config

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
    input_mode:Literal['text','voice']='text'
    client_message_id:str|None=Field(default=None,min_length=1,max_length=120)

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
def _save_chat_turn(
    c,
    *,
    aid: str,
    username: str,
    question: str,
    answer: str,
    origin: str,
    input_mode: str,
    context_source: str,
    stamp: str,
    model: str | None = None,
    client_message_id: str | None = None,
    audit_action: str = 'lati_chat',
) -> None:
    c.execute(
        'INSERT INTO conversations(astronaut_id,role,content,origin,created_at,input_mode,context_source,model,client_message_id) '
        'VALUES(?,?,?,?,?,?,?,?,?)',
        (aid, 'user', question, origin, stamp, input_mode, context_source, model, client_message_id),
    )
    c.execute(
        'INSERT INTO conversations(astronaut_id,role,content,origin,created_at,input_mode,context_source,model,client_message_id) '
        'VALUES(?,?,?,?,?,?,?,?,?)',
        (aid, 'assistant', answer, origin, stamp, input_mode, context_source, model, client_message_id),
    )
    c.execute('INSERT INTO audit(actor,action,created_at) VALUES(?,?,?)', (username, audit_action, stamp))


@router.post('/api/lati/chat')
def lati_chat(data:ChatMessage,authorization:str|None=Header(default=None)):
    user=auth(authorization); need(user,'astronaut')
    language=data.language.lower()
    if language not in ('en','es'): raise HTTPException(422,'language must be en or es')
    aid=user['astronaut_id']
    if not aid:
        raise HTTPException(400,'Astronaut identity required')
    stamp=datetime.now(timezone.utc).isoformat()
    question=data.message.strip()
    if not question: raise HTTPException(422,'message cannot be blank')
    input_mode=data.input_mode
    clean_client_id=data.client_message_id.strip() if data.client_message_id else None
    qfold=question.casefold()

    with conn() as c:
        baseline=calculate_baseline(c,aid,False)
        if clean_client_id:
            existing=c.execute(
                "SELECT content,origin,context_source,model,input_mode FROM conversations "
                "WHERE astronaut_id=? AND role='assistant' AND client_message_id=?",
                (aid,clean_client_id),
            ).fetchone()
            if existing:
                return {
                    'reply':existing['content'],
                    'origin':existing['origin'],
                    'model':existing['model'],
                    'input_mode':existing['input_mode'] or input_mode,
                    'context_source':existing['context_source'] or 'rules_local',
                    'baseline':baseline,
                    'deduplicated':True,
                    'fallback_used':existing['context_source']=='local_fallback',
                }

        sci = answer_scientific_query(question, language)
        if sci is not None:
            answer = sci['reply']
            _save_chat_turn(
                c,
                aid=aid,
                username=user['username'],
                question=question,
                answer=answer,
                origin='rules_local',
                input_mode=input_mode,
                context_source=sci['context_source'],
                stamp=stamp,
                client_message_id=clean_client_id,
            )
            return {
                'reply': answer,
                'origin': 'rules_local',
                'provider': 'rules_local',
                'model': None,
                'input_mode': input_mode,
                'baseline': baseline,
                'context_source': sci['context_source'],
                'citations': sci['citations'],
                'fallback_used': False,
            }

        latest=c.execute('SELECT * FROM metrics WHERE astronaut_id=? AND demo=0 ORDER BY id DESC LIMIT 1',(aid,)).fetchone()
        personal_answer: str | None = None
        if any(w in qfold for w in ('alert','alerta','warning','aviso')):
            alerts_open=c.execute("SELECT id,reason,status FROM alerts WHERE astronaut_id=? AND demo=0 AND status!='closed' ORDER BY id DESC LIMIT 3",(aid,)).fetchall()
            if alerts_open:
                joined=' | '.join(f"#{row['id']}: {row['reason']}" for row in alerts_open)
                personal_answer=(('Existing system alert: ' if language=='en' else 'Alerta vigente del sistema: ')+joined+' '+('This is not a diagnosis; contact your care team for review.' if language=='en' else 'No es un diagnóstico; contacta al equipo médico para revisión.'))
            else:
                personal_answer='There are no open alerts in your real records.' if language=='en' else 'No hay alertas abiertas en tus registros reales.'
        elif any(w in qfold for w in ('baseline','línea base','linea base','patrón','patron')):
            if baseline['sufficient']:
                vals=', '.join(f"{k.replace('_',' ')}={v:.2f}" for k,v in baseline['values'].items())
                personal_answer=(
                    f"Your personal real-data baseline is calculated from {baseline['sample_count']} records (threshold {int(baseline['relative_deviation_threshold']*100)}%): {vals}. This compares against your own pattern and is not a diagnosis."
                    if language=='en'
                    else f"Tu línea base personal con datos reales se calculó con {baseline['sample_count']} registros (umbral {int(baseline['relative_deviation_threshold']*100)}%): {vals}. Compara tus registros contra tu propio patrón y no es un diagnóstico."
                )
            else:
                personal_answer=(
                    f"Your real-data baseline has {baseline['sample_count']} record(s); at least {baseline['minimum_samples']} are needed per indicator before reliable comparison."
                    if language=='en'
                    else f"Tu línea base real tiene {baseline['sample_count']} registro(s); se necesitan al menos {baseline['minimum_samples']} por indicador para una comparación confiable."
                )
        elif any(w in qfold for w in ('checkin','check-in','chequeo')):
            last_ck=c.execute('SELECT fatigue,mood,note,created_at FROM checkins WHERE astronaut_id=? AND demo=0 ORDER BY id DESC LIMIT 1',(aid,)).fetchone()
            if last_ck:
                note_part=f" ({last_ck['note']})" if last_ck['note'] else ''
                personal_answer=(
                    f"Your latest real daily check-in recorded fatigue={last_ck['fatigue']}/5 and mood={last_ck['mood']}/5{note_part}. This is a wellbeing self-report, not a medical diagnosis."
                    if language=='en'
                    else f"Tu último chequeo diario real registró fatiga={last_ck['fatigue']}/5 y ánimo={last_ck['mood']}/5{note_part}. Es un autorreporte de bienestar, no un diagnóstico médico."
                )
            else:
                personal_answer='No real daily check-ins have been recorded for your profile yet.' if language=='en' else 'Aún no hay chequeos diarios reales registrados en tu perfil.'
        elif any(w in qfold for w in ('sleep','sueño','heart','corazón','fatigue','fatiga','mood','ánimo')):
            if latest:
                fmt=lambda v,u='': f"{v}{u}" if v is not None else ('N/A' if language=='en' else 'n/d')
                summary=f"sleep={fmt(latest['sleep'],' h')}, heart rate={fmt(latest['heart_rate'],' bpm')}, fatigue={fmt(latest['fatigue'],'/5')}, mood={fmt(latest['mood'],'/5')}"
                if language=='en':
                    personal_answer=f"Your latest saved record: {summary}. " + (f"Your individual baseline has {baseline['sample_count']} records." if baseline['sufficient'] else f"There are {baseline['sample_count']} baseline records; at least {baseline['minimum_samples']} are needed. No reliable comparison is available yet.")
                else:
                    personal_answer=f"Tu último registro guardado: sueño={fmt(latest['sleep'],' h')}, frecuencia cardíaca={fmt(latest['heart_rate'],' lpm')}, fatiga={fmt(latest['fatigue'],'/5')}, ánimo={fmt(latest['mood'],'/5')}. " + (f"Tu línea base individual tiene {baseline['sample_count']} registros." if baseline['sufficient'] else f"Hay {baseline['sample_count']} registros; se necesitan al menos {baseline['minimum_samples']}. Aún no hay comparación confiable.")
            else:
                personal_answer='No real monitoring records are available for your profile yet.' if language=='en' else 'Aún no hay registros reales de monitoreo en tu perfil.'

        if personal_answer is not None:
            _save_chat_turn(
                c,
                aid=aid,
                username=user['username'],
                question=question,
                answer=personal_answer,
                origin='rules_local',
                input_mode=input_mode,
                context_source='authenticated_astronaut_records',
                stamp=stamp,
                client_message_id=clean_client_id,
            )
            return {
                'reply':personal_answer,
                'origin':'rules_local',
                'provider':'rules_local',
                'model':None,
                'input_mode':input_mode,
                'baseline':baseline,
                'context_source':'authenticated_astronaut_records',
                'fallback_used':False,
            }

        # Build sanitized conversational context strictly excluding private clinical records/check-ins
        recent_rows=c.execute(
            "SELECT role,content,context_source FROM conversations "
            "WHERE astronaut_id=? ORDER BY id DESC LIMIT 20",
            (aid,),
        ).fetchall()

    safe_history: list[dict[str, str]] = []
    for r in reversed(recent_rows):
        cs = (r['context_source'] or '').strip()
        txt = (r['content'] or '').strip()
        if cs == 'authenticated_astronaut_records':
            continue
        if txt.startswith('[Chequeo diario:') or txt.startswith('[Daily check-in:'):
            continue
        safe_history.append({'role': r['role'], 'content': txt})
    safe_history = safe_history[-10:]

    ai_cfg = get_lati_ai_config()
    if ai_cfg.configured:
        try:
            ai_res = generate_lati_reply(question, language=language, history=safe_history)
            with conn() as c:
                _save_chat_turn(
                    c,
                    aid=aid,
                    username=user['username'],
                    question=question,
                    answer=ai_res['reply'],
                    origin=ai_res['origin'],
                    input_mode=input_mode,
                    context_source='external_generative_model',
                    stamp=stamp,
                    model=ai_res['model'],
                    client_message_id=clean_client_id,
                    audit_action=f"lati_chat:{ai_res['origin']}",
                )
            return {
                'reply': ai_res['reply'],
                'origin': ai_res['origin'],
                'provider': ai_res['provider'],
                'model': ai_res['model'],
                'input_mode': input_mode,
                'baseline': baseline,
                'context_source': 'external_generative_model',
                'fallback_used': False,
                'external_model_configured': True,
            }
        except LatiExternalAiError as exc:
            if language == 'en':
                fallback_reply = (
                    "The external generative model is currently unavailable (controlled local fallback active). "
                    "I can still review your saved health indicators, personal baseline, open alerts, daily check-ins, "
                    "and verified NASA/CSA scientific references. I cannot diagnose or prescribe; if you feel unwell, contact your care team."
                )
            else:
                fallback_reply = (
                    "El modelo generativo externo no está disponible en este momento (respaldo local controlado activo). "
                    "Sigo pudiendo revisar tus indicadores guardados, línea base, alertas abiertas, chequeos diarios "
                    "y referencias científicas NASA/CSA. No puedo diagnosticar ni prescribir; si presentas malestar, contacta al equipo médico."
                )
            with conn() as c:
                _save_chat_turn(
                    c,
                    aid=aid,
                    username=user['username'],
                    question=question,
                    answer=fallback_reply,
                    origin='rules_local',
                    input_mode=input_mode,
                    context_source='local_fallback',
                    stamp=stamp,
                    client_message_id=clean_client_id,
                    audit_action=f"lati_chat_fallback:{exc.code}",
                )
            return {
                'reply': fallback_reply,
                'origin': 'rules_local',
                'provider': 'rules_local',
                'model': None,
                'input_mode': input_mode,
                'baseline': baseline,
                'context_source': 'local_fallback',
                'fallback_used': True,
                'fallback_reason': exc.code,
                'external_error': exc.message,
                'external_model_configured': True,
            }

    answer = (
        'I can review your saved health indicators, baseline, open alerts, check-ins, and verified NASA/CSA scientific references. I cannot diagnose or prescribe. If you feel unsafe or need medical help, contact your care team.'
        if language == 'en'
        else 'Puedo revisar tus indicadores guardados, línea base, alertas abiertas, chequeos y referencias científicas verificadas de NASA/CSA. No puedo diagnosticar ni prescribir. Si no te sientes a salvo o necesitas atención, contacta al equipo médico.'
    )
    with conn() as c:
        _save_chat_turn(
            c,
            aid=aid,
            username=user['username'],
            question=question,
            answer=answer,
            origin='rules_local',
            input_mode=input_mode,
            context_source='local_rules_unconfigured',
            stamp=stamp,
            client_message_id=clean_client_id,
        )
    return {
        'reply': answer,
        'origin': 'rules_local',
        'provider': 'rules_local',
        'model': None,
        'input_mode': input_mode,
        'baseline': baseline,
        'context_source': 'local_rules_unconfigured',
        'fallback_used': False,
        'external_model_configured': False,
    }

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
METRIC_CSV_COLUMNS = (
    'id',
    'astronaut_id',
    'day',
    'recorded_at',
    'sleep',
    'heart_rate',
    'fatigue',
    'mood',
    'source',
    'demo',
    'unit',
)


@router.get('/api/admin/reports/astronauts.csv')
def astronaut_report(authorization:str|None=Header(default=None),astronaut_id:str|None=None,demo:bool|None=None):
    u=auth(authorization); need(u,'medic')
    with conn() as c:
        if astronaut_id and not c.execute('SELECT 1 FROM assignments WHERE medic_username=? AND astronaut_id=?',(u['username'],astronaut_id)).fetchone(): raise HTTPException(404,'Astronaut not found')
        cols_sql = ', '.join(f'm.{col}' for col in METRIC_CSV_COLUMNS)
        q=f'SELECT {cols_sql} FROM metrics m JOIN assignments a ON a.astronaut_id=m.astronaut_id WHERE a.medic_username=?'
        args=[u['username']]
        if astronaut_id:
            q+=' AND m.astronaut_id=?'; args.append(astronaut_id)
        if demo is not None:
            q+=' AND m.demo=?'; args.append(int(demo))
        q+=' ORDER BY m.id'
        rows=c.execute(q,args).fetchall()
    out=io.StringIO(); w=csv.writer(out); w.writerow(METRIC_CSV_COLUMNS); [w.writerow([r[col] for col in METRIC_CSV_COLUMNS]) for r in rows]
    from fastapi.responses import Response
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="astronaut-report.csv"'})
@router.get('/api/admin/audit')
def audit_records(authorization:str|None=Header(default=None)):
    u=auth(authorization); need(u,'admin')
    with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC')]
