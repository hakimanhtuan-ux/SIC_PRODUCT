import React from "react";
import { AlertTriangle, CheckCircle, Sparkles } from "lucide-react";
import { ManipulationSignal } from "@/types/verification";

export function ManipulationPanel({
  signals,
  summary,
}: {
  signals: ManipulationSignal[];
  summary: string;
}) {
  const severityStyle: Record<string, string> = {
    HIGH: "bg-rose-100 text-rose-800 border-rose-200",
    MEDIUM: "bg-amber-100 text-amber-900 border-amber-200",
    LOW: "bg-slate-100 text-slate-700 border-slate-200",
  };

  return (
    <div className="tc-surface-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="flex items-start gap-3">
          <div className="h-10 w-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xs font-extrabold uppercase tracking-wider text-indigo-600">
              Manipulation Analysis Engine
            </div>
            <h3 className="text-base font-extrabold text-slate-900">
              Phân tích Tín hiệu Thao túng Ngôn từ & Cách trình bày
            </h3>
          </div>
        </div>
        <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-800 border border-indigo-200">
          Đánh giá độc lập với độ chính xác dữ kiện (Fact Accuracy)
        </span>
      </div>

      <p className="text-sm text-slate-600 bg-slate-50 rounded-xl p-3.5 border border-slate-200/80 mb-4">
        {summary}
      </p>

      {signals.length === 0 ? (
        <div className="flex items-center gap-2 text-xs font-semibold text-emerald-700 bg-emerald-50/70 border border-emerald-200 rounded-xl px-4 py-3">
          <CheckCircle className="h-4 w-4 shrink-0" />
          <span>Văn bản được trình bày trung tính, không phát hiện thủ pháp giật tít hay kích động cảm xúc.</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {signals.map((sig, idx) => (
            <div
              key={`${sig.signal_type}-${idx}`}
              className="rounded-2xl border border-amber-200/80 bg-amber-50/20 p-4"
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-extrabold text-slate-900">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  {sig.label_vi}
                </span>
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${
                    severityStyle[sig.severity] || severityStyle.LOW
                  }`}
                >
                  Mức {sig.severity}
                </span>
              </div>
              <p className="text-xs italic font-medium text-slate-900 bg-white rounded-xl px-3 py-2 border border-amber-200/70 mb-2">
                &ldquo;{sig.trigger_phrase}&rdquo;
              </p>
              <p className="text-xs text-slate-600 leading-relaxed">
                {sig.explanation}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
