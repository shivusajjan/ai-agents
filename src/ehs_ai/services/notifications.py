from __future__ import annotations

import uuid
from typing import List

from ehs_ai.schemas import EmailReceipt, NotificationPlan, NotificationResult, TicketReceipt
from ehs_ai.utils.logger import get_logger

logger = get_logger(__name__)


class NotificationService:
    """Executes ticket and email plans. Integrations are stubbed for demo purposes."""

    async def execute(self, plan: NotificationPlan) -> NotificationResult:
        ticket_receipts = await self._create_tickets(plan)
        email_receipts = await self._send_emails(plan)
        notes = "Tickets and emails processed via stub integrations."
        return NotificationResult(plan=plan, tickets=ticket_receipts, emails=email_receipts, notes=notes)

    async def _create_tickets(self, plan: NotificationPlan) -> List[TicketReceipt]:
        receipts: List[TicketReceipt] = []
        for ticket in plan.tickets:
            ticket_id = f"TCK-{uuid.uuid4().hex[:8].upper()}"
            logger.info("Created ticket %s with priority %s", ticket_id, ticket.priority)
            receipts.append(TicketReceipt(ticket_id=ticket_id, status="created", request=ticket))
        return receipts

    async def _send_emails(self, plan: NotificationPlan) -> List[EmailReceipt]:
        receipts: List[EmailReceipt] = []
        for email in plan.emails:
            message_id = f"MSG-{uuid.uuid4().hex[:10]}"
            logger.info("Queued email to %s with subject '%s'", email.recipient, email.subject)
            receipts.append(
                EmailReceipt(
                    recipient=email.recipient,
                    status="sent",
                    request=email,
                    message_id=message_id,
                )
            )
        return receipts

