"""Package marker cho `tasks` (ARQ job definitions).

Không có file này, mypy coi `tasks/crawl_tasks.py` vừa là module `crawl_tasks`
vừa là `tasks.crawl_tasks` → lỗi "Source file found twice under different module
names". Marker này cố định tên module ``tasks.*``.
"""
