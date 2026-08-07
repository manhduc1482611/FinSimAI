"""Service cho hệ thống Nhiệm vụ & Thưởng.

Cơ chế:
- ``record_event``: endpoint backend tự gọi khi user thực hiện hành vi (đọc bài,
  đặt lệnh, join contest, cập nhật hồ sơ...) — tăng tiến độ tương ứng.
- ``report_event``: sự kiện do frontend báo qua ``POST /tasks/events`` cho các
  hành vi không có endpoint riêng (chat Mentor, hoàn thành kịch bản).
- ``checkin``: đăng nhập hằng ngày + cập nhật chuỗi ngày (streak) + thưởng mốc.
- ``claim_task``: nhận thưởng thủ công cho nhiệm vụ cần xác minh điều kiện
  (đứng top 10 cuộc thi).

Mốc ngày tính theo ``settings.app_timezone`` (mặc định Asia/Ho_Chi_Minh) để nhiệm
vụ hằng ngày / streak không reset lệch với thói quen của người dùng.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from core.config import settings
from models.company import Company
from models.contest import ContestMember
from models.task import Task, UserStreak, UserTaskProgress
from models.trade import Portfolio
from models.user import User
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CAT_ONBOARDING = "onboarding"
CAT_LEARNING = "learning"
CAT_DAILY = "daily"
CAT_STREAK = "streak"
CAT_CONTEST = "contest"

META_ONBOARDING = "onboarding_complete"
META_DAILY = "daily_all_4"
CODE_CONTEST_TOP10 = "contest_top10"

# Sự kiện backend → danh sách task code tương ứng.
EVENT_TASK_CODES: dict[str, list[str]] = {
    "profile_complete": ["profile_complete"],
    "trade_placed": ["first_trade", "daily_trade_1"],
    "knowledge_read": [
        "first_knowledge_read",
        "read_5_knowledge",
        "read_10_knowledge",
        "daily_read_3_knowledge",
    ],
    "news_read": ["first_news_read", "read_10_news", "daily_read_2_news"],
    "company_view": ["first_company_view", "analyze_3_companies"],
    "mentor_chat": ["first_mentor_chat", "mentor_3_chats", "daily_mentor_1"],
    "scenario_complete": ["scenario_1_done"],
    "contest_joined": ["contest_join_1"],
}

# Chỉ các sự kiện này được client báo qua POST /tasks/events (các sự kiện còn
# lại do backend tự ghi khi xử lý hành vi thật — tránh lách thưởng).
CLIENT_EVENTS: frozenset[str] = frozenset({"mentor_chat", "scenario_complete"})


class TaskServiceError(Exception):
    """Lỗi nghiệp vụ của hệ thống nhiệm vụ — API map thành HTTP 400."""


class TaskNotClaimableError(TaskServiceError):
    """Nhiệm vụ chưa đạt điều kiện nhận thưởng."""


class TaskEventUnknownError(TaskServiceError):
    """Sự kiện không tồn tại trong danh mục."""


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


async def _get_active_task(db: AsyncSession, code: str) -> Task | None:
    result = await db.execute(
        select(Task).where(Task.code == code, Task.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def _credit_reward(db: AsyncSession, user: User, amount: Decimal) -> None:
    if amount <= 0:
        return
    result = await db.execute(select(User).where(User.id == user.id).with_for_update())
    locked = result.scalar_one()
    locked.cash_balance = (locked.cash_balance or Decimal("0.00")) + amount


async def _progress_task(
    db: AsyncSession, user: User, task: Task, period_date: date | None
) -> UserTaskProgress:
    stmt = select(UserTaskProgress).where(
        UserTaskProgress.user_id == user.id,
        UserTaskProgress.task_id == task.id,
    )
    if period_date is None:
        stmt = stmt.where(UserTaskProgress.period_date.is_(None))
    else:
        stmt = stmt.where(UserTaskProgress.period_date == period_date)
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()
    if progress is None:
        progress = UserTaskProgress(
            user_id=user.id, task_id=task.id, period_date=period_date, progress_count=0
        )
        db.add(progress)
    return progress


async def _try_complete(
    db: AsyncSession, user: User, progress: UserTaskProgress, task: Task
) -> bool:
    if progress.completed_at is not None:
        return False
    progress.progress_count += 1
    progress.last_progress_at = _now_utc()
    if progress.progress_count < task.target_count:
        return False
    await _credit_reward(db, user, task.reward_amount)
    progress.reward_amount = task.reward_amount
    progress.completed_at = _now_utc()
    return True


async def _count_active_in_category(
    db: AsyncSession, category: str, exclude_code: str
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Task)
        .where(
            Task.is_active.is_(True),
            Task.category == category,
            Task.code != exclude_code,
        )
    )
    return int(result.scalar_one())


async def _count_distinct_completed(
    db: AsyncSession,
    user_id: object,
    category: str,
    exclude_code: str,
    period_date: date | None,
) -> int:
    subq = select(UserTaskProgress.task_id).where(
        UserTaskProgress.user_id == user_id,
        UserTaskProgress.completed_at.is_not(None),
    )
    if period_date is None:
        subq = subq.where(UserTaskProgress.period_date.is_(None))
    else:
        subq = subq.where(UserTaskProgress.period_date == period_date)
    result = await db.execute(
        select(func.count(func.distinct(Task.id))).where(
            Task.is_active.is_(True),
            Task.category == category,
            Task.code != exclude_code,
            Task.id.in_(subq),
        )
    )
    return int(result.scalar_one())


async def _maybe_complete_onboarding(db: AsyncSession, user: User) -> None:
    task = await _get_active_task(db, META_ONBOARDING)
    if task is None:
        return
    progress = await _progress_task(db, user, task, None)
    if progress.completed_at is not None:
        return
    required = await _count_active_in_category(db, CAT_ONBOARDING, META_ONBOARDING)
    completed = await _count_distinct_completed(
        db, user.id, CAT_ONBOARDING, META_ONBOARDING, None
    )
    if required > 0 and completed >= required:
        await _credit_reward(db, user, task.reward_amount)
        progress.reward_amount = task.reward_amount
        progress.progress_count = 1
        progress.completed_at = _now_utc()


async def _maybe_complete_daily(db: AsyncSession, user: User) -> None:
    task = await _get_active_task(db, META_DAILY)
    if task is None:
        return
    today = _today()
    progress = await _progress_task(db, user, task, today)
    if progress.completed_at is not None:
        return
    required = await _count_active_in_category(db, CAT_DAILY, META_DAILY)
    completed = await _count_distinct_completed(
        db, user.id, CAT_DAILY, META_DAILY, today
    )
    if required >= 2 and completed >= required - 1:
        await _credit_reward(db, user, task.reward_amount)
        progress.reward_amount = task.reward_amount
        progress.progress_count = 1
        progress.completed_at = _now_utc()


async def _maybe_complete_streaks(
    db: AsyncSession, user: User, current_streak: int
) -> Decimal:
    total = Decimal("0.00")
    result = await db.execute(
        select(Task).where(Task.is_active.is_(True), Task.category == CAT_STREAK)
    )
    tasks = result.scalars().all()
    for task in tasks:
        if task.target_count > current_streak:
            continue
        progress = await _progress_task(db, user, task, None)
        if progress.completed_at is not None:
            continue
        progress.progress_count = task.target_count
        progress.last_progress_at = _now_utc()
        await _credit_reward(db, user, task.reward_amount)
        progress.reward_amount = task.reward_amount
        progress.completed_at = _now_utc()
        total += task.reward_amount
    return total


async def record_event(db: AsyncSession, user: User, event: str) -> bool:
    """Tăng tiến độ nhiệm vụ theo sự kiện hành vi của user (backend hook)."""
    codes = EVENT_TASK_CODES.get(event)
    if not codes:
        return False
    today = _today()
    dirty = False
    rewarded = False
    for code in codes:
        task = await _get_active_task(db, code)
        if task is None:
            continue
        period = today if task.reset_frequency == "daily" else None
        progress = await _progress_task(db, user, task, period)
        before = progress.progress_count
        completed_now = await _try_complete(db, user, progress, task)
        if progress.progress_count != before or completed_now:
            dirty = True
        if completed_now:
            rewarded = True
            if task.category == CAT_ONBOARDING:
                await _maybe_complete_onboarding(db, user)
            elif task.category == CAT_DAILY:
                await _maybe_complete_daily(db, user)
    if dirty:
        await db.commit()
    return rewarded


async def report_event(db: AsyncSession, user: User, event: str) -> tuple[bool, bool]:
    """Client báo sự kiện (whitelist) → ``(accepted, rewarded)``."""
    if event not in CLIENT_EVENTS:
        raise TaskEventUnknownError(f"Sự kiện không được phép: {event}")
    rewarded = await record_event(db, user, event)
    return True, rewarded


async def checkin(db: AsyncSession, user: User) -> dict[str, object]:
    """Điểm danh hằng ngày — cập nhật streak + thưởng mốc chuỗi ngày."""
    today = _today()
    result = await db.execute(select(UserStreak).where(UserStreak.user_id == user.id))
    streak_row = result.scalar_one_or_none()
    if streak_row is None:
        streak_row = UserStreak(user_id=user.id, current_streak=0, longest_streak=0)
        db.add(streak_row)

    reward = Decimal("0.00")
    already = streak_row.last_checkin_date == today
    if already:
        return {
            "already_checked_in": True,
            "current_streak": streak_row.current_streak,
            "longest_streak": streak_row.longest_streak,
            "reward_earned": reward,
        }

    if streak_row.last_checkin_date == today - timedelta(days=1):
        streak_row.current_streak += 1
    else:
        streak_row.current_streak = 1
    streak_row.last_checkin_date = today
    if streak_row.current_streak > streak_row.longest_streak:
        streak_row.longest_streak = streak_row.current_streak

    task = await _get_active_task(db, "daily_checkin")
    if task is not None:
        progress = await _progress_task(db, user, task, today)
        completed_now = await _try_complete(db, user, progress, task)
        if completed_now:
            reward += task.reward_amount
            await _maybe_complete_daily(db, user)

    reward += await _maybe_complete_streaks(db, user, streak_row.current_streak)
    await db.commit()
    return {
        "already_checked_in": False,
        "current_streak": streak_row.current_streak,
        "longest_streak": streak_row.longest_streak,
        "reward_earned": reward,
    }


async def _rank_in_contest(
    db: AsyncSession, contest_id: object, user_id: object
) -> int | None:
    result = await db.execute(
        select(ContestMember.user_id).where(ContestMember.contest_id == contest_id)
    )
    member_ids = list(result.scalars().all())
    if not member_ids:
        return None

    cash_rows = await db.execute(
        select(User.id, User.cash_balance).where(User.id.in_(member_ids))
    )
    cash_map = {
        uid: Decimal(str(amount)) for uid, amount in cash_rows.all()
    }

    mv_rows = await db.execute(
        select(
            Portfolio.user_id,
            func.sum(Portfolio.quantity * Company.current_price),
        )
        .join(Company, Portfolio.company_id == Company.id)
        .where(
            Portfolio.user_id.in_(member_ids),
            Portfolio.contest_id == contest_id,
        )
        .group_by(Portfolio.user_id)
    )
    mv_map = {uid: Decimal(str(value)) for uid, value in mv_rows.all()}

    navs = {
        uid: cash_map.get(uid, Decimal("0.00")) + mv_map.get(uid, Decimal("0.00"))
        for uid in member_ids
    }
    ordered = sorted(navs.items(), key=lambda item: item[1], reverse=True)
    for rank, (uid, _value) in enumerate(ordered, start=1):
        if uid == user_id:
            return rank
    return None


async def user_best_rank(db: AsyncSession, user_id: object) -> int | None:
    """Hạng tốt nhất hiện tại của user trong các cuộc thi đã tham gia (theo NAV)."""
    result = await db.execute(
        select(ContestMember.contest_id).where(ContestMember.user_id == user_id)
    )
    contest_ids = list(result.scalars().all())
    best: int | None = None
    for contest_id in contest_ids:
        rank = await _rank_in_contest(db, contest_id, user_id)
        if rank is not None and (best is None or rank < best):
            best = rank
    return best


async def list_tasks(db: AsyncSession, user: User) -> dict[str, object]:
    """Danh sách nhiệm vụ active + tiến độ của user (cho trang Nhiệm vụ & Thưởng)."""
    from schemas.task import TaskListResponse, TaskProgressResponse, TaskResponse

    tasks = (
        await db.execute(
            select(Task)
            .where(Task.is_active.is_(True))
            .order_by(Task.sort_order, Task.code)
        )
    ).scalars().all()
    progress_rows = (
        await db.execute(
            select(UserTaskProgress).where(UserTaskProgress.user_id == user.id)
        )
    ).scalars().all()
    streak_result = await db.execute(
        select(UserStreak).where(UserStreak.user_id == user.id)
    )
    streak_row = streak_result.scalar_one_or_none()

    today = _today()
    current = streak_row.current_streak if streak_row else 0
    longest = streak_row.longest_streak if streak_row else 0
    total_reward = Decimal("0.00")
    for row in progress_rows:
        if row.completed_at is not None:
            total_reward += row.reward_amount or Decimal("0.00")

    items: list[TaskProgressResponse] = []
    for task in tasks:
        if task.reset_frequency == "daily":
            prog = next(
                (p for p in progress_rows if p.task_id == task.id and p.period_date == today),
                None,
            )
        else:
            prog = next(
                (p for p in progress_rows if p.task_id == task.id and p.period_date is None),
                None,
            )
        completed = prog is not None and prog.completed_at is not None
        progress_count = prog.progress_count if prog else 0
        if task.category == CAT_STREAK and not completed:
            progress_count = min(current, task.target_count)
        claimable = False
        if task.code == CODE_CONTEST_TOP10 and not completed:
            best_rank = await user_best_rank(db, user.id)
            claimable = best_rank is not None and best_rank <= 10
        items.append(
            TaskProgressResponse(
                task=TaskResponse.model_validate(task),
                progress_count=progress_count,
                target_count=task.target_count,
                completed=completed,
                claimable=claimable,
                completed_at=prog.completed_at if prog else None,
            )
        )
    return TaskListResponse(
        streak_current=current,
        streak_longest=longest,
        total_reward_earned=total_reward,
        tasks=items,
    ).model_dump(mode="json")


async def claim_task(db: AsyncSession, user: User, task_id: object) -> dict[str, object]:
    """Nhận thưởng thủ công — hiện chỉ áp dụng cho nhiệm vụ top 10 cuộc thi."""
    from schemas.task import TaskClaimResponse, TaskResponse

    task = await db.get(Task, task_id)
    if task is None or not task.is_active:
        raise TaskServiceError("Nhiệm vụ không tồn tại hoặc đã bị tắt")

    if task.code == CODE_CONTEST_TOP10:
        best_rank = await user_best_rank(db, user.id)
        if best_rank is None or best_rank > 10:
            raise TaskNotClaimableError(
                "Bạn chưa đứng trong top 10 của bất kỳ cuộc thi nào — chưa thể nhận thưởng"
            )
        progress = await _progress_task(db, user, task, None)
        if progress.completed_at is not None:
            return TaskClaimResponse(
                task=TaskResponse.model_validate(task),
                progress_count=progress.progress_count,
                target_count=task.target_count,
                completed=True,
                reward_earned=Decimal("0.00"),
            ).model_dump(mode="json")
        progress.progress_count = task.target_count
        progress.last_progress_at = _now_utc()
        await _credit_reward(db, user, task.reward_amount)
        progress.reward_amount = task.reward_amount
        progress.completed_at = _now_utc()
        await db.commit()
        return TaskClaimResponse(
            task=TaskResponse.model_validate(task),
            progress_count=task.target_count,
            target_count=task.target_count,
            completed=True,
            reward_earned=task.reward_amount,
        ).model_dump(mode="json")

    raise TaskServiceError("Nhiệm vụ này được thưởng tự động, không cần nhận thủ công")
