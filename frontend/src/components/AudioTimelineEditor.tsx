import { useEffect, useRef, useState } from "react";
import type { MouseEvent, PointerEvent, WheelEvent } from "react";
import { Scissors, X } from "lucide-react";
import { loadAudioTimeline, trimAudioArtifact } from "../api/audioEditor";
import type { AudioTimelineResponse, EditedMediaArtifact } from "../types";

type AudioTimelineEditorProps = {
  artifactUrl: string;
  title: string;
  onClose: () => void;
  onCreateArtifact: (artifact: EditedMediaArtifact) => void;
  onStatus: (message: string) => void;
};

type DragMode = "scrub" | "start" | "end";

const TIMELINE_PEAKS = 160;
const MIN_TRIM_SECONDS = 0.1;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function formatSeconds(value: number) {
  const safeValue = Number.isFinite(value) ? Math.max(0, value) : 0;
  const minutes = Math.floor(safeValue / 60);
  const seconds = safeValue - minutes * 60;
  const paddedSeconds = seconds < 10 ? `0${seconds.toFixed(2)}` : seconds.toFixed(2);

  return `${minutes}:${paddedSeconds}`;
}

function stopEditorMouseEvent(event: MouseEvent<HTMLElement>) {
  event.stopPropagation();
}

function stopEditorPointerEvent(event: PointerEvent<HTMLElement>) {
  event.stopPropagation();
}

function stopEditorWheelEvent(event: WheelEvent<HTMLElement>) {
  event.stopPropagation();
}

