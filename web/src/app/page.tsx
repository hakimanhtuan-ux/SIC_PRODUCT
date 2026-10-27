"use client";

import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  ClipboardPaste,
  Database,
  FileText,
  FileUp,
  Globe,
  Loader2,
  RotateCcw,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { DocumentStudio } from "@/components/DocumentStudio";
import { VerdictBadge } from "@/components/VerdictBadge";
import {
  fetchClaimMemory,
  fetchHealth,
  verifyDocument,
  verifyText,
  verifyUrl,
} from "@/lib/api";
import {
  ClaimMemoryOverview,
  HealthStatus,
  VerificationResponse,
} from "@/types/verification";

const SAMPLE_CASES = [
  {
    tag: "Pháp luật • Văn bản Cấp 1",
    label: "Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15",
    text: "Tại Việt Nam, Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 chính thức có hiệu lực thi hành từ ngày 01/01/2026.",
  },
  {
    tag: "Kinh tế • Thiếu ngữ cảnh",
    label: "Giá điện tăng 50% trong 1 tháng",
    text: "Giá điện đã tăng 50% chỉ trong một tháng.",
  },
  {
    tag: "Giáo dục • Trích dẫn số liệu",
    label: "Khảo sát 80% sinh viên dùng AI",
    text: "Một nghiên cứu cho thấy 80% sinh viên Việt Nam sử dụng AI trong học tập.",
  },
  {
    tag: "Ngôn từ • Giật tít & Tuyệt đối hóa",
    label: "Mọi sinh viên đều dùng AI + Clickbait",
    text: "Sự thật kinh hoàng mà không ai muốn bạn biết! Mọi sinh viên đều sử dụng trí tuệ nhân tạo trong học tập.",
  },
];

const PIPELINE_STEPS = [
  "Lớp 1–2: Chuẩn hóa dữ liệu & Bóc tách các mệnh đề nguyên tử...",
  "Lớp 3: Truy xuất bằng chứng từ Tavily, Google Fact Check & Báo chí VN...",
  "Lớp 4: Kiểm định trích dẫn (Citation Validation) & Phân tầng nguồn Cấp 1–5...",
  "Lớp 5–6: Đưa ra kết luận 6 trạng thái & Phân tích tín hiệu thao túng ngôn từ...",
];

