from lotscope.core.errors import LotScopeError


class AiError(LotScopeError):
    default_message = "An AI request failed."


class EmbeddingError(AiError):
    default_message = "The embedding request failed."


class GenerationError(AiError):
    default_message = "The model generation failed."


class UngroundedAnswerError(AiError):
    default_message = "The model returned an answer without citations."
