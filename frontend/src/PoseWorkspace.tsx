import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Camera,
  CameraOff,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Eye,
  FileVideo,
  Info,
  LoaderCircle,
  Play,
  RefreshCw,
  RotateCcw,
  Square,
  Trash2,
  Upload,
  Video,
} from 'lucide-react';
import { useCameraManager } from './useCameraManager';
import { apiUrl } from './api';

type Props = {
  api: (path: string, token: string, init?: RequestInit) => Promise<any>;
  token: string;
  lang: 'en' | 'es';
  role: string;
  user: any;
  onRefresh?: () => Promise<void>;
};

type PoseMode = 'live' | 'recording' | 'upload';

const ALLOWED_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.webm'];
const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

const copy = {
  en: {
    title: 'Posture and movement analysis (YOLO Pose)',
    subtitle:
      'Use your live camera, record a short movement clip, or upload an existing video. Results are summarized in plain language for medical review.',
    modeLive: 'Live camera',
    modeRecord: 'Record video',
    modeUpload: 'Upload video',
    openCamera: 'Open camera',
    openingCamera: 'Opening camera…',
    closeCamera: 'Close camera',
    switchCamera: 'Switch camera',
    cameraActive: 'Camera active',
    cameraIdle: 'Camera is closed. Open the camera explicitly when you are ready.',
    privacyNote: 'Camera never turns on or records in the background without your explicit action.',
    startLive: 'Start live pose analysis',
    stopLive: 'Stop & finish analysis',
    liveRunning: 'Analyzing live frames with YOLO Pose…',
    liveFrames: 'Frames analyzed',
    liveDetected: 'Frames with person detected',
    liveConf: 'Current detection confidence',
    startRecord: 'Start recording',
    stopRecord: 'Stop recording',
    recordingNow: 'Recording',
    retakeRecord: 'Retake recording',
    processRecorded: 'Process recorded video',
    reviewRecorded: 'Review your recorded video before processing.',
    selectVideo: 'Choose a video file (.mp4, .mov, .avi, .mkv, .webm · max 100 MiB)',
    previewSelected: 'Video preview before processing',
    processVideo: 'Analyze video with YOLO Pose',
    cancelAction: 'Cancel',
    uploading: 'Uploading video…',
    processingYolo: 'Processing frames with YOLO Pose model…',
    invalidFormat: 'Unsupported video format. Allowed: MP4, MOV, AVI, MKV, WEBM.',
    tooLarge: 'Selected video exceeds the 100 MiB size limit.',
    emptyFile: 'Selected video file is empty.',
    summaryTitle: 'General summary',
    observationsTitle: 'Interpreted observations',
    visualTitle: 'Visual indicators',
    limitationsTitle: 'Limitations & guidance',
    techTitle: 'Technical analysis details (audit & debugging)',
    humanReviewBadge: 'Human medical review recommended',
    nonDiagnosticTag: 'Geometric movement patterns · Not a medical diagnosis',
    confidenceLabel: 'Detection confidence',
    keyframesTitle: 'Representative keyframes',
    evolutionTitle: 'Posture evolution during sequence',
    annotatedVideoTitle: 'Annotated video with detected keypoints',
    historyTitle: 'Analysis history',
    historyEmpty: 'No movement analyses saved yet.',
    deleteAnalysis: 'Delete',
    modelReady: 'YOLO Pose model ready',
    modelUnavailable: 'YOLO Pose backend dependencies or weights are not configured',
    noFramesCaptured: 'No frames were processed yet. Keep a person visible in front of the camera for a couple of seconds before stopping.',
    recorderUnsupported: 'Video recording is not supported in this browser. Try Live camera or Upload video.',
    viewDetails: 'View report',
    hideDetails: 'Hide report',
  },
  es: {
    title: 'Análisis de postura y movimiento (YOLO Pose)',
    subtitle:
      'Utiliza la cámara en vivo, graba un clip breve o sube un video existente. Los resultados se presentan en español sencillo para el equipo médico.',
    modeLive: 'Cámara en vivo',
    modeRecord: 'Grabar desde cámara',
    modeUpload: 'Subir video',
    openCamera: 'Abrir cámara',
    openingCamera: 'Abriendo cámara…',
    closeCamera: 'Cerrar cámara',
    switchCamera: 'Cambiar cámara',
    cameraActive: 'Cámara activa',
    cameraIdle: 'La cámara está cerrada. Ábrela explícitamente cuando estés listo.',
    privacyNote: 'La cámara nunca se activa ni graba en segundo plano sin tu acción explícita.',
    startLive: 'Iniciar análisis en vivo',
    stopLive: 'Detener y finalizar análisis',
    liveRunning: 'Analizando fotogramas en vivo con YOLO Pose…',
    liveFrames: 'Fotogramas analizados',
    liveDetected: 'Con detección corporal',
    liveConf: 'Confianza actual',
    startRecord: 'Iniciar grabación',
    stopRecord: 'Detener grabación',
    recordingNow: 'Grabando',
    retakeRecord: 'Repetir grabación',
    processRecorded: 'Procesar video grabado',
    reviewRecorded: 'Revisa la grabación antes de enviarla al procesamiento.',
    selectVideo: 'Seleccionar archivo de video (.mp4, .mov, .avi, .mkv, .webm · máx. 100 MiB)',
    previewSelected: 'Vista previa antes de procesar',
    processVideo: 'Analizar video con YOLO Pose',
    cancelAction: 'Cancelar',
    uploading: 'Subiendo video…',
    processingYolo: 'Procesando fotogramas con el modelo YOLO Pose…',
    invalidFormat: 'Formato de video no permitido. Usa MP4, MOV, AVI, MKV o WEBM.',
    tooLarge: 'El video seleccionado supera el límite permitido de 100 MiB.',
    emptyFile: 'El archivo de video está vacío.',
    summaryTitle: 'Resumen general',
    observationsTitle: 'Observaciones interpretadas',
    visualTitle: 'Indicadores visuales',
    limitationsTitle: 'Limitaciones y advertencias',
    techTitle: 'Detalles técnicos del análisis (auditoría y depuración)',
    humanReviewBadge: 'Requiere revisión por equipo médico',
    nonDiagnosticTag: 'Patrones geométricos de movimiento · No es diagnóstico médico',
    confidenceLabel: 'Confianza de detección',
    keyframesTitle: 'Fotogramas representativos',
    evolutionTitle: 'Evolución de la postura durante el video',
    annotatedVideoTitle: 'Video anotado con puntos clave',
    historyTitle: 'Historial de análisis',
    historyEmpty: 'Aún no hay análisis de movimiento guardados.',
    deleteAnalysis: 'Eliminar',
    modelReady: 'Modelo YOLO Pose disponible',
    modelUnavailable: 'Dependencias o pesos de YOLO Pose no configurados en el servidor',
    noFramesCaptured: 'No se alcanzaron a procesar fotogramas. Mantén a la persona visible unos segundos antes de detener.',
    recorderUnsupported: 'Este navegador no admite grabación directa. Puedes usar Cámara en vivo o Subir video.',
    viewDetails: 'Ver informe',
    hideDetails: 'Ocultar informe',
  },
};

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function pickSupportedRecorderMime(): string {
  if (typeof MediaRecorder === 'undefined') return '';
  const candidates = [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
    'video/mp4',
  ];
  for (const mime of candidates) {
    if (MediaRecorder.isTypeSupported(mime)) return mime;
  }
  return '';
}

