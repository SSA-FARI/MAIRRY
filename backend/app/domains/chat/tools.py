from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai.common.types import ToolResultView, ToolStatus
from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.contracts.models import Contract, Payment
from app.domains.contracts.repository import ContractRepository
from app.domains.contracts.service import build_contract_detail
from app.domains.finance.service import FinanceService
from app.domains.wedding_plan.repository import WeddingPlanRepository

NowProvider = Callable[[], datetime]
TodayProvider = Callable[[], date]


class ChatToolRegistry:
    def __init__(
        self,
        session: Session,
        configuration: Settings,
        *,
        now_provider: NowProvider | None = None,
        today_provider: TodayProvider | None = None,
    ) -> None:
        self._configuration = configuration
        self._plans = WeddingPlanRepository(session)
        self._contracts = ContractRepository(session)
        self._finance = FinanceService(session, configuration)
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._today_provider = today_provider or date.today

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: UUID,
    ) -> ToolResultView:
        tools = {
            "getContractDetails": self._get_contract_details,
            "getUpcomingPayments": self._get_upcoming_payments,
            "getFinanceSummary": self._get_finance_summary,
            "simulateAdditionalExpense": self._simulate_additional_expense,
        }
        tool = tools.get(tool_name)
        if tool is None:
            return self._failure(
                "INVALID_ARGUMENT",
                tool_name,
                "지원하지 않는 Tool입니다.",
            )
        try:
            return tool(arguments, user_id)
        except (KeyError, TypeError, ValueError, ValidationError):
            return self._failure(
                "INVALID_ARGUMENT",
                tool_name,
                "질문에 필요한 입력값을 확인해 주세요.",
            )
        except AppError as exc:
            if exc.code == ErrorCode.RESOURCE_NOT_FOUND:
                tool_status: ToolStatus = (
                    "INSUFFICIENT_DATA"
                    if tool_name in {"getFinanceSummary", "simulateAdditionalExpense"}
                    else "NOT_FOUND"
                )
                return self._failure(tool_status, tool_name, exc.message)
            return self._failure(
                "TOOL_ERROR",
                tool_name,
                "정보를 조회하는 중 일시적인 오류가 발생했습니다.",
            )
        except SQLAlchemyError:
            return self._failure(
                "TOOL_ERROR",
                tool_name,
                "정보를 조회하는 중 일시적인 오류가 발생했습니다.",
            )

    def resolve_contract_id(self, message: str, user_id: UUID) -> UUID | None:
        plan = self._plans.get_current_for_user(user_id)
        if plan is None:
            return None
        contracts = self._contracts.list_confirmed(plan.id)
        matching = [contract for contract in contracts if contract.company in message]
        if len(matching) == 1:
            return matching[0].id
        if not matching and len(contracts) == 1:
            return contracts[0].id
        return None

    def _get_contract_details(
        self,
        arguments: dict[str, Any],
        user_id: UUID,
    ) -> ToolResultView:
        contract_id = UUID(str(arguments["contractId"]))
        plan = self._plans.get_current_for_user(user_id)
        contract = self._contracts.get_confirmed(plan.id, contract_id) if plan is not None else None
        if contract is None:
            return self._failure(
                "NOT_FOUND",
                "getContractDetails",
                "요청한 확정 계약을 찾을 수 없습니다.",
            )
        detail = build_contract_detail(contract)
        return self._success(
            "getContractDetails",
            detail.model_dump(mode="json", by_alias=True),
            self._contract_evidence(contract),
        )

    def _get_upcoming_payments(
        self,
        arguments: dict[str, Any],
        user_id: UUID,
    ) -> ToolResultView:
        from_date = self._optional_date(arguments.get("from")) or self._today_provider()
        to_date = self._optional_date(arguments.get("to"))
        if to_date is not None and from_date > to_date:
            raise ValueError("from must be before to")
        limit = arguments.get("limit", 5)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        contract_id = self._optional_uuid(arguments.get("contractId"))

        plan = self._plans.get_current_for_user(user_id)
        if plan is None:
            return self._failure(
                "NOT_FOUND",
                "getUpcomingPayments",
                "현재 웨딩 계획을 찾을 수 없습니다.",
            )
        contracts = self._contracts.list_confirmed(plan.id)
        if contract_id is not None:
            contracts = [contract for contract in contracts if contract.id == contract_id]
            if not contracts:
                return self._failure(
                    "NOT_FOUND",
                    "getUpcomingPayments",
                    "요청한 확정 계약을 찾을 수 없습니다.",
                )

        candidates = sorted(
            (
                (contract, payment)
                for contract in contracts
                for payment in contract.payments
                if payment.status.value == "UNPAID"
                and payment.due_date is not None
                and payment.due_date >= from_date
                and (to_date is None or payment.due_date <= to_date)
            ),
            key=lambda item: (item[1].due_date, item[1].created_at, item[1].id),
        )[:limit]
        if not candidates:
            return self._failure(
                "NOT_FOUND",
                "getUpcomingPayments",
                "조건에 맞는 미지급 일정을 찾을 수 없습니다.",
            )

        payments = [self._payment_data(contract, payment) for contract, payment in candidates]
        evidence = [
            self._payment_evidence(contract, payment)
            for contract, payment in candidates
            if payment.source_text
        ]
        return self._success("getUpcomingPayments", {"payments": payments}, evidence)

    def _get_finance_summary(
        self,
        arguments: dict[str, Any],
        user_id: UUID,
    ) -> ToolResultView:
        if arguments:
            raise ValueError("getFinanceSummary does not accept arguments")
        summary = self._finance.get_summary(user_id=user_id)
        data = summary.model_dump(mode="json", by_alias=True)
        return self._success("getFinanceSummary", data, [])

    def _simulate_additional_expense(
        self,
        arguments: dict[str, Any],
        user_id: UUID,
    ) -> ToolResultView:
        name = arguments["name"]
        amount = arguments["amount"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("amount must be a positive integer")
        simulation = self._finance.simulate(amount, user_id=user_id)
        data = {"name": name.strip(), **simulation.model_dump(mode="json", by_alias=True)}
        return self._success("simulateAdditionalExpense", data, [])

    def _success(
        self,
        tool_name: str,
        data: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> ToolResultView:
        return ToolResultView(
            status="SUCCESS",
            tool_name=tool_name,
            data=data,
            evidence=evidence,
            calculated_at=self._now_provider(),
            error=None,
        )

    def _failure(
        self,
        status: ToolStatus,
        tool_name: str,
        message: str,
    ) -> ToolResultView:
        return ToolResultView(
            status=status,
            tool_name=tool_name,
            data=None,
            evidence=[],
            calculated_at=self._now_provider(),
            error={"message": message},
        )

    @staticmethod
    def _optional_date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _optional_uuid(value: Any) -> UUID | None:
        return UUID(str(value)) if value is not None else None

    @staticmethod
    def _payment_data(contract: Contract, payment: Payment) -> dict[str, Any]:
        assert payment.due_date is not None
        return {
            "contractId": str(contract.id),
            "company": contract.company,
            "name": payment.name,
            "amount": payment.amount,
            "dueDate": payment.due_date.isoformat(),
            "status": payment.status.value,
        }

    @staticmethod
    def _payment_evidence(contract: Contract, payment: Payment) -> dict[str, Any]:
        return {
            "contractId": str(contract.id),
            "label": f"{contract.company} · {payment.name}",
            "sourceText": payment.source_text,
        }

    def _contract_evidence(self, contract: Contract) -> list[dict[str, Any]]:
        payment_evidence = [
            self._payment_evidence(contract, payment)
            for payment in contract.payments
            if payment.source_text
        ]
        term_evidence = [
            {
                "contractId": str(contract.id),
                "label": f"{contract.company} · 취소조건",
                "sourceText": term.source_text,
            }
            for term in contract.cancellation_terms
            if term.source_text
        ]
        return [*payment_evidence, *term_evidence]
