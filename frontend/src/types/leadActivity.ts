export type LeadActivityHeader = {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  display_name: string;
};

export type LeadStatisticsActivity = {
  campaign_id: string | null;
  last_sequence_step: string | null;
  total_opens: number;
  total_clicks: number;
  total_replies: number;
  lead_score: number | null;
  last_event_type: string | null;
  updated_at: string;
};

export type LeadMessageActivity = {
  id: string;
  message_id: string;
  subject: string | null;
  direction: string;
  sent_at: string | null;
  opened_at: string | null;
  received_at: string | null;
  email_body: string | null;
  reply_intent: string | null;
  created_at: string;
};

export type LeadActivityResponse = {
  lead: LeadActivityHeader;
  statistics: LeadStatisticsActivity | null;
  messages: LeadMessageActivity[];
};
