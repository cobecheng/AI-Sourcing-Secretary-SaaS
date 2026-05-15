from fastapi import APIRouter


router = APIRouter(prefix="/mock", tags=["mock"])


@router.get("/workspace")
def get_mock_workspace() -> dict:
    return {
        "project": {
            "id": "demo-project",
            "name": "UK/EU Pokemon TCG distributors",
            "status": "Mock research in progress",
            "supplier_count": 14,
            "pending_approvals": 2,
            "unread_replies": 0,
        },
        "messages": [
            {
                "sender": "user",
                "type": "text",
                "content": "Find Pokemon TCG distributors in the UK or EU. I want sealed products like booster boxes and ETBs. Prefer suppliers that accept small retailers.",
            },
            {
                "sender": "assistant",
                "type": "milestone_update",
                "content": "Milestone complete: request understood. I will search for official distributors, wholesalers, importers, and specialist TCG suppliers.",
            },
            {
                "sender": "assistant",
                "type": "milestone_update",
                "content": "Milestone complete: 14 mock suppliers look relevant. I am preparing outreach drafts for approval.",
            },
        ],
        "suppliers": [
            {
                "id": "supplier-1",
                "name": "CardTrade Wholesale",
                "country": "UK",
                "status": "Email Drafted",
                "contact_method": "email",
                "relevance_score": 0.91,
                "trust_score": 0.78,
            },
            {
                "id": "supplier-2",
                "name": "EU TCG Distribution",
                "country": "EU",
                "status": "Contact Form Found",
                "contact_method": "form",
                "relevance_score": 0.87,
                "trust_score": 0.73,
            },
        ],
        "approvals": [
            {
                "id": "approval-1",
                "type": "email_send",
                "supplier": "CardTrade Wholesale",
                "status": "pending",
                "title": "Approve supplier outreach email",
            },
            {
                "id": "approval-2",
                "type": "contact_form_submit",
                "supplier": "EU TCG Distribution",
                "status": "pending",
                "title": "Review contact form payload before submission",
            },
        ],
    }

