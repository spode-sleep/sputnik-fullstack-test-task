import type { AlertItem, FileItem } from "@/types";

const API_BASE = "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`Запрос завершился с ошибкой: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchFiles(): Promise<FileItem[]> {
  const res = await fetch(`${API_BASE}/files`, { cache: "no-store" });
  return handleResponse<FileItem[]>(res);
}

export async function fetchAlerts(): Promise<AlertItem[]> {
  const res = await fetch(`${API_BASE}/alerts`, { cache: "no-store" });
  return handleResponse<AlertItem[]>(res);
}

export async function uploadFile(title: string, file: File): Promise<FileItem> {
  const formData = new FormData();
  formData.append("title", title.trim());
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/files`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<FileItem>(res);
}

export function getDownloadUrl(fileId: string): string {
  return `${API_BASE}/files/${fileId}/download`;
}
