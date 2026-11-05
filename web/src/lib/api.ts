import {
  ClaimMemoryOverview,
  HealthStatus,
  VerdictType,
  VerificationResponse,
} from "@/types/verification";

const EXPLICIT_API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

/**
 * Smart multi-path fetch:
 * 1. Uses explicit NEXT_PUBLIC_API_URL if configured.
 * 2. Uses same-origin `/api/v1/...` via Next.js rewrite proxy (when running on Next.js server/Vercel).
 * 3. Automatically falls back to `http://127.0.0.1:8000` and `http://localhost:8000`.
 */
async function apiFetch(endpoint: string, init?: RequestInit): Promise<Response> {
  const isStaticGithubPages =
    typeof window !== "undefined" &&
    window.location.hostname.endsWith("github.io");

  const candidates = EXPLICIT_API_URL
    ? [EXPLICIT_API_URL, "http://127.0.0.1:8000", "http://localhost:8000"]
    : isStaticGithubPages
      ? ["http://127.0.0.1:8000", "http://localhost:8000"]
      : ["", "http://127.0.0.1:8000", "http://localhost:8000"];

  let lastErr: unknown = null;
  for (const base of candidates) {
    try {
      const res = await fetch(`${base}${endpoint}`, init);
      // If Next.js proxy or static host returned 404/405/502/504 on relative path, try next candidate
      if (
        (res.status === 404 ||
          res.status === 405 ||
          res.status === 502 ||
          res.status === 504) &&
        base === ""
      ) {
        continue;
      }
      return res;
    } catch (err) {
      lastErr = err;
    }
  }

  throw new Error(
    lastErr instanceof Error && lastErr.message && lastErr.message !== "Failed to fetch"
      ? lastErr.message
      : "Không thể kết nối tới máy chủ kiểm chứng AI (cổng 8000). Vui lòng đợi vài giây hoặc chạy lại run_all.bat."
  );
}

async function parseApiError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg || "").join("; ") || `Lỗi dữ liệu (${res.status})`;
    }
    return `Lỗi máy chủ (${res.status})`;
  } catch {
    return `Không thể xử lý phản hồi từ máy chủ (mã ${res.status}).`;
  }
}

export async function fetchHealth(): Promise<HealthStatus | null> {
  try {
    const res = await apiFetch("/api/v1/health", {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as HealthStatus;
  } catch {
    return null;
  }
}

export async function verifyText(params: {
  text: string;
  context_url?: string;
  context_title?: string;
  redact_pii?: boolean;
  use_claim_memory?: boolean;
}): Promise<VerificationResponse> {
  const res = await apiFetch("/api/v1/verify/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as VerificationResponse;
}

export async function verifyUrl(params: {
  url: string;
  redact_pii?: boolean;
  use_claim_memory?: boolean;
}): Promise<VerificationResponse> {
  const res = await apiFetch("/api/v1/verify/url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as VerificationResponse;
}

export async function verifyDocument(params: {
  file: File;
  redact_pii: boolean;
  use_claim_memory: boolean;
  async_mode?: boolean;
}): Promise<VerificationResponse> {
  const form = new FormData();
  form.append("file", params.file);
  form.append("redact_pii", String(params.redact_pii));
  form.append("use_claim_memory", String(params.use_claim_memory));
  form.append("async_mode", String(Boolean(params.async_mode)));

  const res = await apiFetch("/api/v1/verify/document", {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  const data = await res.json();

  if (data.job_id && data.status && !data.claims) {
    return pollJobUntilComplete(data.job_id);
  }
  return data as VerificationResponse;
}

export async function verifyImage(params: {
  file: File;
  redact_pii: boolean;
}): Promise<VerificationResponse> {
  const form = new FormData();
  form.append("file", params.file);
  form.append("redact_pii", String(params.redact_pii));

  const res = await apiFetch("/api/v1/verify/image", {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as VerificationResponse;
}

async function pollJobUntilComplete(jobId: string): Promise<VerificationResponse> {
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const res = await apiFetch(`/api/v1/jobs/${jobId}`);
    if (!res.ok) throw new Error(await parseApiError(res));
    const job = await res.json();
    if (job.status === "COMPLETED" && job.result) {
      return job.result as VerificationResponse;
    }
    if (job.status === "FAILED") {
      throw new Error(job.error_message || "Xử lý tài liệu thất bại.");
    }
  }
  throw new Error("Quá thời gian chờ xử lý tài liệu dài.");
}

export async function fetchClaimMemory(): Promise<ClaimMemoryOverview> {
  const res = await apiFetch("/api/v1/claims/memory?limit=25", {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClaimMemoryOverview;
}

export async function deleteDocumentSession(docId: string): Promise<void> {
  const res = await apiFetch(`/api/v1/documents/${docId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
}

export async function submitDisputeFeedback(params: {
  document_id?: string;
  claim_text: string;
  reported_verdict: VerdictType;
  suggested_verdict?: VerdictType;
  reason: string;
  evidence_url?: string;
}): Promise<{ message: string }> {
  const res = await apiFetch("/api/v1/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return await res.json();
}

export function getReportExportUrl(docId: string): string {
  return `${EXPLICIT_API_URL}/api/v1/documents/${docId}/export/report`;
}

export function getAnnotatedPdfExportUrl(docId: string): string {
  return `${EXPLICIT_API_URL}/api/v1/documents/${docId}/export/annotated-pdf`;
}
