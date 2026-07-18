"""运行时代码不得重新暴露已删除的旧智能运维链路。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOTS = (ROOT / "app", ROOT / "frontend-react" / "src")
TEXT_SUFFIXES = {".py", ".ts", ".tsx"}


def test_runtime_contains_no_legacy_agent_symbols_or_user_copy():
    forbidden = (
        "aiops_service",
        "build_aiops_graph",
        "/api/v1/aiops",
        "generic_oncall",
        "AIOps",
        "SRE",
    )
    findings: list[str] = []
    for runtime_root in RUNTIME_ROOTS:
        for path in runtime_root.rglob("*"):
            if path.suffix not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                if token in text:
                    findings.append(f"{path.relative_to(ROOT)}: {token}")

    assert findings == []
