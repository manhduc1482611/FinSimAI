"""Test cấu hình ARQ worker: danh sách task, cron, các tham số an toàn."""

from arq.worker import get_kwargs

from tasks.worker import WorkerSettings, _burst_settings


def test_functions_registered():
    names = {function.__name__ for function in WorkerSettings.functions}
    assert names == {
        "crawl_news",
        "generate_scenario_batch",
        "generate_social_posts",
    }


def test_cron_jobs_defined():
    assert len(WorkerSettings.cron_jobs) == 3
    targets = {job.coroutine.__name__ for job in WorkerSettings.cron_jobs}
    assert targets == {"crawl_news", "generate_scenario_batch", "generate_social_posts"}


def test_safety_params():
    assert WorkerSettings.max_jobs >= 1
    assert WorkerSettings.job_timeout > 0
    assert WorkerSettings.keep_result > 0
    assert WorkerSettings.retry_jobs is True


def test_burst_settings_preserve_functions_and_startup():
    """Hồi quy: ARQ đọc cấu hình qua ``__dict__``, không kế thừa attribute."""
    kwargs = get_kwargs(_burst_settings())
    assert kwargs["burst"] is True
    assert kwargs["cron_jobs"] == []
    assert {function.__name__ for function in kwargs["functions"]} == {
        "crawl_news",
        "generate_scenario_batch",
        "generate_social_posts",
    }
    assert kwargs["on_startup"] is not None
    assert kwargs["redis_settings"] is not None
