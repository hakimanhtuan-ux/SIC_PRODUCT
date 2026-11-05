"use client";

import React, { useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleDot,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  FileDown,
  FileText,
  Flame,
  Globe,
  Image as ImageIcon,
  Layers,
  Palette,
  PieChart as PieChartIcon,
  Scan,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  Wand2,
} from "lucide-react";
import { EvidenceList } from "./EvidenceList";
import { VERDICT_META } from "./VerdictBadge";
import {
  deleteDocumentSession,
  getAnnotatedPdfExportUrl,
  getReportExportUrl,
} from "@/lib/api";
import {
  ForensicRegionBox,
  ImageAuthenticityType,
  VerificationResponse,
} from "@/types/verification";

interface AuthenticityTheme {
  headline: string;
  badgeBg: string;
  badgeText: string;
  badgeBorder: string;
  bannerBg: string;
  bannerBorder: string;
  isReal: boolean;
  isColorOnlyEdit?: boolean;
}

const AUTHENTICITY_THEME: Record<ImageAuthenticityType, AuthenticityTheme> = {
  AUTHENTIC_LIKELY: {
    headline: "KẾT LUẬN: ĐÂY LÀ ẢNH THẬT / NGUYÊN BẢN",
    badgeBg: "bg-emerald-100",
    badgeText: "text-emerald-900",
    badgeBorder: "border-emerald-300",
    bannerBg: "bg-gradient-to-r from-emerald-50 via-white to-teal-50/70",
    bannerBorder: "border-emerald-300",
    isReal: true,
  },
  EDITED_COLOR_OR_RETOUCH: {
    headline: "ẢNH CHỤP THẬT — NHƯNG ĐÃ QUA CHỈNH MÀU / BỘ LỌC HẬU KỲ",
    badgeBg: "bg-sky-100",
    badgeText: "text-sky-950",
    badgeBorder: "border-sky-300",
    bannerBg: "bg-gradient-to-r from-sky-50 via-white to-amber-50/60",
    bannerBorder: "border-sky-300",
    isReal: false,
    isColorOnlyEdit: true,
  },
  AI_GENERATED: {
    headline: "CẢNH BÁO: KHÔNG PHẢI ẢNH THẬT — ẢNH / ẤN PHẨM DO AI TẠO SINH",
    badgeBg: "bg-violet-100",
    badgeText: "text-violet-900",
    badgeBorder: "border-violet-300",
    bannerBg: "bg-gradient-to-r from-violet-50 via-white to-indigo-50/70",
    bannerBorder: "border-violet-300",
    isReal: false,
  },
  FACE_SWAP_OR_DEEPFAKE: {
    headline: "CẢNH BÁO: ẢNH GIẢ MẠO — PHÁT HIỆN THAY / GHÉP MẶT BẰNG AI",
    badgeBg: "bg-rose-100",
    badgeText: "text-rose-900",
    badgeBorder: "border-rose-300",
    bannerBg: "bg-gradient-to-r from-rose-50 via-white to-red-50/70",
    bannerBorder: "border-rose-300",
    isReal: false,
  },
  EDITED_OR_SPLICED: {
    headline: "PHÁT HIỆN: ẢNH ĐÃ QUA CẮT GHÉP / CHỈNH SỬA CHI TIẾT",
    badgeBg: "bg-amber-100",
    badgeText: "text-amber-900",
    badgeBorder: "border-amber-300",
    bannerBg: "bg-gradient-to-r from-amber-50 via-white to-orange-50/70",
    bannerBorder: "border-amber-300",
    isReal: false,
  },
  SCREENSHOT_OR_MEME: {
    headline: "PHÁT HIỆN: ẤN PHẨM THIẾT KẾ BẰNG ỨNG DỤNG ĐỒ HỌA (CANVA / PHOTOSHOP) / ẢNH CHỤP MÀN HÌNH",
    badgeBg: "bg-indigo-100",
    badgeText: "text-indigo-900",
    badgeBorder: "border-indigo-300",
    bannerBg: "bg-gradient-to-r from-indigo-50 via-white to-sky-50/70",
    bannerBorder: "border-indigo-300",
    isReal: false,
  },
  INCONCLUSIVE_LOW_QUALITY: {
    headline: "CHƯA ĐỦ KẾT LUẬN — ẢNH MỜ VỠ / NÉN NHIỀU LẦN",
    badgeBg: "bg-slate-100",
    badgeText: "text-slate-800",
    badgeBorder: "border-slate-300",
    bannerBg: "bg-gradient-to-r from-slate-50 via-white to-amber-50/40",
    bannerBorder: "border-slate-300",
    isReal: false,
  },
};

const ERROR_CATEGORY_META: Record<
  string,
  { label: string; badgeClass: string }
