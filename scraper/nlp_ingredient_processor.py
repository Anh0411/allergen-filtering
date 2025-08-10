"""
Deprecated module: use `allergen_filtering.nlp_processor` instead.
This shim re-exports the unified API for backwards compatibility.
"""

from warnings import warn

warn(
    "scraper.nlp_ingredient_processor is deprecated. Use allergen_filtering.nlp_processor instead.",
    DeprecationWarning,
)

from allergen_filtering.nlp_processor import (  # noqa: F401
    NLPProcessor as NLPIngredientProcessor,
    get_nlp_processor,
    IngredientMatch,
    AllergenAnalysis,
    ConflictPolicy,
)


