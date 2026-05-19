const API_URL = import.meta.env.VITE_API_URL ?? "";

export async function createToolJob(payload) {
  const response = await fetch(`${API_URL}/api/tool-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Tool job request failed");
  }

  return response.json();
}

export async function getToolJob(jobId) {
  const response = await fetch(`${API_URL}/api/tool-jobs/${jobId}`);

  if (!response.ok) {
    throw new Error("Tool job lookup failed");
  }

  return response.json();
}

export async function listToolJobs({ status } = {}) {
  const searchParams = new URLSearchParams();

  if (status) {
    searchParams.set("status", status);
  }

  const query = searchParams.toString();
  const response = await fetch(`${API_URL}/api/tool-jobs${query ? `?${query}` : ""}`);

  if (!response.ok) {
    throw new Error("Tool job list request failed");
  }

  return response.json();
}

export async function waitForToolJob(jobId, { intervalMs = 400, maxAttempts = 30 } = {}) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const job = await getToolJob(jobId);

    if (job.status === "succeeded" || job.status === "failed") {
      return job;
    }

    await new Promise((resolve) => {
      window.setTimeout(resolve, intervalMs);
    });
  }

  throw new Error("Tool job timed out");
}
