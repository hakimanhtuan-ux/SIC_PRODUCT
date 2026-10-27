import React from "react";
import { CheckCircle2, ExternalLink, Globe, ShieldCheck } from "lucide-react";
import { EvidenceItem } from "@/types/verification";

const TIER_BADGE_STYLE: Record<number, string> = {
  1: "bg-emerald-700 text-white",
  2: "bg-indigo-700 text-white",
  3: "bg-slate-800 text-white",
  4: "bg-violet-700 text-white",
  5: "bg-slate-500 text-white",
};

export function EvidenceList({
  title,
  items,
  accent,
}: {
  title: string;
  items: EvidenceItem[];
  accent: "emerald" | "rose" | "slate";
}) {
  if (!items || items.length === 0) return null;

  const containerStyle = {
    emerald: "border-emerald-200/90 bg-emerald-50/30 hover:border-emerald-300",
    rose: "border-rose-200/90 bg-rose-50/30 hover:border-rose-300",
    slate: "border-slate-200/90 bg-slate-50/50 hover:border-slate-300",
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-extrabold uppercase tracking-wider text-slate-600">
          {title}
        </h4>
        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-700">
          {items.length} nguồn
        </span>
      </div>

      <div className="space-y-3">
        {items.map((ev) => (
          <div
            key={ev.id}
            className={`rounded-2xl border p-4 transition-all duration-150 ${containerStyle[accent]}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <span
                  className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] font-bold ${TIER_BADGE_STYLE[ev.tier] || TIER_BADGE_STYLE[5]
                    }`}
                  title={ev.tier_label}
                >
                  <ShieldCheck className="h-3 w-3" />
                  Nguồn Cấp {ev.tier}
                </span>

                {ev.citation_validated ? (
                  <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-100 border border-emerald-200 px-2 py-0.5 text-[11px] font-bold text-emerald-800">
                    <CheckCircle2 className="h-3 w-3" />
                    Đã xác thực trích dẫn
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-lg bg-slate-200/80 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                    Đối chiếu ngữ cảnh
                  </span>
                )}
              </div>

              <a
                href={ev.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-lg bg-white border border-slate-200 px-2.5 py-1 text-xs font-bold text-indigo-600 hover:bg-indigo-50 hover:border-indigo-200 transition shadow-sm"
              >
                <span>Kiểm tra nguồn</span>
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>

            <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
              <Globe className="h-3 w-3 text-slate-400" />
              <span className="font-semibold text-slate-700">{ev.domain}</span>
              {ev.published_date && <span>• {ev.published_date}</span>}
            </div>

            <p className="text-sm font-bold text-slate-900 leading-snug mb-1.5">
              {ev.title}
            </p>
            <p className="text-xs text-slate-600 leading-relaxed bg-white/80 rounded-xl p-2.5 border border-slate-200/60">
              {ev.snippet}
            </p>

            <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] text-slate-600">
              <div className="rounded-lg bg-white/90 px-2.5 py-1.5 border border-slate-200/60">
                <span className="text-slate-400 block text-[10px]">Độ liên quan</span>
                <b className="text-slate-800">{Math.round(ev.scores.relevance * 100)}%</b>
              </div>
              <div className="rounded-lg bg-white/90 px-2.5 py-1.5 border border-slate-200/60">
                <span className="text-slate-400 block text-[10px]">Độ tin cậy nguồn</span>
                <b className="text-slate-800">{Math.round(ev.scores.credibility * 100)}%</b>
              </div>
              <div className="rounded-lg bg-white/90 px-2.5 py-1.5 border border-slate-200/60">
                <span className="text-slate-400 block text-[10px]">Đúng ngữ cảnh</span>
                <b className="text-slate-800">{Math.round(ev.scores.context * 100)}%</b>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
