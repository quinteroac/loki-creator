import { useEffect, useRef, useState } from "react";
import type { MouseEvent, PointerEvent, WheelEvent } from "react";
import { ImagePlus, Scissors, X } from "lucide-react";
import { exportVideoFrame, loadVideoTimeline, trimVideoArtifact } from "../api/videoEditor";
import type { VideoEditArtifact, VideoTimelineResponse } from "../types";

type VideoTimelineEditorProps = {
  artifactUrl: string;
  title: string;
  onClose: () => void;
  onCreateArtifact: (artifact: VideoEditArtifact) => void;
  onStatus: (message: string) => void;
};

type DragMode = "scrub" | "start" | "end";

const TIMELINE_THUMBNAILS = 16;
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

function nearestThumbnail(timeline: VideoTimelineResponse | null, timeSeconds: number) {
  if (!timeline || timeline.thumbnails.length === 0) return null;

  return timeline.thumbnails.reduce((nearest, thumbnail) => {
    const nearestDistance = Math.abs(nearest.timeSeconds - timeSeconds);
    const candidateDistance = Math.abs(thumbnail.timeSeconds - timeSeconds);

    return candidateDistance < nearestDistance ? thumbnail : nearest;
  });
}

export function VideoTimelineEditor({
  artifactUrl,
  title,
  onClose,
  onCreateArtifact,
  onStatus,
}: VideoTimelineEditorProps) {
  const filmstripRef = useRef<HTMLDivElement | null>(null);
  const dragModeRef = useRef<DragMode | null>(null);
  const [timeline, setTimeline] = useState<VideoTimelineResponse | null>(null);
  const [selectedTime, setSelectedTime] = useState(0);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);
  const [error, setError] = useState("");
  const [action, setAction] = useState<"frame" | "trim" | null>(null);
  const isLoading = !timeline && !error;
  const duration = timeline?.durationSeconds ?? 0;
  const selectedPercent = duration > 0 ? (selectedTime / duration) * 100 : 0;
  const trimStartPercent = duration > 0 ? (trimStart / duration) * 100 : 0;
  const trimEndPercent = duration > 0 ? (trimEnd / duration) * 100 : 100;
  const trimDuration = Math.max(0, trimEnd - trimStart);
  const selectedThumbnail = nearestThumbnail(timeline, selectedTime);

  useEffect(() => {
    let isMounted = true;
    setTimeline(null);
    setError("");

    loadVideoTimeline(artifactUrl, TIMELINE_THUMBNAILS)
      .then((loadedTimeline) => {
        if (!isMounted) return;
        const initialTime = Math.min(loadedTimeline.durationSeconds / 2, Math.max(0, loadedTimeline.durationSeconds - 0.001));
        setTimeline(loadedTimeline);
        setSelectedTime(initialTime);
        setTrimStart(0);
        setTrimEnd(loadedTimeline.durationSeconds);
      })
      .catch((loadError) => {
        if (!isMounted) return;
        setError(loadError instanceof Error ? loadError.message : "Could not load video timeline.");
      });

    return () => {
      isMounted = false;
    };
  }, [artifactUrl]);

  function timeFromPointer(event: PointerEvent<HTMLElement>) {
    const filmstrip = filmstripRef.current;
    if (!filmstrip || duration <= 0) return 0;
    const bounds = filmstrip.getBoundingClientRect();
    const ratio = clamp((event.clientX - bounds.left) / Math.max(1, bounds.width), 0, 1);

    return ratio * duration;
  }

  function updateDrag(event: PointerEvent<HTMLElement>, mode: DragMode) {
    const time = timeFromPointer(event);
    if (mode === "start") {
      const nextStart = clamp(time, 0, Math.max(0, trimEnd - MIN_TRIM_SECONDS));
      setTrimStart(nextStart);
      setSelectedTime(nextStart);
      return;
    }

    if (mode === "end") {
      const nextEnd = clamp(time, Math.min(duration, trimStart + MIN_TRIM_SECONDS), duration);
      setTrimEnd(nextEnd);
      setSelectedTime(nextEnd);
      return;
    }

    setSelectedTime(clamp(time, 0, duration));
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

  async function createFrameCard() {
    if (!timeline || action) return;
    try {
      setAction("frame");
      setError("");
      const artifact = await exportVideoFrame(artifactUrl, selectedTime);
      onCreateArtifact(artifact);
      onStatus("Frame added to canvas.");
    } catch (frameError) {
      setError(frameError instanceof Error ? frameError.message : "Could not export frame.");
    } finally {
      setAction(null);
    }
  }

  async function createTrimCard() {
    if (!timeline || action || trimDuration < MIN_TRIM_SECONDS) return;
    try {
      setAction("trim");
      setError("");
      const artifact = await trimVideoArtifact(artifactUrl, trimStart, trimEnd);
      onCreateArtifact(artifact);
      onStatus("Trimmed clip added to canvas.");
    } catch (trimError) {
      setError(trimError instanceof Error ? trimError.message : "Could not trim video.");
    } finally {
      setAction(null);
    }
  }

  return (
    <section
      className="video-timeline-editor"
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
          <span>{timeline ? `${formatSeconds(duration)} · ${timeline.width}x${timeline.height}` : "Loading timeline"}</span>
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
          <figure
            className="video-editor-frame-preview"
            style={{ aspectRatio: `${timeline.width} / ${timeline.height}` }}
          >
            {selectedThumbnail ? (
              <img
                alt={`Frame preview at ${formatSeconds(selectedTime)}`}
                draggable={false}
                src={selectedThumbnail.artifactUrl}
              />
            ) : (
              <span aria-hidden="true" />
            )}
          </figure>

          <div
            className="video-editor-filmstrip"
            ref={filmstripRef}
            role="slider"
            aria-label="Video timeline"
            aria-valuemin={0}
            aria-valuemax={Math.round(duration)}
            aria-valuenow={Number(selectedTime.toFixed(2))}
            tabIndex={0}
            onPointerDown={handleTimelinePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerDone}
            onPointerCancel={handlePointerDone}
          >
            {timeline.thumbnails.map((thumbnail) => (
              <img
                alt=""
                aria-hidden="true"
                draggable={false}
                key={`${thumbnail.artifactUrl}-${thumbnail.timeSeconds}`}
                src={thumbnail.artifactUrl}
              />
            ))}
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
            <span>Frame {formatSeconds(selectedTime)}</span>
            <span>Trim {formatSeconds(trimStart)}-{formatSeconds(trimEnd)}</span>
          </div>

          <div className="video-editor-actions">
            <button
              className="video-editor-action-button"
              type="button"
              disabled={Boolean(action)}
              onClick={createFrameCard}
            >
              <ImagePlus size={15} aria-hidden="true" />
              <span>{action === "frame" ? "Creando..." : "Crear frame"}</span>
            </button>
            <button
              className="video-editor-action-button primary"
              type="button"
              disabled={Boolean(action) || trimDuration < MIN_TRIM_SECONDS}
              onClick={createTrimCard}
            >
              <Scissors size={15} aria-hidden="true" />
              <span>{action === "trim" ? "Recortando..." : "Crear clip"}</span>
            </button>
          </div>
        </>
      )}

      {error && <p className="video-editor-error">{error}</p>}
    </section>
  );
}
