import { describe, expect, it } from "vitest";
import type { DocumentDetail } from "@/domains/documents";
import {
  createReviewForm,
  hasReviewErrors,
  toContractConfirm,
  validateReviewForm,
} from "./review-form";

const document: DocumentDetail = {
  id: "8f32eb5e-a2ac-44be-8ce8-393d466bc901",
  originalName: "hall.pdf",
  status: "REVIEW_REQUIRED",
  analysisSource: "DEMO_FALLBACK",
  extraction: {
    documentType: "WEDDING_HALL",
    company: "A웨딩홀",
    totalPrice: 23_000_000,
    payments: [
      {
        name: "잔금",
        amount: 20_000_000,
        dueDate: "2027-04-30",
        status: "UNPAID",
        sourceText: "잔금 20,000,000원은 2027년 4월 30일까지",
      },
    ],
    cancellationTerms: [],
    warnings: [],
  },
  error: null,
};

describe("contract review form", () => {
  it("uses extraction values as editable initial values", () => {
    expect(createReviewForm(document)).toMatchObject({
      company: "A웨딩홀",
      totalPrice: "23000000",
      payments: [{ name: "잔금", amount: "20000000", dueDate: "2027-04-30" }],
    });
  });

  it("blocks an empty company, invalid amount, and empty payments", () => {
    const form = createReviewForm(document);
    form.company = " ";
    form.totalPrice = "-1";
    form.payments = [];

    const errors = validateReviewForm(form);

    expect(hasReviewErrors(errors)).toBe(true);
    expect(errors.company).toBeDefined();
    expect(errors.totalPrice).toBeDefined();
    expect(errors.payments).toBeDefined();
  });

  it("converts validated text inputs to the OpenAPI confirmation payload", () => {
    const form = createReviewForm(document);
    form.company = "  수정 웨딩홀  ";

    expect(toContractConfirm(form)).toEqual({
      documentType: "WEDDING_HALL",
      company: "수정 웨딩홀",
      totalPrice: 23_000_000,
      payments: [
        {
          name: "잔금",
          amount: 20_000_000,
          dueDate: "2027-04-30",
          status: "UNPAID",
          sourceText: "잔금 20,000,000원은 2027년 4월 30일까지",
        },
      ],
      cancellationTerms: [],
    });
  });
});
