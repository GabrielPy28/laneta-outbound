export type CampaignActiveRow = {
  id: string;
  id_campaign: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type CampaignActiveGetResponse = {
  active: CampaignActiveRow | null;
  effective_id_campaign: string;
};

export type CampaignActiveSetResponse = CampaignActiveRow & {
  effective_id_campaign: string;
};
