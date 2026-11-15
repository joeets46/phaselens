-- Per match and team: how many eligible player rows there are, and how
-- many of those rows have a count of zero for each metric.
-- These count rows within one match. They are not counts of distinct
-- players across the pilot. A zero means the events file holds no
-- qualifying event for the player; it says nothing about playing time.
SELECT
    match_id,
    team_id,
    min(team_name) AS team_name,
    count(*) AS eligible_player_rows,
    count(*) FILTER (WHERE pressure_event_count = 0)
        AS rows_with_zero_pressure_event_count,
    count(*) FILTER (WHERE counterpress_pressure_event_count = 0)
        AS rows_with_zero_counterpress_pressure_event_count,
    count(*) FILTER (WHERE counterpress_flagged_event_count = 0)
        AS rows_with_zero_counterpress_flagged_event_count
FROM player_match_metrics
GROUP BY match_id, team_id
ORDER BY match_id, team_id;
