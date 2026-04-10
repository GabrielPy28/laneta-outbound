export type LeadListItem = {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  company_name: string | null;
  job_title: string | null;
  engagement_status: string | null;
  sequence_status: string | null;
  campaign_id: string | null;
  smartlead_lead_id: string | null;
  hubspot_contact_id: string | null;
  total_opens: number;
  total_clicks: number;
  total_replies: number;
  last_sequence_step: string | null;
  lead_score: number | null;
  reply_type: string | null;
  is_qualified: boolean | null;
  updated_at: string;
};

export type LeadListResponse = {
  items: LeadListItem[];
  total: number;
};
