-- SQLite queries for the deterministic local simulator.
-- Dataset guard: always filter environment = 'local-simulated'. These queries
-- do not represent AWS data and intentionally contain no Security Hub/CVE rows.

-- 1) Failed authentications and their severity.
SELECT timestamp, service, src_ip, status, severity, message
FROM security_events
WHERE environment = 'local-simulated' AND event_type = 'auth_failed'
ORDER BY timestamp;

-- 2) North-South traffic (internet/application boundary).
SELECT direction, action, service, COUNT(*) AS events, COALESCE(SUM(bytes), 0) AS bytes
FROM security_events
WHERE environment = 'local-simulated' AND direction = 'north_south'
GROUP BY direction, action, service
ORDER BY bytes DESC;

-- 3) East-West traffic (service-to-service/database paths).
SELECT direction, action, service, COUNT(*) AS events, COALESCE(SUM(bytes), 0) AS bytes
FROM security_events
WHERE environment = 'local-simulated' AND direction = 'east_west'
GROUP BY direction, action, service
ORDER BY bytes DESC;

-- 4) Denials, including their destination port.
SELECT timestamp, direction, service, src_ip, dst_port, severity, message
FROM security_events
WHERE environment = 'local-simulated' AND (event_type = 'denial' OR action = 'deny')
ORDER BY timestamp;

-- 5/6) Findings and CVEs are intentionally not local queries. Do not add
-- fixtures here. Use the read-only Security Hub/Inspector commands in
-- docs/aws-network-security-queries.md after subscription preflight.

-- 7) Candidate traffic spikes by five-minute bucket. The Python detector is
-- canonical because it also emits the isolated baseline and status. This SQL
-- view is useful when loading the JSONL into SQLite for an audit trail.
WITH buckets AS (
  SELECT
    CAST(strftime('%s', timestamp) / 300 AS INTEGER) AS bucket,
    direction,
    SUM(CASE WHEN event_type = 'denial' THEN 1 ELSE 0 END) AS rejected_events,
    SUM(CASE WHEN event_type = 'flow' THEN COALESCE(bytes, 0) ELSE 0 END) AS flow_bytes
  FROM security_events
  WHERE environment = 'local-simulated'
  GROUP BY bucket, direction
), recent AS (
  SELECT MAX(bucket) AS latest_bucket FROM buckets
)
SELECT bucket, direction, rejected_events, flow_bytes
FROM buckets, recent
WHERE bucket >= recent.latest_bucket - 1
ORDER BY bucket, direction;

-- 8) Cloud-only contract: findings and CVEs are intentionally absent from the
-- local dataset. Use the read-only AWS CLI examples in
-- docs/aws-network-security-queries.md after a subscription preflight.
SELECT COUNT(*) AS local_security_hub_rows
FROM security_events
WHERE environment = 'local-simulated'
  AND event_type IN ('finding', 'cve');
