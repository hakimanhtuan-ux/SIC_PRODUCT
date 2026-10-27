from html import escape
from pathlib import Path
from typing import Optional

from app.schemas.verification import VerdictEnum, VerificationResponse


VERDICT_PDF_RGB: dict[VerdictEnum, tuple[float, float, float]] = {
    VerdictEnum.SUPPORTED: (0.65, 0.95, 0.75),              # Soft Green
    VerdictEnum.REFUTED: (0.98, 0.72, 0.72),                # Soft Red
    VerdictEnum.MISLEADING: (0.99, 0.84, 0.65),             # Soft Orange
    VerdictEnum.INSUFFICIENT_EVIDENCE: (0.99, 0.94, 0.65),  # Soft Yellow
    VerdictEnum.CONFLICTING_EVIDENCE: (0.72, 0.86, 0.99),   # Soft Blue
    VerdictEnum.NOT_VERIFIABLE: (0.88, 0.88, 0.90),         # Neutral Gray
}

VERDICT_HEX: dict[VerdictEnum, str] = {
    VerdictEnum.SUPPORTED: "#16a34a",
    VerdictEnum.REFUTED: "#dc2626",
    VerdictEnum.MISLEADING: "#ea580c",
    VerdictEnum.INSUFFICIENT_EVIDENCE: "#ca8a04",
    VerdictEnum.CONFLICTING_EVIDENCE: "#2563eb",
    VerdictEnum.NOT_VERIFIABLE: "#6b7280",
}


def generate_markdown_report(res: VerificationResponse) -> str:
    """Generates a structured Vietnamese Verification Report in Markdown format."""
    lines: list[str] = [
        "# BÁO CÁO KIỂM CHỨNG THÔNG TIN – TRUECHECK AI",
        "",
        f"- **Mã tài liệu:** `{res.document_id}`",
        f"- **Tiêu đề / Nguồn:** {res.source_title}",
        f"- **URL gốc:** {res.source_url or 'Tài liệu / Văn bản tải lên'}",
        f"- **Thời điểm xác minh:** {res.verified_at}",
        f"- **Chế độ vận hành Engine:** `{res.engine_mode}` ({res.processing_time_ms} ms)",
        "",
        "---",
        "",
        "## 1. Tổng quan Kết quả Kiểm chứng Dữ kiện (Fact Accuracy)",
        "",
        "| Trạng thái kết luận | Số lượng mệnh đề |",
        "| :--- | :---: |",
    ]

    for verdict_key, count in res.summary_counts.items():
        lines.append(f"| `{verdict_key}` | {count} |")

    lines.extend(["", "## 2. Chi tiết Từng Mệnh đề Kiểm chứng", ""])

    for c in res.claims:
        lines.extend([
            f"### [{c.claim_id}] {c.verdict_label_vi} (`{c.verdict.value}`)",
            f"- **Đoạn gốc:** \"{c.original_text}\"",
            f"- **Mệnh đề chuẩn hóa:** {c.normalized_claim}",
            f"- **Phân loại:** {c.claim_type_label_vi} ({c.check_category} – Chủ đề: {c.topic_category})",
            f"- **Mức độ đầy đủ bằng chứng:** {int(c.evidence_completeness * 100)}%",
            f"- **Giải thích:** {c.explanation}",
        ])
        if c.missing_information:
            lines.append(f"- **Thông tin điều kiện còn thiếu:** {'; '.join(c.missing_information)}")
        if c.suggested_correction:
            lines.append(
                f"- **Gợi ý diễn đạt thận trọng (Suggest Correction):** \"{c.suggested_correction.cautious_rewrite}\" "
                f"*(Lý do: {c.suggested_correction.rationale})*"
            )

        all_ev = c.supporting_evidence + c.refuting_evidence + c.contextual_evidence
        if all_ev:
            lines.append("- **Nguồn đối chiếu:**")
            for ev in all_ev:
                val_tag = "Đã xác thực trích dẫn" if ev.citation_validated else "Ngữ cảnh tham khảo"
                lines.append(
                    f"  - [Cấp {ev.tier} | {ev.stance.value} | {val_tag}] **{ev.title}** ({ev.domain}) — {ev.url}"
                )
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 3. Phân tích Tín hiệu Trình bày Ngôn từ (Manipulation Signals)",
        "",
        f"> {res.manipulation_summary}",
        "",
    ])
    for sig in res.manipulation_signals:
        lines.append(
            f"- **{sig.label_vi}** (Mức `{sig.severity}`) tại cụm *\"{sig.trigger_phrase}\"*: {sig.explanation}"
        )

    lines.extend([
        "",
        "---",
        "*Lưu ý nguyên tắc TrueCheck AI: Một mệnh đề 'Chưa đủ bằng chứng' không đồng nghĩa với thông tin sai. "
        "Kết quả phản ánh dữ liệu truy xuất được tại thời điểm xác minh.*",
    ])
    return "\n".join(lines)


