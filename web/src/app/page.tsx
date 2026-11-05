"use client";

import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  ClipboardPaste,
  Database,
  FileText,
  FileUp,
  Globe,
  Image as ImageIcon,
  Loader2,
  RotateCcw,
  Scan,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { DocumentStudio } from "@/components/DocumentStudio";
import { ImageForensicsStudio } from "@/components/ImageForensicsStudio";
import { VerdictBadge } from "@/components/VerdictBadge";
import {
  fetchClaimMemory,
  fetchHealth,
  verifyDocument,
  verifyImage,
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
  {
    tag: "Đa mệnh đề • Biểu đồ tròn (%)",
    label: "Bản tin tổng hợp đa trạng thái",
    text: "Tại Việt Nam, Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 có hiệu lực từ ngày 01/01/2026. Giá điện sinh hoạt đã tăng 50% chỉ trong một tháng qua. Theo tôi, trí tuệ nhân tạo là công nghệ thú vị nhất thập kỷ này.",
  },
];

const PIPELINE_STEPS = [
  "Lớp 1–2: Chuẩn hóa dữ liệu & Bóc tách mệnh đề siêu tốc...",
  "Lớp 3: Truy xuất song song từ Tavily, Fact Check API & Báo chí VN...",
  "Lớp 4–6: Kiểm định trích dẫn, Kết luận 6 trạng thái & Tạo biểu đồ (%)...",
];

const IMAGE_PIPELINE_STEPS = [
  "Bước 1/3: Quét cấu trúc tệp ảnh & bản đồ soi vết cắt ghép...",
  "Bước 2/3: Kiểm tra lỗi ảnh do AI tạo, lỗi ghép mặt & chỉnh sửa...",
  "Bước 3/3: Khoanh vùng vị trí lỗi & tổng hợp biểu đồ tròn (%)...",
];