> = {
  AI_GENERATED_ERROR: {
    label: "Lỗi ảnh do AI tạo",
    badgeClass: "bg-violet-100 text-violet-900 border-violet-300",
  },
  AI_ARTIFACT: {
    label: "Lỗi ảnh do AI tạo",
    badgeClass: "bg-violet-100 text-violet-900 border-violet-300",
  },
  FACE_SWAP_ERROR: {
    label: "Lỗi ghép mặt / Deepfake",
    badgeClass: "bg-rose-100 text-rose-900 border-rose-300",
  },
  FACE_ANOMALY: {
    label: "Lỗi ghép mặt / Deepfake",
    badgeClass: "bg-rose-100 text-rose-900 border-rose-300",
  },
  COLOR_GRADING_ERROR: {
    label: "Đã chỉnh màu / Bộ lọc ánh sáng",
    badgeClass: "bg-sky-100 text-sky-900 border-sky-300",
  },
  EDIT_SPLICE_ERROR: {
    label: "Lỗi cắt ghép / chỉnh sửa",
    badgeClass: "bg-amber-100 text-amber-950 border-amber-300",
  },
  SPLICING: {
    label: "Lỗi cắt ghép / chỉnh sửa",
    badgeClass: "bg-amber-100 text-amber-950 border-amber-300",
  },
  EDITED_TEXT: {
    label: "Lỗi chèn / sửa chữ",
    badgeClass: "bg-amber-100 text-amber-950 border-amber-300",
  },
  LIGHTING: {
    label: "Lỗi ánh sáng / bóng đổ",
    badgeClass: "bg-orange-100 text-orange-950 border-orange-300",
  },
  OTHER_ERROR: {
    label: "Lỗi bất thường khác",
    badgeClass: "bg-slate-100 text-slate-900 border-slate-300",
  },
};

function polarToCartesian(cx: number, cy: number, r: number, angleRad: number) {
  return {
    x: cx + r * Math.cos(angleRad),
    y: cy + r * Math.sin(angleRad),
  };
}

function buildSectorPath(
  cx: number,
  cy: number,
  outerR: number,
  innerR: number,
  startAngle: number,
  endAngle: number
): string {
  const delta = endAngle - startAngle;
  const largeArc = delta > Math.PI ? 1 : 0;
  const oStart = polarToCartesian(cx, cy, outerR, startAngle);
  const oEnd = polarToCartesian(cx, cy, outerR, endAngle);

  if (innerR <= 0) {
    return [
      `M ${cx} ${cy}`,
      `L ${oStart.x.toFixed(2)} ${oStart.y.toFixed(2)}`,
      `A ${outerR} ${outerR} 0 ${largeArc} 1 ${oEnd.x.toFixed(2)} ${oEnd.y.toFixed(2)}`,
      "Z",
    ].join(" ");
  }

  const iStart = polarToCartesian(cx, cy, innerR, startAngle);
  const iEnd = polarToCartesian(cx, cy, innerR, endAngle);
  return [
    `M ${oStart.x.toFixed(2)} ${oStart.y.toFixed(2)}`,
    `A ${outerR} ${outerR} 0 ${largeArc} 1 ${oEnd.x.toFixed(2)} ${oEnd.y.toFixed(2)}`,
    `L ${iEnd.x.toFixed(2)} ${iEnd.y.toFixed(2)}`,
    `A ${innerR} ${innerR} 0 ${largeArc} 0 ${iStart.x.toFixed(2)} ${iStart.y.toFixed(2)}`,
    "Z",
  ].join(" ");
}

function ErrorOverlayStage({
  imageUrl,
  altText,
  regions,
  showBoxes,
  activeRegionId,
  onSelectRegion,
  badgeLabel,
}: {
  imageUrl: string;
  altText: string;
  regions: ForensicRegionBox[];
  showBoxes: boolean;
  activeRegionId: string | null;
  onSelectRegion: (id: string | null) => void;
  badgeLabel: string;
}) {
  return (
    <div className="relative rounded-2xl overflow-hidden bg-slate-950 border border-slate-800 flex items-center justify-center min-h-[280px]">
      <div className="relative inline-block max-w-full">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl}
          alt={altText}
          className="block max-h-[500px] w-auto max-w-full object-contain select-none"
        />

        <span className="pointer-events-none absolute top-2.5 left-2.5 rounded-lg bg-slate-900/80 backdrop-blur px-2.5 py-1 text-[11px] font-bold text-white border border-white/15">
          {badgeLabel}
        </span>

        {showBoxes &&
          regions.map((reg, index) => {
            const [ymin = 0, xmin = 0, ymax = 1000, xmax = 1000] = reg.box_2d;
            const topPct = Math.max(0, Math.min(96, ymin / 10));
            const leftPct = Math.max(0, Math.min(96, xmin / 10));
            const heightPct = Math.max(
              4,
              Math.min(100 - topPct, (ymax - ymin) / 10)
            );
            const widthPct = Math.max(
              4,
              Math.min(100 - leftPct, (xmax - xmin) / 10)
            );

            const isSelected = activeRegionId === reg.region_id;
            const borderColor = reg.category.includes("AI")
              ? "border-violet-400 bg-violet-500/15"
              : reg.category.includes("FACE")
                ? "border-rose-500 bg-rose-500/15"
                : reg.category.includes("COLOR")
                  ? "border-sky-400 bg-sky-400/10"
                  : "border-amber-400 bg-amber-400/15";

            const tagBg = reg.category.includes("AI")
              ? "bg-violet-600 text-white"
              : reg.category.includes("FACE")
                ? "bg-rose-600 text-white"
                : reg.category.includes("COLOR")
                  ? "bg-sky-600 text-white"
                  : "bg-amber-500 text-slate-950";

            return (
              <button
                key={reg.region_id}
                type="button"
                onClick={() =>
                  onSelectRegion(isSelected ? null : reg.region_id)
                }
                onMouseEnter={() => onSelectRegion(reg.region_id)}
                style={{
                  top: `${topPct}%`,
                  left: `${leftPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPct}%`,
                }}
                className={`absolute border-2 rounded-lg transition-all cursor-pointer ${borderColor} ${isSelected
                    ? "ring-4 ring-white/90 z-20 scale-[1.01]"
                    : "hover:ring-2 hover:ring-white/70 z-10"
                  }`}
                title={`Điểm #${index + 1}: ${reg.label_vi}`}
              >
                <span
                  className={`absolute top-1 left-1 max-w-[240px] truncate rounded-md px-2 py-0.5 text-[10px] font-extrabold shadow ${tagBg}`}
                >
                  #{index + 1}: {reg.label_vi}
                </span>
              </button>
            );
          })}
      </div>
    </div>
  );
}

