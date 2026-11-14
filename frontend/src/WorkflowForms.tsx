import { useEffect, useRef, useState } from 'react';
import {
  Camera,
  CameraOff,
  Image as ImageIcon,
  LoaderCircle,
  RotateCcw,
  Send,
  Upload,
} from 'lucide-react';
import { useCameraManager } from './useCameraManager';
import { apiUrl } from './api';
import './workflow.css';

type Props = {
  api: (path: string, token: string, init?: RequestInit) => Promise<any>;
  token: string;
  lang: 'en' | 'es';
  role: string;
  onSaved?: () => Promise<void>;
};

const copy = {
  en: {
    real: 'Real record · not demo',
    source: 'Source',
    unit: 'Unit',
    when: 'Recorded at',
    save: 'Save real measurement',
    chat: 'Chat with LÁTI',
    history: 'Conversation history',
    send: 'Send',
    placeholder: 'Ask about your saved indicators, baseline, or an alert…',
    rules: 'Local rules · no external generative model configured',
    thermal: 'Thermal-image review',
    offline: 'External thermal SDK not connected · Manual or camera capture',
    upload: 'Upload image',
    notice:
      'Image review only. A standard camera is not a calibrated thermal sensor; surface images do not estimate core-body temperature or produce medical diagnoses.',
    empty: 'No stored records.',
    uploadFailed: 'Upload failed.',
    saved: 'Saved.',
    view: 'View image',
    openCam: 'Open camera',
    openingCam: 'Opening camera…',
    closeCam: 'Close camera',
    switchCam: 'Switch camera',
    captureSnap: 'Capture snapshot',
    retakeSnap: 'Retake',
    uploadSnap: 'Save captured image',
    camActive: 'Camera active (for reference/UVC image capture only)',
    previewCap: 'Captured image preview — confirm before saving.',
  },
  es: {
    real: 'Registro real · no es demo',
    source: 'Origen',
    unit: 'Unidad',
    when: 'Fecha y hora',
    save: 'Guardar medición real',
    chat: 'Conversar con LÁTI',
    history: 'Historial de conversación',
    send: 'Enviar',
    placeholder: 'Pregunta sobre tus indicadores, línea base o una alerta…',
    rules: 'Reglas locales · no hay modelo generativo externo configurado',
    thermal: 'Revisión de imagen térmica',
    offline: 'Sensor térmico externo no conectado · Carga o captura visual',
    upload: 'Subir imagen',
    notice:
      'Solo revisión visual. Una cámara convencional no equivale a un sensor térmico calibrado; la imagen superficial no estima temperatura corporal central ni genera diagnósticos.',
    empty: 'No hay registros.',
    uploadFailed: 'Error de carga.',
    saved: 'Guardado.',
    view: 'Ver imagen',
    openCam: 'Abrir cámara',
    openingCam: 'Abriendo cámara…',
    closeCam: 'Cerrar cámara',
    switchCam: 'Cambiar cámara',
    captureSnap: 'Capturar imagen',
    retakeSnap: 'Repetir captura',
    uploadSnap: 'Guardar imagen capturada',
    camActive: 'Cámara activa (solo captura visual o UVC)',
    previewCap: 'Vista previa capturada — revisa antes de guardar.',
  },
};