export default function HomePage() {
  const [activeNav, setActiveNav] = useState<"STUDIO" | "MEMORY">("STUDIO");
  const [inputMode, setInputMode] = useState<
    "TEXT" | "IMAGE" | "DOCUMENT" | "URL"
  >("TEXT");

  const [textInput, setTextInput] = useState(SAMPLE_CASES[0].text);
  const [urlInput, setUrlInput] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);

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
    }, 30000);
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
          context_title: "Kiểm chứng chuyên sâu từ FactCheck Assistent Extension",
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
    }, 850);
    return () => clearInterval(interval);
  }, [loading]);

  useEffect(() => {
    if (activeNav === "MEMORY") {
      fetchClaimMemory()
        .then(setMemoryData)
        .catch(() => setMemoryData({ items: [], topic_trends: [] }));
    }
  }, [activeNav]);

  useEffect(() => {
    if (!selectedImage) {
      setImagePreviewUrl(null);
      return;
    }
    const objUrl = URL.createObjectURL(selectedImage);
    setImagePreviewUrl(objUrl);
    return () => URL.revokeObjectURL(objUrl);
  }, [selectedImage]);

  const handleGlobalPaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.startsWith("image/")) {
        const pastedFile = item.getAsFile();
        if (pastedFile) {
          e.preventDefault();
          setSelectedImage(pastedFile);
          setInputMode("IMAGE");
          setError(null);
          return;
        }
      }
    }
  };

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
      } else if (inputMode === "IMAGE") {
        if (!selectedImage) {
          throw new Error(
            "Vui lòng chọn ảnh hoặc nhấn Ctrl+V dán bức ảnh cần kiểm tra."
          );
        }
        res = await verifyImage({
          file: selectedImage,
          redact_pii: redactPii,
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
          : "Không thể kết nối tới FactCheck Assistent Verification Engine (:8000)."
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
                  FactCheck Assistent
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
                className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${activeNav === "STUDIO"
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
                className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition ${activeNav === "MEMORY"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                  }`}
              >
                <Database className="h-4 w-4 text-indigo-600" />
                Kho Bằng chứng & Radar
              </button>
            </div>

            <div
              className={`hidden md:inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-semibold ${health
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : "border-amber-200 bg-amber-50 text-amber-800"
                }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${health ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
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
                Kiểm chứng 6 Lớp & Giám định Ảnh Deepfake / ELA • Gemini 3.8 Multimodal
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Xác minh tin tức, tài liệu & giám định ảnh chỉnh sửa / ghép mặt AI
              </h1>
              <p className="text-sm text-slate-600">
                Đối chiếu nguồn chính thống Cấp 1–5 cho văn bản, đồng thời phân tích bản đồ nhiệt ELA, dấu vết cắt ghép và ghép giả khuôn mặt (Deepfake) cho hình ảnh.
              </p>
            </div>

            {/* Omnibox Input Card */}
            <section
              onPaste={handleGlobalPaste}
              className="tc-surface-card p-6 sm:p-7"
            >
              {/* Mode Tabs + Privacy Controls */}
              <div className="flex flex-wrap items-center justify-between gap-4 pb-5 border-b border-slate-100">
                <div className="inline-flex flex-wrap rounded-2xl bg-slate-100 p-1.5 gap-1">
                  <button
                    type="button"
                    onClick={() => setInputMode("TEXT")}
                    className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-extrabold transition ${inputMode === "TEXT"
                        ? "bg-white text-indigo-700 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                      }`}
                  >
                    <FileText className="h-4 w-4" />
                    Kiểm chứng Văn bản
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setInputMode("IMAGE");
                      setError(null);
                    }}
                    className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-extrabold transition ${inputMode === "IMAGE"
                        ? "bg-white text-indigo-700 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                      }`}
                  >
                    <Scan className="h-4 w-4 text-rose-600" />
                    Kiểm tra Ảnh Thật / Giả
                    <span className="rounded-full bg-rose-100 px-1.5 py-0.5 text-[9px] font-extrabold text-rose-700">
                      MỚI
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputMode("DOCUMENT")}
                    className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-extrabold transition ${inputMode === "DOCUMENT"
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
                    className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-extrabold transition ${inputMode === "URL"
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
                    className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition ${redactPii
                        ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                        : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                      }`}
                  >
                    <CheckCircle2
                      className={`h-3.5 w-3.5 ${redactPii ? "text-emerald-600" : "text-slate-400"
                        }`}
                    />
                    Ẩn dữ liệu cá nhân PII (Luật 91/2025)
                  </button>

                  <button
                    type="button"
                    onClick={() => setUseClaimMemory((v) => !v)}
                    className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition ${useClaimMemory
                        ? "border-indigo-300 bg-indigo-50 text-indigo-800"
                        : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                      }`}
                  >
                    <Database
                      className={`h-3.5 w-3.5 ${useClaimMemory ? "text-indigo-600" : "text-slate-400"
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
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
                        {SAMPLE_CASES.map((sc, i) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => setTextInput(sc.text)}
                            className={`text-left rounded-xl border p-3 transition-all ${textInput === sc.text
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

                {inputMode === "IMAGE" && (
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const dropped = e.dataTransfer.files?.[0];
                      if (dropped && dropped.type.startsWith("image/")) {
                        setSelectedImage(dropped);
                        setError(null);
                      }
                    }}
                    className="rounded-2xl border-2 border-dashed border-indigo-300 bg-gradient-to-br from-indigo-50/30 via-white to-rose-50/25 p-6 transition hover:border-indigo-500"
                  >
                    {selectedImage && imagePreviewUrl ? (
                      <div className="flex flex-col sm:flex-row items-center gap-5">
                        <div className="relative rounded-2xl overflow-hidden border border-slate-200 bg-slate-950 shrink-0">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={imagePreviewUrl}
                            alt="Xem trước ảnh kiểm tra"
                            className="h-40 w-56 object-contain"
                          />
                        </div>
                        <div className="flex-1 space-y-2 text-center sm:text-left">
                          <div className="inline-flex items-center gap-1.5 rounded-full bg-indigo-100 px-3 py-0.5 text-[11px] font-extrabold text-indigo-800">
                            <ImageIcon className="h-3.5 w-3.5" />
                            Sẵn sàng kiểm tra Ảnh Thật / Giả
                          </div>
                          <div className="text-sm font-extrabold text-slate-900 break-all">
                            {selectedImage.name} (
                            {(selectedImage.size / 1024).toFixed(1)} KB)
                          </div>
                          <p className="text-xs text-slate-500">
                            AI sẽ kiểm tra xem đây có phải ảnh thật nguyên bản không, và khoanh vùng chỉ rõ các lỗi nếu là ảnh do AI tạo, ảnh ghép mặt (Deepfake), ảnh qua chỉnh sửa / cắt ghép hoặc các lỗi bất thường khác.
                          </p>
                          <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 pt-1">
                            <label className="inline-flex items-center gap-1.5 rounded-xl bg-white border border-slate-300 px-3 py-1.5 text-xs font-bold text-slate-700 cursor-pointer hover:border-indigo-400 hover:text-indigo-700">
                              Chọn ảnh khác
                              <input
                                type="file"
                                accept=".jpg,.jpeg,.png,.webp,.bmp,.heic,.heif,image/*"
                                className="hidden"
                                onChange={(e) =>
                                  setSelectedImage(e.target.files?.[0] || null)
                                }
                              />
                            </label>
                            <button
                              type="button"
                              onClick={() => setSelectedImage(null)}
                              className="inline-flex items-center gap-1 rounded-xl bg-white border border-rose-200 px-3 py-1.5 text-xs font-bold text-rose-600 hover:bg-rose-50"
                            >
                              <RotateCcw className="h-3.5 w-3.5" />
                              Gỡ ảnh
                            </button>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <label className="flex flex-col items-center justify-center py-7 cursor-pointer text-center">
                        <div className="h-14 w-14 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center mb-3 shadow-sm">
                          <Scan className="h-7 w-7" />
                        </div>
                        <span className="text-base font-extrabold text-slate-900">
                          Kéo thả ảnh vào đây, nhấn chọn ảnh hoặc bấm{" "}
                          <kbd className="rounded bg-slate-200 px-1.5 py-0.5 text-xs font-mono text-slate-800">
                            Ctrl+V
                          </kbd>{" "}
                          để dán trực tiếp
                        </span>
                        <span className="text-xs text-slate-500 mt-1.5 max-w-xl">
                          Kiểm tra ảnh thật hay giả • Chỉ điểm trực tiếp lỗi ảnh do AI tạo, lỗi ghép mặt (Deepfake), lỗi qua chỉnh sửa / cắt ghép & các dấu hiệu bất thường khác.
                        </span>
                        <input
                          type="file"
                          accept=".jpg,.jpeg,.png,.webp,.bmp,.heic,.heif,image/*"
                          className="hidden"
                          onChange={(e) =>
                            setSelectedImage(e.target.files?.[0] || null)
                          }
                        />
                      </label>
                    )}
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
                        {inputMode === "IMAGE"
                          ? IMAGE_PIPELINE_STEPS[stepIdx]
                          : PIPELINE_STEPS[stepIdx]}
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
                        {inputMode === "IMAGE"
                          ? "Đang soi lỗi hình ảnh..."
                          : "Đang kiểm chứng chuyên sâu..."}
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        {inputMode === "IMAGE"
                          ? "Kiểm tra Ảnh Thật / Giả & Thông tin"
                          : "Kiểm chứng với FactCheck Assistent"}
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
            {result &&
              (result.image_forensics ? (
                <ImageForensicsStudio
                  key={`img-${result.document_id}`}
                  data={result}
                  onDeleted={() => setResult(null)}
                />
              ) : (
                <DocumentStudio
                  key={result.document_id}
                  data={result}
                  onDeleted={() => setResult(null)}
                />
              ))}
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
