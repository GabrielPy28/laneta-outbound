export type PostmasterReportListItem = {
  id: string;
  report_type: string;
  domains_requested: number;
  results_count: number;
  errors_count: number;
  email_sent: boolean;
  email_to: string | null;
  created_at: string;
};

export type PostmasterReportDetail = PostmasterReportListItem & {
  email_error: string | null;
  payload: {
    ok?: boolean;
    domains_requested?: number;
    results_count?: number;
    errors_count?: number;
    results?: Array<{
      domain?: string;
      status?: string;
      action?: string;
      summary?: string;
      score?: number;
      evaluated_date?: string | null;
      key_metrics?: Record<string, unknown>;
    }>;
    errors?: Array<{ domain?: string; error?: string }>;
    [key: string]: unknown;
  };
};
