from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.routers._placeholders import placeholder_response
from app.schemas.projects import ChatMessageResponse, ProjectMessagesResponse
from app.services.project_from_chat import get_project_conversation_id, list_project_messages


router = APIRouter(prefix="/projects/{project_id}", tags=["chat"])


@router.post("/chat")
def post_chat_message(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="chat",
        action="post_chat_message",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.get("/messages", response_model=ProjectMessagesResponse)
def list_project_messages_endpoint(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectMessagesResponse:
    conversation_id = get_project_conversation_id(db, project_id)
    if conversation_id is None:
        raise HTTPException(status_code=404, detail="Project conversation not found")

    messages = list_project_messages(db, project_id)
    return ProjectMessagesResponse(
        project_id=project_id,
        conversation_id=conversation_id,
        messages=[
            ChatMessageResponse(
                id=message.id,
                sender=message.sender,
                message_type=message.message_type,
                content=message.content,
                metadata_json=message.metadata_json,
            )
            for message in messages
        ],
    )
