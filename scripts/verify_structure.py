#!/usr/bin/env python3
"""VPS 기능 소유권과 보조 구현 경계를 정적으로 검증합니다."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COGS = (
    "cogs.leveling",
    "cogs.titles",
    "cogs.menu",
    "cogs.traffic",
    "cogs.music",
    "cogs.tts",
    "cogs.help",
)
EXPECTED_COMMANDS = {
    "cogs.leveling": {"경험치", "랭킹", "경험치지급", "경험치차감", "경험치설정"},
    "cogs.titles": {"칭호추가", "칭호삭제", "칭호목록", "칭호동기화"},
    "cogs.menu": {"식단", "식단채널설정", "식단채널해제", "식단설정"},
    "cogs.traffic": {
        "교통정보",
        "교통정보채널설정",
        "교통정보채널해제",
        "교통정보설정",
        "교통정보주기설정",
    },
    "cogs.music": {
        "재생",
        "일시정지",
        "재개",
        "스킵",
        "이동",
        "정지",
        "퇴장",
        "대기열",
        "볼륨",
        "음악대시보드설정",
    },
    "cogs.tts": {"음성"},
    "cogs.help": {"도움말"},
}
CLOUDFLARE_REQUIRED = {
    "cloudflare/package.json",
    "cloudflare/src/index.ts",
    "cloudflare/src/interactions.ts",
    "cloudflare/src/scheduled.ts",
    "cloudflare/test/index.test.mjs",
}
PERSISTENT_IGNORE_RULES = {".env", ".env.*", "*.db", "youtube-cookies.txt", "cookies/", "models/"}


def fail(message: str) -> NoReturn:
    raise SystemExit(f"구조 검증 실패: {message}")


def assignment_strings(tree: ast.AST, name: str) -> tuple[str, ...]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                break
            if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
                return value
    fail(f"bot.py의 {name} 문자열 튜플을 찾을 수 없습니다")


def command_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    has_setup = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            has_setup = has_setup or node.name == "setup"
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                if not (isinstance(func, ast.Attribute) and func.attr == "command"):
                    continue
                for keyword in decorator.keywords:
                    if (
                        keyword.arg == "name"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        names.add(keyword.value.value)
    if not has_setup:
        fail("Cog 모듈에 extension setup()이 없습니다")
    return names


def main() -> None:
    bot_tree = ast.parse((ROOT / "bot.py").read_text(encoding="utf-8"))
    actual_cogs = assignment_strings(bot_tree, "COGS")
    if actual_cogs != EXPECTED_COGS:
        fail(f"bot.py Cog 목록/순서 변경: {actual_cogs!r}")

    total = 0
    for module in EXPECTED_COGS:
        path = ROOT / f"{module.replace('.', '/')}.py"
        if not path.is_file():
            fail(f"VPS Cog 누락: {path.relative_to(ROOT)}")
        actual = command_names(ast.parse(path.read_text(encoding="utf-8")))
        expected = EXPECTED_COMMANDS[module]
        if actual != expected:
            fail(f"{module} 명령 변경: 누락={sorted(expected-actual)}, 추가={sorted(actual-expected)}")
        total += len(actual)

    missing_cloudflare = sorted(path for path in CLOUDFLARE_REQUIRED if not (ROOT / path).is_file())
    if missing_cloudflare:
        fail(f"Cloudflare 보조 구현 누락: {missing_cloudflare}")

    ignore_rules = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
    missing_rules = sorted(PERSISTENT_IGNORE_RULES - ignore_rules)
    if missing_rules:
        fail(f"영구/민감 데이터 ignore 규칙 누락: {missing_rules}")

    access_tree = ast.parse((ROOT / "access_control.py").read_text(encoding="utf-8"))
    long_ids = [
        node.value
        for node in ast.walk(access_tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and 10**16 <= node.value < 10**20
    ]
    if long_ids:
        fail("access_control.py에 Discord ID로 보이는 정수 리터럴이 있습니다")

    print(f"구조 검증 통과: VPS Cog {len(actual_cogs)}개, 슬래시 명령 {total}개, Cloudflare 보조 범위 보존")


if __name__ == "__main__":
    main()
