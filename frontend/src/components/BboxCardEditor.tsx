import { Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import type { ChangeEvent, KeyboardEvent, PointerEvent } from "react";
import {
  clampNormalizedBbox,
  createClientBboxId,
  IDEOGRAM_ASPECT_DIMENSIONS,
  withBboxBoxes,
  withBboxCanvas,
  type BboxCardData,
  type IdeogramAspectRatio,
  type NormalizedBbox,
} from "../lib/bboxCards";

type BboxCardEditorProps = {
  data: BboxCardData;
  height: number;
  onChange: (data: BboxCardData) => void;
  onDocumentSizeChange: (width: number, height: number) => void;
  onFocusCard: () => void;
  title: string;
};

type DragState = {
  boxId: string;
  mode: "create" | "move" | "resize";
  pointerId: number;
  startBox: NormalizedBbox;
  startX: number;
  startY: number;
};

function clampDimension(value: string, fallback: number) {
  const numericValue = Number.parseInt(value, 10);

  if (!Number.isFinite(numericValue)) return fallback;
  return Math.min(Math.max(numericValue, 64), 4096);
}

function pointerToNormalized(event: PointerEvent<HTMLElement>, element: HTMLElement) {
  const bounds = element.getBoundingClientRect();

  return {
    x: Math.min(Math.max((event.clientX - bounds.left) / Math.max(1, bounds.width), 0), 1),
    y: Math.min(Math.max((event.clientY - bounds.top) / Math.max(1, bounds.height), 0), 1),
  };
}

export function BboxCardEditor({
  data,
  height,
  onChange,
  onDocumentSizeChange,
  onFocusCard,
  title,
}: BboxCardEditorProps) {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const dragStateRef = useRef<DragState | null>(null);
  const [selectedBoxId, setSelectedBoxId] = useState<string | null>(data.boxes[0]?.id ?? null);
  const selectedBox = data.boxes.find((box) => box.id === selectedBoxId) ?? null;

  function updateBoxes(boxes: NormalizedBbox[]) {
    onChange(withBboxBoxes(data, boxes));
  }

  function updateBox(box: NormalizedBbox) {
    updateBoxes(data.boxes.map((candidate) => (candidate.id === box.id ? box : candidate)));
  }

  function handleAspectRatioChange(event: ChangeEvent<HTMLSelectElement>) {
    const aspectRatio = event.target.value as IdeogramAspectRatio;
    const dimensions = IDEOGRAM_ASPECT_DIMENSIONS[aspectRatio];

    onChange(withBboxCanvas(data, { aspectRatio, ...dimensions }));
    onDocumentSizeChange(dimensions.width, dimensions.height);
  }

  function handleWidthChange(event: ChangeEvent<HTMLInputElement>) {
    const width = clampDimension(event.target.value, data.canvas.width);

    onChange(withBboxCanvas(data, { ...data.canvas, width }));
    onDocumentSizeChange(width, data.canvas.height);
  }

  function handleHeightChange(event: ChangeEvent<HTMLInputElement>) {
    const nextHeight = clampDimension(event.target.value, data.canvas.height);

    onChange(withBboxCanvas(data, { ...data.canvas, height: nextHeight }));
    onDocumentSizeChange(data.canvas.width, nextHeight);
  }

  function handleSelectedPromptChange(event: ChangeEvent<HTMLInputElement>) {
    if (!selectedBox) return;

    updateBox({
      ...selectedBox,
      prompt: event.target.value,
    });
  }

  function handleStagePointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || !stageRef.current) return;

    event.preventDefault();
    event.stopPropagation();
    onFocusCard();
    const start = pointerToNormalized(event, stageRef.current);
    const box = clampNormalizedBbox({
      id: createClientBboxId(),
      label: `Box ${data.boxes.length + 1}`,
      prompt: "",
      x: start.x,
      y: start.y,
      width: 0.01,
      height: 0.01,
    });

    setSelectedBoxId(box.id);
    onChange(withBboxBoxes(data, [...data.boxes, box]));
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStateRef.current = {
      boxId: box.id,
      mode: "create",
      pointerId: event.pointerId,
      startBox: box,
      startX: start.x,
      startY: start.y,
    };
  }

  function handleBoxPointerDown(mode: "move" | "resize", box: NormalizedBbox, event: PointerEvent<HTMLElement>) {
    if (event.button !== 0 || !stageRef.current) return;

    event.preventDefault();
    event.stopPropagation();
    onFocusCard();
    setSelectedBoxId(box.id);
    const start = pointerToNormalized(event, stageRef.current);

    event.currentTarget.setPointerCapture(event.pointerId);
    dragStateRef.current = {
      boxId: box.id,
      mode,
      pointerId: event.pointerId,
      startBox: box,
      startX: start.x,
      startY: start.y,
    };
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId || !stageRef.current) return;

    event.preventDefault();
    event.stopPropagation();
    const current = pointerToNormalized(event, stageRef.current);
    const deltaX = current.x - dragState.startX;
    const deltaY = current.y - dragState.startY;
    let nextBox: NormalizedBbox;

    if (dragState.mode === "create") {
      const x = Math.min(dragState.startX, current.x);
      const y = Math.min(dragState.startY, current.y);
      nextBox = clampNormalizedBbox({
        ...dragState.startBox,
        x,
        y,
        width: Math.abs(current.x - dragState.startX),
        height: Math.abs(current.y - dragState.startY),
      });
      updateBoxes(data.boxes.some((box) => box.id === nextBox.id)
        ? data.boxes.map((box) => (box.id === nextBox.id ? nextBox : box))
        : [...data.boxes, nextBox]);
      return;
    } else if (dragState.mode === "resize") {
      nextBox = clampNormalizedBbox({
        ...dragState.startBox,
        width: dragState.startBox.width + deltaX,
        height: dragState.startBox.height + deltaY,
      });
    } else {
      const x = Math.min(Math.max(dragState.startBox.x + deltaX, 0), 1 - dragState.startBox.width);
      const y = Math.min(Math.max(dragState.startBox.y + deltaY, 0), 1 - dragState.startBox.height);

      nextBox = clampNormalizedBbox({
        ...dragState.startBox,
        x,
        y,
      });
    }

    updateBox(nextBox);
  }

  function stopDrag(event: PointerEvent<HTMLDivElement>) {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    dragStateRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function deleteSelectedBox() {
    if (!selectedBoxId) return;

    const nextBoxes = data.boxes.filter((box) => box.id !== selectedBoxId);
    setSelectedBoxId(nextBoxes[0]?.id ?? null);
    updateBoxes(nextBoxes);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Delete" && event.key !== "Backspace") return;

    event.preventDefault();
    deleteSelectedBox();
  }

  return (
    <div
      className="bbox-card"
      role="group"
      aria-label={title}
      style={{ height: `${height}px` }}
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      <div className="bbox-card-toolbar" onPointerDown={(event) => event.stopPropagation()}>
        <select value={data.canvas.aspectRatio} onChange={handleAspectRatioChange} aria-label="BBox aspect ratio">
          {Object.keys(IDEOGRAM_ASPECT_DIMENSIONS).map((aspectRatio) => (
            <option key={aspectRatio} value={aspectRatio}>{aspectRatio}</option>
          ))}
        </select>
        <label>
          <span>W</span>
          <input type="number" value={data.canvas.width} min={64} max={4096} onChange={handleWidthChange} />
        </label>
        <label>
          <span>H</span>
          <input type="number" value={data.canvas.height} min={64} max={4096} onChange={handleHeightChange} />
        </label>
        <button type="button" aria-label="Delete selected bbox" title="Delete" onClick={deleteSelectedBox} disabled={!selectedBox}>
          <Trash2 size={14} aria-hidden="true" />
        </button>
      </div>
      <div className="bbox-card-prompt-row" onPointerDown={(event) => event.stopPropagation()}>
        <input
          type="text"
          value={selectedBox?.prompt ?? ""}
          placeholder="Prompt"
          aria-label="Selected bbox prompt"
          disabled={!selectedBox}
          onChange={handleSelectedPromptChange}
          onKeyDown={(event) => event.stopPropagation()}
        />
      </div>
      <div
        className="bbox-card-stage"
        ref={stageRef}
        onPointerDown={handleStagePointerDown}
        onPointerMove={handlePointerMove}
        onPointerCancel={stopDrag}
        onPointerUp={stopDrag}
      >
        {data.source?.artifactUrl && data.source.kind === "image" && (
          <img src={data.source.artifactUrl} alt={data.source.title} draggable={false} />
        )}
        {data.source?.artifactUrl && data.source.kind === "video" && (
          <video src={data.source.artifactUrl} muted playsInline preload="metadata" />
        )}
        {data.boxes.map((box) => {
          const isSelected = box.id === selectedBoxId;

          return (
            <span
              className={`bbox-card-box ${isSelected ? "selected" : ""}`}
              key={box.id}
              style={{
                left: `${box.x * 100}%`,
                top: `${box.y * 100}%`,
                width: `${box.width * 100}%`,
                height: `${box.height * 100}%`,
              }}
              title={box.prompt || box.label}
              onPointerDown={(event) => handleBoxPointerDown("move", box, event)}
            >
              <small>{box.label}</small>
              <i aria-hidden="true" onPointerDown={(event) => handleBoxPointerDown("resize", box, event)} />
            </span>
          );
        })}
      </div>
    </div>
  );
}
