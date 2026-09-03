export interface WeddingPlan {
  id: string;
  weddingDate: string;
  availableAsset: number;
}

export interface WeddingPlanUpsert {
  weddingDate: string;
  availableAsset: number;
}