export function ManualMetricForm({ api, token, lang, onSaved }: Props) {
  const t = copy[lang];
  const [busy, B] = useState(false);
  const [error, E] = useState('');
  const [notice, N] = useState('');

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">{t.real}</span>
          <h3>{lang === 'es' ? 'Registrar monitoreo' : 'Record monitoring'}</h3>
        </div>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const formElement = e.currentTarget;
          B(true);
          E('');
          N('');
          const form = new FormData(formElement);
          const value = (key: string) =>
            form.get(key) === '' ? null : Number(form.get(key));
          const data = {
            sleep: value('sleep'),
            heart_rate: value('heart_rate'),
            fatigue: value('fatigue'),
            mood: value('mood'),
            source: String(form.get('source')),
            unit: String(form.get('unit')),
            recorded_at: new Date(String(form.get('recorded_at'))).toISOString(),
          };
          try {
            await api('/metrics', token, {
              method: 'POST',
              body: JSON.stringify(data),
            });
            await onSaved?.();
            N(t.saved);
            formElement.reset();
          } catch (err: any) {
            E(err.message || t.uploadFailed);
          } finally {
            B(false);
          }
        }}
      >
        <label>
          {lang === 'es' ? 'Sueño (horas)' : 'Sleep (hours)'}
          <input name="sleep" type="number" min="0" max="24" step="0.1" />
        </label>
        <label>
          {lang === 'es' ? 'Frecuencia cardíaca (lpm)' : 'Heart rate (bpm)'}
          <input name="heart_rate" type="number" min="20" max="240" step="1" />
        </label>
        <label>
          {lang === 'es' ? 'Fatiga (1–5)' : 'Fatigue (1–5)'}
          <input name="fatigue" type="number" min="1" max="5" step="1" />
        </label>
        <label>
          {lang === 'es' ? 'Estado de ánimo (1–5)' : 'Mood (1–5)'}
          <input name="mood" type="number" min="1" max="5" step="1" />
        </label>
        <label>
          {t.source}
          <input
            name="source"
            required
            maxLength={100}
            defaultValue={lang === 'es' ? 'Autorreporte' : 'Self-report'}
          />
        </label>
        <label>
          {t.unit}
          <input
            name="unit"
            required
            maxLength={40}
            defaultValue={lang === 'es' ? 'mixta por indicador' : 'mixed; per indicator'}
          />
        </label>
        <label>
          {t.when}
          <input
            name="recorded_at"
            type="datetime-local"
            required
            defaultValue={new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
              .toISOString()
              .slice(0, 16)}
          />
        </label>
        {error && <div className="error">{error}</div>}
        {notice && <div className="success">{notice}</div>}
        <button className="primary" disabled={busy}>
          {t.save}
        </button>
      </form>
    </div>
  );
}

export function LatiChat({ api, token, lang }: Props) {
  const t = copy[lang];
  const [rows, R] = useState<any[]>([]);
  const [message, M] = useState('');
  const [busy, B] = useState(false);
  const [error, E] = useState('');

  const load = () =>
    api('/conversation', token)
      .then((d) => R(Array.isArray(d) ? d : d.messages || []))
      .catch((e: any) => E(e.message));

  useEffect(() => {
    load();
  }, [token]);

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">{t.chat}</span>
          <h3>{t.history}</h3>
        </div>
        <span className="tag">{t.rules}</span>
      </div>
      <div className="conversation-list">
        {rows.length ? (
          rows.map((row, i) => (
            <article
              className={`conversation-message ${
                row.role === 'assistant' ? 'assistant' : 'user'
              }`}
              key={row.id || i}
            >
              <b>{row.role === 'assistant' ? 'LÁTI' : lang === 'es' ? 'Tú' : 'You'}</b>
              <p>{row.content}</p>
              <small>
                {row.origin === 'rules_local' ? t.rules : row.origin} ·{' '}
                {row.created_at ? new Date(row.created_at).toLocaleString() : ''}
              </small>
            </article>
          ))
        ) : (
          <p>
            {lang === 'es'
              ? 'Completa tu chequeo o pregunta por tus registros.'
              : 'Complete a check-in or ask about your records.'}
          </p>
        )}
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!message.trim()) return;
          B(true);
          E('');
          try {
            await api('/lati/chat', token, {
              method: 'POST',
              body: JSON.stringify({ message: message.trim(), language: lang }),
            });
            M('');
            await load();
          } catch (err: any) {
            E(err.message);
          } finally {
            B(false);
          }
        }}
      >
        <label>
          {lang === 'es' ? 'Mensaje' : 'Message'}
          <textarea
            value={message}
            onChange={(e) => M(e.target.value)}
            maxLength={1000}
            rows={3}
            placeholder={t.placeholder}
          />
        </label>
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={busy || !message.trim()}>
          <Send size={15} />
          {t.send}
        </button>
      </form>
    </div>
  );
}

