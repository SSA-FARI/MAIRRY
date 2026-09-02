import { apiClient } from "@/shared/api/api-client";
import type { ContractConfirm, ContractDetail, ContractList } from "../model/types";
import type { PaymentStatus } from "@/domains/documents";

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

export function updateContract(
  contractId: string,
  payload: ContractConfirm,
): Promise<ContractDetail> {
  return apiClient<ContractDetail>(`/contracts/${contractId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteContract(contractId: string): Promise<void> {
  return apiClient<void>(`/contracts/${contractId}`, { method: "DELETE" });
}

export function updatePaymentStatus(
  contractId: string,
  paymentId: string,
  status: PaymentStatus,
): Promise<ContractDetail> {
  return apiClient<ContractDetail>(`/contracts/${contractId}/payments/${paymentId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
