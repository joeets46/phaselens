-- Team-level totals of the three event counts.
-- Rows are grouped by team_id. The name is a label, so it is carried
-- along with min() and never used as a grouping key.
SELECT
    team_id,
    min(team_name) AS team_name,
    sum(pressure_event_count) AS pressure_event_count,
    sum(counterpress_pressure_event_count) AS counterpress_pressure_event_count,
    sum(counterpress_flagged_event_count) AS counterpress_flagged_event_count
FROM player_match_metrics
GROUP BY team_id
ORDER BY team_id;
