import { useEffect, useRef, useState } from "react";
import type { VideoJobStatus, VideoStatus } from "../api/types";

interface VideoGenerationPanelProps {
  onGenerate: () => Promise<VideoStatus>;
  onPollStatus: () => Promise<VideoStatus>;
  onReady: () => void;
}

const POLL_INTERVAL_MS = 5000;

export default function VideoGenerationPanel({
  onGenerate,
  onPollStatus,
  onReady,
}: VideoGenerationPanelProps) {
  const [status, setStatus] = useState<VideoJobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollHandle = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollHandle.current) window.clearInterval(pollHandle.current);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    onPollStatus()
      .then((result) => {
        if (cancelled) return;
        if (result.status === "done") {
          onReady();
          return;
        }
        setStatus(result.status);
        if (result.status === "error") {
          setError(result.error ?? "No se pudo generar el video.");
        } else if (result.status === "running") {
          startPolling();
        }
      })
      .catch(() => {
        if (!cancelled) setStatus("idle");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startPolling() {
    pollHandle.current = window.setInterval(async () => {
      try {
        const result = await onPollStatus();
        if (result.status === "done") {
          if (pollHandle.current) window.clearInterval(pollHandle.current);
          setStatus("done");
          onReady();
        } else if (result.status === "error") {
          if (pollHandle.current) window.clearInterval(pollHandle.current);
          setStatus("error");
          setError(result.error ?? "No se pudo generar el video.");
        }
      } catch (err) {
        if (pollHandle.current) window.clearInterval(pollHandle.current);
        setStatus("error");
        setError(err instanceof Error ? err.message : String(err));
      }
    }, POLL_INTERVAL_MS);
  }

  async function handleGenerate() {
    setError(null);
    setStatus("running");
    try {
      await onGenerate();
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : String(err));
      return;
    }
    startPolling();
  }

  if (status === null || status === "done") {
    return null;
  }

  return (
    <div className="video-placeholder video-placeholder--panel">
      {status !== "running" && (
        <button
          type="button"
          className="btn btn--primary"
          onClick={handleGenerate}
        >
          Generar video con Gemini Notebook
        </button>
      )}
      {status === "running" && (
        <span>Generando el video… puede tardar varios minutos.</span>
      )}
      {status === "error" && (
        <span className="video-placeholder__error">{error}</span>
      )}
      {status !== "running" && status !== "error" && (
        <span>
          Si alcanzaste el límite de cuota, consultá README &rsaquo; «Generación
          de videos de lecciones».
        </span>
      )}
    </div>
  );
}
