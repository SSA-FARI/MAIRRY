TOOLS = {
    "getContractDetails": {
        "description": "특정 계약의 지급·취소조건과 원문 근거를 조회합니다.",
        "required": ["contractId"],
    },
    "getUpcomingPayments": {
        "description": "확정된 향후 지급 일정을 조회합니다.",
        "required": [],
    },
    "getFinanceSummary": {
        "description": "남은 확정지출과 예상 잔액을 조회합니다.",
        "required": [],
    },
    "simulateAdditionalExpense": {
        "description": "추가지출 반영 후 예상 잔액과 부족액을 계산합니다.",
        "required": ["name", "amount"],
    },
}

