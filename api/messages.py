"""
Messages API endpoints.

Provides endpoints for message feedback and management.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Message
from db.session import get_db
from schemas.message import MessageFeedbackRequest, MessageFeedbackResponse
from utils.logging import get_agent_logger

router = APIRouter(tags=["Messages"])
logger = get_agent_logger("api.messages")


@router.patch(
    "/{message_id}/feedback",
    status_code=status.HTTP_200_OK,
    response_model=MessageFeedbackResponse,
)
async def update_message_feedback(
    message_id: str,
    feedback_data: MessageFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageFeedbackResponse:
    """
    Update message feedback (thumbs up/down) from user.

    This endpoint is called when a user clicks thumbs up or thumbs down on an AI message.
    Helps track AI response quality for model improvements.

    **Request Body:**
    ```json
    {
      "feedback": "up"
    }
    ```

    **Response:**
    ```json
    {
      "success": true,
      "message_id": "123e4567-e89b-12d3-a456-426614174000"
    }
    ```
    """
    logger.logger.info(
        "Updating message feedback",
        extra={
            "message_id": message_id,
            "feedback": feedback_data.feedback,
        },
    )

    try:
        # Convert string UUID to UUID object
        message_uuid = uuid.UUID(message_id)

        # Check if message exists
        result = await db.execute(select(Message).where(Message.id == message_uuid))
        message = result.scalar_one_or_none()

        if not message:
            logger.logger.warning(
                "Message not found",
                extra={"message_id": message_id},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message with id '{message_id}' not found",
            )

        # Update feedback
        stmt = (
            update(Message)
            .where(Message.id == message_uuid)
            .values(feedback=feedback_data.feedback)
        )
        await db.execute(stmt)
        await db.commit()

        logger.logger.info(
            "Message feedback updated successfully",
            extra={
                "message_id": message_id,
                "feedback": feedback_data.feedback,
            },
        )

        return MessageFeedbackResponse(success=True, message_id=message_id)

    except ValueError as e:
        logger.error(
            e,
            context="message_feedback_validation_error",
            message_id=message_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid message_id format: {message_id}",
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise

    except Exception as e:
        await db.rollback()
        logger.error(
            e,
            context="message_feedback_error",
            message_id=message_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update message feedback",
        )
