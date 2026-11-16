import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Camera,
  CameraOff,
  Image as ImageIcon,
  LoaderCircle,
  Mic,
  MicOff,
  RotateCcw,
  Send,
  Square,
  Upload,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { useCameraManager } from './useCameraManager';
import { apiUrl } from './apiConfig';
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
    placeholder: 'Type or use the microphone to talk with LÁTI…',
    rules: 'Local rules · no external generative model configured',
    externalReady: 'External model configured (pending check)',
    externalConnected: 'External model connected',
    fallbackActive: 'Connection error · Local fallback active',
    voiceAvailableBadge: 'Voice available',
    voicePartialBadge: 'Voice output only',
    voiceUnavailableBadge: 'Voice unavailable',
    micStart: 'Talk',
    micStop: 'Stop voice',
    listening: 'Listening… speak clearly and click Stop when finished.',
    autoVoiceSend: 'Auto-send voice',
    voiceAutoSpeakOn: 'Voice reply: ON',
    voiceAutoSpeakOff: 'Voice reply: OFF',
    stopSpeaking: 'Stop voice',
    listenReply: 'Listen',
    speakingNow: 'LÁTI is speaking…',
    voiceModeLabel: 'Voice',
    textModeLabel: 'Text',
    voiceReadyDraft: 'Recognized by voice (ready to send)',
    voiceUnsupported:
      'This browser does not support Web Speech voice recognition. You can still type your messages normally.',
    micDenied:
      'Microphone permission was denied. Allow microphone access in your browser or type your message.',
    micNoSpeech: 'No clear speech was detected. Try speaking closer to the microphone or type below.',
    micAudioCapture: 'No active microphone was found on this device.',
    micGenericError: 'Voice capture interrupted. You can try again or type your message.',
    ttsUnsupported: 'Voice synthesis is unavailable in this browser; written replies remain visible.',
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
    placeholder: 'Escribe o pulsa el micrófono para hablar con LÁTI…',
    rules: 'Reglas locales · modelo generativo externo sin configurar',
    externalReady: 'Modelo externo configurado (pendiente)',
    externalConnected: 'Modelo externo conectado',
    fallbackActive: 'Error de conexión · Respaldo local activo',
    voiceAvailableBadge: 'Voz disponible',
    voicePartialBadge: 'Solo lectura por voz',
    voiceUnavailableBadge: 'Voz no disponible',
    micStart: 'Hablar',
    micStop: 'Detener voz',
    listening: 'Escuchando… habla con claridad y pulsa Detener al terminar.',
    autoVoiceSend: 'Enviar voz al terminar',
    voiceAutoSpeakOn: 'Voz LÁTI: activa',
    voiceAutoSpeakOff: 'Voz LÁTI: silenciada',
    stopSpeaking: 'Detener voz',
    listenReply: 'Escuchar',
    speakingNow: 'LÁTI está hablando…',
    voiceModeLabel: 'Voz',
    textModeLabel: 'Texto',
    voiceReadyDraft: 'Reconocido por voz (listo para enviar)',
    voiceUnsupported:
      'Este navegador no admite reconocimiento de voz (Web Speech API). Puedes escribir tus mensajes normalmente.',
    micDenied:
      'Permiso de micrófono denegado. Habilita el micrófono en tu navegador o escribe tu mensaje.',
    micNoSpeech: 'No se detectó voz clara. Intenta hablar más cerca del micrófono o escribe abajo.',
    micAudioCapture: 'No se encontró un micrófono activo en este dispositivo.',
    micGenericError: 'Captura de voz interrumpida. Puedes reintentar o escribir tu mensaje.',
    ttsUnsupported: 'La síntesis de voz no está disponible en este navegador; las respuestas escritas se conservan.',
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

