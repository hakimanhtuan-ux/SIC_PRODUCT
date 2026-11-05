"use client";

import React, { useMemo, useState } from "react";
import {
  BookOpen,
  Download,
  FileCheck2,
  FileDown,
  FilePenLine,
  LayoutList,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import {
  deleteDocumentSession,
  getAnnotatedPdfExportUrl,
  getReportExportUrl,
} from "@/lib/api";
import {
  ClaimVerificationResult,
  VerdictType,
  VerificationResponse,
} from "@/types/verification";
import { ClaimAssistantPane } from "./ClaimAssistantPane";
import { ManipulationPanel } from "./ManipulationPanel";
import { VERDICT_META, VerdictBadge } from "./VerdictBadge";
import { VerificationCharts } from "./VerificationCharts";

interface HighlightSpanGroup {
  start: number;
  end: number;
  claims: ClaimVerificationResult[];
}

function buildNonOverlappingSpans(
  fullText: string,
  claims: ClaimVerificationResult[]
): HighlightSpanGroup[] {
  const valid = claims
    .filter(
      (c) =>
        c.start_char >= 0 &&
        c.end_char > c.start_char &&
        c.end_char <= fullText.length
    )
    .sort((a, b) => a.start_char - b.start_char || a.end_char - b.end_char);

  const groups: HighlightSpanGroup[] = [];
  for (const c of valid) {
    const prev = groups[groups.length - 1];
    if (prev && c.start_char < prev.end) {
      prev.end = Math.max(prev.end, c.end_char);
      prev.claims.push(c);
    } else {
      groups.push({ start: c.start_char, end: c.end_char, claims: [c] });
    }
  }
  return groups;
}

export function DocumentStudio({
  data,
  onDeleted,
}: {
  data: VerificationResponse;
  onDeleted: () => void;
}) {
  const [selectedClaimId, setSelectedClaimId] = useState<string>(
    data.claims[0]?.claim_id || ""
  );
  const [filterVerdict, setFilterVerdict] = useState<VerdictType | "ALL">("ALL");
  const [leftViewMode, setLeftViewMode] = useState<"DOCUMENT" | "CARDS">(
    "DOCUMENT"
  );
  const [acceptedCorrections, setAcceptedCorrections] = useState<
    Record<string, boolean>
  >({});
  const [deleting, setDeleting] = useState(false);

  const toggleCorrection = (claimId: string) => {
    setAcceptedCorrections((prev) => ({
      ...prev,
      [claimId]: !prev[claimId],
    }));
  };

  const filteredClaims = useMemo(() => {
    if (filterVerdict === "ALL") return data.claims;
    return data.claims.filter((c) => c.verdict === filterVerdict);
  }, [data.claims, filterVerdict]);

  const activeClaim = useMemo(() => {
    return (
      data.claims.find((c) => c.claim_id === selectedClaimId) ||
      filteredClaims[0] ||
      data.claims[0] ||
      null
    );
  }, [data.claims, filteredClaims, selectedClaimId]);

  const spanGroups = useMemo(
    () => buildNonOverlappingSpans(data.full_text, data.claims),
    [data.full_text, data.claims]
  );

  const totalSourcesCount = useMemo(() => {
    const urls = new Set<string>();
    data.claims.forEach((c) => {
      [
        ...c.supporting_evidence,
        ...c.refuting_evidence,
        ...c.contextual_evidence,
      ].forEach((e) => urls.add(e.url));
    });
    return urls.size;
  }, [data.claims]);

  const avgCompleteness = useMemo(() => {
    if (!data.claims.length) return 0;
    const sum = data.claims.reduce((acc, c) => acc + c.evidence_completeness, 0);
    return Math.round((sum / data.claims.length) * 100);
  }, [data.claims]);

  const handleExportCorrectedDraft = () => {
    let draft = data.full_text;
    const acceptedList = data.claims.filter(
      (c) => acceptedCorrections[c.claim_id] && c.suggested_correction
    );
    for (const c of acceptedList) {
      if (c.suggested_correction && c.original_text) {
        draft = draft.replace(
          c.original_text,
          c.suggested_correction.cautious_rewrite
        );
      }
    }
    const blob = new Blob([draft], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `factcheck-assistent-draft-${data.document_id.slice(0, 8)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDeleteData = async () => {
    setDeleting(true);
    try {
      await deleteDocumentSession(data.document_id);
      onDeleted();
    } catch {
      setDeleting(false);
    }
  };

  const renderedTextNodes = useMemo(() => {
    const text = data.full_text;
    if (!spanGroups.length) {
      return <p className="whitespace-pre-wrap leading-relaxed">{text}</p>;
    }

    const pieces: React.ReactNode[] = [];
    let cursor = 0;

    spanGroups.forEach((grp, idx) => {
      if (grp.start > cursor) {
        pieces.push(
          <span key={`plain-${idx}`}>{text.slice(cursor, grp.start)}</span>
        );
      }
      const primary =
        grp.claims.find((c) => c.claim_id === activeClaim?.claim_id) ||
        grp.claims[0];
      const meta = VERDICT_META[primary.verdict];
      const isSelected = grp.claims.some(
        (c) => c.claim_id === activeClaim?.claim_id
      );
      const snippet = text.slice(grp.start, grp.end);

      pieces.push(
        <span
          key={`hl-${idx}`}
          onClick={() => setSelectedClaimId(grp.claims[0].claim_id)}
          className={`cursor-pointer rounded-md px-1.5 py-0.5 transition-all ${
            meta.highlightClass
          } ${isSelected ? meta.activeRingClass : ""}`}
        >
          {snippet}
          <span className="ml-1.5 inline-flex gap-1 align-baseline">
            {grp.claims.map((c) => (
              <button
                key={c.claim_id}
                type="button"
                onClick={(ev) => {
                  ev.stopPropagation();
                  setSelectedClaimId(c.claim_id);
                }}
                className={`rounded-md px-1.5 py-0.5 text-[10px] font-extrabold transition ${
                  c.claim_id === activeClaim?.claim_id
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "bg-white text-slate-800 border border-slate-300 hover:bg-slate-100"
                }`}
              >
                {c.claim_id}
                {acceptedCorrections[c.claim_id] ? " ✓" : ""}
              </button>
            ))}
          </span>
        </span>
      );
      cursor = grp.end;
    });

    if (cursor < text.length) {
      pieces.push(<span key="plain-tail">{text.slice(cursor)}</span>);
    }

    return (
      <div className="whitespace-pre-wrap text-base leading-9 text-slate-800">
        {pieces}
      </div>
    );
  }, [data.full_text, spanGroups, activeClaim, acceptedCorrections]);

  const acceptedCount = Object.values(acceptedCorrections).filter(Boolean).length;

  return (
    <div className="space-y-6">
      {/* Privacy & Security Alerts */}
      {(data.privacy_scan.has_pii ||
        data.privacy_scan.prompt_injection_detected ||
        data.privacy_scan.ocr_required_pages.length > 0) && (
        <div className="rounded-2xl border border-amber-300 bg-amber-50/90 p-4 space-y-1.5 text-xs text-amber-950 shadow-sm">
          <div className="flex items-center gap-2 font-extrabold text-sm">
            <ShieldAlert className="h-4 w-4 text-amber-600" />
            Cảnh báo Bảo vệ Dữ liệu Cá nhân (Luật 91/2025/QH15) & An toàn AI
          </div>
          {data.privacy_scan.privacy_notice && (
            <p>{data.privacy_scan.privacy_notice}</p>
          )}
          {data.privacy_scan.prompt_injection_detected && (
            <p className="text-rose-800 font-semibold">
              Phát hiện mẫu chuỗi có dấu hiệu Prompt Injection. Hệ thống đã cô lập nội dung như dữ liệu không đáng tin cậy.
            </p>
          )}
        </div>
      )}

      {/* Executive KPI Overview Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="tc-surface-card p-4">
          <span className="text-xs font-semibold text-slate-500">
            Mệnh đề đã bóc tách
          </span>
          <div className="text-2xl font-extrabold text-slate-900 mt-1">
            {data.claims.length} mệnh đề
          </div>
          <span className="text-[11px] text-indigo-600 font-medium">
            Tự động phân tách nguyên tử (Lớp 2)
          </span>
        </div>

        <div className="tc-surface-card p-4">
          <span className="text-xs font-semibold text-slate-500">
            Nguồn đối chiếu thu thập
          </span>
          <div className="text-2xl font-extrabold text-slate-900 mt-1">
            {totalSourcesCount} nguồn
          </div>
          <span className="text-[11px] text-emerald-700 font-medium">
            Phân tầng Cấp 1–5 & Citation Validation
          </span>
        </div>

        <div className="tc-surface-card p-4">
          <span className="text-xs font-semibold text-slate-500">
            Độ đầy đủ bằng chứng TB
          </span>
          <div className="text-2xl font-extrabold text-slate-900 mt-1">
            {avgCompleteness}%
          </div>
          <span className="text-[11px] text-slate-500">
            Chống ảo giác khi thiếu dữ liệu
          </span>
        </div>

        <div className="tc-surface-card p-4">
          <span className="text-xs font-semibold text-slate-500">
            Tín hiệu ngôn từ cần lưu ý
          </span>
          <div className="text-2xl font-extrabold text-slate-900 mt-1">
            {data.manipulation_signals.length} tín hiệu
          </div>
          <span className="text-[11px] text-amber-700 font-medium">
            Độc lập với kết luận Đúng/Sai
          </span>
        </div>
      </div>

      {/* Interactive Pie & Donut Charts (%) */}
      <VerificationCharts
        data={data}
        activeClaim={activeClaim}
        filterVerdict={filterVerdict}
        onSelectVerdictFilter={setFilterVerdict}
      />

      {/* Filter & Export Action Bar */}
      <div className="tc-surface-card p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setFilterVerdict("ALL")}
            className={`rounded-full px-3.5 py-1.5 text-xs font-bold border transition ${
              filterVerdict === "ALL"
                ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
            }`}
          >
            Tất cả ({data.claims.length})
          </button>
          {(Object.keys(VERDICT_META) as VerdictType[]).map((vKey) => {
            const count = data.summary_counts[vKey] || 0;
            if (count === 0) return null;
            const meta = VERDICT_META[vKey];
            return (
              <button
                key={vKey}
                type="button"
                onClick={() => setFilterVerdict(vKey)}
                className={`rounded-full px-3.5 py-1.5 text-xs font-bold border transition ${
                  filterVerdict === vKey
                    ? "ring-2 ring-slate-900 " + meta.badgeClass
                    : meta.badgeClass
                }`}
              >
                {meta.dot} {meta.shortVi} ({count})
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <a
            href={getReportExportUrl(data.document_id)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-bold text-slate-800 hover:bg-slate-50 transition shadow-sm"
          >
            <FileDown className="h-4 w-4 text-indigo-600" />
            Báo cáo (.MD)
          </a>
          <a
            href={getAnnotatedPdfExportUrl(data.document_id)}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-indigo-700 transition shadow-sm"
          >
            <Download className="h-4 w-4" />
            Tải Annotated PDF
          </a>
          <button
            type="button"
            onClick={handleExportCorrectedDraft}
            className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-300 bg-emerald-50 px-3.5 py-2 text-xs font-bold text-emerald-900 hover:bg-emerald-100 transition"
          >
            <FilePenLine className="h-4 w-4" />
            Bản thảo đã sửa ({acceptedCount})
          </button>
          <button
            type="button"
            disabled={deleting}
            onClick={handleDeleteData}
            title="Xóa ngay tài liệu và phiên kiểm chứng khỏi máy chủ"
            className="inline-flex items-center gap-1 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-bold text-rose-700 hover:bg-rose-100 disabled:opacity-50 transition"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Main Split-Pane Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: DOCUMENT VIEWER / CLAIM CARDS */}
        <div className="lg:col-span-7 tc-surface-card overflow-hidden">
          <div className="border-b border-slate-200 bg-slate-50/80 px-5 py-3.5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="text-[11px] font-extrabold uppercase tracking-wider text-indigo-600">
                BÊN TRÁI • TÀI LIỆU GỐC & MỆNH ĐỀ
              </span>
              <h3 className="text-sm font-extrabold text-slate-900 truncate max-w-md">
                {data.source_title}
              </h3>
            </div>

            <div className="inline-flex rounded-xl bg-slate-200/80 p-1">
              <button
                type="button"
                onClick={() => setLeftViewMode("DOCUMENT")}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-bold transition ${
                  leftViewMode === "DOCUMENT"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <BookOpen className="h-3.5 w-3.5" />
                Tô màu trên văn bản
              </button>
              <button
                type="button"
                onClick={() => setLeftViewMode("CARDS")}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-bold transition ${
                  leftViewMode === "CARDS"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <LayoutList className="h-3.5 w-3.5" />
                Danh sách mệnh đề ({filteredClaims.length})
              </button>
            </div>
          </div>

          {/* Color Legend Bar */}
          <div className="border-b border-slate-100 bg-white px-5 py-2.5 flex flex-wrap items-center gap-3 text-[11px] text-slate-600">
            <span className="font-bold text-slate-400 uppercase">Chú giải màu:</span>
            <span>🟢 Được hỗ trợ</span>
            <span>🔴 Bị bác bỏ</span>
            <span>🟠 Thiếu ngữ cảnh</span>
            <span>🟡 Chưa đủ bằng chứng</span>
            <span>🔵 Mâu thuẫn</span>
            <span>⚪ Quan điểm</span>
          </div>

          <div className="p-6 max-h-[680px] overflow-y-auto">
            {leftViewMode === "DOCUMENT" ? (
              renderedTextNodes
            ) : (
              <div className="space-y-3">
                {filteredClaims.map((c) => {
                  const isSel = activeClaim?.claim_id === c.claim_id;
                  return (
                    <div
                      key={c.claim_id}
                      onClick={() => setSelectedClaimId(c.claim_id)}
                      className={`cursor-pointer rounded-2xl border p-4 transition-all ${
                        isSel
                          ? "border-indigo-600 bg-indigo-50/30 ring-2 ring-indigo-500/20"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="rounded-lg bg-slate-900 px-2 py-0.5 text-xs font-extrabold text-white">
                            {c.claim_id}
                          </span>
                          <span className="text-xs font-semibold text-slate-500">
                            {c.check_category}
                          </span>
                        </div>
                        <VerdictBadge verdict={c.verdict} size="sm" />
                      </div>
                      <p className="text-sm font-bold text-slate-900 mb-1">
                        &ldquo;{c.original_text}&rdquo;
                      </p>
                      <p className="text-xs text-slate-600 line-clamp-2">
                        {c.explanation}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: TRUECHECK AI ASSISTANT */}
        <div className="lg:col-span-5 tc-surface-card overflow-hidden lg:sticky lg:top-20">
          <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 px-5 py-4 flex items-center justify-between text-white">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-white/10 flex items-center justify-center text-emerald-400">
                <FileCheck2 className="h-4 w-4" />
              </div>
              <div>
                <div className="text-xs font-extrabold tracking-wider uppercase text-indigo-300">
                  BÊN PHẢI • HỒ SƠ BẰNG CHỨNG
                </div>
                <div className="text-sm font-extrabold">
                  FACTCHECK ASSISTENT
                </div>
              </div>
            </div>
            <span className="rounded-lg bg-white/10 px-2.5 py-1 text-[11px] font-semibold text-slate-200">
              {(data.processing_time_ms / 1000).toFixed(1)}s • {data.engine_mode}
            </span>
          </div>

          <div className="p-5 max-h-[680px] overflow-y-auto">
            {activeClaim ? (
              <ClaimAssistantPane
                claim={activeClaim}
                documentId={data.document_id}
                isCorrectionAccepted={Boolean(
                  acceptedCorrections[activeClaim.claim_id]
                )}
                onToggleCorrection={toggleCorrection}
              />
            ) : (
              <div className="py-12 text-center text-sm text-slate-500">
                Không tìm thấy mệnh đề nào cần kiểm chứng trong nội dung này.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Independent Manipulation Signals Engine */}
      <ManipulationPanel
        signals={data.manipulation_signals}
        summary={data.manipulation_summary}
      />
    </div>
  );
}
