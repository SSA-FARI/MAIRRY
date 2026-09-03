export type AnswerType = "CONTRACT" | "CALCULATION" | "NOT_FOUND";

export interface Citation {
  contractId: string;
  label: string;
  sourceText: string;
}

interface CalculationBase {
  toolName: string;
  calculatedAt: string;
}

export interface FinanceCalculation extends CalculationBase {
  availableAsset: number;
  remainingExpense: number;
  expectedBalance: number;
}

export interface SimulationCalculation extends CalculationBase {
  currentExpectedBalance: number;
  simulatedExpectedBalance: number;
  shortageAmount: number;
}

export interface ChatResponse {
  answer: string;
  answerType: AnswerType;
  citations: Citation[];
  calculation: FinanceCalculation | SimulationCalculation | null;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
}
