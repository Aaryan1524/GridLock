"""Deterministic name comparison between filing endpoints and OSM feature names."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz.fuzz import ratio

from gridlock.settings.models import ResolutionConfig

_PARENTHETICAL = re.compile(r"\([^)]*\)")
_VOLTAGE = re.compile(r"\b\d+(?:\.\d+)?\s*kv\b")


@dataclass(frozen=True)
class NormalizedName:
    text: str
    # The same text with noise words kept; breaks ties such as "Winder Primary" vs "Winder".
    full_text: str
    distinguishing: frozenset[str]
    numbers: frozenset[str]


def _apply_suffixes(token: str, equivalents: dict[str, str]) -> str:
    for suffix, replacement in equivalents.items():
        if token.endswith(suffix) and len(token) > len(suffix):
            return token[: -len(suffix)] + replacement
    return token


def normalize_name(value: str, rules: ResolutionConfig) -> NormalizedName:
    """Lower-case, drop qualifiers/voltages/noise words, expand abbreviations; same rules for both sides."""
    text = _VOLTAGE.sub(" ", _PARENTHETICAL.sub(" ", value.casefold()))
    tokens = [rules.name_abbreviations.get(token, token) for token in re.sub(r"[^a-z0-9]+", " ", text).split()]
    if tokens:
        tokens[0] = rules.name_leading_abbreviations.get(tokens[0], tokens[0])
    tokens = [_apply_suffixes(token, rules.name_suffix_equivalents) for token in tokens]
    noise = {word.casefold() for word in rules.name_noise_words}
    full_text = " ".join(token for token in tokens if not token.isdigit())
    tokens = [token for token in tokens if token not in noise]
    distinguishing = {word.casefold() for word in rules.distinguishing_tokens}
    return NormalizedName(
        # Numbers ("#2" substation, "#5" circuit) are compared on their own, not as part of the text.
        text=" ".join(token for token in tokens if not token.isdigit()),
        full_text=full_text,
        distinguishing=frozenset(token for token in tokens if token in distinguishing),
        numbers=frozenset(token for token in tokens if token.isdigit()),
    )


def name_score(endpoint: NormalizedName, feature: NormalizedName) -> float:
    """Similarity 0-100, or 0 when a distinguishing word or a number on both sides disagrees."""
    if not endpoint.text or not feature.text:
        return 0.0
    if endpoint.distinguishing != feature.distinguishing:
        return 0.0
    if endpoint.numbers and feature.numbers and endpoint.numbers != feature.numbers:
        return 0.0
    return round(ratio(endpoint.text, feature.text), 2)


def tie_break_score(endpoint: NormalizedName, feature: NormalizedName) -> float:
    return round(ratio(endpoint.full_text, feature.full_text), 2)
