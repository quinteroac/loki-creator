import { useEffect, useRef, useState } from "react";
import type { MouseEvent, PointerEvent, WheelEvent } from "react";
import { ImagePlus, Images, Palette, Scissors, X } from "lucide-react";
import { exportVideoFrame, listVideoLuts, loadVideoTimeline, trimVideoArtifact } from "../api/videoEditor";
import type { VideoEditArtifact, VideoLutOption, VideoTimelineResponse } from "../types";

type VideoTimelineEditorProps = {
  artifactUrl: string;
  title: string;
  onClose: () => void;
  onCreateArtifact: (artifact: VideoEditArtifact, placementOffset?: number) => void;
  onStatus: (message: string) => void;
};

type DragMode = "scrub" | "start" | "end";

const TIMELINE_THUMBNAILS = 16;
const MIN_TRIM_SECONDS = 0.1;
const ORIGINAL_LUT: VideoLutOption = { id: "original", label: "Original" };

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

function formatSecondsInput(value: number) {
  const safeValue = Number.isFinite(value) ? Math.max(0, value) : 0;
  return safeValue.toFixed(2);
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
  const lastArtifactUrlRef = useRef<string | null>(null);
  const [timeline, setTimeline] = useState<VideoTimelineResponse | null>(null);
  const [luts, setLuts] = useState<VideoLutOption[]>([ORIGINAL_LUT]);
  const [selectedLutId, setSelectedLutId] = useState(ORIGINAL_LUT.id);
  const [selectedTime, setSelectedTime] = useState(0);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);
  const [error, setError] = useState("");
  const [action, setAction] = useState<"frame" | "bounds" | "trim" | null>(null);
  const isLoading = !timeline && !error;
  const duration = timeline?.durationSeconds ?? 0;
  const selectedPercent = duration > 0 ? (selectedTime / duration) * 100 : 0;
  const trimStartPercent = duration > 0 ? (trimStart / duration) * 100 : 0;
  const trimEndPercent = duration > 0 ? (trimEnd / duration) * 100 : 100;
  const trimDuration = Math.max(0, trimEnd - trimStart);
  const selectedThumbnail = nearestThumbnail(timeline, selectedTime);

  useEffect(() => {
    let isMounted = true;

    listVideoLuts()
      .then((loadedLuts) => {
        if (!isMounted) return;
        const normalizedLuts = loadedLuts.some((lut) => lut.id === ORIGINAL_LUT.id)
          ? loadedLuts
          : [ORIGINAL_LUT, ...loadedLuts];
        setLuts(normalizedLuts);
        setSelectedLutId((currentId) =>
          normalizedLuts.some((lut) => lut.id === currentId) ? currentId : ORIGINAL_LUT.id,
        );
      })
      .catch(() => {
        if (!isMounted) return;
        setLuts([ORIGINAL_LUT]);
        setSelectedLutId(ORIGINAL_LUT.id);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const shouldPreserveRange = lastArtifactUrlRef.current === artifactUrl && timeline !== null;
    const previousSelectedTime = selectedTime;
    const previousTrimStart = trimStart;
    const previousTrimEnd = trimEnd;
    lastArtifactUrlRef.current = artifactUrl;
    setTimeline(null);
    setError("");

    loadVideoTimeline(artifactUrl, TIMELINE_THUMBNAILS, selectedLutId)
      .then((loadedTimeline) => {
        if (!isMounted) return;
        const safeMaxTime = Math.max(0, loadedTimeline.durationSeconds - 0.001);
        const initialTime = Math.min(loadedTimeline.durationSeconds / 2, safeMaxTime);
        setTimeline(loadedTimeline);
        if (shouldPreserveRange) {
          const nextStart = clamp(previousTrimStart, 0, Math.max(0, loadedTimeline.durationSeconds - MIN_TRIM_SECONDS));
          const previousEnd = previousTrimEnd > previousTrimStart ? previousTrimEnd : loadedTimeline.durationSeconds;
          const nextEnd = clamp(previousEnd, Math.min(loadedTimeline.durationSeconds, nextStart + MIN_TRIM_SECONDS), loadedTimeline.durationSeconds);
          setSelectedTime(clamp(previousSelectedTime, 0, safeMaxTime));
          setTrimStart(nextStart);
          setTrimEnd(nextEnd);
          return;
        }
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
  }, [artifactUrl, selectedLutId]);

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

  function handleTrimStartInput(value: string) {
    const parsedValue = Number.parseFloat(value);
    if (!Number.isFinite(parsedValue)) return;
    const nextStart = clamp(parsedValue, 0, Math.max(0, trimEnd - MIN_TRIM_SECONDS));
    setTrimStart(nextStart);
    setSelectedTime(nextStart);
  }

  function handleTrimEndInput(value: string) {
    const parsedValue = Number.parseFloat(value);
    if (!Number.isFinite(parsedValue)) return;
    const nextEnd = clamp(parsedValue, Math.min(duration, trimStart + MIN_TRIM_SECONDS), duration);
    setTrimEnd(nextEnd);
    setSelectedTime(nextEnd);
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
      const artifact = await exportVideoFrame(artifactUrl, selectedTime, selectedLutId);
      onCreateArtifact(artifact);
      onStatus("Frame added to canvas.");
    } catch (frameError) {
      setError(frameError instanceof Error ? frameError.message : "Could not export frame.");
    } finally {
      setAction(null);
    }
  }

  async function createBoundaryFrameCards() {
    if (!timeline || action) return;
    try {
      setAction("bounds");
      setError("");
      const [firstFrame, lastFrame] = await Promise.all([
        exportVideoFrame(artifactUrl, 0, selectedLutId),
        exportVideoFrame(artifactUrl, timeline.durationSeconds, selectedLutId),
      ]);
      onCreateArtifact(firstFrame, 0);
      onCreateArtifact(lastFrame, 1);
      onStatus("First and last frames added to canvas.");
    } catch (boundaryError) {
      setError(boundaryError instanceof Error ? boundaryError.message : "Could not export first and last frames.");
    } finally {
      setAction(null);
    }
  }

  async function createTrimCard() {
    if (!timeline || action || trimDuration < MIN_TRIM_SECONDS) return;
    try {
      setAction("trim");
      setError("");
      const artifact = await trimVideoArtifact(artifactUrl, trimStart, trimEnd, selectedLutId);
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

          <div className="video-editor-controls">
            <div className="video-editor-readout" aria-live="polite">
              <span>Frame {formatSeconds(selectedTime)}</span>
              <span>Trim {formatSeconds(trimStart)}-{formatSeconds(trimEnd)}</span>
            </div>

            <label className="video-editor-lut-select">
              <Palette size={14} aria-hidden="true" />
              <span>LUT</span>
              <select
                aria-label="Video LUT"
                disabled={Boolean(action)}
                value={selectedLutId}
                onChange={(event) => setSelectedLutId(event.target.value)}
              >
                {luts.map((lut) => (
                  <option key={lut.id} value={lut.id}>
                    {lut.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="video-editor-range-inputs" aria-label="Trim range in seconds">
            <label>
              <span>Start (s)</span>
              <input
                aria-label="Trim start seconds"
                disabled={Boolean(action)}
                inputMode="decimal"
                min={0}
                max={Math.max(0, trimEnd - MIN_TRIM_SECONDS)}
                step="0.01"
                type="number"
                value={formatSecondsInput(trimStart)}
                onChange={(event) => handleTrimStartInput(event.target.value)}
              />
            </label>
            <label>
              <span>End (s)</span>
              <input
                aria-label="Trim end seconds"
                disabled={Boolean(action)}
                inputMode="decimal"
                min={Math.min(duration, trimStart + MIN_TRIM_SECONDS)}
                max={duration}
                step="0.01"
                type="number"
                value={formatSecondsInput(trimEnd)}
                onChange={(event) => handleTrimEndInput(event.target.value)}
              />
            </label>
            <span>{formatSeconds(trimDuration)}</span>
          </div>

          <div className="video-editor-actions">
            <button
              className="video-editor-action-button"
              type="button"
              disabled={Boolean(action)}
              onClick={createFrameCard}
            >
              <ImagePlus size={15} aria-hidden="true" />
              <span>{action === "frame" ? "Creating..." : "Create frame"}</span>
            </button>
            <button
              className="video-editor-action-button"
              type="button"
              disabled={Boolean(action)}
              onClick={createBoundaryFrameCards}
            >
              <Images size={15} aria-hidden="true" />
              <span>{action === "bounds" ? "Extracting..." : "First/last"}</span>
            </button>
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
