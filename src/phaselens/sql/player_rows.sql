-- All player rows, in composite-key order.
-- The order is by identifier. It is not a ranking of players.
SELECT
    team_id,
    team_name,
    player_id,
    player_name,
    pressure_event_count,
    counterpress_pressure_event_count,
    counterpress_flagged_event_count
FROM player_match_metrics
ORDER BY team_id, player_id;
