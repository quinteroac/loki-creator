const API_URL = import.meta.env.VITE_API_URL ?? "";

export async function sendInstruction(payload) {
  const response = await fetch(`${API_URL}/api/instructions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Instruction request failed");
  }

  return response.json();
}
