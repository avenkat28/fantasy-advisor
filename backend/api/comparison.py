"""Pure, independently testable start/sit recommendation logic."""

def compare_projections(first: dict, second: dict, threshold: float) -> dict:
    difference = first['projected_ppr_points'] - second['projected_ppr_points']
    close = abs(difference) <= threshold
    winner = first if difference > 0 else second if difference < 0 else None
    recommendation = winner['player_id'] if winner else None
    explanation = (f"{winner['player_name']} has the higher projected PPR score by {abs(difference):.2f}."
                   if winner else 'The projections are tied; there is no model preference.')
    if close:
        explanation += f' This is a close call within the {threshold:g}-point threshold.'
    for player in [first, second]:
        recent = player['recent_ppr_mean_3']
        allowed = player['matchup_features'].get('opponent_ppr_allowed_position_mean_3')
        if recent is not None:
            explanation += f" {player['player_name']} averaged {recent:.2f} PPR over up to three prior appearances."
        if allowed is not None:
            explanation += f" {player['opponent']} allowed {allowed:.2f} PPR to the position over up to three prior games."
    return dict(player1=first, player2=second, difference=difference, recommended_player_id=recommendation,
                close_call=close, close_call_threshold=threshold, explanation=explanation)
