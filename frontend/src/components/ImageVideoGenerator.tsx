import { useEffect, useState } from "react";
import type { MouseEvent, PointerEvent, WheelEvent } from "react";
import { Clapperboard, Palette, Sparkles, X } from "lucide-react";
import { createVideoFromImage, listVideoEffects, listVideoLuts } from "../api/videoEditor";
import type { VideoEditArtifact, VideoEffectOption, VideoLutOption } from "../types";

type ImageVideoGeneratorProps = {
  artifactUrl: string;
  title: string;
  onClose: () => void;
  onCreateArtifact: (artifact: VideoEditArtifact) => void;
  onStatus: (message: string) => void;
};

const ORIGINAL_LUT: VideoLutOption = { id: "original", label: "Original" };
const NO_EFFECT: VideoEffectOption = { id: "none", label: "None", kind: "filter", available: true };
const DEFAULT_DURATION_SECONDS = 5;
const DEFAULT_FPS = 24;

function stopEditorMouseEvent(event: MouseEvent<HTMLElement>) {
  event.stopPropagation();
}

function stopEditorPointerEvent(event: PointerEvent<HTMLElement>) {
  event.stopPropagation();
}

function stopEditorWheelEvent(event: WheelEvent<HTMLElement>) {
  event.stopPropagation();
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function effectLabel(effect: VideoEffectOption) {
  if (effect.id === NO_EFFECT.id) return effect.label;
  return `${effect.kind === "generator" ? "Generated" : "Filter"} - ${effect.label}`;
}

export function ImageVideoGenerator({
  artifactUrl,
  title,
  onClose,
  onCreateArtifact,
  onStatus,
}: ImageVideoGeneratorProps) {
  const [luts, setLuts] = useState<VideoLutOption[]>([ORIGINAL_LUT]);
  const [effects, setEffects] = useState<VideoEffectOption[]>([NO_EFFECT]);
  const [selectedLutId, setSelectedLutId] = useState(ORIGINAL_LUT.id);
  const [selectedEffectId, setSelectedEffectId] = useState(NO_EFFECT.id);
  const [durationSeconds, setDurationSeconds] = useState(DEFAULT_DURATION_SECONDS);
  const [fps, setFps] = useState(DEFAULT_FPS);
  const [error, setError] = useState("");
  const [isCreating, setIsCreating] = useState(false);

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

    listVideoEffects()
      .then((loadedEffects) => {
        if (!isMounted) return;
        const normalizedEffects = loadedEffects.some((effect) => effect.id === NO_EFFECT.id)
          ? loadedEffects
          : [NO_EFFECT, ...loadedEffects];
        const availableEffects = normalizedEffects.filter((effect) => effect.available);
        setEffects(availableEffects.length > 0 ? availableEffects : [NO_EFFECT]);
        setSelectedEffectId((currentId) => {
          const currentEffect = availableEffects.find((effect) => effect.id === currentId);
          return currentEffect?.available ? currentId : NO_EFFECT.id;
        });
      })
      .catch(() => {
        if (!isMounted) return;
        setEffects([NO_EFFECT]);
        setSelectedEffectId(NO_EFFECT.id);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  function handleDurationInput(value: string) {
    const parsedValue = Number.parseFloat(value);
    if (!Number.isFinite(parsedValue)) return;
    setDurationSeconds(clamp(parsedValue, 0.5, 60));
  }

  function handleFpsInput(value: string) {
    const parsedValue = Number.parseFloat(value);
    if (!Number.isFinite(parsedValue)) return;
    setFps(clamp(parsedValue, 1, 60));
  }

  async function handleCreateVideo() {
    if (isCreating) return;
    try {
      setIsCreating(true);
      setError("");
      const artifact = await createVideoFromImage(artifactUrl, durationSeconds, fps, selectedLutId, selectedEffectId);
      onCreateArtifact(artifact);
      onStatus("Video added to canvas.");
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Could not create video from image.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <section
      className="video-timeline-editor image-video-generator"
      aria-label={`Create video from ${title}`}
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
          <span>Create video from image</span>
        </div>
        <button className="video-editor-icon-button" type="button" aria-label="Close generator" onClick={onClose}>
          <X size={15} aria-hidden="true" />
        </button>
      </header>

      <figure className="video-editor-frame-preview image-video-generator-preview">
        <img alt={`${title} preview`} draggable={false} src={artifactUrl} />
      </figure>

      <div className="video-editor-controls">
        <label className="video-editor-lut-select">
          <Palette size={14} aria-hidden="true" />
          <span>LUT</span>
          <select
            aria-label="Generated video LUT"
            disabled={isCreating}
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

        <label className="video-editor-effect-select">
          <Sparkles size={14} aria-hidden="true" />
          <span>Effect</span>
          <select
            aria-label="Generated video effect"
            disabled={isCreating}
            value={selectedEffectId}
            onChange={(event) => setSelectedEffectId(event.target.value)}
          >
            {effects.map((effect) => (
              <option key={effect.id} value={effect.id}>
                {effectLabel(effect)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="video-editor-range-inputs" aria-label="Generated video settings">
        <label>
          <span>Duration (s)</span>
          <input
            aria-label="Generated video duration seconds"
            disabled={isCreating}
            inputMode="decimal"
            min={0.5}
            max={60}
            step="0.5"
            type="number"
            value={durationSeconds}
            onChange={(event) => handleDurationInput(event.target.value)}
          />
        </label>
        <label>
          <span>FPS</span>
          <input
            aria-label="Generated video FPS"
            disabled={isCreating}
            inputMode="decimal"
            min={1}
            max={60}
            step="1"
            type="number"
            value={fps}
            onChange={(event) => handleFpsInput(event.target.value)}
          />
        </label>
        <span>{durationSeconds.toFixed(1)}s</span>
      </div>

      <div className="video-editor-actions">
        <button
          className="video-editor-action-button primary"
          type="button"
          disabled={isCreating}
          onClick={handleCreateVideo}
        >
          <Clapperboard size={15} aria-hidden="true" />
          <span>{isCreating ? "Creating..." : "Create video"}</span>
        </button>
      </div>

      {error && <p className="video-editor-error">{error}</p>}
    </section>
  );
}
