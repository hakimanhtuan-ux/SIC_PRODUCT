export type VerdictType =
  | "SUPPORTED"
  | "REFUTED"
  | "MISLEADING"
  | "INSUFFICIENT_EVIDENCE"
  | "CONFLICTING_EVIDENCE"
  | "NOT_VERIFIABLE";

export type ClaimType =
  | "FACTUAL_CLAIM"
  | "OPINION"
  | "PREDICTION"
  | "SATIRE"
  | "UNVERIFIABLE";

export type EvidenceStance = "SUPPORTING" | "REFUTING" | "CONTEXTUAL";

export interface EvidenceEvaluationScores {
  relevance: number;
  credibility: number;
  timeliness: number;
  context: number;
  consistency: number;
  traceability: number;
}

export interface EvidenceItem {
  id: string;
  title: string;
  url: string;
  domain: string;
  publisher: string;
  published_date?: string | null;
  tier: number;
  tier_label: string;
  stance: EvidenceStance;
  snippet: string;
  scores: EvidenceEvaluationScores;
  citation_validated: boolean;
  validation_note: string;
}

export interface SuggestedCorrection {
  original_span: string;
  cautious_rewrite: string;
  rationale: string;
  distinction_note: string;
}

export interface ManipulationSignal {
  signal_type:
    | "CLICKBAIT"
    | "EMOTIONAL_MANIPULATION"
    | "CHERRY_PICKING"
    | "MISLEADING_STATISTICS"
    | "FALSE_AUTHORITY"
    | "MISSING_CONTEXT";
  label_vi: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | string;
  trigger_phrase: string;
  explanation: string;
}

export interface DocumentSegment {
  segment_id: string;
  text: string;
  start_char: number;
  end_char: number;
  page_number?: number | null;
  block_type: string;
}

export interface ClaimVerificationResult {
  claim_id: string;
  original_text: string;
  normalized_claim: string;
  claim_type: ClaimType;
  claim_type_label_vi: string;
  check_category: string;
  topic_category: string;
  start_char: number;
  end_char: number;
  page_number?: number | null;

  verdict: VerdictType;
  verdict_label_vi: string;
  evidence_completeness: number;
  explanation: string;
  missing_information: string[];
  limitations: string;

  supporting_evidence: EvidenceItem[];
  refuting_evidence: EvidenceItem[];
  contextual_evidence: EvidenceItem[];

  suggested_correction?: SuggestedCorrection | null;
  from_claim_memory: boolean;
  memory_version: number;
  verified_at: string;
}

export interface PrivacyScanInfo {
  has_pii: boolean;
  pii_types: string[];
  privacy_notice?: string | null;
  prompt_injection_detected: boolean;
  injection_warnings: string[];
  ocr_required_pages: number[];
}

export type ImageAuthenticityType =
  | "AUTHENTIC_LIKELY"
  | "EDITED_COLOR_OR_RETOUCH"
  | "EDITED_OR_SPLICED"
  | "FACE_SWAP_OR_DEEPFAKE"
  | "AI_GENERATED"
  | "SCREENSHOT_OR_MEME"
  | "INCONCLUSIVE_LOW_QUALITY";

export interface ForensicRegionBox {
  region_id: string;
  label_vi: string;
  category:
    | "FACE_ANOMALY"
    | "SPLICING"
    | "LIGHTING"
    | "AI_ARTIFACT"
    | "EDITED_TEXT"
    | string;
  severity: "LOW" | "MEDIUM" | "HIGH" | string;
  confidence: number;
  box_2d: [number, number, number, number] | number[];
  explanation_vi: string;
}

export interface ImageOriginProbabilityBreakdown {
  authentic_pct: number;
  edited_spliced_pct: number;
  face_swap_deepfake_pct: number;
  ai_generated_pct: number;
}

export interface TechnicalForensicsInfo {
  format: string;
  width: number;
  height: number;
  file_size_kb: number;
  has_exif: boolean;
  camera_info?: string | null;
  software_traces: string[];
  c2pa_or_ai_watermark?: string | null;
  ela_mean_error: number;
  ela_regional_inconsistency: number;
  ela_heatmap_data_url?: string | null;
  preview_data_url?: string | null;
}

export interface ImageForensicsReport {
  authenticity_verdict: ImageAuthenticityType;
  authenticity_label_vi: string;
  tamper_confidence_pct: number;
  faces_detected: number;
  face_swap_risk_pct: number;
  face_analysis_vi: string;
  lighting_and_blend_vi: string;
  summary_explanation_vi: string;
  origin_probabilities: ImageOriginProbabilityBreakdown;
  suspicious_regions: ForensicRegionBox[];
  forensic_signals: string[];
  extracted_ocr_text: string;
  limitations_vi: string;
  technical: TechnicalForensicsInfo;
}

export interface VerificationResponse {
  request_id: string;
  document_id: string;
  source_type: "TEXT" | "DOCUMENT" | "URL" | "IMAGE" | string;
  source_title: string;
  source_url?: string | null;
  full_text: string;
  segments: DocumentSegment[];
  claims: ClaimVerificationResult[];
  image_forensics?: ImageForensicsReport | null;
  manipulation_signals: ManipulationSignal[];
  manipulation_summary: string;
  privacy_scan: PrivacyScanInfo;
  summary_counts: Record<string, number>;
  engine_mode: "LIVE_AI" | "HYBRID" | "DEMO_FALLBACK" | string;
  processing_time_ms: number;
  verified_at: string;
}

export interface HealthStatus {
  status: string;
  database: string;
  redis_connected: boolean;
  engine_ready_mode: string;
  providers: {
    gemini_configured: boolean;
    gemini_model: string;
    google_factcheck_configured: boolean;
    tavily_configured: boolean;
    google_cse_configured: boolean;
  };
}

export interface ClaimMemoryItem {
  id: string;
  normalized_claim: string;
  topic_category: string;
  verdict: VerdictType;
  verdict_label_vi: string;
  evidence_completeness: number;
  version: number;
  hit_count: number;
  verified_at: string;
  expires_at: string;
  evidence_count: number;
}

export interface ClaimMemoryOverview {
  items: ClaimMemoryItem[];
  topic_trends: Array<{ topic: string; total_queries: number }>;
}

