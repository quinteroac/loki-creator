const API_URL = import.meta.env.VITE_API_URL ?? "";

type ArchiveArtifactsResponse = {
  artifacts: Array<{
    artifactUrl: string;
    deletedPath?: string | null;
    status: string;
  }>;
};

export type ImportedArtifact = {
  artifactUrl: string;
  name: string;
  mimeType: string;
  size: number;
};

export async function archiveArtifacts(artifactUrls: string[]): Promise<ArchiveArtifactsResponse> {
  if (artifactUrls.length === 0) {
    return { artifacts: [] };
  }

  const response = await fetch(`${API_URL}/api/artifacts/archive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ artifactUrls }),
  });

  if (!response.ok) {
    throw new Error(`Failed to archive artifacts: ${response.status}`);
  }

  return response.json();
}

export async function importArtifact(file: File): Promise<ImportedArtifact> {
  const formData = new FormData();
  formData.set("file", file);

  const response = await fetch(`${API_URL}/api/artifacts/import`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Failed to import artifact: ${response.status}`);
  }

  return response.json();
}
