import { apiClient } from "@/shared/api/api-client";
import type { ContractConfirm, ContractDetail, ContractList } from "../model/types";

export function confirmDocument(
  documentId: string,
  payload: ContractConfirm,
): Promise<ContractDetail> {
  return apiClient<ContractDetail>(`/documents/${documentId}/confirm`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function listContracts(): Promise<ContractList> {
  return apiClient<ContractList>("/contracts");
}

export function getContract(contractId: string): Promise<ContractDetail> {
  return apiClient<ContractDetail>(`/contracts/${contractId}`);
}