export function AudioTimelineEditor({
  artifactUrl,
  title,
  onClose,
  onCreateArtifact,
  onStatus,
}: AudioTimelineEditorProps) {
  const waveformRef = useRef<HTMLDivElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const dragModeRef = useRef<DragMode | null>(null);
  const [timeline, setTimeline] = useState<AudioTimelineResponse | null>(null);
  const [selectedTime, setSelectedTime] = useState(0);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);
  const [error, setError] = useState("");
  const [action, setAction] = useState<"trim" | null>(null);
  const isLoading = !timeline && !error;
  const duration = timeline?.durationSeconds ?? 0;
  const selectedPercent = duration > 0 ? (selectedTime / duration) * 100 : 0;
  const trimStartPercent = duration > 0 ? (trimStart / duration) * 100 : 0;
  const trimEndPercent = duration > 0 ? (trimEnd / duration) * 100 : 100;
  const trimDuration = Math.max(0, trimEnd - trimStart);

  useEffect(() => {
    let isMounted = true;
    setTimeline(null);
    setError("");

    loadAudioTimeline(artifactUrl, TIMELINE_PEAKS)
      .then((loadedTimeline) => {
        if (!isMounted) return;
        setTimeline(loadedTimeline);
        setSelectedTime(0);
        setTrimStart(0);
        setTrimEnd(loadedTimeline.durationSeconds);
      })
      .catch((loadError) => {
        if (!isMounted) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load audio timeline.");
      });

    return () => {
      isMounted = false;
    };
  }, [artifactUrl]);

  function syncAudioTime(timeSeconds: number) {
    const audio = audioRef.current;
    if (audio && Number.isFinite(timeSeconds)) {
      audio.currentTime = clamp(timeSeconds, 0, duration);
    }
  }

  function timeFromPointer(event: PointerEvent<HTMLElement>) {
    const waveform = waveformRef.current;
    if (!waveform || duration <= 0) return 0;
    const bounds = waveform.getBoundingClientRect();
    const ratio = clamp((event.clientX - bounds.left) / Math.max(1, bounds.width), 0, 1);

    return ratio * duration;
  }

  function updateDrag(event: PointerEvent<HTMLElement>, mode: DragMode) {
    const time = timeFromPointer(event);
    if (mode === "start") {
      const nextStart = clamp(time, 0, Math.max(0, trimEnd - MIN_TRIM_SECONDS));
      setTrimStart(nextStart);
      setSelectedTime(nextStart);
      syncAudioTime(nextStart);
      return;
    }

    if (mode === "end") {
      const nextEnd = clamp(time, Math.min(duration, trimStart + MIN_TRIM_SECONDS), duration);
      setTrimEnd(nextEnd);
      setSelectedTime(nextEnd);
      syncAudioTime(nextEnd);
      return;
    }

    const nextTime = clamp(time, 0, duration);
    setSelectedTime(nextTime);
    syncAudioTime(nextTime);
  }

  function handleTimelinePointerDown(event: PointerEvent<HTMLDivElement>) {
    if (!timeline || event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragModeRef.current = "scrub";
    updateDrag(event, "scrub");
  }

  function handleHandlePointerDown(mode: "start" | "end", event: PointerEvent<HTMLButtonElement>) {
    if (!timeline || event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragModeRef.current = mode;
    updateDrag(event, mode);
  }

  function handlePointerMove(event: PointerEvent<HTMLElement>) {
    const mode = dragModeRef.current;
    if (!mode) return;
    event.preventDefault();
    event.stopPropagation();
    updateDrag(event, mode);
  }

  function handlePointerDone(event: PointerEvent<HTMLElement>) {
    dragModeRef.current = null;
    event.stopPropagation();
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handlePlayerTimeUpdate() {
    const audio = audioRef.current;
    if (!audio || dragModeRef.current) return;
    setSelectedTime(clamp(audio.currentTime, 0, duration));
  }

  async function createTrimCard() {
    if (!timeline || action || trimDuration < MIN_TRIM_SECONDS) return;
    try {
      setAction("trim");
      setError("");
      const artifact = await trimAudioArtifact(artifactUrl, trimStart, trimEnd);
      onCreateArtifact(artifact);
      onStatus("Audio clip added to canvas.");
    } catch (trimError) {
      setError(trimError instanceof Error ? trimError.message : "Could not trim audio.");
    } finally {
      setAction(null);
    }
  }

  return (
    <section
      className="audio-timeline-editor"
      aria-label={`Edit ${title}`}
      onClick={stopEditorMouseEvent}
      onContextMenu={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onPointerDown={stopEditorPointerEvent}
      onPointerMove={stopEditorPointerEvent}
      onWheel={stopEditorWheelEvent}
    >
      <header className="video-editor-header">
        <div>
          <strong>{title}</strong>
          <span>
            {timeline
              ? `${formatSeconds(duration)} · ${timeline.channels} ch · ${Math.round(timeline.sampleRate / 1000)} kHz`
              : "Loading timeline"}
          </span>
        </div>
        <button className="video-editor-icon-button" type="button" aria-label="Close editor" onClick={onClose}>
          <X size={15} aria-hidden="true" />
        </button>
      </header>

      {isLoading && (
        <div className="video-editor-loading" aria-live="polite">
          <span />
          <span />
          <span />
        </div>
      )}

      {timeline && (
        <>
          <audio
            className="audio-editor-player"
            ref={audioRef}
            src={artifactUrl}
            controls
            preload="metadata"
            onTimeUpdate={handlePlayerTimeUpdate}
          />

          <div
            className="audio-editor-waveform"
            ref={waveformRef}
            role="slider"
            aria-label="Audio timeline"
            aria-valuemin={0}
            aria-valuemax={Math.round(duration)}
            aria-valuenow={Number(selectedTime.toFixed(2))}
            tabIndex={0}
            onPointerDown={handleTimelinePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerDone}
            onPointerCancel={handlePointerDone}
          >
            <div className="audio-editor-peaks" aria-hidden="true">
              {timeline.peaks.map((peak, index) => (
                <span
                  className="audio-editor-peak"
                  key={`${index}-${peak}`}
                  style={{ height: `${Math.max(6, peak * 100)}%` }}
                />
              ))}
            </div>
            <span
              className="video-editor-trim-range"
              style={{
                left: `${trimStartPercent}%`,
                width: `${Math.max(0, trimEndPercent - trimStartPercent)}%`,
              }}
            />
            <span className="video-editor-playhead" style={{ left: `${selectedPercent}%` }} />
            <button
              className="video-editor-trim-handle start"
              type="button"
              aria-label="Trim start"
              style={{ left: `${trimStartPercent}%` }}
              onPointerDown={(event) => handleHandlePointerDown("start", event)}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerDone}
              onPointerCancel={handlePointerDone}
            />
            <button
              className="video-editor-trim-handle end"
              type="button"
              aria-label="Trim end"
              style={{ left: `${trimEndPercent}%` }}
              onPointerDown={(event) => handleHandlePointerDown("end", event)}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerDone}
              onPointerCancel={handlePointerDone}
            />
          </div>

          <div className="video-editor-readout" aria-live="polite">
            <span>Playhead {formatSeconds(selectedTime)}</span>
            <span>Trim {formatSeconds(trimStart)}-{formatSeconds(trimEnd)}</span>
          </div>

          <div className="video-editor-actions">
            <button
              className="video-editor-action-button primary"
              type="button"
              disabled={Boolean(action) || trimDuration < MIN_TRIM_SECONDS}
              onClick={createTrimCard}
            >
              <Scissors size={15} aria-hidden="true" />
              <span>{action === "trim" ? "Trimming..." : "Create clip"}</span>
            </button>
          </div>
        </>
      )}

      {error && <p className="video-editor-error">{error}</p>}
    </section>
  );
}