def _build_html_summary_for_pdf(res: VerificationResponse) -> str:
    claim_blocks: list[str] = []
    for c in res.claims:
        color = VERDICT_HEX.get(c.verdict, "#374151")
        ev_items = "".join(
            f"<li>[Cấp {e.tier} - {escape(e.stance.value)}] <b>{escape(e.title)}</b> ({escape(e.domain)})</li>"
            for e in (c.supporting_evidence + c.refuting_evidence + c.contextual_evidence)[:4]
        )
        rewrite_html = (
            f"<p><b>Gợi ý sửa thận trọng:</b> <i>{escape(c.suggested_correction.cautious_rewrite)}</i></p>"
            if c.suggested_correction
            else ""
        )
        claim_blocks.append(
            f"""
            <div style="margin-bottom: 12pt; padding: 8pt; border-left: 3pt solid {color}; background-color: #f8fafc;">
                <p style="margin:0 0 4pt 0;"><b>[{escape(c.claim_id)}] <span style="color:{color};">{escape(c.verdict_label_vi)}</span></b></p>
                <p style="margin:0 0 4pt 0;"><b>Văn bản gốc:</b> "{escape(c.original_text)}"</p>
                <p style="margin:0 0 4pt 0;"><b>Giải thích:</b> {escape(c.explanation)}</p>
                {rewrite_html}
                {f'<ul>{ev_items}</ul>' if ev_items else ''}
            </div>
            """
        )

    return f"""
    <div style="font-family: sans-serif; font-size: 9.5pt; line-height: 1.4; color: #0f172a;">
        <h1 style="font-size: 15pt; color: #0f172a; margin-bottom: 4pt;">BÁO CÁO ĐÍNH KÈM – TRUECHECK AI</h1>
        <p style="color: #475569; margin-bottom: 10pt;">
            Tài liệu: <b>{escape(res.source_title)}</b> | Thời điểm xác minh: {escape(res.verified_at)}
        </p>
        {''.join(claim_blocks)}
        <hr/>
        <p style="font-size: 8.5pt; color: #64748b;">
            Nguyên tắc kiểm chứng: Tách biệt Fact Accuracy và Manipulation Signals. Chưa đủ bằng chứng không đồng nghĩa với thông tin sai.
        </p>
    </div>
    """


def generate_annotated_pdf(
    res: VerificationResponse,
    original_file_path: Optional[Path] = None,
) -> bytes:
    """
    Generates an Annotated PDF (Phần III.2):
    - If original file is a PDF: highlights claim quotes directly on original pages with
      color-coded annotations & pop-up notes, then appends the TrueCheck Verification Appendix.
    - Otherwise: renders a full Vietnamese UTF-8 Verification PDF report via PyMuPDF Story.
    """
    import fitz

    if original_file_path and original_file_path.exists() and original_file_path.suffix.lower() == ".pdf":
        doc = fitz.open(str(original_file_path))
        for claim in res.claims:
            snippet = claim.original_text.strip()
            if len(snippet) < 8:
                continue
            search_term = snippet[:85]
            rgb = VERDICT_PDF_RGB.get(claim.verdict, (0.95, 0.95, 0.65))
            target_pages = (
                [claim.page_number - 1]
                if (claim.page_number and 1 <= claim.page_number <= len(doc))
                else list(range(len(doc)))
            )
            for pno in target_pages:
                page = doc[pno]
                quads = page.search_for(search_term, quads=True)
                if quads:
                    annot = page.add_highlight_annot(quads)
                    annot.set_colors(stroke=rgb)
                    annot.set_info(
                        title=f"TrueCheck AI [{claim.claim_id}]",
                        content=f"{claim.verdict_label_vi}\n\n{claim.explanation}",
                    )
                    annot.update()
                    break
    else:
        doc = fitz.open()

    # Append UTF-8 Vietnamese Verification Summary pages using fitz.Story
    html_content = _build_html_summary_for_pdf(res)
    story = fitz.Story(html=html_content)
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (36, 36, -36, -36)

    more = True
    while more:
        page = doc.new_page(width=mediabox.width, height=mediabox.height)
        more, _ = story.place(where)
        story.draw(page)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

