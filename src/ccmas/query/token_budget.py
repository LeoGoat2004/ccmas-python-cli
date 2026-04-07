"""Token budget tracking for CCMAS."""

import re
from dataclasses import dataclass
from typing import Optional


COMPLETION_THRESHOLD = 0.9
DIMINISHING_THRESHOLD = 500


MULTIPLIERS = {
    'k': 1_000,
    'm': 1_000_000,
    'b': 1_000_000_000,
}


SHORTHAND_START_RE = re.compile(r'^\s*\+(\d+(?:\.\d+)?)\s*(k|m|b)\b', re.IGNORECASE)
SHORTHAND_END_RE = re.compile(r'\s\+(\d+(?:\.\d+)?)\s*(k|m|b)\s*[.!?]?\s*$', re.IGNORECASE)
VERBOSE_RE = re.compile(r'\b(?:use|spend)\s+(\d+(?:\.\d+)?)\s*(k|m|b)\s*tokens?\b', re.IGNORECASE)


@dataclass
class BudgetTracker:
    continuation_count: int = 0
    last_delta_tokens: int = 0
    last_global_turn_tokens: int = 0
    started_at: int = 0

    @classmethod
    def create(cls) -> 'BudgetTracker':
        import time
        return cls(started_at=int(time.time() * 1000))


def parse_budget_match(value: str, suffix: str) -> int:
    return int(float(value) * MULTIPLIERS.get(suffix.lower(), 0))


def parse_token_budget(text: str) -> Optional[int]:
    start_match = SHORTHAND_START_RE.match(text)
    if start_match:
        return parse_budget_match(start_match.group(1), start_match.group(2))

    end_match = SHORTHAND_END_RE.search(text)
    if end_match:
        return parse_budget_match(end_match.group(1), end_match.group(2))

    verbose_match = VERBOSE_RE.search(text)
    if verbose_match:
        return parse_budget_match(verbose_match.group(1), verbose_match.group(2))

    return None


def find_token_budget_positions(text: str) -> list[dict]:
    positions = []

    start_match = SHORTHAND_START_RE.match(text)
    if start_match:
        match_str = start_match.group(0)
        offset = len(match_str) - len(match_str.stripStart())
        positions.append({
            'start': start_match.start() + offset,
            'end': start_match.end(),
        })

    end_match = SHORTHAND_END_RE.search(text)
    if end_match:
        end_start = end_match.start() + 1
        already_covered = any(
            p['start'] <= end_start < p['end'] for p in positions
        )
        if not already_covered:
            positions.append({
                'start': end_start,
                'end': end_match.end(),
            })

    for match in VERBOSE_RE.finditer(text):
        positions.append({
            'start': match.start(),
            'end': match.end(),
        })

    return positions


def get_budget_continuation_message(pct: int, turn_tokens: int, budget: int) -> str:
    def fmt(n: int) -> str:
        return f"{n:,}"
    return f"Stopped at {pct}% of token target ({fmt(turn_tokens)} / {fmt(budget)}). Keep working — do not summarize."


@dataclass
class ContinueDecision:
    action: str = 'continue'
    nudge_message: str = ''
    continuation_count: int = 0
    pct: int = 0
    turn_tokens: int = 0
    budget: int = 0


@dataclass
class StopDecision:
    action: str = 'stop'
    completion_event: Optional[dict] = None


TokenBudgetDecision = ContinueDecision | StopDecision


def check_token_budget(
    tracker: BudgetTracker,
    agent_id: Optional[str],
    budget: Optional[int],
    global_turn_tokens: int,
) -> TokenBudgetDecision:
    if agent_id or budget is None or budget <= 0:
        return StopDecision(action='stop', completion_event=None)

    turn_tokens = global_turn_tokens
    pct = round((turn_tokens / budget) * 100)
    delta_since_last_check = global_turn_tokens - tracker.last_global_turn_tokens

    is_diminishing = (
        tracker.continuation_count >= 3
        and delta_since_last_check < DIMINISHING_THRESHOLD
        and tracker.last_delta_tokens < DIMINISHING_THRESHOLD
    )

    if not is_diminishing and turn_tokens < budget * COMPLETION_THRESHOLD:
        tracker.continuation_count += 1
        tracker.last_delta_tokens = delta_since_last_check
        tracker.last_global_turn_tokens = global_turn_tokens
        return ContinueDecision(
            action='continue',
            nudge_message=get_budget_continuation_message(pct, turn_tokens, budget),
            continuation_count=tracker.continuation_count,
            pct=pct,
            turn_tokens=turn_tokens,
            budget=budget,
        )

    if is_diminishing or tracker.continuation_count > 0:
        import time
        return StopDecision(
            action='stop',
            completion_event={
                'continuationCount': tracker.continuation_count,
                'pct': pct,
                'turnTokens': turn_tokens,
                'budget': budget,
                'diminishingReturns': is_diminishing,
                'durationMs': int(time.time() * 1000) - tracker.started_at,
            },
        )

    return StopDecision(action='stop', completion_event=None)
