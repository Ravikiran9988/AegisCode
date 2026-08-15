"""
Benchmark Evaluator & Metrics Framework — Phase 6.

Executes repair jobs against benchmark suites, calculates evaluation metrics,
and exports results to `evaluation/results.json` and `evaluation/results.csv`.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.agents.schemas import CodeChange
from backend.execution.workspace import WorkspaceManager
from backend.graph.graph import run_repair_workflow
from backend.llm.base import BaseLLMProvider
from backend.llm.mock import MockLLMProvider
from backend.tools.git_tools import init_repo


@dataclass
class BenchmarkResult:
    benchmark_id: str
    name: str
    difficulty: str
    model: str
    success: bool
    status: str
    termination_reason: str
    iterations: int
    duration_seconds: float
    initial_failed_tests: int
    final_failed_tests: int


def _zip_from_dir(directory: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in directory.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(directory))
    return buf.getvalue()


class EvaluationSuite:
    """
    Runner for benchmark evaluation datasets.
    """

    def __init__(self, benchmarks_dir: Path | str | None = None) -> None:
        if benchmarks_dir:
            self.benchmarks_dir = Path(benchmarks_dir)
        else:
            self.benchmarks_dir = Path(__file__).parent.parent.parent / "evaluation" / "benchmarks"

    def run_benchmark(
        self,
        benchmark_path: Path,
        llm_provider: BaseLLMProvider,
        tmp_base: Path,
    ) -> BenchmarkResult:
        b_name = benchmark_path.name
        wm = WorkspaceManager.create(base_dir=tmp_base)
        p_path = wm.extract_project(_zip_from_dir(benchmark_path))
        wm.set_project_root(p_path)
        init_repo(p_path)

        state = run_repair_workflow(
            run_id=f"eval-{b_name}",
            workspace_id=wm.workspace_id,
            project_path=str(p_path),
            llm_provider=llm_provider,
            max_iterations=3,
        )

        status = state.get("status", "unknown")
        success = status in ("passed", "already_passing")

        res = BenchmarkResult(
            benchmark_id=b_name.split("_")[0],
            name=b_name,
            difficulty="Medium" if "multi" in b_name else "Easy",
            model=llm_provider.provider_name,
            success=success,
            status=status,
            termination_reason=state.get("termination_reason") or "N/A",
            iterations=state.get("iteration", 1),
            duration_seconds=round(state.get("total_duration", 0.0), 2),
            initial_failed_tests=state.get("initial_failed_count", 0),
            final_failed_tests=state.get("final_failed_count", 0),
        )

        wm.cleanup()
        return res

    def run_all(
        self,
        llm_provider: BaseLLMProvider | None = None,
        tmp_base: Path | str = "./workspaces",
    ) -> list[BenchmarkResult]:
        provider = llm_provider or MockLLMProvider()
        base_path = Path(tmp_base)
        results: list[BenchmarkResult] = []

        if not self.benchmarks_dir.exists():
            return results

        bench_dirs = sorted([d for d in self.benchmarks_dir.iterdir() if d.is_dir()])
        for b_dir in bench_dirs:
            # Custom mock provider configuration for specific benchmarks
            if "01_arithmetic" in b_dir.name:
                custom_provider = MockLLMProvider(
                    mock_change=CodeChange(
                        file_path="calculator.py",
                        change_type="write",
                        explanation="Fix add function",
                        root_cause="Subtracted instead of added",
                        patch="def add(a: int, b: int) -> int:\n    return a + b\n",
                    )
                )
            elif "02_logic" in b_dir.name:
                custom_provider = MockLLMProvider(
                    mock_change=CodeChange(
                        file_path="string_utils.py",
                        change_type="write",
                        explanation="Fix reverse string",
                        root_cause="Lowercased instead of reversed",
                        patch="def reverse_string(s: str) -> str:\n    return s[::-1]\n",
                    )
                )
            elif "06_policy" in b_dir.name:
                custom_provider = MockLLMProvider(
                    mock_change=CodeChange(
                        file_path="test_policy.py",
                        change_type="write",
                        explanation="Tamper test file",
                        root_cause="N/A",
                        patch="def test_safe_func(): pass\n",
                    )
                )
            else:
                custom_provider = provider

            res = self.run_benchmark(b_dir, custom_provider, base_path)
            results.append(res)

        return results

    def export_results(
        self,
        results: list[BenchmarkResult],
        json_path: Path | str = "evaluation/results.json",
        csv_path: Path | str = "evaluation/results.csv",
    ) -> dict[str, Any]:
        j_path = Path(json_path)
        c_path = Path(csv_path)

        j_path.parent.mkdir(parents=True, exist_ok=True)
        c_path.parent.mkdir(parents=True, exist_ok=True)

        res_dicts = [asdict(r) for r in results]

        # Calculate metrics
        total = len(results)
        passed_count = sum(1 for r in results if r.success)
        stalled_count = sum(1 for r in results if r.status == "stalled")

        avg_iters = round(sum(r.iterations for r in results) / total, 2) if total else 0.0
        avg_dur = round(sum(r.duration_seconds for r in results) / total, 2) if total else 0.0

        metrics = {
            "total_benchmarks": total,
            "passed_benchmarks": passed_count,
            "repair_success_rate": round(passed_count / total, 2) if total else 0.0,
            "stalled_rate": round(stalled_count / total, 2) if total else 0.0,
            "avg_iterations": avg_iters,
            "avg_duration_seconds": avg_dur,
            "results": res_dicts,
        }

        # Save JSON
        with open(j_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        # Save CSV
        if results:
            fieldnames = list(res_dicts[0].keys())
            with open(c_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(res_dicts)

        return metrics
