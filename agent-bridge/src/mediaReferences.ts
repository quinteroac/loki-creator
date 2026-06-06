import { lstat } from "node:fs/promises";
import { resolve } from "node:path";
import { repoRoot } from "./config";
import type { AgentAttachment, AgentRunRequest, SelectedCardSnapshot } from "./types";

export type LocalMediaKind = "image" | "video" | "audio";

export type LocalMediaReference = {
  kind: LocalMediaKind;
  artifactUrl: string;
  path: string;
  source: "selected-card-metadata" | "selected-card-media-asset" | "attachment";
  cardId?: string;
  attachmentId?: string;
  mimeType?: string;
};

const localMediaKinds = new Set<LocalMediaKind>(["image", "video", "audio"]);

function isLocalMediaKind(value: unknown): value is LocalMediaKind {
  return typeof value === "string" && localMediaKinds.has(value as LocalMediaKind);
}

export function resolveLocalArtifactPath(src: string) {
  if (!src.startsWith("/api/artifacts/")) {
    throw new Error(`Media reference must be a Loki artifact URL, got: ${src.slice(0, 80) || "empty"}`);
  }

  let relativeArtifactPath = "";
  try {
    relativeArtifactPath = decodeURIComponent(src.slice("/api/artifacts/".length));
  } catch {
    throw new Error(`Invalid encoded artifact URL: ${src}`);
  }

  const artifactsRoot = resolve(repoRoot, ".loki");
  const artifactPath = resolve(artifactsRoot, relativeArtifactPath);
  if (artifactPath === artifactsRoot || !artifactPath.startsWith(`${artifactsRoot}/`)) {
    throw new Error(`Artifact URL escapes Loki artifacts root: ${src}`);
  }

  return artifactPath;
}

async function requireExistingFile(src: string) {
  const artifactPath = resolveLocalArtifactPath(src);
  const stat = await lstat(artifactPath).catch((error) => {
    throw new Error(`Artifact does not exist for media reference ${src}: ${error instanceof Error ? error.message : String(error)}`);
  });
  if (!stat.isFile()) {
    throw new Error(`Artifact media reference is not a file: ${src}`);
  }
  return artifactPath;
}

async function addReference(
  references: LocalMediaReference[],
  seen: Set<string>,
  reference: Omit<LocalMediaReference, "path">,
) {
  const key = `${reference.kind}:${reference.artifactUrl}`;
  if (seen.has(key)) return;
  const path = await requireExistingFile(reference.artifactUrl);
  seen.add(key);
  references.push({ ...reference, path });
}

async function collectSnapshotReferences(
  snapshot: SelectedCardSnapshot,
  references: LocalMediaReference[],
  seen: Set<string>,
) {
  const metadata = snapshot.metadata ?? {};
  if (isLocalMediaKind(metadata.kind) && typeof metadata.artifactUrl === "string" && metadata.artifactUrl.trim()) {
    await addReference(references, seen, {
      kind: metadata.kind,
      artifactUrl: metadata.artifactUrl.trim(),
      source: "selected-card-metadata",
      cardId: snapshot.id,
    });
  }

  for (const asset of snapshot.mediaAssets ?? []) {
    if (asset.omitted || !isLocalMediaKind(asset.kind) || !asset.src?.trim()) continue;
    await addReference(references, seen, {
      kind: asset.kind,
      artifactUrl: asset.src.trim(),
      source: "selected-card-media-asset",
      cardId: snapshot.id,
      mimeType: asset.mimeType,
    });
  }
}

async function collectAttachmentReference(
  attachment: AgentAttachment,
  references: LocalMediaReference[],
  seen: Set<string>,
) {
  if (attachment.omitted || !isLocalMediaKind(attachment.kind)) return;
  const artifactUrl = attachment.artifactUrl?.trim() || attachment.src?.trim();
  if (!artifactUrl) return;
  await addReference(references, seen, {
    kind: attachment.kind,
    artifactUrl,
    source: "attachment",
    attachmentId: attachment.id,
    mimeType: attachment.mimeType,
  });
}

export async function collectLocalMediaReferences(request: AgentRunRequest) {
  const references: LocalMediaReference[] = [];
  const seen = new Set<string>();

  for (const snapshot of request.selectedCardSnapshots ?? []) {
    await collectSnapshotReferences(snapshot, references, seen);
  }

  for (const attachment of request.attachments ?? []) {
    await collectAttachmentReference(attachment, references, seen);
  }

  return references;
}
