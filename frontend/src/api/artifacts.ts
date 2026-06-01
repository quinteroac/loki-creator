const API_URL = import.meta.env.VITE_API_URL ?? "";

type ArchiveArtifactsResponse = {
  artifacts: Array<{
    artifactUrl: string;
    deletedPath?: string | null;
    status: string;
  }>;
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
