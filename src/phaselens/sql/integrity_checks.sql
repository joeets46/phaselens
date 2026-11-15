-- Integrity checks on the table. Every check should report 0 violations.
SELECT 'duplicate_composite_key' AS check_name, count(*) AS violations
FROM (
    SELECT source_commit, metric_contract_version, match_id, team_id, player_id
    FROM player_match_metrics
    GROUP BY source_commit, metric_contract_version, match_id, team_id, player_id
    HAVING count(*) > 1
)
UNION ALL
SELECT 'negative_count', count(*)
FROM player_match_metrics
WHERE pressure_event_count < 0
   OR counterpress_pressure_event_count < 0
   OR counterpress_flagged_event_count < 0
UNION ALL
SELECT 'counterpress_pressure_exceeds_pressure', count(*)
FROM player_match_metrics
WHERE counterpress_pressure_event_count > pressure_event_count
UNION ALL
SELECT 'counterpress_pressure_exceeds_flagged', count(*)
FROM player_match_metrics
WHERE counterpress_pressure_event_count > counterpress_flagged_event_count
ORDER BY check_name;
