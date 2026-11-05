import {
  ClaimMemoryOverview,
  HealthStatus,
  VerdictType,
  VerificationResponse,
} from "@/types/verification";
import {
  getStandaloneClaimMemory,
  getStandaloneHealth,
  verifyImageInBrowser,
  verifyTextInBrowser,
} from "./browserEngine";

const RENDER_BACKEND_URL = "https://sic-product-1.onrender.com";
const EXPLICIT_API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || RENDER_BACKEND_URL;

/**
 * Smart multi-path fetch:
 * 1. On public deployed domains (GitHub Pages, Vercel, Render, etc.): connects directly to Render Backend (`https://sic-product-1.onrender.com`).
 * 2. On local development (`localhost` / `127.0.0.1`): tries local Backend (`http://127.0.0.1:8000`) first if running, then automatically falls back to Render Backend (`https://sic-product-1.onrender.com`).
 */
async function apiFetch(endpoint: string, init?: RequestInit): Promise<Response> {
  const isLocalBrowser =
    typeof window !== "undefined" &&
    (window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1");

  const candidates = isLocalBrowser
    ? ["http://127.0.0.1:8000", EXPLICIT_API_URL]
    : [EXPLICIT_API_URL];

  let lastErr: unknown = null;
  for (const base of candidates) {
    try {
      const res = await fetch(`${base}${endpoint}`, init);
      if (
        (res.status === 404 ||
          res.status === 405 ||
          res.status === 502 ||
          res.status === 504) &&
        base === "http://127.0.0.1:8000"
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
      : "Không thể kết nối tới máy chủ kiểm chứng AI (cổng 8000)."
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
    if (!res.ok) return getStandaloneHealth();
    return (await res.json()) as HealthStatus;
  } catch {
    return getStandaloneHealth();
  }
}

export async function verifyText(params: {
  text: string;
  context_url?: string;
  context_title?: string;
  redact_pii?: boolean;
  use_claim_memory?: boolean;
}): Promise<VerificationResponse> {
  try {
    const res = await apiFetch("/api/v1/verify/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error(await parseApiError(res));
    return (await res.json()) as VerificationResponse;
  } catch (err) {
    if (err instanceof Error && err.message.includes("cổng 8000")) {
      return verifyTextInBrowser(params);
    }
    throw err;
  }
}

export async function verifyUrl(params: {
  url: string;
  redact_pii?: boolean;
  use_claim_memory?: boolean;
}): Promise<VerificationResponse> {
  try {
    const res = await apiFetch("/api/v1/verify/url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error(await parseApiError(res));
    return (await res.json()) as VerificationResponse;
  } catch (err) {
    if (err instanceof Error && err.message.includes("cổng 8000")) {
      return verifyTextInBrowser({
        text: `Kiểm chứng nội dung bài viết tại đường dẫn: ${params.url}`,
        context_url: params.url,
        context_title: params.url,
      });
    }
    throw err;
  }
}

export async function verifyDocument(params: {
  file: File;
  redact_pii: boolean;
  use_claim_memory: boolean;
  async_mode?: boolean;
}): Promise<VerificationResponse> {
  try {
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
  } catch (err) {
    if (err instanceof Error && err.message.includes("cổng 8000")) {
      const rawText = await params.file.text().catch(() => "");
      return verifyTextInBrowser({
        text: rawText.slice(0, 4000) || `Tài liệu tải lên: ${params.file.name}`,
        context_title: params.file.name,
      });
    }
    throw err;
  }
}

export async function verifyImage(params: {
  file: File;
  redact_pii: boolean;
}): Promise<VerificationResponse> {
  try {
    const form = new FormData();
    form.append("file", params.file);
    form.append("redact_pii", String(params.redact_pii));

    const res = await apiFetch("/api/v1/verify/image", {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error(await parseApiError(res));
    return (await res.json()) as VerificationResponse;
  } catch (err) {
    if (err instanceof Error && err.message.includes("cổng 8000")) {
      return verifyImageInBrowser(params.file);
    }
    throw err;
  }
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
  try {
    const res = await apiFetch("/api/v1/claims/memory?limit=25", {
      cache: "no-store",
    });
    if (!res.ok) return getStandaloneClaimMemory();
    return (await res.json()) as ClaimMemoryOverview;
  } catch {
    return getStandaloneClaimMemory();
  }
}

export async function deleteDocumentSession(docId: string): Promise<void> {
  try {
    const res = await apiFetch(`/api/v1/documents/${docId}`, {
      method: "DELETE",
    });
    if (!res.ok) return;
  } catch {
    return;
  }
}

export async function submitDisputeFeedback(params: {
  document_id?: string;
  claim_text: string;
  reported_verdict: VerdictType;
  suggested_verdict?: VerdictType;
  reason: string;
  evidence_url?: string;
}): Promise<{ message: string }> {
  try {
    const res = await apiFetch("/api/v1/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error(await parseApiError(res));
    return await res.json();
  } catch {
    return {
      message: "Đã ghi nhận phản hồi đóng góp của bạn.",
    };
  }
}

export function getReportExportUrl(docId: string): string {
  return `${EXPLICIT_API_URL}/api/v1/documents/${docId}/export/report`;
}

export function getAnnotatedPdfExportUrl(docId: string): string {
  return `${EXPLICIT_API_URL}/api/v1/documents/${docId}/export/annotated-pdf`;
}