export default function HomePage() {
  const [activeNav, setActiveNav] = useState<"STUDIO" | "MEMORY">("STUDIO");
  const [inputMode, setInputMode] = useState<"TEXT" | "DOCUMENT" | "URL">(
    "TEXT"
  );

  const [textInput, setTextInput] = useState(SAMPLE_CASES[0].text);
  const [urlInput, setUrlInput] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [redactPii, setRedactPii] = useState(false);
  const [useClaimMemory, setUseClaimMemory] = useState(true);

  const [loading, setLoading] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerificationResponse | null>(null);

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [memoryData, setMemoryData] = useState<ClaimMemoryOverview | null>(
    null
  );

  useEffect(() => {
    fetchHealth().then(setHealth);
    const timer = setInterval(() => {
      fetchHealth().then(setHealth);
    }, 6000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const extClaim = params.get("claim");
      const extUrl = params.get("url") || undefined;
      if (extClaim && extClaim.trim().length >= 5) {
        setTextInput(extClaim.trim());
        setInputMode("TEXT");
        setLoading(true);
        verifyText({
          text: extClaim.trim(),
          context_url: extUrl,
          context_title: "Kiểm chứng chuyên sâu từ TrueCheck Chrome Extension",
          use_claim_memory: true,
        })
          .then((res) => setResult(res))
          .catch((err) =>
            setError(err instanceof Error ? err.message : "Lỗi kiểm chứng.")
          )
          .finally(() => setLoading(false));
      }
    }
  }, []);

  useEffect(() => {
    if (!loading) {
      setStepIdx(0);
      return;
    }
    const interval = setInterval(() => {
      setStepIdx((prev) => (prev < PIPELINE_STEPS.length - 1 ? prev + 1 : prev));
    }, 1800);
    return () => clearInterval(interval);
  }, [loading]);

  useEffect(() => {
    if (activeNav === "MEMORY") {
      fetchClaimMemory()
        .then(setMemoryData)
        .catch(() => setMemoryData({ items: [], topic_trends: [] }));
    }
  }, [activeNav]);

  const handlePasteClipboard = async () => {
    try {
      const clip = await navigator.clipboard.readText();
      if (clip) setTextInput(clip);
    } catch {
      // ignore clipboard permission error
    }
  };

  const handleVerifySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      let res: VerificationResponse;
      if (inputMode === "TEXT") {
        res = await verifyText({
          text: textInput,
          redact_pii: redactPii,
          use_claim_memory: useClaimMemory,
        });
      } else if (inputMode === "URL") {
        res = await verifyUrl({
          url: urlInput,
          redact_pii: redactPii,
          use_claim_memory: useClaimMemory,
        });
      } else {
        if (!selectedFile) {
          throw new Error("Vui lòng chọn tệp PDF, DOCX hoặc TXT để kiểm chứng.");
        }
        res = await verifyDocument({
          file: selectedFile,
          redact_pii: redactPii,
          use_claim_memory: useClaimMemory,
          async_mode: false,
        });
      }
      setResult(res);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Không thể kết nối tới TrueCheck Verification Engine (:8000)."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Modern Glass Header */}
      <header className="tc-glass-header sticky top-0 z-30">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-2xl bg-gradient-to-br from-indigo-600 to-slate-900 flex items-center justify-center text-white shadow-md">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg tracking-tight text-slate-900">
                  TrueCheck AI
                </span>
                <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-[11px] font-bold text-indigo-700 border border-indigo-200">
                  Evidence-Based Studio
                </span>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">
                Kiểm chứng tại điểm chạm, tin tưởng dựa trên bằng chứng
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200/80">
              <button
                type="button"
                onClick={() => setActiveNav("STUDIO")}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${
                  activeNav === "STUDIO"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <SearchCheck className="h-4 w-4 text-indigo-600" />
                Bàn làm việc Kiểm chứng
              </button>
              <button
                type="button"
                onClick={() => setActiveNav("MEMORY")}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${
                  activeNav === "MEMORY"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Database className="h-4 w-4 text-indigo-600" />
                Kho Bằng chứng & Radar
              </button>
            </div>

            <div
              className={`hidden md:inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-semibold ${
                health
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : "border-amber-200 bg-amber-50 text-amber-800"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  health ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
                }`}
              />
              <span>
                {health
                  ? `Engine Sẵn sàng (${health.engine_ready_mode})`
                  : "Đang kết nối Backend (:8000)..."}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="mx-auto max-w-7xl w-full flex-1 px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {activeNav === "STUDIO" ? (
          <>
            {/* Hero Banner */}
            <div className="text-center max-w-3xl mx-auto space-y-2 pt-2">
              <div className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 border border-indigo-200/80 px-3.5 py-1 text-xs font-bold text-indigo-700">
                <Zap className="h-3.5 w-3.5" />
                Hệ thống Kiểm chứng 6 Lớp • Gemini 3.8 + Tavily + Fact Check API
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Xác minh thông tin & Rà soát tài liệu dựa trên bằng chứng gốc
              </h1>
              <p className="text-sm text-slate-600">
                Tự động tách từng mệnh đề, đối chiếu nguồn chính thống Cấp 1–5, kiểm định trích dẫn và gợi ý diễn đạt thận trọng.
              </p>
            </div>

            {/* Omnibox Input Card */}
            <section className="tc-surface-card p-6 sm:p-7">
              {/* Mode Tabs + Privacy Controls */}
              <div className="flex flex-wrap items-center justify-between gap-4 pb-5 border-b border-slate-100">
                <div className="inline-flex flex-wrap rounded-2xl bg-slate-100 p-1.5 gap-1">
                  <button
                    type="button"
                    onClick={() => setInputMode("TEXT")}
                    className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-extrabold transition ${
                      inputMode === "TEXT"
                        ? "bg-white text-indigo-700 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <FileText className="h-4 w-4" />
                    Kiểm chứng Văn bản
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputMode("DOCUMENT")}
                    className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-extrabold transition ${
                      inputMode === "DOCUMENT"
                        ? "bg-white text-indigo-700 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <FileUp className="h-4 w-4" />
                    Tải Tài liệu (PDF / DOCX / TXT)
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputMode("URL")}
                    className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-extrabold transition ${
                      inputMode === "URL"
                        ? "bg-white text-indigo-700 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <Globe className="h-4 w-4" />
                    Dán Link Bài báo (URL)
                  </button>
                </div>

                {/* Pill Toggles */}
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setRedactPii((v) => !v)}
                    className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition ${
                      redactPii
                        ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                        : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <CheckCircle2
                      className={`h-3.5 w-3.5 ${
                        redactPii ? "text-emerald-600" : "text-slate-400"
                      }`}
                    />
                    Ẩn dữ liệu cá nhân PII (Luật 91/2025)
                  </button>

                  <button
                    type="button"
                    onClick={() => setUseClaimMemory((v) => !v)}
                    className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition ${
                      useClaimMemory
                        ? "border-indigo-300 bg-indigo-50 text-indigo-800"
                        : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <Database
                      className={`h-3.5 w-3.5 ${
                        useClaimMemory ? "text-indigo-600" : "text-slate-400"
                      }`}
                    />
                    Claim Memory
                  </button>
                </div>
              </div>

              <form onSubmit={handleVerifySubmit} className="mt-5 space-y-5">
                {inputMode === "TEXT" && (
                  <div className="space-y-4">
                    <div className="relative">
                      <textarea
                        required
                        minLength={5}
                        rows={4}
                        value={textInput}
                        onChange={(e) => setTextInput(e.target.value)}
                        placeholder="Nhập hoặc dán câu tuyên bố, đoạn bài viết, số liệu thống kê cần xác minh..."
                        className="w-full rounded-2xl border border-slate-300 bg-slate-50/60 p-4 pb-10 text-base text-slate-900 leading-relaxed focus:border-indigo-600 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 focus:outline-none transition"
                      />
                      <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between text-xs text-slate-400">
                        <span>{textInput.length} ký tự</span>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={handlePasteClipboard}
                            className="inline-flex items-center gap-1 rounded-lg bg-white border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-600 hover:text-indigo-600 hover:border-indigo-200"
                          >
                            <ClipboardPaste className="h-3 w-3" />
                            Dán nhanh
                          </button>
                          {textInput && (
                            <button
                              type="button"
                              onClick={() => setTextInput("")}
                              className="inline-flex items-center gap-1 rounded-lg bg-white border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-600 hover:text-rose-600"
                            >
                              <RotateCcw className="h-3 w-3" />
                              Xóa
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Quick Sample Cards */}
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2.5">
                        Chọn nhanh tình huống kiểm thử mẫu:
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                        {SAMPLE_CASES.map((sc, i) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => setTextInput(sc.text)}
                            className={`text-left rounded-xl border p-3 transition-all ${
                              textInput === sc.text
                                ? "border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-500/15"
                                : "border-slate-200 bg-slate-50/60 hover:bg-white hover:border-indigo-300"
                            }`}
                          >
                            <div className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 mb-1">
                              {sc.tag}
                            </div>
                            <div className="text-xs font-bold text-slate-900 line-clamp-1">
                              {sc.label}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {inputMode === "DOCUMENT" && (
                  <label className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-indigo-300 bg-indigo-50/20 p-10 cursor-pointer hover:border-indigo-500 hover:bg-indigo-50/40 transition">
                    <div className="h-12 w-12 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center mb-3">
                      <FileUp className="h-6 w-6" />
                    </div>
                    <span className="text-base font-extrabold text-slate-900">
                      {selectedFile
                        ? `Đã chọn tệp: ${selectedFile.name} (${(
                            selectedFile.size / 1024
                          ).toFixed(1)} KB)`
                        : "Kéo thả hoặc nhấn để chọn tệp PDF, DOCX, TXT (Tối đa 15MB)"}
                    </span>
                    <span className="text-xs text-slate-500 mt-1">
                      Tự động tách từng mệnh đề trong tài liệu, đối chiếu bằng chứng và xuất bản PDF có tô màu chú thích.
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.docx,.txt,.md"
                      className="hidden"
                      onChange={(e) =>
                        setSelectedFile(e.target.files?.[0] || null)
                      }
                    />
                  </label>
                )}

                {inputMode === "URL" && (
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-600">
                      Đường dẫn bài báo hoặc trang thông tin công khai:
                    </label>
                    <input
                      type="url"
                      required
                      value={urlInput}
                      onChange={(e) => setUrlInput(e.target.value)}
                      placeholder="https://vnexpress.net/... hoặc https://baochinhphu.vn/..."
                      className="w-full rounded-2xl border border-slate-300 bg-slate-50/60 px-4 py-3.5 text-sm text-slate-900 focus:border-indigo-600 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 focus:outline-none"
                    />
                  </div>
                )}

                {/* Submit Bar + Live Progress Step */}
                <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
                  <div className="text-xs text-slate-500">
                    {loading ? (
                      <span className="inline-flex items-center gap-2 font-semibold text-indigo-700">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {PIPELINE_STEPS[stepIdx]}
                      </span>
                    ) : (
                      <span>
                        Nguyên tắc IFCN: Minh bạch nguồn gốc • Chưa đủ bằng chứng không đồng nghĩa với tin giả.
                      </span>
                    )}
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="tc-btn-gradient inline-flex items-center gap-2.5 rounded-2xl px-7 py-3.5 text-sm font-extrabold"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Đang kiểm chứng chuyên sâu...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        Kiểm chứng với TrueCheck AI
                      </>
                    )}
                  </button>
                </div>
              </form>

              {error && (
                <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3.5 text-xs font-semibold text-rose-800">
                  {error}
                </div>
              )}
            </section>

            {/* Studio Output */}
            {result && (
              <DocumentStudio
                key={result.document_id}
                data={result}
                onDeleted={() => setResult(null)}
              />
            )}
          </>
        ) : (
          /* Claim Memory & Rumor Radar View */
          <section className="space-y-6">
            <div className="tc-surface-card p-6">
              <h2 className="text-lg font-extrabold text-slate-900 mb-1">
                Xu hướng Chủ đề Kiểm chứng (Rumor Radar)
              </h2>
              <p className="text-xs text-slate-500 mb-4">
                Thống kê các nhóm lĩnh vực đang được truy vấn nhiều trong bộ nhớ kiểm chứng.
              </p>
              {memoryData && memoryData.topic_trends.length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {memoryData.topic_trends.map((t) => (
                    <div
                      key={t.topic}
                      className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
                    >
                      <div className="text-xs font-semibold text-indigo-600">
                        {t.topic}
                      </div>
                      <div className="text-2xl font-extrabold text-slate-900 mt-1">
                        {t.total_queries} lượt
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500">
                  Chưa có dữ liệu thống kê xu hướng. Hãy kiểm chứng một vài mệnh đề để khởi tạo kho dữ liệu!
                </p>
              )}
            </div>

            <div className="tc-surface-card p-6">
              <h2 className="text-lg font-extrabold text-slate-900 mb-4">
                Bộ nhớ Kiểm chứng Có Phiên bản (Versioned Claim Memory)
              </h2>
              <div className="space-y-3">
                {memoryData?.items.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-2xl border border-slate-200 p-4 flex flex-wrap items-center justify-between gap-3 hover:border-indigo-200 transition"
                  >
                    <div className="space-y-1.5 max-w-2xl">
                      <div className="flex flex-wrap items-center gap-2">
                        <VerdictBadge verdict={item.verdict} size="sm" />
                        <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-bold text-indigo-700">
                          {item.topic_category}
                        </span>
                        <span className="text-xs text-slate-400">
                          Phiên bản v{item.version} • {item.evidence_count} nguồn •{" "}
                          {item.hit_count} lượt tra cứu
                        </span>
                      </div>
                      <p className="text-sm font-bold text-slate-900">
                        {item.normalized_claim}
                      </p>
                    </div>
                    <div className="text-right text-xs text-slate-500">
                      <div>
                        Xác minh:{" "}
                        {new Date(item.verified_at).toLocaleDateString("vi-VN")}
                      </div>
                      <div>
                        Hết hạn:{" "}
                        {new Date(item.expires_at).toLocaleDateString("vi-VN")}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
