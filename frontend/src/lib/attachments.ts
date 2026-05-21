import type { AgentAttachment, AgentAttachmentKind } from "../types";

export const ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024;
export const ATTACHMENT_TOTAL_MAX_BYTES = 15 * 1024 * 1024;

const TEXT_EXTENSIONS = new Set(["csv", "md", "txt", "xml", "yaml", "yml"]);

function getFileExtension(fileName: string): string {
  return fileName.split(".").pop()?.toLowerCase() ?? "";
}

export function getAttachmentKind(file: File): AgentAttachmentKind {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("audio/")) return "audio";
  if (file.type === "application/json" || getFileExtension(file.name) === "json") return "json";
  if (file.type === "application/pdf" || getFileExtension(file.name) === "pdf") return "pdf";
  if (file.type.startsWith("text/") || TEXT_EXTENSIONS.has(getFileExtension(file.name))) return "text";

  return "artifact";
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}

function readAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read file"));
    reader.readAsText(file);
  });
}

function createAttachmentId(file: File): string {
  const randomId = crypto.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`;
  const safeName = file.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  return `attachment_${safeName || "file"}_${randomId.replaceAll("-", "")}`;
}

export async function createAgentAttachments(
  files: FileList | File[],
  initialTotalBytes = 0,
): Promise<AgentAttachment[]> {
  const attachments: AgentAttachment[] = [];
  let totalBytes = initialTotalBytes;

  for (const file of Array.from(files)) {
    const kind = getAttachmentKind(file);
    const baseAttachment = {
      id: createAttachmentId(file),
      name: file.name,
      mimeType: file.type || "application/octet-stream",
      size: file.size,
      kind,
    };
    const exceedsLimit = file.size > ATTACHMENT_MAX_BYTES || totalBytes + file.size > ATTACHMENT_TOTAL_MAX_BYTES;

    if (exceedsLimit) {
      attachments.push({
        ...baseAttachment,
        omitted: true,
        reason: "size-limit",
      });
      continue;
    }

    try {
      totalBytes += file.size;
      if (kind === "text" || kind === "json") {
        attachments.push({
          ...baseAttachment,
          text: await readAsText(file),
        });
        continue;
      }

      attachments.push({
        ...baseAttachment,
        dataUrl: await readAsDataUrl(file),
      });
    } catch {
      attachments.push({
        ...baseAttachment,
        omitted: true,
        reason: "read-error",
      });
    }
  }

  return attachments;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
