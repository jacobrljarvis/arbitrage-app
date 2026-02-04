"""Core arbitrage calculation logic."""

from collections import defaultdict
from datetime import datetime
from typing import Optional

from .config import MIN_PROFIT_MARGIN
from .models import (
    Market,
    Outcome,
    ArbitrageOpportunity,
    StakeRecommendation,
    CalculateStakesResponse,
)


def calculate_implied_probability(odds: float) -> float:
    """Calculate implied probability from decimal odds."""
    if odds <= 0:
        return 0
    return 1 / odds


def find_best_odds_per_outcome(markets: list[Market]) -> dict[str, dict[str, Outcome]]:
    """
    Group markets by event and find the best odds for each outcome.

    Returns:
        Dict mapping event_id -> outcome_name -> best Outcome
    """
    # Group by event_id and market_key
    events: dict[str, dict[str, list[Outcome]]] = defaultdict(lambda: defaultdict(list))

    for market in markets:
        key = f"{market.event_id}:{market.market_key}"
        for outcome in market.outcomes:
            events[key][outcome.name].append(outcome)

    # Find best odds for each outcome
    best_odds: dict[str, dict[str, Outcome]] = {}

    for event_key, outcomes_dict in events.items():
        best_odds[event_key] = {}
        for outcome_name, outcomes in outcomes_dict.items():
            # Find the outcome with the highest odds (best for bettor)
            best = max(outcomes, key=lambda o: o.price)
            best_odds[event_key][outcome_name] = best

    return best_odds


def check_arbitrage(outcomes: dict[str, Outcome]) -> Optional[tuple[float, float]]:
    """
    Check if arbitrage exists for a set of outcomes.

    Args:
        outcomes: Dict mapping outcome_name -> best Outcome

    Returns:
        Tuple of (profit_margin, total_implied_probability) if arbitrage exists,
        None otherwise.
    """
    if len(outcomes) < 2:
        return None

    # Calculate sum of implied probabilities
    total_implied = sum(
        calculate_implied_probability(o.price)
        for o in outcomes.values()
    )

    # Arbitrage exists if total implied probability < 1
    if total_implied < 1:
        profit_margin = 1 - total_implied
        return (profit_margin, total_implied)

    return None


def find_arbitrage_opportunities(
    markets: list[Market],
    min_profit_margin: float = MIN_PROFIT_MARGIN,
) -> list[ArbitrageOpportunity]:
    """
    Scan all markets for arbitrage opportunities.

    Args:
        markets: List of Market objects from various bookmakers
        min_profit_margin: Minimum profit margin to consider (default 0.1%)

    Returns:
        List of ArbitrageOpportunity objects sorted by profit margin
    """
    opportunities = []

    # Get best odds per outcome for each event
    best_odds = find_best_odds_per_outcome(markets)

    # Create a lookup for event metadata
    event_metadata: dict[str, Market] = {}
    for market in markets:
        key = f"{market.event_id}:{market.market_key}"
        if key not in event_metadata:
            event_metadata[key] = market

    # Check each event for arbitrage
    for event_key, outcomes in best_odds.items():
        arb_result = check_arbitrage(outcomes)

        if arb_result and arb_result[0] >= min_profit_margin:
            profit_margin, total_implied = arb_result
            metadata = event_metadata.get(event_key)

            if metadata:
                opportunity = ArbitrageOpportunity(
                    event_id=metadata.event_id,
                    sport_key=metadata.sport_key,
                    sport_title=metadata.sport_title,
                    home_team=metadata.home_team,
                    away_team=metadata.away_team,
                    commence_time=metadata.commence_time,
                    market_key=metadata.market_key,
                    profit_margin=profit_margin,
                    total_implied_probability=total_implied,
                    outcomes=list(outcomes.values()),
                )
                opportunities.append(opportunity)

    # Sort by profit margin (highest first)
    opportunities.sort(key=lambda o: o.profit_margin, reverse=True)

    return opportunities


def calculate_stakes(
    outcomes: list[Outcome],
    total_stake: float,
) -> CalculateStakesResponse:
    """
    Calculate optimal stake distribution for an arbitrage opportunity.

    The formula for optimal stake on outcome i is:
    stake_i = total_stake * (1/odds_i) / sum(1/odds for all outcomes)

    This ensures equal return regardless of which outcome wins.

    Args:
        outcomes: List of outcomes with best odds
        total_stake: Total amount to stake

    Returns:
        CalculateStakesResponse with stake recommendations
    """
    if not outcomes or total_stake <= 0:
        return CalculateStakesResponse(
            total_stake=total_stake,
            guaranteed_profit=0,
            profit_percentage=0,
            stakes=[],
        )

    # Calculate total implied probability
    implied_probs = {o.name: calculate_implied_probability(o.price) for o in outcomes}
    total_implied = sum(implied_probs.values())

    # Calculate optimal stakes
    stakes = []
    guaranteed_return = None

    for outcome in outcomes:
        implied_prob = implied_probs[outcome.name]
        stake = total_stake * (implied_prob / total_implied)
        potential_return = stake * outcome.price

        # All outcomes should have the same return (that's the point of arbitrage)
        if guaranteed_return is None:
            guaranteed_return = potential_return

        stakes.append(StakeRecommendation(
            outcome_name=outcome.name,
            bookmaker=outcome.bookmaker,
            odds=outcome.price,
            stake=round(stake, 2),
            potential_return=round(potential_return, 2),
        ))

    guaranteed_return = guaranteed_return or total_stake
    guaranteed_profit = guaranteed_return - total_stake
    profit_percentage = (guaranteed_profit / total_stake) * 100 if total_stake > 0 else 0

    return CalculateStakesResponse(
        total_stake=total_stake,
        guaranteed_profit=round(guaranteed_profit, 2),
        profit_percentage=round(profit_percentage, 2),
        stakes=stakes,
    )


def calculate_profit(
    outcomes: list[Outcome],
    total_stake: float,
) -> float:
    """
    Calculate guaranteed profit for an arbitrage opportunity.

    Args:
        outcomes: List of outcomes with best odds
        total_stake: Total amount to stake

    Returns:
        Guaranteed profit amount
    """
    result = calculate_stakes(outcomes, total_stake)
    return result.guaranteed_profit


def format_opportunity_summary(opportunity: ArbitrageOpportunity) -> str:
    """Format an opportunity for display."""
    lines = [
        f"Event: {opportunity.event_name}",
        f"Sport: {opportunity.sport_title}",
        f"Profit Margin: {opportunity.profit_percentage:.2f}%",
        f"Start Time: {opportunity.commence_time.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Best Odds:",
    ]

    for outcome in opportunity.outcomes:
        lines.append(f"  {outcome.name}: {outcome.price:.2f} @ {outcome.bookmaker}")

    return "\n".join(lines)
