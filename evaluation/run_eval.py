"""
TrueCheck AI – Benchmark Evaluation Runner (Phần X)
Đo lường tự động các chỉ số chất lượng cốt lõi:
- Claim Extraction Recall (Mục tiêu >= 90%)
- Citation Validity Rate (Mục tiêu >= 95%)
- Correct Verdict Rate (Mục tiêu >= 85%)
- False Accusation Rate (Mục tiêu < 5% - Gán nhãn REFUTED sai cho mệnh đề đúng/ý kiến/thiếu dữ liệu)
- Average Latency (Mục tiêu 5–15 giây)
"""

import argparse
import json
from pathlib import Path
import statistics
import time
import urllib.request


def post_verify(api_base: str, text: str) -> tuple[dict, float]:
    url = f"{api_base.rstrip('/')}/api/v1/verify/text"
    payload = json.dumps({"text": text, "use_claim_memory": False}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=45) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - t0
    return body, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TrueCheck AI Vietnamese Benchmark")
    parser.add_argument("--api", default="http://localhost:8000", help="TrueCheck Backend URL")
    parser.add_argument(
        "--dataset",
        default=str(Path(__file__).resolve().parent / "vn_benchmark_seed.json"),
        help="Path to benchmark JSON file",
    )
    args = parser.parse_args()

    samples = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    total_expected_claims = 0
    total_extracted_claims = 0
    verdict_matches = 0
    false_accusations = 0
    total_non_false_samples = 0
    validated_citations = 0
    decisive_citations_total = 0
    latencies: list[float] = []

    print(f"=== CHẠY ĐÁNH GIÁ CHẤT LƯỢNG TRUECHECK AI ({len(samples)} mẫu) ===\n")

    for item in samples:
        res, sec = post_verify(args.api, item["input_text"])
        latencies.append(sec)
        claims = res.get("claims", [])

        exp_cnt = int(item["expected_claim_count"])
        ext_cnt = min(len(claims), exp_cnt)
        total_expected_claims += exp_cnt
        total_extracted_claims += ext_cnt

        primary_verdict = claims[0]["verdict"] if claims else "NONE"
        matched = primary_verdict == item["expected_verdict"]
        if matched:
            verdict_matches += 1

        if item.get("is_actually_true_or_unverified"):
            total_non_false_samples += 1
            if primary_verdict == "REFUTED":
                false_accusations += 1

        for c in claims:
            for ev in c.get("supporting_evidence", []) + c.get("refuting_evidence", []):
                decisive_citations_total += 1
                if ev.get("citation_validated"):
                    validated_citations += 1

        print(
            f"[{item['id']}] Claims: {len(claims)}/{exp_cnt} | "
            f"Verdict: {primary_verdict} (Kỳ vọng: {item['expected_verdict']}) | "
            f"Time: {sec:.2f}s"
        )

    recall = (total_extracted_claims / total_expected_claims * 100) if total_expected_claims else 0.0
    verdict_acc = (verdict_matches / len(samples) * 100) if samples else 0.0
    false_acc_rate = (
        (false_accusations / total_non_false_samples * 100) if total_non_false_samples else 0.0
    )
    citation_validity = (
        (validated_citations / decisive_citations_total * 100)
        if decisive_citations_total
        else 100.0
    )
    avg_latency = statistics.mean(latencies) if latencies else 0.0

    print("\n=== TỔNG HỢP CHỈ SỐ CHẤT LƯỢNG (PHẦN X) ===")
    print(f"- Claim Extraction Recall : {recall:.1f}% (Mục tiêu >= 90%)")
    print(f"- Citation Validity       : {citation_validity:.1f}% (Mục tiêu >= 95%)")
    print(f"- Correct Verdict Rate    : {verdict_acc:.1f}% (Mục tiêu >= 85%)")
    print(f"- False Accusation Rate   : {false_acc_rate:.1f}% (Mục tiêu < 5%)")
    print(f"- Avg Response Time       : {avg_latency:.2f}s (Mục tiêu 5–15s)")


if __name__ == "__main__":
    main()

