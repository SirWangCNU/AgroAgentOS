import asyncio

import pytest

from app.exceptions import AppException
from app.runtime.farm_run_context import (
    FarmRunContext,
    bind_farm_run_context,
    get_farm_run_context,
    require_farm_run_context,
)


def test_require_farm_run_context_rejects_missing_context() -> None:
    assert get_farm_run_context() is None

    with pytest.raises(AppException) as exc_info:
        require_farm_run_context()

    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "FARM_RUN_CONTEXT_MISSING"


def test_bind_farm_run_context_restores_outer_context() -> None:
    outer_context = FarmRunContext(
        user_id=7,
        farm_id=11,
        run_id="run-1",
        run_type="inspection",
    )
    inner_context = FarmRunContext(
        user_id=8,
        farm_id=12,
        run_id="run-2",
        run_type="task_verification",
        task_id="task-1",
    )

    with bind_farm_run_context(outer_context) as bound_context:
        assert bound_context == outer_context
        assert require_farm_run_context() == outer_context

        with bind_farm_run_context(inner_context):
            assert require_farm_run_context() == inner_context

        assert require_farm_run_context() == outer_context

    assert get_farm_run_context() is None


def test_bind_farm_run_context_resets_after_body_raises() -> None:
    context = FarmRunContext(
        user_id=7,
        farm_id=11,
        run_id="run-1",
        run_type="inspection",
    )

    with pytest.raises(RuntimeError, match="body failed"):
        with bind_farm_run_context(context):
            assert require_farm_run_context() == context
            raise RuntimeError("body failed")

    assert get_farm_run_context() is None


@pytest.mark.asyncio
async def test_bind_farm_run_context_isolates_concurrent_tasks() -> None:
    first_context = FarmRunContext(
        user_id=7,
        farm_id=11,
        run_id="run-1",
        run_type="inspection",
    )
    second_context = FarmRunContext(
        user_id=8,
        farm_id=12,
        run_id="run-2",
        run_type="inspection",
    )
    both_bound = asyncio.Event()
    bound_count = 0
    bound_count_lock = asyncio.Lock()

    async def read_bound_context(context: FarmRunContext) -> FarmRunContext:
        nonlocal bound_count
        with bind_farm_run_context(context):
            async with bound_count_lock:
                bound_count += 1
                if bound_count == 2:
                    both_bound.set()
            await both_bound.wait()
            await asyncio.sleep(0)
            return require_farm_run_context()

    observed_contexts = await asyncio.gather(
        read_bound_context(first_context),
        read_bound_context(second_context),
    )

    assert observed_contexts == [first_context, second_context]
    assert get_farm_run_context() is None
