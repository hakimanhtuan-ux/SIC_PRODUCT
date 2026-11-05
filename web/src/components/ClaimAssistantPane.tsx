"use client";

import React, { useState } from "react";
import {
  Check,
  Database,
  Flag,
  HelpCircle,
  Info,
  PenLine,
  Undo2,
} from "lucide-react";
import { submitDisputeFeedback } from "@/lib/api";
import { ClaimVerificationResult } from "@/types/verification";
import { EvidenceList } from "./EvidenceList";
import { VERDICT_META, VerdictBadge } from "./VerdictBadge";

export function ClaimAssistantPane({
  claim,
  documentId,
  isCorrectionAccepted,
  onToggleCorrection,
}: {
  claim: ClaimVerificationResult;
  documentId: string;
  isCorrectionAccepted: boolean;
  onToggleCorrection: (claimId: string) => void;
}) {
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackReason, setFeedbackReason] = useState("");
  const [feedbackUrl, setFeedbackUrl] = useState("");
  const [feedbackSentMsg, setFeedbackSentMsg] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSendFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (feedbackReason.trim().length < 10) return;
    setSubmitting(true);
    try {
      const res = await submitDisputeFeedback({
        document_id: documentId,
        claim_text: claim.normalized_claim,
        reported_verdict: claim.verdict,
        reason: feedbackReason.trim(),
        evidence_url: feedbackUrl.trim() || undefined,
      });
      setFeedbackSentMsg(res.message);
      setFeedbackReason("");
      setFeedbackUrl("");
    } catch (err) {
      setFeedbackSentMsg(
        err instanceof Error ? err.message : "Gửi phản hồi thất bại."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const completenessPct = Math.round(claim.evidence_completeness * 100);
  const vMeta = VERDICT_META[claim.verdict] || VERDICT_META.INSUFFICIENT_EVIDENCE;

  const suppCount = claim.supporting_evidence.length;
  const refCount = claim.refuting_evidence.length;
  const ctxCount = claim.contextual_evidence.length;
  const totalClaimEv = suppCount + refCount + ctxCount;
  const suppPct = totalClaimEv > 0 ? Math.round((suppCount / totalClaimEv) * 100) : 0;
  const refPct = totalClaimEv > 0 ? Math.round((refCount / totalClaimEv) * 100) : 0;
  const ctxPct = totalClaimEv > 0 ? Math.max(0, 100 - suppPct - refPct) : 0;
  const ringR = 22;
  const ringCirc = 2 * Math.PI * ringR;
  const ringOffset = ringCirc * (1 - Math.min(1, Math.max(0, claim.evidence_completeness)));

  return (
    <div className="space-y-5">
      {/* Metadata Pills */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-extrabold text-white">
            Mệnh đề {claim.claim_id}
          </span>
          <span className="rounded-lg bg-slate-100 border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700">
            {claim.check_category}
          </span>
          <span className="rounded-lg bg-indigo-50 border border-indigo-100 px-2.5 py-1 text-xs font-semibold text-indigo-700">
            {claim.topic_category}
          </span>
        </div>
        {claim.from_claim_memory && (
          <span className="inline-flex items-center gap-1 rounded-full bg-violet-100 border border-violet-200 px-2.5 py-0.5 text-[11px] font-bold text-violet-800">
            <Database className="h-3 w-3" />
            Claim Memory v{claim.memory_version}
          </span>
        )}
      </div>

      {/* QUESTION 1: Verdict & Explanation Banner */}
      <div className={`rounded-2xl border p-4 space-y-3 ${vMeta.bannerBg}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <VerdictBadge verdict={claim.verdict} size="lg" />
          <span className="text-xs font-medium text-slate-600">
            {claim.claim_type_label_vi}
          </span>
        </div>

        <p className="text-sm font-medium text-slate-800 leading-relaxed bg-white/85 rounded-xl p-3.5 border border-white">
          {claim.explanation}
        </p>

        <div className="flex items-center gap-3.5 bg-white/85 rounded-xl p-3 border border-white">
          <div className="relative h-14 w-14 shrink-0">
            <svg className="h-14 w-14 -rotate-90" viewBox="0 0 56 56">
              <circle
                cx="28"
                cy="28"
                r={ringR}
                fill="none"
                stroke="#e2e8f0"
                strokeWidth="6"
              />
              <circle
                cx="28"
                cy="28"
                r={ringR}
                fill="none"
                stroke={vMeta.accentColor}
                strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray={ringCirc}
                strokeDashoffset={ringOffset}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center text-xs font-extrabold text-slate-900">
              {completenessPct}%
            </div>
          </div>

          <div className="flex-1 min-w-0 space-y-1.5">
            <div className="flex items-center justify-between text-xs text-slate-700">
              <span className="font-bold">Độ đầy đủ bằng chứng</span>
              <span className="font-extrabold text-slate-900">{completenessPct}%</span>
            </div>
            {totalClaimEv > 0 ? (
              <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-bold">
                <span className="rounded-md bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 text-emerald-800">
                  Ủng hộ: {suppPct}%
                </span>
                <span className="rounded-md bg-rose-50 border border-rose-200 px-1.5 py-0.5 text-rose-800">
                  Bác bỏ: {refPct}%
                </span>
                <span className="rounded-md bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 text-indigo-800">
                  Ngữ cảnh: {ctxPct}%
                </span>
              </div>
            ) : (
              <p className="text-[11px] text-slate-500">
                Mệnh đề thuộc nhóm nhận định / không áp dụng tỷ lệ nguồn tra cứu.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Missing Context Box */}
      {claim.missing_information && claim.missing_information.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4">
          <div className="flex items-center gap-1.5 text-xs font-extrabold text-amber-900 mb-2">
            <HelpCircle className="h-4 w-4 text-amber-600" />
            Thông tin điều kiện còn thiếu cần kiểm tra thêm
          </div>
          <ul className="list-disc list-inside space-y-1 text-xs text-amber-950 leading-relaxed">
            {claim.missing_information.map((info, idx) => (
              <li key={idx}>{info}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Suggest Correction Box */}
      {claim.suggested_correction && (
        <div className="rounded-2xl border border-indigo-200 bg-indigo-50/50 p-4 space-y-3">
          <div className="flex items-center gap-1.5 text-xs font-extrabold text-indigo-950">
            <PenLine className="h-4 w-4 text-indigo-600" />
            Suggest Correction – Gợi ý viết lại thận trọng hơn
          </div>

          <div className="rounded-xl bg-white border border-indigo-100 p-3.5 text-sm font-medium text-slate-900 leading-relaxed shadow-sm">
            &ldquo;{claim.suggested_correction.cautious_rewrite}&rdquo;
          </div>

          <p className="text-xs text-slate-600">
            <b>Lý do đề xuất:</b> {claim.suggested_correction.rationale}
          </p>

          <button
            type="button"
            onClick={() => onToggleCorrection(claim.claim_id)}
            className={`w-full inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition shadow-sm ${
              isCorrectionAccepted
                ? "bg-emerald-600 text-white hover:bg-emerald-700"
                : "bg-indigo-600 text-white hover:bg-indigo-700"
            }`}
          >
            {isCorrectionAccepted ? (
              <>
                <Undo2 className="h-4 w-4" />
                Đã áp dụng vào Bản thảo (Nhấn để hoàn tác)
              </>
            ) : (
              <>
                <Check className="h-4 w-4" />
                Áp dụng câu sửa này vào Bản thảo xuất ra
              </>
            )}
          </button>
        </div>
      )}

      {/* QUESTIONS 2 & 3: Evidence & Traceability */}
      <EvidenceList
        title="Bằng chứng Ủng hộ"
        items={claim.supporting_evidence}
        accent="emerald"
      />
      <EvidenceList
        title="Bằng chứng Bác bỏ"
        items={claim.refuting_evidence}
        accent="rose"
      />
      <EvidenceList
        title="Nguồn Đối chiếu & Ngữ cảnh Tham khảo"
        items={claim.contextual_evidence}
        accent="slate"
      />

      {/* Footer Note & Error Reporting */}
      <div className="pt-3 border-t border-slate-200 space-y-2.5">
        {claim.limitations && (
          <p className="flex items-start gap-1.5 text-[11px] text-slate-500 leading-relaxed">
            <Info className="h-3.5 w-3.5 shrink-0 mt-0.5 text-slate-400" />
            <span>{claim.limitations}</span>
          </p>
        )}

        <button
          type="button"
          onClick={() => {
            setShowFeedback((v) => !v);
            setFeedbackSentMsg(null);
          }}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-rose-600 transition"
        >
          <Flag className="h-3.5 w-3.5" />
          Báo cáo sai sót hoặc gửi nguồn đính chính cho mệnh đề này
        </button>

        {showFeedback && (
          <form
            onSubmit={handleSendFeedback}
            className="mt-2 rounded-2xl border border-slate-200 bg-slate-50 p-3.5 space-y-2.5"
          >
            <textarea
              required
              minLength={10}
              value={feedbackReason}
              onChange={(e) => setFeedbackReason(e.target.value)}
              placeholder="Mô tả điểm chưa chính xác hoặc thông tin cần xem xét lại (tối thiểu 10 ký tự)..."
              className="w-full rounded-xl border border-slate-300 bg-white p-2.5 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
              rows={2}
            />
            <input
              type="url"
              value={feedbackUrl}
              onChange={(e) => setFeedbackUrl(e.target.value)}
              placeholder="Liên kết tài liệu gốc chứng minh (không bắt buộc)"
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
            />
            <div className="flex items-center justify-between gap-2">
              <button
                type="submit"
                disabled={submitting}
                className="rounded-xl bg-slate-900 px-3.5 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {submitting ? "Đang gửi..." : "Gửi yêu cầu đính chính"}
              </button>
              {feedbackSentMsg && (
                <span className="text-xs text-emerald-700 font-semibold">
                  {feedbackSentMsg}
                </span>
              )}
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
