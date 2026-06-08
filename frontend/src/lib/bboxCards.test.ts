import { createBboxCardDocument } from "./cardDocuments";
import {
  clampNormalizedBbox,
  IDEOGRAM_ASPECT_DIMENSIONS,
  ideogramBboxFromNormalized,
  normalizeBboxData,
} from "./bboxCards";
import type { CardDocument } from "../types";

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${message}\nExpected: ${JSON.stringify(expected)}\nActual: ${JSON.stringify(actual)}`);
  }
}

function mediaCard(id: string, kind: "image" | "video"): CardDocument {
  return {
    id,
    name: `${kind} source`,
    prompt: "source",
    html: "",
    metadata: {
      kind,
      title: `${kind} source`,
      artifactUrl: `/api/artifacts/${kind}/source.${kind === "image" ? "png" : "mp4"}`,
      width: 1280,
      height: 720,
    },
  };
}

assertEqual(
  ideogramBboxFromNormalized({ x: 0.12, y: 0.18, width: 0.3, height: 0.4 }),
  [180, 120, 580, 420],
  "converts normalized coordinates to Ideogram y_min,x_min,y_max,x_max",
);

assertEqual(
  clampNormalizedBbox({ id: "box", label: "Box", x: -0.2, y: 0.9, width: 2, height: 0.5 }).ideogramBbox,
  [900, 0, 1000, 1000],
  "clamps boxes inside normalized bounds",
);

assertEqual(IDEOGRAM_ASPECT_DIMENSIONS["21:9"], { width: 1344, height: 576 }, "keeps Ideogram 21:9 preset");
assertEqual(IDEOGRAM_ASPECT_DIMENSIONS["3:2"], { width: 1248, height: 832 }, "keeps Ideogram 3:2 preset");

const whiteCard = createBboxCardDocument({ aspectRatio: "16:9" });
const whiteData = normalizeBboxData(whiteCard.metadata?.bboxData);
assertEqual(whiteCard.metadata?.kind, "bbox", "creates a bbox card");
assertEqual(whiteData.source, null, "white bbox card has no source");
assertEqual(whiteData.canvas, { width: 1360, height: 768, aspectRatio: "16:9" }, "white bbox uses preset dimensions");

const imageCard = createBboxCardDocument({ sourceDocument: mediaCard("image_1", "image") });
const imageData = normalizeBboxData(imageCard.metadata?.bboxData);
assertEqual(imageData.source?.kind, "image", "image source is stored in metadata");
assertEqual(imageData.source?.artifactUrl, "/api/artifacts/image/source.png", "image artifact is preserved");

const videoCard = createBboxCardDocument({ sourceDocument: mediaCard("video_1", "video") });
const videoData = normalizeBboxData(videoCard.metadata?.bboxData);
assertEqual(videoData.source?.kind, "video", "video source is stored in metadata");
assertEqual(videoData.source?.artifactUrl, "/api/artifacts/video/source.mp4", "video artifact is preserved");

console.log("bboxCards tests passed");
