-- Per team: how many players are eligible, and how many of them have a
-- count of zero for each metric.
-- A zero means the events file holds no qualifying event for the player.
-- It says nothing about how long the player was on the pitch.
SELECT
    team_id,
    min(team_name) AS team_name,
    count(*) AS eligible_players,
    count(*) FILTER (WHERE pressure_event_count = 0) AS zero_pressure_event_count,
    count(*) FILTER (WHERE counterpress_pressure_event_count = 0)
        AS zero_counterpress_pressure_event_count,
    count(*) FILTER (WHERE counterpress_flagged_event_count = 0)
        AS zero_counterpress_flagged_event_count
FROM player_match_metrics
GROUP BY team_id
ORDER BY team_id;