export function ThermalCard({ api, token, lang, role }: Props) {
  const t = copy[lang];
  const [items, I] = useState<any[]>([]);
  const [busy, B] = useState(false);
  const [error, E] = useState('');
  const [notice, setNotice] = useState('');
  const [preview, P] = useState('');
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [capturedUrl, setCapturedUrl] = useState('');

  const cam = useCameraManager('thermography', lang);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const load = () =>
    api('/thermography/history', token)
      .then((d) => I(Array.isArray(d) ? d : []))
      .catch((e: any) => E(e.message));

  useEffect(() => {
    load();
  }, [token]);

  useEffect(() => {
    const vid = videoRef.current;
    if (!vid) return;
    if (cam.stream) {
      vid.srcObject = cam.stream;
      vid.play().catch(() => {});
    } else {
      vid.srcObject = null;
    }
  }, [cam.stream]);

  useEffect(() => {
    return () => {
      if (capturedUrl) URL.revokeObjectURL(capturedUrl);
    };
  }, [capturedUrl]);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  const handleCaptureSnapshot = () => {
    const vid = videoRef.current;
    if (!vid || !vid.videoWidth || !vid.videoHeight) return;
    const canvas = document.createElement('canvas');
    canvas.width = vid.videoWidth;
    canvas.height = vid.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(vid, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        if (capturedUrl) URL.revokeObjectURL(capturedUrl);
        setCapturedBlob(blob);
        setCapturedUrl(URL.createObjectURL(blob));
      },
      'image/png',
    );
  };

  const handleUploadSnapshot = async () => {
    if (!capturedBlob) return;
    B(true);
    E('');
    setNotice('');
    try {
      const form = new FormData();
      const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      form.append('file', capturedBlob, `captura-camara-${stamp}.png`);
      await api('/thermography/upload', token, { method: 'POST', body: form });
      if (capturedUrl) URL.revokeObjectURL(capturedUrl);
      setCapturedBlob(null);
      setCapturedUrl('');
      cam.closeCamera();
      setNotice(t.saved);
      await load();
    } catch (err: any) {
      E(err.message || t.uploadFailed);
    } finally {
      B(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">{t.thermal}</span>
          <h3>{t.offline}</h3>
        </div>
        <span className="mode-pill">
          {lang === 'es' ? 'SIN SENSOR TÉRMICO DEDICADO' : 'NO DEDICATED THERMAL SENSOR'}
        </span>
      </div>
      <p>{t.notice}</p>

      {(error || cam.error) && (
        <div className="error-banner" style={{ marginTop: 10 }}>
          <span>{error || cam.error}</span>
          <button
            type="button"
            onClick={() => {
              E('');
              cam.clearError();
            }}
          >
            ×
          </button>
        </div>
      )}
      {notice && <div className="success" style={{ marginTop: 8 }}>{notice}</div>}

      {role === 'astronaut' && (
        <>
          <div className="camera-stage-box" style={{ marginTop: 14 }}>
            <div className="camera-toolbar">
              <span className={`camera-state-label ${cam.isActive ? 'active' : ''}`}>
                {cam.isActive ? <Camera size={14} /> : <CameraOff size={14} />}
                {cam.isActive
                  ? t.camActive
                  : lang === 'es'
                  ? 'Captura opcional desde cámara del dispositivo'
                  : 'Optional device camera capture'}
              </span>
              <div className="camera-controls">
                {!cam.isActive ? (
                  <button
                    type="button"
                    className="secondary"
                    disabled={cam.isRequesting || busy}
                    onClick={() => cam.openCamera()}
                  >
                    {cam.isRequesting ? (
                      <LoaderCircle size={14} className="spin" />
                    ) : (
                      <Camera size={14} />
                    )}
                    {cam.isRequesting ? t.openingCam : t.openCam}
                  </button>
                ) : (
                  <>
                    {cam.devices.length > 1 && (
                      <label className="camera-select-wrap">
                        <span>{t.switchCam}</span>
                        <select
                          aria-label={t.switchCam}
                          value={cam.selectedDeviceId}
                          onChange={(e) => cam.switchCamera(e.target.value)}
                        >
                          {cam.devices.map((d) => (
                            <option key={d.deviceId} value={d.deviceId}>
                              {d.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => cam.closeCamera()}
                    >
                      <CameraOff size={14} />
                      {t.closeCam}
                    </button>
                  </>
                )}
              </div>
            </div>

            {cam.isActive && !capturedUrl && (
              <>
                <div className="camera-viewport">
                  <video ref={videoRef} autoPlay playsInline muted className="camera-video" />
                </div>
                <div className="camera-action-bar">
                  <button type="button" className="primary" onClick={handleCaptureSnapshot}>
                    <Camera size={15} />
                    {t.captureSnap}
                  </button>
                </div>
              </>
            )}

            {capturedUrl && (
              <div className="review-box">
                <p className="review-caption">{t.previewCap}</p>
                <img className="thermal-preview" src={capturedUrl} alt={t.previewCap} />
                <div className="camera-action-bar">
                  <button
                    type="button"
                    className="primary"
                    disabled={busy}
                    onClick={handleUploadSnapshot}
                  >
                    <Upload size={14} />
                    {t.uploadSnap}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={() => {
                      if (capturedUrl) URL.revokeObjectURL(capturedUrl);
                      setCapturedBlob(null);
                      setCapturedUrl('');
                    }}
                  >
                    <RotateCcw size={14} />
                    {t.retakeSnap}
                  </button>
                </div>
              </div>
            )}
          </div>

          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const formElement = e.currentTarget;
              const file = new FormData(formElement).get('file') as File;
              if (!file) return;
              B(true);
              E('');
              setNotice('');
              try {
                const form = new FormData();
                form.append('file', file);
                await api('/thermography/upload', token, { method: 'POST', body: form });
                setNotice(t.saved);
                await load();
                formElement.reset();
              } catch (err: any) {
                E(err.message || t.uploadFailed);
              } finally {
                B(false);
              }
            }}
          >
            <label>
              {lang === 'es' ? 'Subir archivo de imagen (.png, .jpg, .tif)' : 'Thermal image file (.png, .jpg, .tif)'}
              <input name="file" type="file" accept=".png,.jpg,.jpeg,.tif,.tiff" required />
            </label>
            <button className="primary" disabled={busy}>
              <Upload size={15} />
              {t.upload}
            </button>
          </form>
        </>
      )}

      <div className="thermal-list">
        {items.length ? (
          items.map((item) => (
            <button
              className="small-btn"
              key={item.id}
              onClick={async () => {
                try {
                  const r = await fetch(apiUrl(`/api/thermography/image/${item.id}`), {
                    headers: { Authorization: `Bearer ${token}` },
                  });
                  if (!r.ok) throw Error(`HTTP ${r.status}`);
                  const url = URL.createObjectURL(await r.blob());
                  if (preview) URL.revokeObjectURL(preview);
                  P(url);
                } catch (e: any) {
                  E(e.message);
                }
              }}
            >
              <ImageIcon size={14} />
              {item.filename} · {new Date(item.created_at).toLocaleString()} · {item.astronaut_id}
            </button>
          ))
        ) : (
          <p>{t.empty}</p>
        )}
      </div>
      {preview && <img className="thermal-preview" src={preview} alt={t.view} />}
    </div>
  );
}
