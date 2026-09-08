TOOLS = {
    "getUserContracts": {
        "description": "현재 사용자의 활성 웨딩 계획에서 확정 계약 보유 현황을 조회합니다.",
        "required": [],
    },
    "getContractDetails": {
        "description": "특정 계약의 지급·취소조건과 원문 근거를 조회합니다.",
        "required": ["contractId"],
    },
    "getContractDeposit": {
        "description": "특정 확정 계약의 계약금·예약금 지급항목과 상태를 조회합니다.",
        "required": ["contractId"],
    },
    "getContractPayments": {
        "description": "확정 계약의 미지급 잔금과 지급항목을 조회합니다.",
        "required": [],
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
