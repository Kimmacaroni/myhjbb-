-- 교통정보 확인 주기를 명령어(/교통정보주기설정)로 설정할 수 있게, 값과
-- 마지막으로 실제 확인한 시각을 저장하는 테이블입니다. id=1 고정 한 행만
-- 씁니다 — 모든 서버가 공통으로 하나의 확인 주기를 씁니다(교통정보 API
-- 조회 자체가 서버별이 아니라 전체 한 번이라 확인 주기도 전체 공통입니다).

CREATE TABLE IF NOT EXISTS traffic_poll_state (
    id               INTEGER NOT NULL PRIMARY KEY CHECK (id = 1),
    interval_minutes INTEGER NOT NULL DEFAULT 30,
    last_run_at      TEXT
);

INSERT OR IGNORE INTO traffic_poll_state (id, interval_minutes, last_run_at) VALUES (1, 30, NULL);
