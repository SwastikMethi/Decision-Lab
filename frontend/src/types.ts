import type { components } from "./api-schema";
export type RunConfig = components["schemas"]["RunConfiguration"];
export type Json =
  string | number | boolean | null | Json[] | { [key: string]: Json };
export interface Metric {
  value: number | null;
  numerator: number | null;
  denominator: number;
  unavailable_reason?: string;
  ci95?: number[] | null;
}
export interface RiskPoint {
  threshold: number;
  accepted: number;
  errors: number;
  denominator: number;
  coverage: number;
  risk: number | null;
  unstable: boolean;
  escalations?: number;
}
export interface Bin {
  lower: number;
  upper: number;
  count: number;
  confidence: number | null;
  accuracy: number | null;
}
export interface Robustness {
  variant: string;
  primitive: string;
  count: number;
  comparable_count: number;
  missing_pairs: number;
  answer_flip_rate: number | null;
  harmful_flip_rate: number;
  beneficial_flip_rate: number;
  accuracy_delta: number;
  probability_drift: Metric;
  case_ids: string[];
}
export interface SystemMetrics {
  correctness: {
    accuracy: Metric;
    answered_accuracy: Metric;
    macro_f1: Metric;
    ordinal_mae: Metric;
    ranked_probability_score: Metric;
    auroc: Metric;
  };
  calibration: {
    brier: Metric;
    log_loss: Metric;
    ece: Metric;
    bins: Bin[];
    excluded: number;
    confidence_histogram: {
      lower: number;
      upper: number;
      count: number;
      correct: number;
      incorrect: number;
    }[];
    confidence_distribution: { confidence: number; correct: boolean }[];
  };
  selective_automation: {
    curve: RiskPoint[];
    thresholds: RiskPoint[];
    operating_points: { target_risk: number; point: RiskPoint | null }[];
    signal: string;
    frozen_policy: {
      accepted: number;
      denominator: number;
      errors: number;
      coverage: number;
      risk: number | null;
      unstable: boolean;
    } | null;
  };
  robustness: Robustness[];
  repeatability: {
    case_id: string;
    calls: number;
    valid: number;
    modal_agreement: number | null;
    any_flip: boolean | null;
    mean_probability_std: number | null;
    max_probability_std: number | null;
    mean_js_divergence: number | null;
  }[];
  performance: {
    warm_p50_ms: number | null;
    warm_p95_ms: number | null;
    warm_p99_ms: number | null;
    warm_count: number;
    latencies: number[];
    warmup?: { cold_start_ms: number } | null;
    load_tests: {
      concurrency: number;
      batch_size: number;
      count: number;
      questions_per_second: number | null;
      failures: number;
      queue_p50_ms: number;
    }[];
  };
  cost: {
    provider_reported_total_usd: number | null;
    estimated_api_total_usd: number | null;
    per_1000_decisions_usd: number | null;
    estimated_local_total_usd?: number;
    local_basis?: string;
  };
  failures: {
    count: number;
    denominator: number;
    rate: number | null;
    retries: number;
    categories: Record<string, number>;
  };
  diagnostics: {
    variant: string;
    bucket: number;
    accuracy: number;
    count: number;
    failures: number;
  }[];
  resources?: Record<string, Json>;
}
export interface Summary {
  run_id: string;
  scoring_version: string;
  track: string;
  simulation: boolean;
  provisional: boolean;
  partial: boolean;
  status: string;
  counts: {
    cases: number;
    families: number;
    successful_predictions: number;
    failed_predictions: number;
  };
  systems: Record<string, SystemMetrics>;
  slices: {
    system_id: string;
    dimension: string;
    value: string;
    count: number;
    metrics: SystemMetrics;
  }[];
  comparisons: {
    metric: string;
    left: string;
    right: string;
    difference: number | null;
    ci95: number[] | null;
    families: number;
  }[];
  findings: {
    text: string;
    metric_ref: string;
    filters: Record<string, string>;
    exploratory: boolean;
  }[];
  limitations: string[];
  definitions: Record<string, string>;
  sealed_results_withheld: boolean;
  filter_options: { domains: string[] };
}
export interface Manifest {
  run_id: string;
  name: string;
  status: string;
  track: string;
  mode: string;
  created_at: string;
  started_at: string;
  ended_at: string | null;
  effective_config: RunConfig;
  submitted_config: RunConfig;
  dataset_digest: string;
  scoring_version: string;
  progress: {
    completed: number;
    total: number;
    systems: Record<
      string,
      {
        completed: number;
        failures: number;
        retries: number;
        latency_ms?: number;
      }
    >;
  };
  warnings: string[];
  partial: boolean;
  sealed_released: boolean;
  publication: boolean;
  artifacts: string[];
}
export interface Dataset {
  dataset_id: string;
  name: string;
  created_at: string;
  digest: string;
  valid: boolean;
  counts: {
    cases: number;
    families: number;
    primitive: Record<string, number>;
    domain: Record<string, number>;
    split: Record<string, number>;
    variant: Record<string, number>;
  };
  issues: { line: number; field: string; message: string }[];
  review_status: string;
  review?: { approved: number; total: number; complete: boolean };
}
export interface Readiness {
  jev: {
    configured: boolean;
    reachable: boolean | null;
    model: string;
    note: string;
  };
  laya: {
    ready: boolean;
    installed?: boolean;
    reason?: string;
    revision?: string;
    package_version?: string;
    size_bytes?: number;
  };
  storage: { writable: boolean };
  simulation_available: boolean;
}
export interface EvaluationCase {
  id: string;
  family_id: string;
  split: string;
  domain: string;
  primitive: string;
  variant: string;
  state?: Json;
  state_preview?: string;
  question: { id: string; instructions: string; criteria: Json };
  expected: { value: string | number | boolean };
  label_map?: Record<string, string>;
  metadata: Record<string, Json>;
}
export interface Prediction {
  evaluation_id: string;
  adapter_id: string;
  system_id: string;
  case_id: string;
  suite: string;
  status: string;
  answer: {
    selected: string;
    score: number | null;
    probabilities: Record<string, number>;
    raw_probabilities?: Record<string, number>;
    decision_probability: number;
    provider_confidence: number | null;
  } | null;
  timing: {
    latency_ms: number;
    inference_ms: number | null;
    queue_ms?: number;
  };
  usage: Record<string, Json>;
  raw_response?: Json;
  retry_count: number;
  error: { category: string; message: string } | null;
  model: Record<string, Json>;
}
export interface CaseRow {
  case: EvaluationCase;
  predictions: Record<string, Prediction>;
  correctness: Record<string, boolean>;
  disagreement: boolean;
}
export interface CaseDetail extends CaseRow {
  family: CaseRow[];
  all_predictions: Prediction[];
}
export interface Calibration {
  calibration_id: string;
  run_id: string;
  source_mode: string;
  dataset_digest: string;
  parameters: Record<
    string,
    {
      temperature: number;
      threshold: number | null;
      samples: number;
      families: number;
      unstable: boolean;
    }
  >;
}
export interface Protocol {
  protocol_id: string;
  dataset_id: string;
  dataset_digest: string;
  sealed_released: boolean;
  tracks: Record<string, { configuration: RunConfig; fingerprint: string }>;
  runs: Record<string, string>;
}
