"""Transparent availability policy; multipliers are heuristics, not fitted probabilities."""
import pandas as pd

UNAVAILABLE_ROSTER = {'RES', 'INA', 'IR', 'PUP', 'NFI', 'SUS'}
PROJECTABLE_ROSTER = UNAVAILABLE_ROSTER | {'ACT'}
# Tune only with held-out forecast outcomes; these are not clinical severity scores.
STATUS_MULTIPLIERS = {'doubtful': 0.25, 'questionable': 0.75}
PRACTICE_MULTIPLIERS = {'missed': 0.8, 'limited': 0.9}


def adjust_injury(data, metadata, value):
    cutoff = min(pd.Timestamp(metadata.get('game_kickoff') or metadata['feature_cutoff']),
                 pd.Timestamp.now(tz='UTC'))
    injuries = data.injuries
    status = observed = injury = practice = None
    if not injuries.empty:
        timestamps = pd.to_datetime(injuries.observed_at, utc=True, errors='coerce')
        mask = (injuries.gsis_id.eq(metadata['player_id']) & injuries.season.eq(metadata['season'])
                & injuries.week.eq(metadata['week']) & timestamps.le(cutoff)
                & timestamps.ge(cutoff - pd.Timedelta(days=7)))
        if 'team' in injuries:
            mask &= injuries.team.eq(metadata['team'])
        rows = injuries[mask].assign(_observed=timestamps[mask]).sort_values('_observed')
        if not rows.empty:
            row = rows.iloc[-1]

            def field(name):
                v = row.get(name)
                return str(v).strip() if pd.notna(v) and str(v).strip() else None

            status, observed = field('report_status'), field('observed_at')
            injury = field('report_primary_injury') or field('practice_primary_injury')
            practice = field('practice_status')
    roster = str(metadata.get('roster_status') or '').upper()
    normalized = (status or '').lower()
    multiplier, availability = 1.0, 'unknown'
    reason = 'No fresh injury report for this week; availability unknown'
    if observed:
        availability = 'reported_available' if not status else 'uncertain'
        reason = 'No availability restriction reported'
        # Operational risk estimates, deliberately separate from the fitted performance model.
        if normalized == 'doubtful':
            multiplier, reason = STATUS_MULTIPLIERS['doubtful'], 'Doubtful: 75% availability-risk reduction'
        elif normalized == 'questionable':
            multiplier, reason = STATUS_MULTIPLIERS['questionable'], 'Questionable: 25% availability-risk reduction'
        participation = (practice or '').lower()
        if 'did not participate' in participation:
            multiplier *= PRACTICE_MULTIPLIERS['missed']
            reason += '; missed practice: 20% performance-risk reduction'
        elif 'limited' in participation:
            multiplier *= PRACTICE_MULTIPLIERS['limited']
            reason += '; limited practice: 10% performance-risk reduction'
        if multiplier < 1:
            availability = 'uncertain'
    if normalized in {'out', 'ir', 'injured reserve', 'reserve/injured', 'inactive', 'suspended', 'pup', 'nfi'}:
        multiplier, availability, reason = 0.0, 'unavailable', f'{status}: zero projected points'
    if roster in UNAVAILABLE_ROSTER:
        multiplier, availability = 0.0, 'unavailable'
        reason = f'Roster status {roster}: zero projected points (reserve/inactive; RES does not identify a specific injury)'
    return {**metadata, 'base_projected_ppr_points': float(value),
            'projected_ppr_points': 0.0 if multiplier == 0 else max(0.0, float(value)) * multiplier,
            'injury_status': status, 'injury_observed_at': observed,
            'injury_description': injury, 'practice_status': practice,
            'availability': availability, 'injury_multiplier': multiplier,
            'injury_policy': 'availability-heuristic-v1', 'injury_adjustment': reason}
