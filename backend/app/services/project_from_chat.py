from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, Conversation, Milestone, Project, ProjectMemory, User
from app.schemas.projects import CreateProjectFromChatRequest, ProjectFromChatResponse


REQUIRED_BUSINESS_INFO = [
    "business name",
    "contact name",
    "business email",
    "store website",
    "country",
    "expected monthly order size",
]


def create_project_from_chat(
    db: Session,
    request: CreateProjectFromChatRequest,
) -> ProjectFromChatResponse:
    user = _get_or_create_user(db, request.user_email, request.user_name)
    sourcing_request = _extract_mock_sourcing_request(request.message)
    project = Project(
        user_id=user.id,
        name=sourcing_request["project_name"],
        description=request.message,
        target_products=sourcing_request["target_products"],
        region=sourcing_request["region"],
        budget={"mock_mode": True, "max_llm_cost_usd": 5},
        status="mock_research",
    )
    db.add(project)
    db.flush()

    conversation = Conversation(project_id=project.id, user_id=user.id)
    db.add(conversation)
    db.flush()

    user_message = ChatMessage(
        conversation_id=conversation.id,
        sender="user",
        message_type="text",
        content=request.message,
        metadata_json={"source": "project_from_chat"},
    )
    understood_message = ChatMessage(
        conversation_id=conversation.id,
        sender="assistant",
        message_type="milestone_update",
        content=(
            "Got it. I will look for UK/EU suppliers that sell Pokemon TCG sealed "
            "products and may accept small retailers. I will report back after each milestone."
        ),
        metadata_json={"milestone": "request_understood", "mock_mode": True},
    )
    missing_info_message = ChatMessage(
        conversation_id=conversation.id,
        sender="assistant",
        message_type="missing_info_prompt",
        content=(
            "Some suppliers ask for business information before they share wholesale pricing. "
            "Please provide the missing details you want me to use."
        ),
        metadata_json={"missing_business_info": REQUIRED_BUSINESS_INFO},
    )
    db.add_all([user_message, understood_message, missing_info_message])
    db.flush()

    memory_items = [
        ProjectMemory(
            project_id=project.id,
            key="original_sourcing_request",
            value={"message": request.message},
            source_message_id=user_message.id,
        ),
        ProjectMemory(
            project_id=project.id,
            key="structured_sourcing_request",
            value=sourcing_request,
            source_message_id=user_message.id,
        ),
        ProjectMemory(
            project_id=project.id,
            key="missing_business_info",
            value={"fields": REQUIRED_BUSINESS_INFO},
            source_message_id=missing_info_message.id,
        ),
    ]
    db.add_all(memory_items)

    request_understood = Milestone(
        project_id=project.id,
        name="request_understood",
        status="complete",
        summary="The user's sourcing request was structured and stored in mock mode.",
        metadata_json=sourcing_request,
    )
    suppliers_discovered = Milestone(
        project_id=project.id,
        name="suppliers_discovered",
        status="pending",
        summary="Mock supplier discovery has not started yet.",
        metadata_json={"mock_mode": True},
    )
    db.add_all([request_understood, suppliers_discovered])
    db.flush()

    db.commit()

    return ProjectFromChatResponse(
        project_id=project.id,
        conversation_id=conversation.id,
        user_id=user.id,
        project_name=project.name,
        status=project.status,
        created_message_ids=[user_message.id, understood_message.id, missing_info_message.id],
        milestone_ids=[request_understood.id, suppliers_discovered.id],
        missing_business_info=REQUIRED_BUSINESS_INFO,
    )


def list_project_messages(db: Session, project_id: int) -> list[ChatMessage]:
    statement: Select[tuple[ChatMessage]] = (
        select(ChatMessage)
        .join(Conversation, ChatMessage.conversation_id == Conversation.id)
        .where(Conversation.project_id == project_id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return list(db.scalars(statement))


def get_project_conversation_id(db: Session, project_id: int) -> int | None:
    statement = select(Conversation.id).where(Conversation.project_id == project_id).order_by(Conversation.id)
    return db.scalar(statement)


def _get_or_create_user(db: Session, email: str, name: str | None) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user

    user = User(email=email, name=name)
    db.add(user)
    db.flush()
    return user


def _extract_mock_sourcing_request(message: str) -> dict:
    normalized = message.lower()
    region = "UK/EU" if "uk" in normalized or "eu" in normalized else "Unspecified"
    products = ["Pokemon TCG sealed products"]
    if "booster" in normalized:
        products.append("booster boxes")
    if "etb" in normalized:
        products.append("ETBs")

    return {
        "project_name": "Pokemon TCG sourcing" if "pokemon" in normalized else "Sourcing project",
        "target_products": products,
        "region": region,
        "supplier_preferences": ["accepts small retailers"] if "small retailer" in normalized else [],
        "mock_mode": True,
    }

