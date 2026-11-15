-- The three event counts summed per match and team.
-- A team that plays in several matches has one row per match; the
-- matches are never added together. The name is a label, carried along
-- with min() and never used as a grouping key.
SELECT
    match_id,
    team_id,
    min(team_name) AS team_name,
    sum(pressure_event_count) AS pressure_event_count,
    sum(counterpress_pressure_event_count) AS counterpress_pressure_event_count,
    sum(counterpress_flagged_event_count) AS counterpress_flagged_event_count
FROM player_match_metrics
GROUP BY match_id, team_id
ORDER BY match_id, team_id;
