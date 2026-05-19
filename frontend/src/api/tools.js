const API_URL = import.meta.env.VITE_API_URL ?? "";

export async function listTools() {
  const response = await fetch(`${API_URL}/api/tools`);

  if (!response.ok) {
    throw new Error("Tool list request failed");
  }

  return response.json();
}