function drawSkeletonOverlay(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  frameData: any | null,
) {
  const width = video.videoWidth || 640;
  const height = video.videoHeight || 480;
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.clearRect(0, 0, width, height);
  if (!frameData || !Array.isArray(frameData.persons)) return;

  const edges: [number, number][] = frameData.skeleton || [];
  for (const person of frameData.persons) {
    const kps = person.keypoints || [];
    ctx.lineWidth = 3;
    ctx.strokeStyle = 'rgba(104, 217, 189, 0.9)';
    for (const [i, j] of edges) {
      const a = kps[i];
      const b = kps[j];
      if (!a || !b) continue;
      if (a.confidence < 0.3 || b.confidence < 0.3) continue;
      ctx.beginPath();
      ctx.moveTo(a.nx * width, a.ny * height);
      ctx.lineTo(b.nx * width, b.ny * height);
      ctx.stroke();
    }
    for (const kp of kps) {
      if (kp.confidence < 0.3) continue;
      ctx.beginPath();
      ctx.arc(kp.nx * width, kp.ny * height, 5, 0, Math.PI * 2);
      ctx.fillStyle = kp.confidence >= 0.65 ? '#66d4b2' : '#eab86a';
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = '#08111e';
      ctx.stroke();
    }
  }
}

function captureSnapshotWithOverlay(
  video: HTMLVideoElement,
  overlay: HTMLCanvasElement | null,
): string | null {
  const vw = video.videoWidth || 0;
  const vh = video.videoHeight || 0;
  if (!vw || !vh) return null;
  const targetW = Math.min(400, vw);
  const targetH = Math.max(1, Math.round((vh / vw) * targetW));
  const off = document.createElement('canvas');
  off.width = targetW;
  off.height = targetH;
  const ctx = off.getContext('2d');
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, targetW, targetH);
  if (overlay && overlay.width > 0 && overlay.height > 0) {
    ctx.drawImage(overlay, 0, 0, targetW, targetH);
  }
  return off.toDataURL('image/jpeg', 0.72);
}

