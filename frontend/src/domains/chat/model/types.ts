export type AnswerType = "CONTRACT" | "CALCULATION" | "NOT_FOUND" | "RAG" | "MIXED";

export interface Citation {
  contractId: string | null;
  documentId?: string | null;
  sourceType?: "CONTRACT_CLAUSE" | "SERVICE_FAQ" | "DOMAIN_KNOWLEDGE" | "CURATED_QA";
  title?: string | null;
  clauseTitle?: string | null;
  page?: number | null;
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
  conversationId?: string | null;
  messageId?: string | null;
  answer: string;
  answerType: AnswerType;
  citations: Citation[];
  calculation: FinanceCalculation | SimulationCalculation | null;
  usedRag?: boolean;
}

export interface ChatMessage {
  id: number | string;
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
}
