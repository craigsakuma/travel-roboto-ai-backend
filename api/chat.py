"""
Chat API endpoints for Travel Concierge agent.

Provides POST /chat endpoint for conversational travel assistance.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents import TravelConciergeAgent
from config import Settings, get_settings
from db.models import Conversation, Message
from db.session import get_db
from models.factory import get_llm_factory
from schemas.messages import ChatRequest, ChatResponse
from tools import ToolRegistry, register_trip_tools
from utils.logging import get_agent_logger

logger = get_agent_logger("chat_api")

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """
    Process a chat message through the Travel Concierge agent.

    Args:
        request: Chat request with user message and conversation context
        db: Database session
        settings: Application settings

    Returns:
        ChatResponse with assistant's reply and metadata

    Raises:
        HTTPException: If conversation not found or processing fails
    """
    logger.logger.info(
        "Processing chat request",
        extra={
            "user_id": request.user_id,
            "trip_id": request.trip_id,
            "conversation_id": request.conversation_id,
        },
    )

    try:
        # Get or create conversation
        conversation_id, conversation_history = await _get_or_create_conversation(
            db, request
        )

        # Initialize LLM and agent
        llm_factory = get_llm_factory(settings)
        llm = llm_factory.create_default()

        # Initialize tool registry
        tool_registry = ToolRegistry()
        register_trip_tools(tool_registry)

        # Create agent
        agent = TravelConciergeAgent(
            llm=llm,
            tool_registry=tool_registry,
            db=db,
        )

        # Generate response
        response_text, metadata = await agent.chat(
            user_message=request.message,
            conversation_history=conversation_history,
        )

        # Save messages to database
        await _save_messages(
            db=db,
            conversation_id=conversation_id,
            user_message=request.message,
            assistant_message=response_text,
            metadata=metadata,
        )

        # Build response
        return ChatResponse(
            message=response_text,
            conversation_id=str(conversation_id),
            timestamp=datetime.now(UTC),
            sources=None,  # TODO: Populate sources from tool calls in Phase 2
            model_used=f"{metadata['model_info']['provider']}:{metadata['model_info']['model']}",
            metadata={
                "tokens": metadata["tokens"],
                "tool_calls": metadata["tool_calls"],
            },
        )

    except Exception as e:
        logger.error(
            e,
            context="chat_processing_failed",
            user_id=request.user_id,
            conversation_id=request.conversation_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat message: {str(e)}",
        )


async def _get_or_create_conversation(
    db: AsyncSession, request: ChatRequest
) -> tuple[uuid.UUID, list]:
    """
    Get existing conversation or create new one.

    Args:
        db: Database session
        request: Chat request

    Returns:
        Tuple of (conversation_id, conversation_history)
    """
    if request.conversation_id:
        # Load existing conversation
        try:
            conversation_uuid = uuid.UUID(request.conversation_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid conversation_id format: {request.conversation_id}",
            )

        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_uuid)
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation not found: {request.conversation_id}",
            )

        # Load message history
        messages_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_uuid)
            .order_by(Message.turn_number)
        )
        messages = messages_result.scalars().all()

        # Convert to LangChain messages
        conversation_history = []
        for msg in messages:
            if msg.role == "user":
                conversation_history.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                conversation_history.append(AIMessage(content=msg.content))

        logger.logger.debug(
            f"Loaded conversation with {len(conversation_history)} messages"
        )

        return conversation_uuid, conversation_history

    else:
        # Create new conversation
        conversation = Conversation(
            id=uuid.uuid4(),
            user_id=uuid.UUID(request.user_id),
            trip_id=uuid.UUID(request.trip_id) if request.trip_id else None,
            conversation_type="user_chat",
            next_turn_number=1,
        )
        db.add(conversation)
        await db.commit()

        logger.logger.info(f"Created new conversation: {conversation.id}")

        return conversation.id, []


async def _save_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_message: str,
    assistant_message: str,
    metadata: dict,
) -> None:
    """
    Save user and assistant messages to database.

    Args:
        db: Database session
        conversation_id: Conversation UUID
        user_message: User's message text
        assistant_message: Assistant's response text
        metadata: Response metadata (model info, tokens, etc.)
    """
    # Get current turn number
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one()

    # Save user message
    user_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content=user_message,
        turn_number=conversation.next_turn_number,
    )
    db.add(user_msg)

    # Save assistant message with metadata
    assistant_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_message,
        turn_number=conversation.next_turn_number + 1,
        model_provider=metadata["model_info"]["provider"],
        model_name=metadata["model_info"]["model"],
        tokens_input=metadata["tokens"]["prompt"],
        tokens_output=metadata["tokens"]["completion"],
        tool_calls=metadata["tool_calls"] if metadata["tool_calls"] else None,
    )
    db.add(assistant_msg)

    # Update conversation turn number
    conversation.next_turn_number += 2
    conversation.updated_at = datetime.now(UTC)

    await db.commit()

    logger.logger.debug(
        "Saved messages to database",
        extra={
            "conversation_id": str(conversation_id),
            "turn_number": user_msg.turn_number,
        },
    )
