import { useCallback, useEffect, useRef, useState } from 'react';

export type CameraDeviceInfo = {
  deviceId: string;
  label: string;
};

type ActiveLease = {
  owner: string;
  stream: MediaStream;
  onRevoke: () => void;
};

// Module-level exclusive camera lease: ensures two modules never control the same device simultaneously.
let currentLease: ActiveLease | null = null;

function releaseActiveLease(exceptOwner?: string) {
  if (!currentLease) return;
  if (exceptOwner && currentLease.owner === exceptOwner) return;
  const prev = currentLease;
  currentLease = null;
  try {
    prev.stream.getTracks().forEach((track) => track.stop());
  } catch {
    // Ignore already-stopped tracks
  }
  try {
    prev.onRevoke();
  } catch {
    // Ignore stale callback
  }
}

export function releaseAllCameras() {
  releaseActiveLease();
}

export function getActiveCameraOwner(): string | null {
  return currentLease?.owner ?? null;
}

function mapCameraError(err: any, lang: 'en' | 'es'): string {
  const name = String(err?.name || '');
  const msg = String(err?.message || '');
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError' || msg.toLowerCase().includes('permission')) {
    return lang === 'es'
      ? 'Permiso de cámara denegado. Habilita el acceso a la cámara en el navegador (icono de candado junto a la URL) y vuelve a intentarlo.'
      : 'Camera permission was denied. Enable camera access in your browser site settings and try again.';
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return lang === 'es'
      ? 'No se detectó ninguna cámara disponible en este dispositivo.'
      : 'No camera device was detected on this system.';
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return lang === 'es'
      ? 'La cámara está siendo utilizada por otra aplicación o pestaña. Ciérrala e intenta nuevamente.'
      : 'The camera is currently in use by another application or tab. Close it and try again.';
  }
  if (name === 'OverconstrainedError' || name === 'ConstraintNotSatisfiedError') {
    return lang === 'es'
      ? 'La cámara seleccionada no admite la configuración solicitada. Prueba con otro dispositivo.'
      : 'The selected camera does not support the requested configuration. Try another camera.';
  }
  if (name === 'SecurityError' || !window.isSecureContext) {
    return lang === 'es'
      ? 'El navegador bloqueó el acceso a la cámara porque el sitio no se ejecuta en localhost ni bajo HTTPS.'
      : 'Browser blocked camera access because this page is not running on localhost or HTTPS.';
  }
  return lang === 'es'
    ? `No se pudo abrir la cámara (${name || 'error de dispositivo'}). Verifica la conexión y permisos.`
    : `Could not open camera (${name || 'device error'}). Check connection and permissions.`;
}

export function useCameraManager(owner: string, lang: 'en' | 'es') {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [devices, setDevices] = useState<CameraDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [isRequesting, setIsRequesting] = useState(false);
  const [error, setError] = useState('');
  const mountedRef = useRef(true);
  const streamRef = useRef<MediaStream | null>(null);

  const refreshDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const list = await navigator.mediaDevices.enumerateDevices();
      const videoInputs = list
        .filter((d) => d.kind === 'videoinput')
        .map((d, idx) => ({
          deviceId: d.deviceId,
          label:
            d.label ||
            (lang === 'es' ? `Cámara ${idx + 1}` : `Camera ${idx + 1}`),
        }));
      if (mountedRef.current) {
        setDevices(videoInputs);
      }
    } catch {
      // Ignore enumerateDevices errors when permissions are not yet granted
    }
  }, [lang]);

  const closeCamera = useCallback(() => {
    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach((t) => t.stop());
      } catch {
        // Ignore
      }
      streamRef.current = null;
    }
    if (currentLease?.owner === owner) {
      currentLease = null;
    }
    if (mountedRef.current) {
      setStream(null);
    }
  }, [owner]);

  const openCamera = useCallback(
    async (requestedDeviceId?: string) => {
      setError('');
      if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
        setError(
          lang === 'es'
            ? 'Este navegador o contexto actual no permite acceder a la cámara. Usa localhost o HTTPS.'
            : 'Camera access is unavailable in this browser or insecure context. Use localhost or HTTPS.',
        );
        return null;
      }

      // Release any other module holding the camera, and release our previous stream before opening a new one.
      releaseActiveLease();
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }

      setIsRequesting(true);
      try {
        const targetId = requestedDeviceId ?? selectedDeviceId;
        const videoConstraints: MediaTrackConstraints = targetId
          ? { deviceId: { exact: targetId }, width: { ideal: 1280 }, height: { ideal: 720 } }
          : { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } };

        const media = await navigator.mediaDevices.getUserMedia({
          video: videoConstraints,
          audio: false,
        });

        if (!mountedRef.current) {
          media.getTracks().forEach((t) => t.stop());
          return null;
        }

        const activeTrack = media.getVideoTracks()[0];
        const actualId = activeTrack?.getSettings?.().deviceId || targetId || '';
        streamRef.current = media;
        currentLease = {
          owner,
          stream: media,
          onRevoke: () => {
            streamRef.current = null;
            if (mountedRef.current) setStream(null);
          },
        };

        setStream(media);
        if (actualId) setSelectedDeviceId(actualId);
        await refreshDevices();
        return media;
      } catch (err: any) {
        if (mountedRef.current) {
          setError(mapCameraError(err, lang));
          setStream(null);
        }
        return null;
      } finally {
        if (mountedRef.current) {
          setIsRequesting(false);
        }
      }
    },
    [lang, owner, refreshDevices, selectedDeviceId],
  );

  const switchCamera = useCallback(
    async (deviceId: string) => {
      setSelectedDeviceId(deviceId);
      if (streamRef.current) {
        await openCamera(deviceId);
      }
    },
    [openCamera],
  );

  useEffect(() => {
    mountedRef.current = true;
    const onDeviceChange = () => {
      refreshDevices();
    };
    const onPageHide = () => {
      closeCamera();
    };
    navigator.mediaDevices?.addEventListener?.('devicechange', onDeviceChange);
    window.addEventListener('pagehide', onPageHide);
    return () => {
      mountedRef.current = false;
      navigator.mediaDevices?.removeEventListener?.('devicechange', onDeviceChange);
      window.removeEventListener('pagehide', onPageHide);
      closeCamera();
    };
  }, [closeCamera, refreshDevices]);

  return {
    stream,
    isActive: Boolean(stream),
    isRequesting,
    devices,
    selectedDeviceId,
    error,
    clearError: () => setError(''),
    openCamera,
    switchCamera,
    closeCamera,
    refreshDevices,
  };
}
