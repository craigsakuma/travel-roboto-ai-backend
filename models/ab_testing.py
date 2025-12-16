"""
A/B testing system for model and prompt experimentation.

Provides:
- Conversation-level model assignment (hash-based deterministic split)
- Tracking of assignments for evaluation
- Support for multi-variant testing
"""

import hashlib
import logging

from config import Settings, get_settings
from models.base import BaseLLM
from models.factory import LLMFactory, ProviderType

logger = logging.getLogger(__name__)


class ABTestAssignment:
    """
    Tracks A/B test assignment for a conversation.

    Attributes:
        conversation_id: Unique conversation identifier
        variant_index: Index into the variants list (0-based)
        provider: LLM provider name
        model: Model name
    """

    def __init__(
        self,
        conversation_id: str,
        variant_index: int,
        provider: ProviderType,
        model: str,
    ):
        self.conversation_id = conversation_id
        self.variant_index = variant_index
        self.provider = provider
        self.model = model

    def to_dict(self) -> dict[str, str | int]:
        """Convert to dictionary for logging/storage."""
        return {
            "conversation_id": self.conversation_id,
            "variant_index": self.variant_index,
            "provider": self.provider,
            "model": self.model,
        }


def _hash_conversation_id(conversation_id: str, num_variants: int) -> int:
    """
    Deterministically assign conversation to a variant using hashing.

    Uses SHA-256 hash to ensure:
    - Deterministic: Same conversation_id always gets same variant
    - Uniform: Distribution across variants is roughly equal
    - Stable: Assignment doesn't change if you add new variants (for existing IDs)

    Args:
        conversation_id: Unique conversation identifier
        num_variants: Number of variants to distribute across

    Returns:
        int: Variant index (0 to num_variants-1)
    """
    # Hash the conversation_id
    hash_digest = hashlib.sha256(conversation_id.encode()).hexdigest()

    # Convert first 8 hex chars to int and modulo by num_variants
    hash_int = int(hash_digest[:8], 16)

    return hash_int % num_variants


def get_model_for_conversation(
    conversation_id: str,
    settings: Settings | None = None,
) -> tuple[BaseLLM, ABTestAssignment]:
    """
    Get LLM instance for a conversation with A/B testing.

    If A/B testing is enabled, deterministically assigns a model variant based on
    conversation_id hash. Otherwise, returns the default model.

    Args:
        conversation_id: Unique conversation identifier
        settings: Application settings (if None, uses get_settings())

    Returns:
        tuple[BaseLLM, ABTestAssignment]: LLM instance and assignment details

    Example:
        ```python
        llm, assignment = get_model_for_conversation("conv_123")
        print(f"Using {assignment.provider} - {assignment.model}")

        # Log assignment for evaluation
        logger.info("AB test assignment", extra=assignment.to_dict())
        ```
    """
    settings = settings or get_settings()
    factory = LLMFactory(settings)

    # If A/B testing is disabled, use default model
    if not settings.ab_testing_enabled:
        llm = factory.create_default()
        assignment = ABTestAssignment(
            conversation_id=conversation_id,
            variant_index=0,
            provider=settings.default_model_provider,
            model=settings.default_model_name,
        )
        logger.debug(f"A/B testing disabled, using default: {assignment.model}")
        return llm, assignment

    # Get variants from settings
    variants = settings.ab_model_variants

    if not variants:
        logger.warning("ab_testing_enabled=true but no variants configured, using default")
        llm = factory.create_default()
        assignment = ABTestAssignment(
            conversation_id=conversation_id,
            variant_index=0,
            provider=settings.default_model_provider,
            model=settings.default_model_name,
        )
        return llm, assignment

    # Hash-based assignment
    variant_index = _hash_conversation_id(conversation_id, len(variants))
    variant = variants[variant_index]

    # Create LLM for assigned variant
    provider = variant["provider"]
    model = variant["model"]

    llm = factory.create(provider=provider, model=model)

    assignment = ABTestAssignment(
        conversation_id=conversation_id,
        variant_index=variant_index,
        provider=provider,
        model=model,
    )

    logger.info(
        f"A/B test assignment for {conversation_id}: "
        f"variant {variant_index} ({provider} - {model})"
    )

    return llm, assignment


def get_variant_distribution(
    conversation_ids: list[str],
    settings: Settings | None = None,
) -> dict[int, int]:
    """
    Calculate variant distribution for a list of conversations.

    Useful for validating that hash-based assignment gives uniform distribution.

    Args:
        conversation_ids: List of conversation IDs
        settings: Application settings (if None, uses get_settings())

    Returns:
        dict[int, int]: Mapping of variant_index to count

    Example:
        ```python
        conv_ids = [f"conv_{i}" for i in range(1000)]
        distribution = get_variant_distribution(conv_ids)
        # {0: 503, 1: 497} - roughly 50/50 split
        ```
    """
    settings = settings or get_settings()
    num_variants = len(settings.ab_model_variants)

    if num_variants == 0:
        return {0: len(conversation_ids)}

    distribution: dict[int, int] = {i: 0 for i in range(num_variants)}

    for conv_id in conversation_ids:
        variant_index = _hash_conversation_id(conv_id, num_variants)
        distribution[variant_index] += 1

    return distribution
