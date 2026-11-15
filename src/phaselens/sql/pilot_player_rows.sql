-- Every player-match row of the combined pilot table, in composite-key order.
-- One row per match, team and player: a player who appears in several
-- matches has one row for each. The order is by identifier, not a ranking.
SELECT
    match_id,
    team_id,
    team_name,
    player_id,
    player_name,
    pressure_event_count,
    counterpress_pressure_event_count,
    counterpress_flagged_event_count
FROM player_match_metrics
ORDER BY match_id, team_id, player_id;