export function ImageForensicsStudio({
  data,
  onDeleted,
}: {
  data: VerificationResponse;
  onDeleted: () => void;
}) {
  const forensics = data.image_forensics;
  const [viewMode, setViewMode] = useState<"ORIGINAL" | "ELA" | "SPLIT">(
    "ORIGINAL"
  );
  const [showBoxes, setShowBoxes] = useState(true);
  const [activeRegionId, setActiveRegionId] = useState<string | null>(
    forensics?.suspicious_regions?.[0]?.region_id || null
  );
  const [chartStyle, setChartStyle] = useState<"PIE" | "DONUT">("PIE");
  const [hoveredSliceId, setHoveredSliceId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [ocrCopied, setOcrCopied] = useState(false);

  const textClaims = useMemo(
    () => data.claims.filter((c) => c.claim_id !== "IMG01"),
    [data.claims]
  );

  const handleCopyOcr = async () => {
    if (!forensics?.extracted_ocr_text) return;
    try {
      await navigator.clipboard.writeText(forensics.extracted_ocr_text);
      setOcrCopied(true);
      setTimeout(() => setOcrCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  const originSlices = useMemo(() => {
    if (!forensics) return [];
    const p = forensics.origin_probabilities;
    return [
      {
        id: "AUTHENTIC",
        label: "Ảnh thật tự nhiên (Nguyên bản)",
        shortLabel: "Ảnh thật tự nhiên",
        value: p.authentic_pct,
        color: "#059669",
      },
      {
        id: "EDITED",
        label: "Qua chỉnh màu / bộ lọc / cắt ghép",
        shortLabel: "Chỉnh màu / Chỉnh sửa",
        value: p.edited_spliced_pct,
        color: "#d97706",
      },
      {
        id: "FACESWAP",
        label: "Ảnh ghép mặt / Deepfake",
        shortLabel: "Ghép mặt / Deepfake",
        value: p.face_swap_deepfake_pct,
        color: "#dc2626",
      },
      {
        id: "AIGEN",
        label: "Ảnh do AI tạo sinh (GenAI)",
        shortLabel: "Ảnh do AI tạo",
        value: p.ai_generated_pct,
        color: "#7c3aed",
      },
    ];
  }, [forensics]);

  const computedArcs = useMemo(() => {
    const nonZero = originSlices.filter((s) => s.value > 0);
    const total = nonZero.reduce((acc, s) => acc + s.value, 0);
    if (total <= 0) return [];
    let currentAngle = -Math.PI / 2;
    return nonZero.map((s) => {
      const fraction = s.value / total;
      const sweep = fraction * Math.PI * 2;
      const startAngle = currentAngle;
      const endAngle = currentAngle + sweep;
      const midAngle = startAngle + sweep / 2;
      currentAngle = endAngle;
      return {
        ...s,
        fraction,
        pctText: `${(fraction * 100).toFixed(1).replace(/\.0$/, "")}%`,
        startAngle,
        endAngle,
        midAngle,
      };
    });
  }, [originSlices]);

  if (!forensics) return null;

  const theme =
    AUTHENTICITY_THEME[forensics.authenticity_verdict] ||
    AUTHENTICITY_THEME.INCONCLUSIVE_LOW_QUALITY;
  const tech = forensics.technical;
  const dominantArc =
    computedArcs.find((a) => a.id === hoveredSliceId) ||
    [...computedArcs].sort((a, b) => b.value - a.value)[0] ||
    null;

  const handleDelete = async () => {
    if (!window.confirm("Xóa bức ảnh và kết quả kiểm tra này khỏi hệ thống?")) {
      return;
    }
    setDeleting(true);
    try {
      await deleteDocumentSession(data.document_id);
      onDeleted();
    } catch {
      setDeleting(false);
    }
  };

  const pieSize = 180;
  const cx = pieSize / 2;
  const cy = pieSize / 2;
  const outerR = 78;
  const innerR = chartStyle === "DONUT" ? 45 : 0;

  return (
    <section className="space-y-6">
      {/* 1. KẾT LUẬN CHÍNH */}
      <div
        className={`rounded-3xl border-2 p-6 shadow-sm ${theme.bannerBg} ${theme.bannerBorder}`}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2 max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1 text-xs font-extrabold ${theme.badgeBg} ${theme.badgeText} ${theme.badgeBorder}`}
              >
                {theme.isReal ? (
                  <ShieldCheck className="h-4 w-4" />
                ) : theme.isColorOnlyEdit ? (
                  <Palette className="h-4 w-4" />
                ) : forensics.authenticity_verdict ===
                  "FACE_SWAP_OR_DEEPFAKE" ? (
                  <ShieldAlert className="h-4 w-4" />
                ) : (
                  <AlertTriangle className="h-4 w-4" />
                )}
                {forensics.authenticity_label_vi}
              </span>

              <span className="inline-flex items-center gap-1 rounded-full bg-white border border-slate-200 px-3 py-1 text-xs font-bold text-slate-800">
                <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
                Độ tin cậy: {forensics.tamper_confidence_pct}% •{" "}
                {(data.processing_time_ms / 1000).toFixed(1)}s
              </span>
            </div>

            <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900">
              {theme.headline}
            </h2>
            <p className="text-sm font-medium text-slate-800 leading-relaxed">
              {forensics.summary_explanation_vi}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <a
              href={getReportExportUrl(data.document_id)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl bg-white border border-slate-200 px-3.5 py-2 text-xs font-bold text-slate-700 hover:border-indigo-300 hover:text-indigo-700 shadow-sm transition"
            >
              <FileDown className="h-4 w-4" />
              Báo cáo (.MD)
            </a>
            <a
              href={getAnnotatedPdfExportUrl(data.document_id)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-indigo-700 shadow-sm transition"
            >
              <FileDown className="h-4 w-4" />
              Xuất PDF
            </a>
            <button
              type="button"
              disabled={deleting}
              onClick={handleDelete}
              className="inline-flex items-center gap-1.5 rounded-xl bg-white border border-rose-200 px-3 py-2 text-xs font-bold text-rose-700 hover:bg-rose-50 transition"
            >
              <Trash2 className="h-4 w-4" />
              Xóa ảnh
            </button>
          </div>
        </div>
      </div>

      {/* 2. BÀN SOI ẢNH (TRÁI) & CHỈ ĐIỂM LỖI + BIỂU ĐỒ TRÒN % (PHẢI) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* CỘT TRÁI (7 cột): Khung ảnh khoanh vùng trực tiếp */}
        <div className="lg:col-span-7 tc-surface-card p-5 sm:p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center border border-indigo-100">
                <Scan className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-extrabold text-slate-900">
                  Khoanh vùng kiểm tra trên ảnh
                </h3>
                <p className="text-xs font-medium text-slate-600">
                  {forensics.suspicious_regions.length > 0
                    ? `Đánh dấu ${forensics.suspicious_regions.length} vùng phát hiện chỉnh màu / can thiệp / lỗi giả mạo`
                    : "Không phát hiện vùng cắt ghép, chỉnh màu hay lỗi AI trên khung hình"}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200/80">
                <button
                  type="button"
                  onClick={() => setViewMode("ORIGINAL")}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold transition ${viewMode === "ORIGINAL"
                      ? "bg-white text-indigo-700 shadow-sm"
                      : "text-slate-600 hover:text-slate-900"
                    }`}
                >
                  <ImageIcon className="h-3.5 w-3.5" />
                  Ảnh gốc
                </button>
                {tech.ela_heatmap_data_url && (
                  <>
                    <button
                      type="button"
                      onClick={() => setViewMode("ELA")}
                      className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold transition ${viewMode === "ELA"
                          ? "bg-white text-rose-700 shadow-sm"
                          : "text-slate-600 hover:text-slate-900"
                        }`}
                    >
                      <Flame className="h-3.5 w-3.5" />
                      Soi nhiệt cắt ghép
                    </button>
                    <button
                      type="button"
                      onClick={() => setViewMode("SPLIT")}
                      className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold transition ${viewMode === "SPLIT"
                          ? "bg-white text-indigo-700 shadow-sm"
                          : "text-slate-600 hover:text-slate-900"
                        }`}
                    >
                      <Layers className="h-3.5 w-3.5" />
                      Song song
                    </button>
                  </>
                )}
              </div>

              {forensics.suspicious_regions.length > 0 && (
                <button
                  type="button"
                  onClick={() => setShowBoxes((v) => !v)}
                  className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition ${showBoxes
                      ? "border-indigo-300 bg-indigo-50 text-indigo-800"
                      : "border-slate-200 bg-slate-50 text-slate-600"
                    }`}
                >
                  {showBoxes ? (
                    <Eye className="h-3.5 w-3.5" />
                  ) : (
                    <EyeOff className="h-3.5 w-3.5" />
                  )}
                  {showBoxes ? "Đang hiện khung" : "Đã ẩn khung"}
                </button>
              )}
            </div>
          </div>

          {tech.preview_data_url && (
            <>
              {viewMode === "ORIGINAL" && (
                <ErrorOverlayStage
                  imageUrl={tech.preview_data_url}
                  altText={data.source_title}
                  regions={forensics.suspicious_regions}
                  showBoxes={showBoxes}
                  activeRegionId={activeRegionId}
                  onSelectRegion={setActiveRegionId}
                  badgeLabel="Ảnh kiểm tra"
                />
              )}

              {viewMode === "ELA" && tech.ela_heatmap_data_url && (
                <ErrorOverlayStage
                  imageUrl={tech.ela_heatmap_data_url}
                  altText="Bản đồ soi vùng cắt ghép"
                  regions={forensics.suspicious_regions}
                  showBoxes={showBoxes}
                  activeRegionId={activeRegionId}
                  onSelectRegion={setActiveRegionId}
                  badgeLabel="Bản đồ nhiệt soi vết cắt ghép"
                />
              )}

              {viewMode === "SPLIT" && tech.ela_heatmap_data_url && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <ErrorOverlayStage
                    imageUrl={tech.preview_data_url}
                    altText={data.source_title}
                    regions={forensics.suspicious_regions}
                    showBoxes={showBoxes}
                    activeRegionId={activeRegionId}
                    onSelectRegion={setActiveRegionId}
                    badgeLabel="Ảnh gốc"
                  />
                  <ErrorOverlayStage
                    imageUrl={tech.ela_heatmap_data_url}
                    altText="Bản đồ soi vùng cắt ghép"
                    regions={forensics.suspicious_regions}
                    showBoxes={showBoxes}
                    activeRegionId={activeRegionId}
                    onSelectRegion={setActiveRegionId}
                    badgeLabel="Soi nhiệt cắt ghép"
                  />
                </div>
              )}
            </>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3.5 text-xs space-y-1">
              <div className="font-extrabold text-slate-900 flex items-center gap-1.5">
                <Wand2 className="h-3.5 w-3.5 text-rose-600" />
                Khuôn mặt ({forensics.faces_detected} mặt • Rủi ro ghép:{" "}
                {Math.round(forensics.face_swap_risk_pct)}%)
              </div>
              <p className="text-slate-700 leading-relaxed">
                {forensics.face_analysis_vi}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3.5 text-xs space-y-1">
              <div className="font-extrabold text-slate-900 flex items-center gap-1.5">
                <Palette className="h-3.5 w-3.5 text-indigo-600" />
                Màu sắc, Bộ lọc & Ánh sáng
              </div>
              <p className="text-slate-700 leading-relaxed">
                {forensics.lighting_and_blend_vi}
              </p>
            </div>
          </div>
        </div>

        {/* CỘT PHẢI (5 cột): CHỈ ĐIỂM CÁC LỖI & BIỂU ĐỒ TRÒN (%) RÕ NÉT */}
        <div className="lg:col-span-5 space-y-6">
          {/* Card 1: CHỈ ĐIỂM LỖI / DẤU HIỆU */}
          <div className="tc-surface-card p-5 space-y-4">
            <div className="border-b border-slate-100 pb-3">
              <h3 className="text-base font-extrabold text-slate-900">
                {theme.isReal
                  ? "Kết quả rà soát lỗi & chỉnh sửa"
                  : "Chỉ điểm các lỗi / dấu hiệu can thiệp"}
              </h3>
              <p className="text-xs font-medium text-slate-600 mt-0.5">
                {theme.isReal
                  ? "Đã kiểm tra cấu trúc AI, viền ghép mặt, dải màu RGB và vết cắt ghép"
                  : "Nhấn vào từng mục bên dưới để đối chiếu vị trí trên ảnh"}
              </p>
            </div>

            {theme.isReal && forensics.suspicious_regions.length === 0 ? (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4 space-y-2.5">
                <div className="flex items-center gap-2 text-[13px] font-extrabold text-emerald-950">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  Ảnh gốc tự nhiên — Không phát hiện lỗi AI, ghép mặt hay chỉnh màu
                </div>
                <ul className="space-y-1.5">
                  {forensics.forensic_signals.map((sig, idx) => (
                    <li
                      key={idx}
                      className="flex items-start gap-2 text-xs font-medium text-emerald-900"
                    >
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-emerald-600 shrink-0" />
                      <span>{sig}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="space-y-3">
                {forensics.suspicious_regions.map((reg, index) => {
                  const active = activeRegionId === reg.region_id;
                  const catMeta =
                    ERROR_CATEGORY_META[reg.category] ||
                    ERROR_CATEGORY_META.OTHER_ERROR;
                  return (
                    <button
                      key={reg.region_id}
                      type="button"
                      onClick={() =>
                        setActiveRegionId(active ? null : reg.region_id)
                      }
                      onMouseEnter={() => setActiveRegionId(reg.region_id)}
                      className={`w-full text-left rounded-2xl border p-3.5 transition ${active
                          ? "border-indigo-500 bg-indigo-50/50 ring-2 ring-indigo-500/15"
                          : "border-slate-200 bg-slate-50/70 hover:bg-white hover:border-indigo-300"
                        }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="rounded-md bg-slate-900 px-2 py-0.5 text-[11px] font-extrabold text-white">
                            Điểm #{index + 1}
                          </span>
                          <span
                            className={`rounded-md border px-2 py-0.5 text-[11px] font-extrabold ${catMeta.badgeClass}`}
                          >
                            {catMeta.label}
                          </span>
                        </span>
                        <span className="text-[11px] font-bold text-slate-600">
                          Độ rõ: {Math.round(reg.confidence * 100)}%
                        </span>
                      </div>
                      <div className="text-[13px] font-extrabold text-slate-900 mb-1">
                        {reg.label_vi}
                      </div>
                      <p className="text-xs font-medium text-slate-700 leading-relaxed">
                        {reg.explanation_vi}
                      </p>
                    </button>
                  );
                })}

                {forensics.forensic_signals.length > 0 && (
                  <div className="rounded-2xl border border-slate-200 bg-white p-3.5 space-y-2">
                    <div className="text-xs font-extrabold text-slate-900">
                      Các dấu hiệu chi tiết ghi nhận được:
                    </div>
                    <ul className="space-y-1.5">
                      {forensics.forensic_signals.map((sig, idx) => (
                        <li
                          key={idx}
                          className="flex items-start gap-2 text-xs font-medium text-slate-800"
                        >
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
                          <span>{sig}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {(tech.software_traces.length > 0 || tech.c2pa_or_ai_watermark) && (
              <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs font-medium text-amber-950">
                <strong>Dấu vết công cụ trong tệp ảnh:</strong>{" "}
                {[...tech.software_traces, tech.c2pa_or_ai_watermark]
                  .filter(Boolean)
                  .join(" • ")}
              </div>
            )}
          </div>

          {/* Card 2: BIỂU ĐỒ TRÒN PHÂN LOẠI ẢNH (%) — CHÚ THÍCH RỘNG RÃI, ĐẬM RÕ 100% */}
          <div className="tc-surface-card p-5 space-y-4">
            <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-[15px] font-extrabold text-slate-900">
                  Biểu đồ Tròn Phân loại Ảnh (%)
                </h3>
                <p className="text-xs font-medium text-slate-600 mt-0.5">
                  Tỷ lệ khả năng giữa ảnh thật, chỉnh màu/sửa, ghép mặt và AI tạo
                </p>
              </div>
              <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200/80 shrink-0">
                <button
                  type="button"
                  onClick={() => setChartStyle("PIE")}
                  className={`rounded-lg p-1.5 text-xs font-bold transition ${chartStyle === "PIE"
                      ? "bg-white text-indigo-700 shadow-sm"
                      : "text-slate-600"
                    }`}
                  title="Biểu đồ Tròn"
                >
                  <PieChartIcon className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setChartStyle("DONUT")}
                  className={`rounded-lg p-1.5 text-xs font-bold transition ${chartStyle === "DONUT"
                      ? "bg-white text-indigo-700 shadow-sm"
                      : "text-slate-600"
                    }`}
                  title="Biểu đồ Vành khuyên"
                >
                  <CircleDot className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Xếp dọc: Biểu đồ tròn căn giữa bên trên + Bảng chú thích 100% chiều rộng bên dưới */}
            <div className="flex flex-col items-center gap-4">
              <div
                className="relative shrink-0"
                style={{ width: pieSize, height: pieSize }}
              >
                <svg
                  width={pieSize}
                  height={pieSize}
                  viewBox={`0 0 ${pieSize} ${pieSize}`}
                  className="overflow-visible drop-shadow-sm"
                >
                  {computedArcs.length === 1 ? (
                    chartStyle === "DONUT" ? (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={(outerR + innerR) / 2}
                        fill="none"
                        stroke={computedArcs[0].color}
                        strokeWidth={outerR - innerR}
                      />
                    ) : (
                      <>
                        <circle
                          cx={cx}
                          cy={cy}
                          r={outerR}
                          fill={computedArcs[0].color}
                          stroke="#ffffff"
                          strokeWidth={2.5}
                        />
                        <text
                          x={cx}
                          y={cy}
                          textAnchor="middle"
                          dominantBaseline="central"
                          className="fill-white text-xl font-extrabold pointer-events-none drop-shadow"
                        >
                          100%
                        </text>
                      </>
                    )
                  ) : (
                    computedArcs.map((arc) => {
                      const isHovered = hoveredSliceId === arc.id;
                      const push = isHovered ? 5 : 0;
                      const ox = Math.cos(arc.midAngle) * push;
                      const oy = Math.sin(arc.midAngle) * push;
                      const labelR =
                        chartStyle === "DONUT"
                          ? (outerR + innerR) / 2
                          : outerR * 0.6;
                      const lpos = polarToCartesian(cx, cy, labelR, arc.midAngle);
                      return (
                        <g
                          key={arc.id}
                          transform={`translate(${ox.toFixed(2)}, ${oy.toFixed(2)})`}
                          onMouseEnter={() => setHoveredSliceId(arc.id)}
                          onMouseLeave={() => setHoveredSliceId(null)}
                          className="transition-transform duration-200 cursor-pointer"
                        >
                          <path
                            d={buildSectorPath(
                              cx,
                              cy,
                              outerR,
                              innerR,
                              arc.startAngle,
                              arc.endAngle
                            )}
                            fill={arc.color}
                            stroke="#ffffff"
                            strokeWidth={2.5}
                          />
                          {arc.fraction >= 0.08 && (
                            <text
                              x={lpos.x}
                              y={lpos.y}
                              textAnchor="middle"
                              dominantBaseline="central"
                              className="fill-white text-xs font-extrabold pointer-events-none drop-shadow"
                            >
                              {Math.round(arc.fraction * 100)}%
                            </text>
                          )}
                        </g>
                      );
                    })
                  )}
                </svg>

                {chartStyle === "DONUT" && dominantArc && (
                  <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center px-5">
                    <span
                      className="text-xl font-extrabold leading-none"
                      style={{ color: dominantArc.color }}
                    >
                      {dominantArc.pctText}
                    </span>
                    <span className="text-[11px] font-bold text-slate-700 mt-1 leading-tight">
                      {dominantArc.shortLabel}
                    </span>
                  </div>
                )}
              </div>

              {/* Chú thích đầy đủ chiều ngang, chữ đậm rõ, kèm thanh tỷ lệ trực quan */}
              <div className="w-full space-y-2">
                {originSlices.map((s) => {
                  const pctStr = `${s.value.toFixed(1).replace(/\.0$/, "")}%`;
                  return (
                    <div
                      key={s.id}
                      onMouseEnter={() => setHoveredSliceId(s.id)}
                      onMouseLeave={() => setHoveredSliceId(null)}
                      className={`w-full rounded-xl px-3.5 py-2.5 border transition ${hoveredSliceId === s.id
                          ? "bg-indigo-50/60 border-indigo-400 shadow-sm"
                          : "bg-slate-50/80 border-slate-200/90"
                        }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2.5 min-w-0">
                          <span
                            className="h-3.5 w-3.5 rounded-[4px] shrink-0 shadow-sm"
                            style={{ backgroundColor: s.color }}
                          />
                          <span className="text-[13px] font-bold text-slate-900 leading-snug">
                            {s.label}
                          </span>
                        </span>
                        <span className="shrink-0 text-[13px] font-extrabold text-slate-950 tabular-nums">
                          {pctStr}
                        </span>
                      </div>
                      <div className="mt-1.5 h-1.5 w-full rounded-full bg-slate-200/80 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{
                            width: `${Math.max(s.value > 0 ? 3 : 0, s.value)}%`,
                            backgroundColor: s.color,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 2: KIỂM CHỨNG DỮ KIỆN & NỘI DUNG THÔNG TIN TRONG ẢNH (DUAL FORENSICS + FACT-CHECKING) */}
      <div className="tc-surface-card p-6 space-y-6 border-t-4 border-t-indigo-600">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-200/80 pb-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 border border-indigo-200 px-3 py-1 text-xs font-extrabold text-indigo-700 mb-2">
              <BookOpen className="h-3.5 w-3.5" />
              Dual Forensics & Fact-Checking Engine (Chuẩn Quốc tế & Việt Nam)
            </div>
            <h3 className="text-lg font-black text-slate-900 tracking-tight">
              Kiểm chứng Thông tin & Dữ kiện trên Hình ảnh (Khi đủ điều kiện xác nhận)
            </h3>
            <p className="text-xs font-medium text-slate-600 mt-1 max-w-2xl">
              Hệ thống phân biệt rõ <strong>Thiết kế bằng ứng dụng đồ họa (Canva/Photoshop)</strong> với <strong>Ảnh AI tạo sinh (theo chuẩn DeepAI Detector & Học thuật DIRE/NPR)</strong>, đồng thời đọc văn bản (OCR) và tự động đối chiếu các thông tin đủ điều kiện xác minh với <strong>tingia.gov.vn</strong>, <strong>bocongan.gov.vn</strong>, <strong>politifact.com</strong> & <strong>Cơ sở dữ liệu Học thuật Quốc tế (OpenAlex/DOI)</strong>.
            </p>
            <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
              <span className="rounded-md bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[11px] font-bold text-emerald-800">
                ✓ tingia.gov.vn (Trung tâm Xử lý Tin giả VN)
              </span>
              <span className="rounded-md bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[11px] font-bold text-emerald-800">
                ✓ bocongan.gov.vn (Bộ Công an)
              </span>
              <span className="rounded-md bg-sky-50 border border-sky-200 px-2 py-0.5 text-[11px] font-bold text-sky-800">
                ✓ PolitiFact.com (IFCN Truth-O-Meter)
              </span>
              <span className="rounded-md bg-violet-50 border border-violet-200 px-2 py-0.5 text-[11px] font-bold text-violet-800">
                ✓ DeepAI Image Detector & CVPR DIRE
              </span>
              <span className="rounded-md bg-amber-50 border border-amber-200 px-2 py-0.5 text-[11px] font-bold text-amber-900">
                ✓ OpenAlex / Crossref DOI (Tài liệu Học thuật)
              </span>
            </div>
          </div>

          {textClaims.length > 0 && (
            <div className="inline-flex items-center gap-2 rounded-xl bg-slate-100 border border-slate-200 px-3 py-2 text-xs font-bold text-slate-800 self-start sm:self-auto shrink-0">
              <Sparkles className="h-4 w-4 text-indigo-600" />
              <span>Đã kiểm chứng: <strong>{textClaims.length}</strong> mệnh đề</span>
            </div>
          )}
        </div>

        {/* 1. OCR Text extracted from image */}
        {forensics.extracted_ocr_text ? (
          <div className="rounded-2xl border border-slate-200/90 bg-slate-50/80 p-4 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-slate-700">
                <FileText className="h-4 w-4 text-indigo-600" />
                Văn bản nhận diện từ ảnh (OCR):
              </span>
              <button
                type="button"
                onClick={handleCopyOcr}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition"
              >
                {ocrCopied ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    <span className="text-emerald-700">Đã chép</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    <span>Sao chép chữ</span>
                  </>
                )}
              </button>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs font-medium text-slate-800 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
              {forensics.extracted_ocr_text}
            </div>
          </div>
        ) : null}

        {/* 2. Fact-Checking results for claims inside the image */}
        {textClaims.length > 0 ? (
          <div className="space-y-4">
            <h4 className="text-sm font-extrabold text-slate-900 flex items-center gap-2">
              <span>Danh sách Mệnh đề & Kết quả Đối chiếu:</span>
              <span className="text-xs font-semibold text-slate-500">
                (Nhấp vào từng mệnh đề để xem bằng chứng truy xuất)
              </span>
            </h4>

            <div className="space-y-4">
              {textClaims.map((claim, idx) => {
                const verdictMeta = VERDICT_META[claim.verdict] || VERDICT_META.INSUFFICIENT_EVIDENCE;
                return (
                  <div
                    key={claim.claim_id}
                    className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:border-indigo-300 transition space-y-4"
                  >
                    {/* Header: ID + Verdict badge */}
                    <div className="flex flex-wrap items-center justify-between gap-2.5 border-b border-slate-100 pb-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-lg bg-indigo-600 px-2 py-0.5 text-xs font-extrabold text-white">
                          #{claim.claim_id}
                        </span>
                        <span className="text-xs font-bold text-slate-600 bg-slate-100 px-2.5 py-0.5 rounded-lg">
                          {claim.check_category}
                        </span>
                        {claim.topic_category && (
                          <span className="text-xs font-medium text-slate-500">
                            • {claim.topic_category}
                          </span>
                        )}
                      </div>

                      <div
                        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-black ${verdictMeta.badgeClass}`}
                      >
                        <span>{verdictMeta.dot}</span>
                        <span>{claim.verdict_label_vi}</span>
                      </div>
                    </div>

                    {/* Normalized Claim */}
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                        Nội dung cần xác thực:
                      </div>
                      <p className="text-[15px] font-extrabold text-slate-900 leading-snug">
                        {claim.normalized_claim}
                      </p>
                      {claim.original_text && claim.original_text !== claim.normalized_claim && (
                        <p className="text-xs font-medium text-slate-500 mt-1 italic">
                          Trích nguyên văn trong ảnh: &ldquo;{claim.original_text}&rdquo;
                        </p>
                      )}
                    </div>

                    {/* Explanation */}
                    <div className="rounded-xl bg-slate-50 border border-slate-200/80 p-3.5 space-y-2">
                      <div className="text-xs font-extrabold text-slate-900">
                        Phân tích đối chiếu & Giải thích sự thật:
                      </div>
                      <p className="text-xs font-medium text-slate-700 leading-relaxed">
                        {claim.explanation}
                      </p>
                    </div>

                    {/* Suggested Correction if available */}
                    {claim.suggested_correction && (
                      <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3.5 space-y-1.5">
                        <div className="flex items-center gap-1.5 text-xs font-extrabold text-emerald-900">
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                          <span>Đề xuất diễn đạt chuẩn xác / Đính chính:</span>
                        </div>
                        <p className="text-xs font-bold text-emerald-950">
                          {claim.suggested_correction.cautious_rewrite}
                        </p>
                        <p className="text-xs font-medium text-emerald-800">
                          {claim.suggested_correction.rationale}
                        </p>
                      </div>
                    )}

                    {/* Evidence Sources */}
                    <div className="space-y-3 pt-2">
                      <EvidenceList
                        title="Bằng chứng Hỗ trợ"
                        items={claim.supporting_evidence}
                        accent="emerald"
                      />
                      <EvidenceList
                        title="Bằng chứng Bác bỏ / Phản biện"
                        items={claim.refuting_evidence}
                        accent="rose"
                      />
                      <EvidenceList
                        title="Bằng chứng Ngữ cảnh Bổ sung"
                        items={claim.contextual_evidence}
                        accent="slate"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-6 text-center space-y-2">
            <div className="mx-auto h-10 w-10 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-500">
              <CheckCircle2 className="h-5 w-5 text-indigo-600" />
            </div>
            <h4 className="text-xs font-extrabold text-slate-800">
              {forensics.extracted_ocr_text
                ? "Đã nhận diện văn bản nhưng không có phát ngôn/số liệu cần bác bỏ"
                : "Không phát hiện văn bản hoặc phát ngôn cần xác thực"}
            </h4>
            <p className="text-xs font-medium text-slate-500 max-w-md mx-auto">
              {forensics.extracted_ocr_text
                ? "Văn bản trong ảnh mang tính chất trang trí, nhãn mác hoặc tiêu đề ngắn, không chứa các tuyên bố số liệu hay tin tức giật gân cần kiểm chứng tính đúng/sai."
                : "Bức ảnh này là ảnh chân dung, ảnh chụp sự vật hoặc phong cảnh thuần túy. Hệ thống đã hoàn tất giám định kỹ thuật số tính thật/giả của bức ảnh ở phần trên."}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
