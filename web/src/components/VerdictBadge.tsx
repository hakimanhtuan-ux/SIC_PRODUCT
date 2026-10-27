import React from "react";
import { VerdictType } from "@/types/verification";

export const VERDICT_META: Record<
  VerdictType,
  {
    dot: string;
    labelVi: string;
    shortVi: string;
    badgeClass: string;
    highlightClass: string;
    activeRingClass: string;
    bannerBg: string;
    accentColor: string;
  }
> = {
  SUPPORTED: {
    dot: "🟢",
    labelVi: "Có bằng chứng hỗ trợ",
    shortVi: "Được hỗ trợ",
    badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
    highlightClass:
      "bg-emerald-100/90 hover:bg-emerald-200/90 border-b-2 border-emerald-500 text-slate-900",
    activeRingClass: "ring-2 ring-emerald-600 bg-emerald-200 font-semibold",
    bannerBg: "bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-200",
    accentColor: "#059669",
  },
  REFUTED: {
    dot: "🔴",
    labelVi: "Có bằng chứng đáng tin cậy bác bỏ",
    shortVi: "Bị bác bỏ",
    badgeClass: "bg-rose-50 text-rose-800 border-rose-200",
    highlightClass:
      "bg-rose-100/90 hover:bg-rose-200/90 border-b-2 border-rose-500 text-slate-900",
    activeRingClass: "ring-2 ring-rose-600 bg-rose-200 font-semibold",
    bannerBg: "bg-gradient-to-r from-rose-50 to-red-50 border-rose-200",
    accentColor: "#dc2626",
  },
  MISLEADING: {
    dot: "🟠",
    labelVi: "Thiếu ngữ cảnh / Dễ gây hiểu nhầm",
    shortVi: "Thiếu ngữ cảnh",
    badgeClass: "bg-orange-50 text-orange-800 border-orange-200",
    highlightClass:
      "bg-orange-100/90 hover:bg-orange-200/90 border-b-2 border-orange-500 text-slate-900",
    activeRingClass: "ring-2 ring-orange-600 bg-orange-200 font-semibold",
    bannerBg: "bg-gradient-to-r from-orange-50 to-amber-50 border-orange-200",
    accentColor: "#ea580c",
  },
  INSUFFICIENT_EVIDENCE: {
    dot: "🟡",
    labelVi: "Chưa đủ bằng chứng kết luận",
    shortVi: "Chưa đủ bằng chứng",
    badgeClass: "bg-amber-50 text-amber-900 border-amber-300",
    highlightClass:
      "bg-yellow-100/90 hover:bg-yellow-200/90 border-b-2 border-yellow-500 text-slate-900",
    activeRingClass: "ring-2 ring-amber-600 bg-yellow-200 font-semibold",
    bannerBg: "bg-gradient-to-r from-yellow-50 to-amber-50 border-amber-200",
    accentColor: "#d97706",
  },
  CONFLICTING_EVIDENCE: {
    dot: "🔵",
    labelVi: "Các bằng chứng đang mâu thuẫn",
    shortVi: "Bằng chứng mâu thuẫn",
    badgeClass: "bg-sky-50 text-sky-800 border-sky-200",
    highlightClass:
      "bg-sky-100/90 hover:bg-sky-200/90 border-b-2 border-sky-500 text-slate-900",
    activeRingClass: "ring-2 ring-sky-600 bg-sky-200 font-semibold",
    bannerBg: "bg-gradient-to-r from-sky-50 to-blue-50 border-sky-200",
    accentColor: "#0284c7",
  },
  NOT_VERIFIABLE: {
    dot: "⚪",
    labelVi: "Quan điểm / Không kiểm chứng khách quan",
    shortVi: "Không thể kiểm chứng",
    badgeClass: "bg-slate-100 text-slate-700 border-slate-300",
    highlightClass:
      "bg-slate-200/80 hover:bg-slate-300/80 border-b-2 border-slate-400 text-slate-800",
    activeRingClass: "ring-2 ring-slate-600 bg-slate-300 font-semibold",
    bannerBg: "bg-gradient-to-r from-slate-50 to-gray-100 border-slate-300",
    accentColor: "#475569",
  },
};

export function VerdictBadge({
  verdict,
  size = "md",
}: {
  verdict: VerdictType;
  size?: "sm" | "md" | "lg";
}) {
  const meta = VERDICT_META[verdict] || VERDICT_META.INSUFFICIENT_EVIDENCE;
  const sizeClasses =
    size === "sm"
      ? "px-2.5 py-0.5 text-xs font-semibold"
      : size === "lg"
        ? "px-4 py-1.5 text-sm font-bold shadow-sm"
        : "px-3 py-1 text-xs font-bold";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${sizeClasses} ${meta.badgeClass}`}
    >
      <span>{meta.dot}</span>
      <span>{meta.labelVi}</span>
    </span>
  );
}
