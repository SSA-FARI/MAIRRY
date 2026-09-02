export interface UpcomingPayment {
  contractId: string;
  company: string;
  name: string;
  amount: number;
  dueDate: string;
}

export interface FinanceSummary {
  availableAsset: number;
  remainingExpense: number;
  expectedBalance: number;
  nearestPayment: UpcomingPayment | null;
  timeline: UpcomingPayment[];
}

export interface SimulationRequest {
  name: string;
  amount: number;
}

export interface SimulationResult {
  currentExpectedBalance: number;
  simulatedExpectedBalance: number;
  shortageAmount: number;
}
