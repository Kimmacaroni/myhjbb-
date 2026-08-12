-- 교통정보(고속도로 돌발상황) 알림 기능.
--
-- guild_settings에 채널 컬럼을 추가하고, 이미 알린 돌발상황을 기억해 두는
-- 테이블을 새로 만듭니다 (같은 상황을 5분마다 반복해서 알리지 않기 위함).

ALTER TABLE guild_settings ADD COLUMN traffic_channel_id TEXT;

CREATE TABLE IF NOT EXISTS traffic_seen_incidents (
    incident_key TEXT NOT NULL PRIMARY KEY,
    seen_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_traffic_seen_at ON traffic_seen_incidents (seen_at);
