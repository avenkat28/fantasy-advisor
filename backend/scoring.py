"""Explicit default league scoring; K/DST scores share the legacy points column.

D/ST points allowed uses the opponent's final scoreboard total. Platforms that
exclude defensive scores or conversions require a different scoring policy.
"""
import pandas as pd

POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
SCORING_POLICY = 'default-k-dst-v1'
KICKING = {**{f'fg_made_{band}': 3 for band in ['0_19', '20_29', '30_39']},
           'fg_made_40_49': 4, 'fg_made_50_59': 5, 'fg_made_60_': 5, 'pat_made': 1}
DEFENSE = {'def_sacks': 1, 'def_interceptions': 2, 'fumble_recovery_opp': 2,
           'def_tds': 6, 'special_teams_tds': 6, 'def_safeties': 2,
           'def_punt_blocks': 2, 'def_fg_blocks': 2, 'def_pat_blocks': 2,
           'def_2pt_made': 2}


def weighted_points(frame, weights):
    missing = set(weights) - set(frame)
    if missing:
        raise ValueError(f'Missing scoring columns: {sorted(missing)}')
    return frame[list(weights)].apply(pd.to_numeric, errors='raise').mul(pd.Series(weights)).sum(
        axis=1, min_count=len(weights))


def points_allowed_bonus(points):
    points = pd.to_numeric(points, errors='raise')
    result = pd.Series(float('nan'), index=points.index)
    for low, high, value in [(0, 0, 10), (1, 6, 7), (7, 13, 4), (14, 20, 1),
                             (21, 27, 0), (28, 34, -1), (35, float('inf'), -4)]:
        result.loc[points.between(low, high)] = value
    return result


def defense_records(raw, schedules, teams=None):
    """One real team-game record, never individual defenders or a fake roster."""
    required = {'team', 'season', 'week', 'season_type', 'game_id'} | set(DEFENSE)
    if required - set(raw):
        raise ValueError(f'Missing team-stat columns: {sorted(required - set(raw))}')
    frame = raw.copy()
    if frame.duplicated(['team', 'season', 'season_type', 'week']).any():
        raise ValueError('Duplicate team-game statistics')
    scores = schedules[['game_id', 'home_team', 'away_team', 'home_score', 'away_score']]
    frame = frame.merge(scores, on='game_id', how='left', validate='many_to_one')
    valid = frame.team.eq(frame.home_team) | frame.team.eq(frame.away_team)
    if not valid.all():
        raise ValueError('Team statistics disagree with schedule')
    frame['points_allowed'] = frame.away_score.where(frame.team.eq(frame.home_team), frame.home_score)
    frame['fantasy_points_ppr'] = weighted_points(frame, DEFENSE) + points_allowed_bonus(frame.points_allowed)
    frame['player_id'] = 'DST:' + frame.team
    names = {} if teams is None else teams.set_index('team_abbr').team_name.to_dict()
    logos = {} if teams is None else teams.set_index('team_abbr').team_logo_espn.to_dict()
    frame['player_name'] = frame.team.map(names).fillna(frame.team) + ' D/ST'
    frame['headshot_url'] = frame.team.map(logos)
    frame['position'] = 'DST'
    # Offensive activity is inapplicable to team defense; don't use offensive
    # totals from the team feed as defense prediction features.
    columns = ['player_id', 'player_name', 'position', 'team', 'season', 'week',
               'season_type', 'game_id', 'headshot_url', 'fantasy_points_ppr',
               'points_allowed'] + list(DEFENSE)
    return frame[columns]
