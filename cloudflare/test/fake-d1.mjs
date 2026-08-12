// D1Database 인터페이스를 node:sqlite로 흉내내는 테스트용 어댑터.
// 실제 D1도 SQLite 엔진이라 쿼리 동작이 거의 동일하게 검증됩니다.
import { DatabaseSync } from "node:sqlite";
import { readdirSync, readFileSync } from "node:fs";

/**
 * migrations/ 안의 *.sql 파일을 파일명 순서대로 이어붙입니다. 실제 D1도
 * 배포 시 마이그레이션을 순서대로 누적 적용하므로, 테스트용 빈 DB도 같은
 * 순서로 전부 적용해야 최신 스키마와 일치합니다.
 */
export function readAllMigrations() {
  const dir = new URL("../migrations/", import.meta.url);
  const files = readdirSync(dir).filter((f) => f.endsWith(".sql")).sort();
  return files.map((f) => readFileSync(new URL(f, dir), "utf8")).join("\n");
}

class FakeStatement {
  constructor(db, sql) {
    this.db = db;
    this.sql = sql;
    this.params = [];
  }
  bind(...params) {
    this.params = params;
    return this;
  }
  async run() {
    const info = this.db.prepare(this.sql).run(...this.params);
    return { success: true, meta: { changes: info.changes, last_row_id: info.lastInsertRowid } };
  }
  async first() {
    const row = this.db.prepare(this.sql).get(...this.params);
    return row ?? null;
  }
  async all() {
    const results = this.db.prepare(this.sql).all(...this.params);
    return { results, success: true, meta: {} };
  }
}

export function makeFakeD1(schemaSql) {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec(schemaSql);
  return {
    prepare(sql) {
      return new FakeStatement(sqlite, sql);
    },
  };
}