function sanitizeTextForSpeech(raw: string): string {
  return String(raw || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/gi, '$1')
    .replace(/https?:\/\/\S+/gi, '')
    .replace(/[*_#>~]+/g, ' ')
    .replace(/\s*\|\s*/g, '. ')
    .replace(/\s+/g, ' ')
    .trim();
}

function getSpeechRecognitionCtor(): any {
  if (typeof window === 'undefined') return null;
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || null;
}

function makeClientMsgId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function LatiChat({ api, token, lang }: Props) {
  const t = copy[lang];
  const [rows, R] = useState<any[]>([]);
  const [latiStatus, setLatiStatus] = useState<any>(null);
  const [message, M] = useState('');
  const [inputMode, setInputMode] = useState<'text' | 'voice'>('text');
  const [busy, B] = useState(false);
  const [error, E] = useState('');
  const [voiceNotice, setVoiceNotice] = useState('');

  const [isListening, setIsListening] = useState(false);
  const [interimText, setInterimText] = useState('');
  const [autoSendVoice, setAutoSendVoice] = useState(true);
  const [autoSpeak, setAutoSpeak] = useState<boolean>(() => {
    try {
      return localStorage.getItem('latira-lati-autospeak') !== 'false';
    } catch {
      return true;
    }
  });
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingKey, setSpeakingKey] = useState<string | null>(null);

  const voiceSupported = Boolean(getSpeechRecognitionCtor());
  const ttsSupported =
    typeof window !== 'undefined' &&
    'speechSynthesis' in window &&
    typeof SpeechSynthesisUtterance !== 'undefined';

  const recognitionRef = useRef<any>(null);
  const capturedTranscriptRef = useRef<string>('');
  const autoSendVoiceRef = useRef<boolean>(autoSendVoice);
  const autoSpeakRef = useRef<boolean>(autoSpeak);
  const sendingRef = useRef<boolean>(false);
  const listRef = useRef<HTMLDivElement | null>(null);
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    autoSendVoiceRef.current = autoSendVoice;
  }, [autoSendVoice]);

  useEffect(() => {
    autoSpeakRef.current = autoSpeak;
    try {
      localStorage.setItem('latira-lati-autospeak', String(autoSpeak));
    } catch {
      // ignore storage failure
    }
  }, [autoSpeak]);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // ignore synthesis cancel errors
      }
    }
    setIsSpeaking(false);
    setSpeakingKey(null);
  }, []);

  const speakText = useCallback(
    (rawText: string, key: string) => {
      if (!ttsSupported) {
        setVoiceNotice(t.ttsUnsupported);
        return;
      }
      const clean = sanitizeTextForSpeech(rawText);
      if (!clean) return;
      try {
        window.speechSynthesis.cancel();
      } catch {
        // ignore
      }
      const utterance = new SpeechSynthesisUtterance(clean);
      const targetPrefix = lang === 'es' ? 'es' : 'en';
      utterance.lang = lang === 'es' ? 'es-ES' : 'en-US';
      utterance.rate = 1.0;
      const availableVoices =
        voicesRef.current.length > 0
          ? voicesRef.current
          : typeof window.speechSynthesis.getVoices === 'function'
            ? window.speechSynthesis.getVoices()
            : [];
      const matchingVoice =
        availableVoices.find((v) => v.lang.toLowerCase().startsWith(targetPrefix) && v.localService) ||
        availableVoices.find((v) => v.lang.toLowerCase().startsWith(targetPrefix));
      if (matchingVoice) {
        utterance.voice = matchingVoice;
      }
      utterance.onstart = () => {
        setIsSpeaking(true);
        setSpeakingKey(key);
      };
      utterance.onend = () => {
        setIsSpeaking(false);
        setSpeakingKey(null);
      };
      utterance.onerror = () => {
        setIsSpeaking(false);
        setSpeakingKey(null);
      };
      setIsSpeaking(true);
      setSpeakingKey(key);
      window.speechSynthesis.speak(utterance);
    },
    [lang, t.ttsUnsupported, ttsSupported],
  );

  useEffect(() => {
    if (!ttsSupported) return;
    const syncVoices = () => {
      try {
        voicesRef.current = window.speechSynthesis.getVoices() || [];
      } catch {
        voicesRef.current = [];
      }
    };
    syncVoices();
    if (typeof window.speechSynthesis.addEventListener === 'function') {
      window.speechSynthesis.addEventListener('voiceschanged', syncVoices);
      return () => {
        window.speechSynthesis.removeEventListener('voiceschanged', syncVoices);
      };
    }
    return undefined;
  }, [ttsSupported]);

  const load = useCallback(async () => {
    try {
      const [convData, statusData] = await Promise.all([
        api('/conversation', token),
        api('/lati/status', token).catch(() => null),
      ]);
      R(Array.isArray(convData) ? convData : convData.messages || []);
      if (statusData) setLatiStatus(statusData);
    } catch (e: any) {
      E(e.message);
    }
  }, [api, token]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [rows.length]);

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
      stopSpeaking();
    };
  }, [stopSpeaking, token]);

  const submitMessage = useCallback(
    async (rawText: string, mode: 'text' | 'voice') => {
      const clean = rawText.trim();
      if (!clean || sendingRef.current) return;
      sendingRef.current = true;
      B(true);
      E('');
      try {
        const res = await api('/lati/chat', token, {
          method: 'POST',
          body: JSON.stringify({
            message: clean,
            language: lang,
            input_mode: mode,
            client_message_id: makeClientMsgId(),
          }),
        });
        M('');
        setInputMode('text');
        setInterimText('');
        if (res?.fallback_used) {
          setVoiceNotice(
            lang === 'es'
              ? `${t.fallbackActive}${res.fallback_reason ? ` (${res.fallback_reason})` : ''}.`
              : `${t.fallbackActive}${res.fallback_reason ? ` (${res.fallback_reason})` : ''}.`,
          );
        }
        await load();
        if (autoSpeakRef.current && ttsSupported && res?.reply) {
          speakText(res.reply, 'latest');
        }
      } catch (err: any) {
        E(err.message);
        if (mode === 'voice' && !message.trim()) {
          M(clean);
          setInputMode('voice');
        }
      } finally {
        sendingRef.current = false;
        B(false);
      }
    },
    [api, lang, load, message, speakText, t.fallbackActive, token, ttsSupported],
  );

  const stopListening = useCallback(() => {
    const rec = recognitionRef.current;
    if (!rec) {
      setIsListening(false);
      return;
    }
    try {
      rec.stop();
    } catch {
      setIsListening(false);
    }
  }, []);

  const startListening = useCallback(() => {
    E('');
    setVoiceNotice('');
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setVoiceNotice(t.voiceUnsupported);
      return;
    }
    if (isListening) {
      stopListening();
      return;
    }
    stopSpeaking();

    try {
      const rec = new Ctor();
      recognitionRef.current = rec;
      capturedTranscriptRef.current = '';
      setInterimText('');
      rec.lang = lang === 'es' ? 'es-ES' : 'en-US';
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;

      rec.onstart = () => {
        setIsListening(true);
      };

      rec.onresult = (event: any) => {
        let finalStr = '';
        let interimStr = '';
        const results = event?.results;
        if (results) {
          for (let i = 0; i < results.length; i += 1) {
            const seg = results[i]?.[0]?.transcript || '';
            if (results[i]?.isFinal) {
              finalStr += `${seg} `;
            } else {
              interimStr += `${seg} `;
            }
          }
        }
        const combined = `${finalStr}${interimStr}`.trim();
        capturedTranscriptRef.current = combined;
        setInterimText(combined);
      };

      rec.onerror = (event: any) => {
        const code = String(event?.error || '');
        if (code === 'not-allowed' || code === 'service-not-allowed') {
          setVoiceNotice(t.micDenied);
        } else if (code === 'no-speech') {
          setVoiceNotice(t.micNoSpeech);
        } else if (code === 'audio-capture') {
          setVoiceNotice(t.micAudioCapture);
        } else if (code !== 'aborted') {
          setVoiceNotice(t.micGenericError);
        }
        setIsListening(false);
      };

      rec.onend = () => {
        recognitionRef.current = null;
        setIsListening(false);
        const recognized = capturedTranscriptRef.current.trim();
        capturedTranscriptRef.current = '';
        setInterimText('');
        if (recognized) {
          if (autoSendVoiceRef.current) {
            void submitMessage(recognized, 'voice');
          } else {
            M((prev) => (prev.trim() ? `${prev.trim()} ${recognized}` : recognized));
            setInputMode('voice');
          }
        }
      };

      rec.start();
    } catch {
      recognitionRef.current = null;
      setIsListening(false);
      setVoiceNotice(t.micGenericError);
    }
  }, [
    isListening,
    lang,
    stopListening,
    stopSpeaking,
    submitMessage,
    t.micAudioCapture,
    t.micDenied,
    t.micGenericError,
    t.micNoSpeech,
    t.voiceUnsupported,
  ]);

  const formatOrigin = (row: any) => {
    if (row.context_source === 'local_fallback') {
      return lang === 'es' ? 'Respaldo local' : 'Local fallback';
    }
    if (row.origin === 'external_gemini') {
      return `Gemini${row.model ? ` (${row.model})` : ''}`;
    }
    if (row.origin === 'external_llm') {
      return `${lang === 'es' ? 'Modelo externo' : 'External model'}${row.model ? ` (${row.model})` : ''}`;
    }
    if (row.origin === 'rules_local') {
      return lang === 'es' ? 'Reglas locales' : 'Local rules';
    }
    return row.origin || 'rules_local';
  };

  const renderStatusTag = () => {
    if (!latiStatus || !latiStatus.configured) {
      return <span className="tag">{t.rules}</span>;
    }
    if (latiStatus.verification_status === 'connected') {
      return (
        <span className="tag lati-tag-connected">
          {t.externalConnected} · {latiStatus.model || latiStatus.provider}
        </span>
      );
    }
    if (latiStatus.last_error_code || latiStatus.status === 'connection_error') {
      return (
        <span className="tag lati-tag-warn">
          {t.fallbackActive} ({latiStatus.last_error_code || 'error'})
        </span>
      );
    }
    return (
      <span className="tag lati-tag-ready">
        {t.externalReady} · {latiStatus.model || latiStatus.provider}
      </span>
    );
  };

  const renderVoiceTag = () => {
    if (voiceSupported && ttsSupported) {
      return <span className="tag lati-tag-ready">{t.voiceAvailableBadge}</span>;
    }
    if (ttsSupported || voiceSupported) {
      return <span className="tag">{t.voicePartialBadge}</span>;
    }
    return <span className="tag lati-tag-warn">{t.voiceUnavailableBadge}</span>;
  };

  return (
    <div className="panel">
      <div className="panel-head lati-head">
        <div>
          <span className="eyebrow">{t.chat}</span>
          <h3>{t.history}</h3>
        </div>
        <div className="lati-head-actions">
          {renderStatusTag()}
          {renderVoiceTag()}
          <button
            type="button"
            className={`small-btn ${autoSpeak ? 'lati-voice-active' : ''}`}
            disabled={!ttsSupported}
            onClick={() => {
              if (autoSpeak) stopSpeaking();
              setAutoSpeak((v) => !v);
            }}
            title={ttsSupported ? undefined : t.ttsUnsupported}
          >
            {autoSpeak ? <Volume2 size={13} /> : <VolumeX size={13} />}
            {autoSpeak ? t.voiceAutoSpeakOn : t.voiceAutoSpeakOff}
          </button>
          {isSpeaking && (
            <button type="button" className="small-btn lati-stop-speak" onClick={stopSpeaking}>
              <Square size={12} />
              {t.stopSpeaking}
            </button>
          )}
        </div>
      </div>

      {isSpeaking && (
        <div className="lati-speaking-strip" role="status" aria-live="polite">
          <Volume2 size={14} />
          <span>{t.speakingNow}</span>
        </div>
      )}

      <div className="conversation-list" ref={listRef}>
        {rows.length ? (
          rows.map((row, i) => {
            const msgKey = String(row.id ?? i);
            const isAssistant = row.role === 'assistant';
            const rowIsSpeaking = isSpeaking && (speakingKey === msgKey || (speakingKey === 'latest' && i === rows.length - 1));
            return (
              <article
                className={`conversation-message ${isAssistant ? 'assistant' : 'user'}`}
                key={msgKey}
              >
                <div className="conversation-msg-head">
                  <b>{isAssistant ? 'LÁTI' : lang === 'es' ? 'Tú' : 'You'}</b>
                  {!isAssistant && (
                    <span className={`lati-mode-badge ${row.input_mode === 'voice' ? 'voice' : 'text'}`}>
                      {row.input_mode === 'voice' ? <Mic size={11} /> : null}
                      {row.input_mode === 'voice' ? t.voiceModeLabel : t.textModeLabel}
                    </span>
                  )}
                  {isAssistant && ttsSupported && (
                    <button
                      type="button"
                      className="lati-msg-speak-btn"
                      onClick={() => (rowIsSpeaking ? stopSpeaking() : speakText(row.content, msgKey))}
                      aria-label={rowIsSpeaking ? t.stopSpeaking : t.listenReply}
                    >
                      {rowIsSpeaking ? <Square size={11} /> : <Volume2 size={12} />}
                      {rowIsSpeaking ? t.stopSpeaking : t.listenReply}
                    </button>
                  )}
                </div>
                <p>{row.content}</p>
                <small>
                  {formatOrigin(row)} ·{' '}
                  {row.created_at ? new Date(row.created_at).toLocaleString() : ''}
                </small>
              </article>
            );
          })
        ) : (
          <p>
            {lang === 'es'
              ? 'Completa tu chequeo o habla/pregunta a LÁTI sobre tu bienestar o tus registros.'
              : 'Complete a check-in or talk/ask LÁTI about your wellbeing or saved records.'}
          </p>
        )}
      </div>

      {isListening && (
        <div className="lati-listening-banner" role="status" aria-live="polite">
          <span className="lati-pulse-dot" />
          <div className="lati-listening-copy">
            <strong>{t.listening}</strong>
            {interimText && <p>{interimText}</p>}
          </div>
          <button type="button" className="danger-btn" onClick={stopListening}>
            <Square size={12} />
            {t.micStop}
          </button>
        </div>
      )}

      {voiceNotice && (
        <div className="nasa-notice lati-voice-notice" role="status">
          <span>{voiceNotice}</span>
          <button type="button" onClick={() => setVoiceNotice('')}>
            ×
          </button>
        </div>
      )}

      <form
        onSubmit={async (e) => {
          e.preventDefault();
          await submitMessage(message, inputMode);
        }}
      >
        <label>
          <span>
            {lang === 'es' ? 'Mensaje' : 'Message'}
            {inputMode === 'voice' && message.trim() ? ` · ${t.voiceReadyDraft}` : ''}
          </span>
          <textarea
            value={message}
            onChange={(e) => {
              M(e.target.value);
              if (!e.target.value.trim()) {
                setInputMode('text');
              }
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (message.trim() && !busy) {
                  void submitMessage(message, inputMode);
                }
              }
            }}
            maxLength={1000}
            rows={3}
            placeholder={t.placeholder}
          />
        </label>
        {error && <div className="error">{error}</div>}
        <div className="lati-composer-bar">
          <button
            type="button"
            className={isListening ? 'danger-btn' : 'secondary lati-mic-btn'}
            disabled={busy}
            onClick={isListening ? stopListening : startListening}
            aria-label={isListening ? t.micStop : t.micStart}
            aria-pressed={isListening}
          >
            {isListening ? <MicOff size={15} /> : <Mic size={15} />}
            {isListening ? t.micStop : t.micStart}
          </button>

          <button className="primary" disabled={busy || !message.trim() || isListening}>
            {busy ? <LoaderCircle size={15} className="spin" /> : <Send size={15} />}
            {t.send}
          </button>

          {voiceSupported && (
            <label className="lati-autosend-check">
              <input
                type="checkbox"
                checked={autoSendVoice}
                onChange={(e) => setAutoSendVoice(e.target.checked)}
              />
              <span>{t.autoVoiceSend}</span>
            </label>
          )}
        </div>
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
                  const r = await fetch(apiUrl(`/thermography/image/${item.id}`), {
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