export default function PoseWorkspace({ api, token, lang, onRefresh }: Props) {
  const t = copy[lang];
  const [mode, setMode] = useState<PoseMode>('live');
  const [poseStatus, setPoseStatus] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [activeResult, setActiveResult] = useState<any>(null);
  const [expandedHistoryId, setExpandedHistoryId] = useState<string | null>(null);
  const [error, setError] = useState('');

  // Camera manager (exclusive device lease shared with Thermography)
  const cam = useCameraManager('pose', lang);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null);

  // Live analysis state
  const [liveActive, setLiveActive] = useState(false);
  const liveActiveRef = useRef(false);
  const [liveFrameCount, setLiveFrameCount] = useState(0);
  const [liveDetectedCount, setLiveDetectedCount] = useState(0);
  const [liveLastFrame, setLiveLastFrame] = useState<any>(null);
  const liveSamplesRef = useRef<any[]>([]);
  const liveSnapshotsRef = useRef<any[]>([]);
  const liveStartMonoRef = useRef<number>(0);

  // Recording state
  const [recording, setRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordedUrl, setRecordedUrl] = useState('');
  const [recordedExt, setRecordedExt] = useState('.webm');
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFileUrl, setSelectedFileUrl] = useState('');
  const [processingState, setProcessingState] = useState<'idle' | 'uploading' | 'analyzing'>('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const loadWorkspaceData = useCallback(async () => {
    try {
      const [st, hist] = await Promise.all([
        api('/pose/status', token).catch(() => null),
        api('/pose/history', token).catch(() => []),
      ]);
      if (st) setPoseStatus(st);
      setHistory(Array.isArray(hist) ? hist : hist?.items || []);
    } catch (e: any) {
      setError(e.message || 'Failed to load Pose workspace');
    }
  }, [api, token]);

  useEffect(() => {
    loadWorkspaceData();
  }, [loadWorkspaceData]);

  // Bind MediaStream to <video> whenever stream or mode changes
  useEffect(() => {
    const vid = videoRef.current;
    if (!vid) return;
    if (cam.stream && (mode === 'live' || mode === 'recording')) {
      vid.srcObject = cam.stream;
      vid.play().catch(() => {});
    } else {
      vid.srcObject = null;
    }
  }, [cam.stream, mode]);

  // Clear overlay canvas when camera closes or live analysis stops
  useEffect(() => {
    if (!cam.isActive || !liveActive) {
      const canvas = overlayCanvasRef.current;
      const ctx = canvas?.getContext('2d');
      if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }, [cam.isActive, liveActive]);

  // Clean up object URLs on change/unmount
  useEffect(() => {
    return () => {
      if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    };
  }, [recordedUrl]);

  useEffect(() => {
    return () => {
      if (selectedFileUrl) URL.revokeObjectURL(selectedFileUrl);
    };
  }, [selectedFileUrl]);

  // Stop live analysis or recording cleanly if camera closes or component unmounts
  useEffect(() => {
    if (!cam.isActive) {
      liveActiveRef.current = false;
      setLiveActive(false);
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        try {
          recorderRef.current.stop();
        } catch {
          // Ignore
        }
      }
      setRecording(false);
    }
  }, [cam.isActive]);

  useEffect(() => {
    return () => {
      liveActiveRef.current = false;
      abortControllerRef.current?.abort();
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        try {
          recorderRef.current.stop();
        } catch {
          // Ignore
        }
      }
    };
  }, []);

  // Recording timer
  useEffect(() => {
    if (!recording) return;
    const id = window.setInterval(() => {
      setRecordSeconds((s) => s + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, [recording]);

  // Switch modes cleanly without breaking camera if both are camera modes
  const handleModeSwitch = (nextMode: PoseMode) => {
    if (liveActiveRef.current) return;
    if (recording) return;
    setError('');
    setMode(nextMode);
    if (nextMode === 'upload' && cam.isActive) {
      cam.closeCamera();
    }
  };

  // Sequential live analysis loop (prevents request pileup / freezing)
  const runLiveLoop = useCallback(async () => {
    while (liveActiveRef.current) {
      const video = videoRef.current;
      if (!video || video.readyState < 2 || !video.videoWidth) {
        await new Promise((r) => setTimeout(r, 150));
        continue;
      }

      const vw = video.videoWidth;
      const vh = video.videoHeight;
      const targetW = Math.min(640, vw);
      const targetH = Math.max(1, Math.round((vh / vw) * targetW));

      let cap = captureCanvasRef.current;
      if (!cap) {
        cap = document.createElement('canvas');
        captureCanvasRef.current = cap;
      }
      cap.width = targetW;
      cap.height = targetH;
      const ctx = cap.getContext('2d');
      if (!ctx) break;
      ctx.drawImage(video, 0, 0, targetW, targetH);

      const blob: Blob | null = await new Promise((resolve) =>
        cap!.toBlob((b) => resolve(b), 'image/jpeg', 0.78),
      );
      if (!blob || !liveActiveRef.current) break;

      try {
        const form = new FormData();
        form.append('file', blob, 'frame.jpg');
        const res = await fetch(apiUrl('/api/pose/frame'), {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.detail || `HTTP ${res.status}`);
        }

        if (!liveActiveRef.current) break;
        const idx = liveSamplesRef.current.length + 1;
        const elapsed = Number(((performance.now() - liveStartMonoRef.current) / 1000).toFixed(2));
        const sample = {
          frame: idx,
          timestamp_s: elapsed,
          visible_keypoints: data.visible_keypoints ?? 0,
          mean_confidence: data.mean_confidence ?? null,
          trunk_inclination_deg: data.trunk_inclination_deg ?? null,
          shoulder_tilt_deg: data.shoulder_tilt_deg ?? null,
          hip_tilt_deg: data.hip_tilt_deg ?? null,
          person_count: data.person_count ?? 0,
          regions: data.regions ?? null,
        };
        liveSamplesRef.current.push(sample);
        setLiveFrameCount(idx);
        if ((data.visible_keypoints ?? 0) > 0) {
          setLiveDetectedCount((c) => c + 1);
        }
        setLiveLastFrame(data);

        if (overlayCanvasRef.current && videoRef.current) {
          drawSkeletonOverlay(overlayCanvasRef.current, videoRef.current, data);
          if (
            (data.visible_keypoints ?? 0) >= 4 &&
            (liveSnapshotsRef.current.length === 0 || idx % 8 === 0) &&
            liveSnapshotsRef.current.length < 3
          ) {
            const snapUrl = captureSnapshotWithOverlay(videoRef.current, overlayCanvasRef.current);
            if (snapUrl) {
              liveSnapshotsRef.current.push({
                frame: idx,
                timestamp_s: elapsed,
                trunk_inclination_deg: data.trunk_inclination_deg ?? null,
                confidence_percent: Math.round((data.mean_confidence ?? 0) * 100),
                image_data_url: snapUrl,
              });
            }
          }
        }
      } catch (e: any) {
        liveActiveRef.current = false;
        setLiveActive(false);
        setError(e.message || 'Live pose inference failed');
        break;
      }

      await new Promise((r) => setTimeout(r, 220));
    }
  }, [token]);

  const handleStartLive = () => {
    if (!cam.isActive) return;
    setError('');
    liveSamplesRef.current = [];
    liveSnapshotsRef.current = [];
    liveStartMonoRef.current = performance.now();
    setLiveFrameCount(0);
    setLiveDetectedCount(0);
    setLiveLastFrame(null);
    liveActiveRef.current = true;
    setLiveActive(true);
    runLiveLoop();
  };

  const handleStopLive = async () => {
    liveActiveRef.current = false;
    setLiveActive(false);
    const samples = [...liveSamplesRef.current];
    const snapshots = [...liveSnapshotsRef.current];
    const duration = Number(((performance.now() - liveStartMonoRef.current) / 1000).toFixed(2));
    if (samples.length === 0) {
      setError(t.noFramesCaptured);
      return;
    }
    setProcessingState('analyzing');
    setError('');
    try {
      const completed = await api('/pose/live/complete', token, {
        method: 'POST',
        body: JSON.stringify({
          model: liveLastFrame?.model || poseStatus?.model || 'yolo11n-pose.pt',
          duration_seconds: duration,
          input_name: lang === 'es' ? 'Sesión de cámara en vivo' : 'Live camera session',
          frames: samples,
          representative_frames: snapshots,
        }),
      });
      setActiveResult(completed);
      await loadWorkspaceData();
      await onRefresh?.();
    } catch (e: any) {
      setError(e.message || 'Failed to finalize live session');
    } finally {
      setProcessingState('idle');
    }
  };

  // Video recording handlers
  const handleStartRecording = () => {
    if (!cam.stream) return;
    if (typeof MediaRecorder === 'undefined') {
      setError(t.recorderUnsupported);
      return;
    }
    setError('');
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    setRecordedBlob(null);
    setRecordedUrl('');
    setRecordSeconds(0);
    chunksRef.current = [];

    const mimeType = pickSupportedRecorderMime();
    const ext = mimeType.includes('mp4') ? '.mp4' : '.webm';
    setRecordedExt(ext);
    try {
      const recorder = mimeType
        ? new MediaRecorder(cam.stream, { mimeType })
        : new MediaRecorder(cam.stream);
      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) {
          chunksRef.current.push(ev.data);
        }
      };
      recorder.onstop = () => {
        const type = recorder.mimeType || mimeType || 'video/webm';
        const blob = new Blob(chunksRef.current, { type });
        if (blob.size > 0) {
          setRecordedBlob(blob);
          setRecordedUrl(URL.createObjectURL(blob));
        }
        setRecording(false);
      };
      recorderRef.current = recorder;
      recorder.start(250);
      setRecording(true);
    } catch (e: any) {
      setError(e.message || t.recorderUnsupported);
      setRecording(false);
    }
  };

  const handleStopRecording = () => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop();
    }
  };

  const handleDiscardRecording = () => {
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    setRecordedBlob(null);
    setRecordedUrl('');
    setRecordSeconds(0);
  };

  // Shared video upload & processing pipeline (used by both Recording and Upload modes)
  const submitVideoFile = async (file: File, sourceMode: 'recording' | 'upload') => {
    setError('');
    setProcessingState('uploading');
    setUploadProgress(0);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const payload = await new Promise<any>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', apiUrl('/api/pose/process'));
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);

        xhr.upload.onprogress = (ev) => {
          if (ev.lengthComputable) {
            const pct = Math.round((ev.loaded / ev.total) * 100);
            setUploadProgress(pct);
            if (pct >= 100) setProcessingState('analyzing');
          }
        };
        xhr.onload = () => {
          let parsed: any = {};
          try {
            parsed = JSON.parse(xhr.responseText || '{}');
          } catch {
            parsed = {};
          }
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(parsed);
          } else {
            reject(new Error(parsed.detail || `HTTP ${xhr.status}`));
          }
        };
        xhr.onerror = () => reject(new Error(lang === 'es' ? 'Error de red al subir el video.' : 'Network error uploading video.'));
        xhr.onabort = () => reject(new Error(lang === 'es' ? 'Procesamiento cancelado por el usuario.' : 'Processing canceled by user.'));

        controller.signal.addEventListener('abort', () => xhr.abort());
        const form = new FormData();
        form.append('file', file, file.name);
        form.append('source_mode', sourceMode);
        xhr.send(form);
      });

      setActiveResult(payload);
      if (sourceMode === 'recording') {
        handleDiscardRecording();
      } else {
        setSelectedFile(null);
        if (selectedFileUrl) URL.revokeObjectURL(selectedFileUrl);
        setSelectedFileUrl('');
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
      await loadWorkspaceData();
      await onRefresh?.();
    } catch (e: any) {
      setError(e.message || 'Video processing failed');
    } finally {
      setProcessingState('idle');
      setUploadProgress(0);
      abortControllerRef.current = null;
    }
  };

  const handleProcessRecording = async () => {
    if (!recordedBlob) return;
    const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const file = new File([recordedBlob], `pose-camara-${stamp}${recordedExt}`, {
      type: recordedBlob.type || 'video/webm',
    });
    await submitVideoFile(file, 'recording');
  };

  const handleFileChange = (ev: React.ChangeEvent<HTMLInputElement>) => {
    setError('');
    const file = ev.target.files?.[0] || null;
    if (selectedFileUrl) URL.revokeObjectURL(selectedFileUrl);
    setSelectedFileUrl('');
    setSelectedFile(null);
    if (!file) return;

    const lower = file.name.toLowerCase();
    const hasAllowedExt = ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
    if (!hasAllowedExt) {
      setError(t.invalidFormat);
      ev.target.value = '';
      return;
    }
    if (file.size === 0) {
      setError(t.emptyFile);
      ev.target.value = '';
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError(t.tooLarge);
      ev.target.value = '';
      return;
    }
    setSelectedFile(file);
    setSelectedFileUrl(URL.createObjectURL(file));
  };

  const handleDeleteHistory = async (analysisId: string) => {
    try {
      await api(`/pose/history/${encodeURIComponent(analysisId)}`, token, { method: 'DELETE' });
      if (activeResult?.id === analysisId) setActiveResult(null);
      await loadWorkspaceData();
    } catch (e: any) {
      setError(e.message || 'Delete failed');
    }
  };

  const isBusy = processingState !== 'idle';
  const cameraRequiredForMode = mode === 'live' || mode === 'recording';
  const liveMeanPct =
    liveLastFrame?.mean_confidence != null
      ? `${Math.round(Number(liveLastFrame.mean_confidence) * 100)}%`
      : '—';

  return (
    <section className="module-stack">
      <div className="panel pose-workspace-panel">
        <div className="panel-head pose-head">
          <div>
            <span className="eyebrow">YOLO POSE · {t.nonDiagnosticTag}</span>
            <h3>{t.title}</h3>
            <p className="muted pose-subtitle">{t.subtitle}</p>
          </div>
          <span className={`pose-engine-state ${poseStatus?.status === 'configured' ? 'ready' : 'pending'}`}>
            {poseStatus?.status === 'configured' ? t.modelReady : t.modelUnavailable}
          </span>
        </div>

        {poseStatus && poseStatus.status !== 'configured' && (
          <div className="pose-info-banner">
            <Info size={16} />
            <div>
              <strong>{t.modelUnavailable}</strong>
              <p>{poseStatus.reason}</p>
            </div>
          </div>
        )}

        <div className="metric-mode-toggle" role="tablist" aria-label="Pose capture modes">
          <button
            type="button"
            className="small-btn"
            aria-pressed={mode === 'live'}
            disabled={liveActive || recording || isBusy}
            onClick={() => handleModeSwitch('live')}
          >
            <Camera size={14} />
            {t.modeLive}
          </button>
          <button
            type="button"
            className="small-btn"
            aria-pressed={mode === 'recording'}
            disabled={liveActive || recording || isBusy}
            onClick={() => handleModeSwitch('recording')}
          >
            <Video size={14} />
            {t.modeRecord}
          </button>
          <button
            type="button"
            className="small-btn"
            aria-pressed={mode === 'upload'}
            disabled={liveActive || recording || isBusy}
            onClick={() => handleModeSwitch('upload')}
          >
            <Upload size={14} />
            {t.modeUpload}
          </button>
        </div>

        {(error || cam.error) && (
          <div className="error-banner" role="alert">
            <span>{error || cam.error}</span>
            <button
              type="button"
              onClick={() => {
                setError('');
                cam.clearError();
              }}
            >
              ×
            </button>
          </div>
        )}

        {cameraRequiredForMode && (
          <div className="camera-stage-box">
            <div className="camera-toolbar">
              <div className="camera-status-group">
                <span className={`camera-state-label ${cam.isActive ? 'active' : ''}`}>
                  {cam.isActive ? <Camera size={14} /> : <CameraOff size={14} />}
                  {cam.isActive ? t.cameraActive : t.cameraIdle}
                </span>
                {recording && (
                  <span className="recording-indicator tabular-nums">
                    <CircleDot size={13} />
                    {t.recordingNow} · {formatDuration(recordSeconds)}
                  </span>
                )}
              </div>

              <div className="camera-controls">
                {!cam.isActive ? (
                  <button
                    type="button"
                    className="primary"
                    disabled={cam.isRequesting || isBusy}
                    onClick={() => cam.openCamera()}
                  >
                    {cam.isRequesting ? <LoaderCircle size={15} className="spin" /> : <Camera size={15} />}
                    {cam.isRequesting ? t.openingCamera : t.openCamera}
                  </button>
                ) : (
                  <>
                    {cam.devices.length > 1 && (
                      <label className="camera-select-wrap">
                        <span>{t.switchCamera}</span>
                        <select
                          aria-label={t.switchCamera}
                          value={cam.selectedDeviceId}
                          disabled={liveActive || recording}
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
                      disabled={liveActive || recording}
                      onClick={() => cam.closeCamera()}
                    >
                      <CameraOff size={14} />
                      {t.closeCamera}
                    </button>
                  </>
                )}
              </div>
            </div>

            {!cam.isActive && (
              <p className="camera-privacy-note">{t.privacyNote}</p>
            )}

            {cam.isActive && !(mode === 'recording' && recordedUrl) && (
              <div className="camera-viewport">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="camera-video"
                />
                {mode === 'live' && (
                  <canvas ref={overlayCanvasRef} className="camera-overlay-canvas" />
                )}
              </div>
            )}

            {mode === 'live' && cam.isActive && (
              <div className="camera-action-bar">
                {!liveActive ? (
                  <button
                    type="button"
                    className="primary"
                    disabled={isBusy}
                    onClick={handleStartLive}
                  >
                    <Play size={15} />
                    {t.startLive}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="danger-btn"
                    onClick={handleStopLive}
                  >
                    <Square size={14} />
                    {t.stopLive}
                  </button>
                )}

                {(liveActive || liveFrameCount > 0) && (
                  <div className="live-telemetry-strip tabular-nums">
                    <span>{liveActive ? t.liveRunning : ''}</span>
                    <span>
                      {t.liveFrames}: <b>{liveFrameCount}</b>
                    </span>
                    <span>
                      {t.liveDetected}: <b>{liveDetectedCount}</b>
                    </span>
                    <span>
                      {t.liveConf}: <b>{liveMeanPct}</b>
                    </span>
                  </div>
                )}
              </div>
            )}

            {mode === 'recording' && cam.isActive && !recordedUrl && (
              <div className="camera-action-bar">
                {!recording ? (
                  <button
                    type="button"
                    className="primary"
                    disabled={isBusy}
                    onClick={handleStartRecording}
                  >
                    <CircleDot size={15} />
                    {t.startRecord}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="danger-btn"
                    onClick={handleStopRecording}
                  >
                    <Square size={14} />
                    {t.stopRecord} ({formatDuration(recordSeconds)})
                  </button>
                )}
              </div>
            )}

            {mode === 'recording' && recordedUrl && (
              <div className="review-box">
                <p className="review-caption">{t.reviewRecorded}</p>
                <video className="pose-video" controls src={recordedUrl} />
                <div className="camera-action-bar">
                  <button
                    type="button"
                    className="primary"
                    disabled={isBusy}
                    onClick={handleProcessRecording}
                  >
                    {isBusy ? <LoaderCircle size={15} className="spin" /> : <Play size={15} />}
                    {t.processRecorded}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    disabled={isBusy}
                    onClick={handleDiscardRecording}
                  >
                    <RotateCcw size={14} />
                    {t.retakeRecord}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {mode === 'upload' && (
          <div className="upload-stage-box">
            <label className="upload-field">
              <span>{t.selectVideo}</span>
              <input
                ref={fileInputRef}
                type="file"
                accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm,.mp4,.mov,.avi,.mkv,.webm"
                disabled={isBusy}
                onChange={handleFileChange}
              />
            </label>

            {selectedFile && selectedFileUrl && (
              <div className="review-box">
                <p className="review-caption">
                  <FileVideo size={14} /> {t.previewSelected}: <b>{selectedFile.name}</b> ({(selectedFile.size / (1024 * 1024)).toFixed(2)} MiB)
                </p>
                <video className="pose-video" controls src={selectedFileUrl} />
              </div>
            )}

            <div className="camera-action-bar">
              <button
                type="button"
                className="primary"
                disabled={!selectedFile || isBusy}
                onClick={() => selectedFile && submitVideoFile(selectedFile, 'upload')}
              >
                {isBusy ? <LoaderCircle size={15} className="spin" /> : <Upload size={15} />}
                {t.processVideo}
              </button>
              {selectedFile && !isBusy && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    if (selectedFileUrl) URL.revokeObjectURL(selectedFileUrl);
                    setSelectedFile(null);
                    setSelectedFileUrl('');
                    if (fileInputRef.current) fileInputRef.current.value = '';
                  }}
                >
                  {t.cancelAction}
                </button>
              )}
            </div>
          </div>
        )}

        {isBusy && (
          <div className="pose-progress-box">
            <LoaderCircle size={16} className="spin" />
            <span>
              {processingState === 'uploading'
                ? `${t.uploading} ${uploadProgress}%`
                : t.processingYolo}
            </span>
            {abortControllerRef.current && (
              <button
                type="button"
                className="small-btn"
                onClick={() => abortControllerRef.current?.abort()}
              >
                {t.cancelAction}
              </button>
            )}
          </div>
        )}
      </div>

      {activeResult && (
        <PoseInterpretationCard
          result={activeResult}
          token={token}
          lang={lang}
          t={t}
        />
      )}

      <div className="panel">
        <div className="panel-head">
          <h4>{t.historyTitle}</h4>
          <button type="button" className="small-btn" onClick={loadWorkspaceData}>
            <RefreshCw size={13} />
          </button>
        </div>

        {history.length === 0 ? (
          <p className="muted" style={{ marginTop: 10 }}>{t.historyEmpty}</p>
        ) : (
          <div className="pose-history-list">
            {history.map((item, idx) => {
              const id = String(item.id || idx);
              const isOpen = expandedHistoryId === id;
              const interp = item.interpretation;
              const summaryText = interp?.summary?.[lang] || `${item.input_name || id} · ${item.frames_processed ?? 0} frames`;
              const confPct = interp?.confidence_percent;
              return (
                <article className="pose-history-row" key={id}>
                  <div className="pose-history-top">
                    <div>
                      <strong>{item.input_name || id}</strong>
                      <div className="pose-history-meta tabular-nums">
                        {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
                        {' · '}
                        {item.frames_processed ?? 0} {lang === 'es' ? 'cuadros' : 'frames'}
                        {confPct != null ? ` · ${t.confidenceLabel}: ${confPct}%` : ''}
                      </div>
                      <p className="pose-history-summary">{summaryText}</p>
                    </div>
                    <div className="pose-history-actions">
                      <button
                        type="button"
                        className="small-btn"
                        onClick={() => setExpandedHistoryId(isOpen ? null : id)}
                      >
                        <Eye size={13} />
                        {isOpen ? t.hideDetails : t.viewDetails}
                      </button>
                      <button
                        type="button"
                        className="small-btn"
                        onClick={() => handleDeleteHistory(id)}
                        title={t.deleteAnalysis}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                  {isOpen && (
                    <div className="pose-history-expanded">
                      <PoseInterpretationCard result={item} token={token} lang={lang} t={t} embedded />
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

function PoseInterpretationCard({
  result,
  token,
  lang,
  t,
  embedded = false,
}: {
  result: any;
  token: string;
  lang: 'en' | 'es';
  t: (typeof copy)['es'];
  embedded?: boolean;
}) {
  const interp = result.interpretation;
  const summaryText = interp?.summary?.[lang] || `${result.input_name} · ${result.frames_processed ?? 0} frames`;
  const observations: string[] = interp?.observations?.[lang] || [];
  const limitations: string[] = interp?.limitations?.[lang] || [];
  const confLabel = interp?.confidence_label?.[lang] || '';
  const confPct = Number(interp?.confidence_percent ?? 0);
  const confBand = String(interp?.confidence_band || 'moderate');
  const notice = interp?.non_diagnostic_notice?.[lang] || result.notice || '';
  const timeline: any[] = Array.isArray(interp?.timeline) ? interp.timeline : [];
  const reps: any[] = Array.isArray(result.representative_frames) ? result.representative_frames : [];
  const tech = interp?.technical_details || {
    model: result.model,
    frames_processed: result.frames_processed,
  };

  return (
    <div className={embedded ? 'pose-report embedded' : 'panel pose-report'}>
      <div className="panel-head pose-report-head">
        <div>
          <span className="eyebrow">{t.summaryTitle}</span>
          <h3>{result.input_name}</h3>
        </div>
        <div className="pose-report-flags">
          {interp?.requires_human_review && (
            <span className="review-flag">
              <AlertTriangle size={13} />
              {t.humanReviewBadge}
            </span>
          )}
        </div>
      </div>

      {/* A. Resumen general */}
      <div className="pose-section-block">
        <p className="pose-summary-lead">{summaryText}</p>
        <div className="confidence-meter-row">
          <div className="confidence-meter-label">
            <span>{t.confidenceLabel}:</span>
            <strong>{confLabel || `${confPct}%`}</strong>
          </div>
          <div className="confidence-bar-track" aria-label={`${t.confidenceLabel}: ${confPct}%`}>
            <div
              className={`confidence-bar-fill band-${confBand}`}
              style={{ width: `${Math.max(4, Math.min(100, confPct))}%` }}
            />
          </div>
        </div>
      </div>

      {/* B. Observaciones interpretadas */}
      <div className="pose-section-block">
        <h4>{t.observationsTitle}</h4>
        <ul className="pose-plain-list">
          {observations.map((obs, idx) => (
            <li key={idx}>
              <CheckCircle2 size={15} className="obs-icon" />
              <span>{obs}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* C. Indicadores visuales */}
      {(result.video_url || reps.length > 0 || timeline.length > 1) && (
        <div className="pose-section-block">
          <h4>{t.visualTitle}</h4>

          {result.video_url && (
            <div className="pose-visual-item">
              <small className="visual-caption">{t.annotatedVideoTitle}</small>
              <AuthorizedVideo url={result.video_url} token={token} />
            </div>
          )}

          {reps.length > 0 && (
            <div className="pose-visual-item">
              <small className="visual-caption">{t.keyframesTitle}</small>
              <div className="pose-keyframes-grid">
                {reps.map((kf, idx) => (
                  <figure className="pose-keyframe-card" key={idx}>
                    <img src={kf.image_data_url} alt={`${t.keyframesTitle} #${kf.frame}`} />
                    <figcaption className="tabular-nums">
                      {lang === 'es' ? `Cuadro ${kf.frame}` : `Frame ${kf.frame}`}
                      {kf.timestamp_s != null ? ` · ${kf.timestamp_s}s` : ''}
                      {kf.trunk_inclination_deg != null ? ` · ${kf.trunk_inclination_deg}°` : ''}
                    </figcaption>
                  </figure>
                ))}
              </div>
            </div>
          )}

          {timeline.length > 1 && (
            <div className="pose-visual-item">
              <small className="visual-caption">{t.evolutionTitle}</small>
              <PostureTimelineChart timeline={timeline} lang={lang} />
            </div>
          )}
        </div>
      )}

      {/* D. Limitaciones y advertencias */}
      <div className="pose-section-block pose-limitations-box">
        <h4>{t.limitationsTitle}</h4>
        {limitations.length > 0 && (
          <ul className="pose-plain-list">
            {limitations.map((lim, idx) => (
              <li key={idx}>
                <AlertTriangle size={14} className="lim-icon" />
                <span>{lim}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="pose-non-diagnostic">{notice}</p>
      </div>

      {/* E. Detalles técnicos secundarios (colapsable) */}
      <details className="pose-tech-details">
        <summary>
          <span>{t.techTitle}</span>
          <ChevronDown size={15} />
        </summary>
        <div className="pose-tech-body">
          <dl className="pose-tech-grid tabular-nums">
            <div>
              <dt>{lang === 'es' ? 'Identificador de análisis' : 'Analysis ID'}</dt>
              <dd>{result.id}</dd>
            </div>
            <div>
              <dt>{lang === 'es' ? 'Modelo utilizado' : 'Model'}</dt>
              <dd>{tech.model || result.model}</dd>
            </div>
            <div>
              <dt>{lang === 'es' ? 'Cuadros procesados / detectados' : 'Frames processed / detected'}</dt>
              <dd>
                {tech.frames_processed ?? result.frames_processed} / {tech.frames_with_detection ?? '—'}
              </dd>
            </div>
            <div>
              <dt>{lang === 'es' ? 'Confianza numérica media' : 'Mean numerical confidence'}</dt>
              <dd>{tech.mean_confidence != null ? Number(tech.mean_confidence).toFixed(4) : '—'}</dd>
            </div>
            <div>
              <dt>{lang === 'es' ? 'Inclinación de tronco (media / máx.)' : 'Trunk inclination (mean / max)'}</dt>
              <dd>
                {tech.trunk_inclination_stats_deg?.mean != null
                  ? `${tech.trunk_inclination_stats_deg.mean}° / ${tech.trunk_inclination_stats_deg.max}°`
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>{lang === 'es' ? 'Desnivel de hombros (media / máx.)' : 'Shoulder tilt (mean / max)'}</dt>
              <dd>
                {tech.shoulder_tilt_stats_deg?.mean != null
                  ? `${tech.shoulder_tilt_stats_deg.mean}° / ${tech.shoulder_tilt_stats_deg.max}°`
                  : '—'}
              </dd>
            </div>
          </dl>
          <pre>{JSON.stringify({ id: result.id, model: result.model, frames_processed: result.frames_processed, technical_details: tech, measurements: result.measurements }, null, 2)}</pre>
        </div>
      </details>
    </div>
  );
}

function PostureTimelineChart({ timeline, lang }: { timeline: any[]; lang: 'en' | 'es' }) {
  const validAngles = useMemo(
    () => timeline.filter((pt) => pt.trunk_inclination_deg != null),
    [timeline],
  );
  const w = 640;
  const h = 150;
  const padL = 38;
  const padR = 14;
  const padT = 14;
  const padB = 26;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;

  const anglePoints = validAngles
    .map((pt) => {
      const idx = timeline.indexOf(pt);
      const x = padL + (idx / Math.max(timeline.length - 1, 1)) * innerW;
      const clamped = Math.min(60, Math.max(0, Number(pt.trunk_inclination_deg)));
      const y = padT + innerH - (clamped / 60) * innerH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  const confPoints = timeline
    .filter((pt) => pt.mean_confidence != null)
    .map((pt) => {
      const idx = timeline.indexOf(pt);
      const x = padL + (idx / Math.max(timeline.length - 1, 1)) * innerW;
      const y = padT + innerH - Math.min(1, Math.max(0, Number(pt.mean_confidence))) * innerH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <div className="posture-timeline-wrap">
      <div className="posture-timeline-legend">
        <span>
          <i className="dot-trunk" />
          {lang === 'es' ? 'Inclinación del tronco (0°–60°)' : 'Trunk inclination (0°–60°)'}
        </span>
        <span>
          <i className="dot-conf" />
          {lang === 'es' ? 'Confianza de detección (0–100%)' : 'Detection confidence (0–100%)'}
        </span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="posture-timeline-svg" role="img" aria-label={lang === 'es' ? 'Evolución de postura' : 'Posture evolution'}>
        {[0, 30, 60].map((deg) => {
          const y = padT + innerH - (deg / 60) * innerH;
          return (
            <g key={deg}>
              <line x1={padL} y1={y} x2={w - padR} y2={y} stroke="#1d2d40" strokeDasharray="3 3" />
              <text x={4} y={y + 4} fill="#788ba0" fontSize="10" fontFamily="DM Mono, monospace">
                {deg}°
              </text>
            </g>
          );
        })}
        {confPoints && (
          <polyline fill="none" stroke="#72a9ff" strokeWidth="1.75" strokeDasharray="4 3" points={confPoints} />
        )}
        {anglePoints && (
          <polyline fill="none" stroke="#68d9bd" strokeWidth="2.5" points={anglePoints} />
        )}
        <text x={padL} y={h - 6} fill="#788ba0" fontSize="10" fontFamily="DM Mono, monospace">
          0s
        </text>
        <text x={w - padR - 36} y={h - 6} fill="#788ba0" fontSize="10" fontFamily="DM Mono, monospace">
          {timeline.at(-1)?.timestamp_s != null ? `${timeline.at(-1).timestamp_s}s` : `${timeline.length}f`}
        </text>
      </svg>
    </div>
  );
}

function AuthorizedVideo({ url, token }: { url: string; token: string }) {
  const [source, setSource] = useState('');
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    let objectUrl = '';
    setFailed(false);
    setSource('');
    fetch(apiUrl(url), { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        if (!response.ok) throw Error(`HTTP ${response.status}`);
        return response.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (active) setSource(objectUrl);
      })
      .catch(() => {
        if (active) {
          setSource('');
          setFailed(true);
        }
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, token]);
  if (source) return <video className="pose-video" controls src={source} />;
  return <span className="muted">{!token ? '—' : failed ? 'Video unavailable' : 'Loading video…'}</span>;
}
