import {
  ClaimMemoryOverview,
  HealthStatus,
  VerdictType,
  VerificationResponse,
} from "@/types/verification";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function parseApiError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    return data.detail || `Lỗi máy chủ (${res.status})`;
  } catch {
    return `Không thể kết nối hoặc lỗi phản hồi (${res.status})`;
  }
}

export async function fetchHealth(): Promise<HealthStatus | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/health`, {
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
  const res = await fetch(`${API_BASE_URL}/api/v1/verify/text`, {
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
  const res = await fetch(`${API_BASE_URL}/api/v1/verify/url`, {
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

  const res = await fetch(`${API_BASE_URL}/api/v1/verify/document`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  const data = await res.json();

  // If async Celery worker queued the job, poll until completion
  if (data.job_id && data.status && !data.claims) {
    return pollJobUntilComplete(data.job_id);
  }
  return data as VerificationResponse;
}

async function pollJobUntilComplete(jobId: string): Promise<VerificationResponse> {
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}`);
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
  const res = await fetch(`${API_BASE_URL}/api/v1/claims/memory?limit=25`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ClaimMemoryOverview;
}

export async function deleteDocumentSession(docId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/v1/documents/${docId}`, {
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
  const res = await fetch(`${API_BASE_URL}/api/v1/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return await res.json();
}

export function getReportExportUrl(docId: string): string {
  return `${API_BASE_URL}/api/v1/documents/${docId}/export/report`;
}

export function getAnnotatedPdfExportUrl(docId: string): string {
  return `${API_BASE_URL}/api/v1/documents/${docId}/export/annotated-pdf`;
}

