"use client";

import React, { useMemo, useState } from "react";
import { CircleDot, PieChart as PieChartIcon, Sparkles } from "lucide-react";
import {
  ClaimVerificationResult,
  EvidenceItem,
  VerdictType,
  VerificationResponse,
} from "@/types/verification";
import { VERDICT_META } from "./VerdictBadge";

export interface PieSliceItem {
  id: string;
  label: string;
  shortLabel: string;
  value: number;
  color: string;
  dot?: string;
}

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

function InteractiveSvgPie({
  title,
  subtitle,
  slices,
  chartStyle,
  centerPrimary,
  centerSecondary,
  unitLabel,
  emptyLabel,
  selectedId,
  onSelectSlice,
}: {
  title: string;
  subtitle: string;
  slices: PieSliceItem[];
  chartStyle: "PIE" | "DONUT";
  centerPrimary: string;
  centerSecondary: string;
  unitLabel: string;
  emptyLabel: string;
  selectedId?: string | null;
  onSelectSlice?: (id: string) => void;
}) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const nonZeroSlices = useMemo(
    () => slices.filter((s) => s.value > 0),
    [slices]
  );
  const total = useMemo(
    () => nonZeroSlices.reduce((acc, s) => acc + s.value, 0),
    [nonZeroSlices]
  );

  const size = 180;
  const cx = size / 2;
  const cy = size / 2;
  const outerR = 78;
  const innerR = chartStyle === "DONUT" ? 45 : 0;

  const computedArcs = useMemo(() => {
    if (total <= 0) return [];
    let currentAngle = -Math.PI / 2;
    return nonZeroSlices.map((s) => {
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
  }, [nonZeroSlices, total]);

  const activeSlice = useMemo(() => {
    const targetId =
      hoveredId || (selectedId && selectedId !== "ALL" ? selectedId : null);
    if (!targetId) return null;
    return computedArcs.find((a) => a.id === targetId) || null;
  }, [computedArcs, hoveredId, selectedId]);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 flex flex-col justify-between gap-4 shadow-sm hover:border-indigo-300 transition">
      <div>
        <h4 className="text-[15px] font-extrabold text-slate-900">{title}</h4>
        <p className="text-xs font-medium text-slate-600 mt-1">{subtitle}</p>
      </div>

      {/* Centered Pie / Donut Chart */}
      <div className="flex flex-col items-center gap-4">
        <div className="relative shrink-0" style={{ width: size, height: size }}>
          <svg
            width={size}
            height={size}
            viewBox={`0 0 ${size} ${size}`}
            className="overflow-visible drop-shadow-sm"
          >
            {total <= 0 ? (
              chartStyle === "DONUT" ? (
                <circle
                  cx={cx}
                  cy={cy}
                  r={(outerR + innerR) / 2}
                  fill="none"
                  stroke="#e2e8f0"
                  strokeWidth={outerR - innerR}
                />
              ) : (
                <circle cx={cx} cy={cy} r={outerR} fill="#e2e8f0" />
              )
            ) : computedArcs.length === 1 ? (
              <g
                onMouseEnter={() => setHoveredId(computedArcs[0].id)}
                onMouseLeave={() => setHoveredId(null)}
                onClick={() => onSelectSlice?.(computedArcs[0].id)}
                className={onSelectSlice ? "cursor-pointer" : ""}
              >
                {chartStyle === "DONUT" ? (
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
                )}
              </g>
            ) : (
              computedArcs.map((arc) => {
                const isSelected =
                  hoveredId === arc.id ||
                  (selectedId && selectedId !== "ALL" && selectedId === arc.id);
                const pushDist = isSelected ? 5 : 0;
                const offsetX = Math.cos(arc.midAngle) * pushDist;
                const offsetY = Math.sin(arc.midAngle) * pushDist;

                const labelRadius =
                  chartStyle === "DONUT"
                    ? (outerR + innerR) / 2
                    : outerR * 0.6;
                const labelPos = polarToCartesian(
                  cx,
                  cy,
                  labelRadius,
                  arc.midAngle
                );

                return (
                  <g
                    key={arc.id}
                    transform={`translate(${offsetX.toFixed(2)}, ${offsetY.toFixed(2)})`}
                    onMouseEnter={() => setHoveredId(arc.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    onClick={() => onSelectSlice?.(arc.id)}
                    className={`transition-transform duration-200 ${onSelectSlice ? "cursor-pointer" : ""
                      }`}
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
                        x={labelPos.x}
                        y={labelPos.y}
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

          {(chartStyle === "DONUT" || total <= 0) && (
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center px-5">
              {total <= 0 ? (
                <span className="text-xs font-bold text-slate-500">
                  {emptyLabel}
                </span>
              ) : activeSlice ? (
                <>
                  <span
                    className="text-xl font-extrabold leading-none"
                    style={{ color: activeSlice.color }}
                  >
                    {activeSlice.pctText}
                  </span>
                  <span className="text-[11px] font-bold text-slate-700 mt-1 line-clamp-2 leading-tight">
                    {activeSlice.shortLabel}
                  </span>
                </>
              ) : (
                <>
                  <span className="text-xl font-extrabold text-slate-900 leading-none">
                    {centerPrimary}
                  </span>
                  <span className="text-[11px] font-semibold text-slate-600 mt-1 leading-tight">
                    {centerSecondary}
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {/* Full-Width High-Contrast Legend List (Zero Truncation!) */}
        <div className="w-full space-y-2">
          {total <= 0 ? (
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-xs font-medium text-slate-600 text-center">
              {emptyLabel}
            </div>
          ) : (
            computedArcs.map((arc) => {
              const isHighlighted =
                hoveredId === arc.id ||
                (selectedId && selectedId !== "ALL" && selectedId === arc.id);
              return (
                <button
                  key={arc.id}
                  type="button"
                  onMouseEnter={() => setHoveredId(arc.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={() => onSelectSlice?.(arc.id)}
                  className={`w-full rounded-xl px-3.5 py-2.5 text-left transition border ${isHighlighted
                      ? "bg-indigo-50/60 border-indigo-400 shadow-sm"
                      : "bg-slate-50/80 border-slate-200/90 hover:bg-white hover:border-slate-300"
                    }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="flex items-start gap-2.5 min-w-0">
                      <span
                        className="mt-1 h-3.5 w-3.5 rounded-[4px] shrink-0 shadow-sm"
                        style={{ backgroundColor: arc.color }}
                      />
                      <span className="text-[13px] font-bold text-slate-900 leading-snug">
                        {arc.label}
                      </span>
                    </span>

                    <span className="shrink-0 inline-flex items-center gap-1.5 tabular-nums">
                      <span className="text-[13px] font-extrabold text-slate-950">
                        {arc.pctText}
                      </span>
                      <span className="rounded-md bg-white border border-slate-200 px-1.5 py-0.5 text-[11px] font-bold text-slate-700">
                        {arc.value} {unitLabel}
                      </span>
                    </span>
                  </div>

                  {/* Subtle Proportion Bar */}
                  <div className="mt-2 h-1.5 w-full rounded-full bg-slate-200/80 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.max(4, arc.fraction * 100)}%`,
                        backgroundColor: arc.color,
                      }}
                    />
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export function VerificationCharts({
  data,
  activeClaim,
  filterVerdict,
  onSelectVerdictFilter,
}: {
  data: VerificationResponse;
  activeClaim: ClaimVerificationResult | null;
  filterVerdict: VerdictType | "ALL";
  onSelectVerdictFilter: (v: VerdictType | "ALL") => void;
}) {
  const [chartStyle, setChartStyle] = useState<"PIE" | "DONUT">("PIE");
  const [evidenceScope, setEvidenceScope] = useState<"ALL" | "ACTIVE">(
    data.claims.length > 1 ? "ALL" : "ACTIVE"
  );

  // 1. Verdict Distribution (%)
  const verdictSlices: PieSliceItem[] = useMemo(() => {
    const order: VerdictType[] = [
      "SUPPORTED",
      "REFUTED",
      "MISLEADING",
      "INSUFFICIENT_EVIDENCE",
      "CONFLICTING_EVIDENCE",
      "NOT_VERIFIABLE",
    ];
    return order.map((vKey) => {
      const meta = VERDICT_META[vKey];
      const count =
        data.summary_counts[vKey] ??
        data.claims.filter((c) => c.verdict === vKey).length;
      return {
        id: vKey,
        label: meta.labelVi,
        shortLabel: meta.shortVi,
        value: count,
        color: meta.accentColor,
        dot: meta.dot,
      };
    });
  }, [data.claims, data.summary_counts]);

  // Collect deduplicated EvidenceItems for scope ("ALL" vs "ACTIVE" claim)
  const scopedEvidences: EvidenceItem[] = useMemo(() => {
    const targetClaims =
      evidenceScope === "ACTIVE" && activeClaim ? [activeClaim] : data.claims;
    const byUrl = new Map<string, EvidenceItem>();
    for (const c of targetClaims) {
      const list = [
        ...c.supporting_evidence,
        ...c.refuting_evidence,
        ...c.contextual_evidence,
      ];
      for (const ev of list) {
        const key = ev.url || ev.id;
        const existing = byUrl.get(key);
        if (
          !existing ||
          (existing.stance === "CONTEXTUAL" && ev.stance !== "CONTEXTUAL")
        ) {
          byUrl.set(key, ev);
        }
      }
    }
    return Array.from(byUrl.values());
  }, [activeClaim, data.claims, evidenceScope]);

  // 2. Evidence Stance Distribution (%)
  const stanceSlices: PieSliceItem[] = useMemo(() => {
    let supp = 0;
    let ref = 0;
    let ctx = 0;
    for (const ev of scopedEvidences) {
      if (ev.stance === "SUPPORTING") supp += 1;
      else if (ev.stance === "REFUTING") ref += 1;
      else ctx += 1;
    }
    return [
      {
        id: "SUPPORTING",
        label: "Bằng chứng Ủng hộ trực tiếp",
        shortLabel: "Ủng hộ",
        value: supp,
        color: "#059669",
      },
      {
        id: "REFUTING",
        label: "Bằng chứng Bác bỏ trực tiếp",
        shortLabel: "Bác bỏ",
        value: ref,
        color: "#dc2626",
      },
      {
        id: "CONTEXTUAL",
        label: "Nguồn Ngữ cảnh & Đối chiếu",
        shortLabel: "Ngữ cảnh",
        value: ctx,
        color: "#6366f1",
      },
    ];
  }, [scopedEvidences]);

  // 3. Source Credibility Tier Distribution (%)
  const tierSlices: PieSliceItem[] = useMemo(() => {
    let t1 = 0;
    let t2 = 0;
    let t3 = 0;
    let t45 = 0;
    for (const ev of scopedEvidences) {
      if (ev.tier === 1) t1 += 1;
      else if (ev.tier === 2) t2 += 1;
      else if (ev.tier === 3) t3 += 1;
      else t45 += 1;
    }
    return [
      {
        id: "TIER_1",
        label: "Nguồn Cấp 1 (Cơ quan Nhà nước)",
        shortLabel: "Nguồn Cấp 1",
        value: t1,
        color: "#0f766e",
      },
      {
        id: "TIER_2",
        label: "Nguồn Cấp 2 (Học thuật / Quốc tế)",
        shortLabel: "Nguồn Cấp 2",
        value: t2,
        color: "#2563eb",
      },
      {
        id: "TIER_3",
        label: "Nguồn Cấp 3 (Báo chí chính thống)",
        shortLabel: "Nguồn Cấp 3",
        value: t3,
        color: "#7c3aed",
      },
      {
        id: "TIER_4_5",
        label: "Nguồn Cấp 4–5 (Nguồn tham khảo)",
        shortLabel: "Nguồn Cấp 4–5",
        value: t45,
        color: "#d97706",
      },
    ];
  }, [scopedEvidences]);

  const validatedPct = useMemo(() => {
    if (!scopedEvidences.length) return 0;
    const validCount = scopedEvidences.filter((e) => e.citation_validated).length;
    return Math.round((validCount / scopedEvidences.length) * 100);
  }, [scopedEvidences]);

  const handleVerdictSliceClick = (sliceId: string) => {
    const asVerdict = sliceId as VerdictType;
    if (filterVerdict === asVerdict) {
      onSelectVerdictFilter("ALL");
    } else {
      onSelectVerdictFilter(asVerdict);
    }
  };

  return (
    <section className="tc-surface-card p-5 sm:p-6 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div className="flex items-start gap-3">
          <div className="h-10 w-10 rounded-2xl bg-indigo-50 border border-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
            <PieChartIcon className="h-5 w-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-extrabold text-slate-900">
                Biểu đồ Tròn Phân tích Kiểm chứng (%)
              </h3>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800">
                <Sparkles className="h-3 w-3" />
                {(data.processing_time_ms / 1000).toFixed(2)}s
              </span>
            </div>
            <p className="text-xs font-medium text-slate-600 mt-0.5">
              Trực quan hóa tỷ lệ % mệnh đề, tương quan bằng chứng và phân tầng nguồn Cấp 1–5.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {data.claims.length > 1 && activeClaim && (
            <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200/80">
              <button
                type="button"
                onClick={() => setEvidenceScope("ALL")}
                className={`rounded-lg px-2.5 py-1 text-xs font-bold transition ${evidenceScope === "ALL"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                  }`}
              >
                Toàn tài liệu
              </button>
              <button
                type="button"
                onClick={() => setEvidenceScope("ACTIVE")}
                className={`rounded-lg px-2.5 py-1 text-xs font-bold transition ${evidenceScope === "ACTIVE"
                    ? "bg-white text-indigo-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                  }`}
              >
                Mệnh đề {activeClaim.claim_id}
              </button>
            </div>
          )}

          <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200/80">
            <button
              type="button"
              onClick={() => setChartStyle("PIE")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-bold transition ${chartStyle === "PIE"
                  ? "bg-white text-indigo-700 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
                }`}
            >
              <PieChartIcon className="h-3.5 w-3.5" />
              Biểu đồ Tròn (%)
            </button>
            <button
              type="button"
              onClick={() => setChartStyle("DONUT")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-bold transition ${chartStyle === "DONUT"
                  ? "bg-white text-indigo-700 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
                }`}
            >
              <CircleDot className="h-3.5 w-3.5" />
              Vành khuyên (%)
            </button>
          </div>
        </div>
      </div>

      {/* 3 Spacious Pie Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <InteractiveSvgPie
          title="1. Tỷ lệ Kết luận 6 Trạng thái (%)"
          subtitle="Nhấn vào mục chú thích để lọc mệnh đề tương ứng"
          slices={verdictSlices}
          chartStyle={chartStyle}
          centerPrimary={`${data.claims.length}`}
          centerSecondary="mệnh đề"
          unitLabel="mệnh đề"
          emptyLabel="0% mệnh đề"
          selectedId={filterVerdict}
          onSelectSlice={handleVerdictSliceClick}
        />

        <InteractiveSvgPie
          title="2. Tương quan Nguồn Bằng chứng (%)"
          subtitle={
            evidenceScope === "ACTIVE" && activeClaim
              ? `Phân bổ nguồn của mệnh đề ${activeClaim.claim_id}`
              : "Phân bổ chiều hướng của tổng số nguồn đối chiếu"
          }
          slices={stanceSlices}
          chartStyle={chartStyle}
          centerPrimary={`${scopedEvidences.length}`}
          centerSecondary="nguồn đối chiếu"
          unitLabel="nguồn"
          emptyLabel="Không áp dụng tra cứu nguồn"
        />

        <InteractiveSvgPie
          title="3. Cơ cấu Cấp độ Uy tín Nguồn (%)"
          subtitle={`Đã xác thực trích dẫn trực tiếp: ${validatedPct}% số nguồn`}
          slices={tierSlices}
          chartStyle={chartStyle}
          centerPrimary={`${validatedPct}%`}
          centerSecondary="xác thực trích dẫn"
          unitLabel="nguồn"
          emptyLabel="Chưa có nguồn phân tầng"
        />
      </div>
    </section>
  );
}
