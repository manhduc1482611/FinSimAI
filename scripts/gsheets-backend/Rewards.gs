/**
 * Capia Apps Script - Rewards/Quests engine
 * ----------------------------------------------------
 * Persist trạng thái nhiệm vụ (daily reset theo ngày VN, thành tựu tích lũy
 * không reset) vào 2 sheet:
 *
 *   reward_progress : user_id | task_id | period_date | progress_count
 *                     | completed_at | claimed_at
 *   reward_meta     : user_id | current_streak | longest_streak | last_checkin_date
 *
 * Phần thưởng KHÔNG cộng thẳng khi hoàn thành — user phải bấm "Nhận thưởng"
 * (manual claim) thì tiền mới cộng vào users.cash_balance.
 */

// ------------------------------------------------------------------
// Ngày & mốc reset (Asia/Ho_Chi_Minh)
// ------------------------------------------------------------------
function taskItem_(t) {
  return {
    id: t.id, code: t.code, name: t.name, description: t.description, category: t.category,
    reward_amount: t.reward_amount ? String(t.reward_amount) : '0',
    target_count: Number(t.target_count || 1),
    reset_frequency: t.reset_frequency || 'none',
    // Nhóm hiển thị: nhiệm vụ hằng ngày reset mỗi ngày, còn lại là thành tựu.
    group: t.category === 'daily' ? 'daily' : 'achievement'
  };
}

/** Hook khi đặt lệnh (gọi từ Router.gs ordersCreate_) — tăng nhiệm vụ giao dịch. */
function taskOnTradeFilled_(uid) {
  bumpTask_(uid, 'first_trade', '');
  bumpTask_(uid, 'daily_trade_1', vnToday_());
}

function vnToday_() {
  return Utilities.formatDate(new Date(), 'Asia/Ho_Chi_Minh', 'yyyy-MM-dd');
}

function vnDaySerial_(label) {
  if (!label) return -Number.MAX_VALUE;
  var p = String(label).split('-').map(Number);
  return Math.floor(Date.UTC(p[0], p[1] - 1, p[2]) / 86400000);
}

/** Mốc reset kế tiếp (00:00 Asia/Ho_Chi_Minh) dưới dạng ISO-8601. */
function vnNextResetIso_() {
  var labels = Utilities.formatDate(
    new Date(), 'Asia/Ho_Chi_Minh', 'yyyy|MM|dd'
  ).split('|');
  var d = Date.UTC(Number(labels[0]), Number(labels[1]) - 1, Number(labels[2]) + 1);
  // 00:00 VN = UTC+7 → trừ 7h để ra đúng thời điểm reset.
  return new Date(d - 7 * 3600 * 1000).toISOString();
}

// ------------------------------------------------------------------
// reward_progress helpers
// ------------------------------------------------------------------
function progressRow_(uid, taskId, period) {
  var rows = readAll_(getSheet_('reward_progress'));
  for (var i = 0; i < rows.length; i++) {
    if (
      rows[i].user_id === uid &&
      rows[i].task_id === taskId &&
      String(rows[i].period_date || '') === String(period || '')
    ) {
      return rows[i];
    }
  }
  return null;
}

function upsertProgress_(uid, taskId, period, patch) {
  var sheet = getSheet_('reward_progress');
  if (getHeaders_(sheet).length === 0) {
    sheet.getRange(1, 1, 1, 6).setValues([
      ['user_id', 'task_id', 'period_date', 'progress_count', 'completed_at', 'claimed_at']
    ]);
  }
  var headers = getHeaders_(sheet);
  var rows = readAll_(sheet);
  var found = null;
  for (var i = 0; i < rows.length; i++) {
    if (
      rows[i].user_id === uid &&
      rows[i].task_id === taskId &&
      String(rows[i].period_date || '') === String(period || '')
    ) {
      found = i + 2;
      break;
    }
  }
  if (found !== null) {
    for (var j = 0; j < headers.length; j++) {
      var col = headers[j];
      if (patch[col] !== undefined) {
        sheet.getRange(found, j + 1).setValue(patch[col]);
      }
    }
    return;
  }
  var base = {
    user_id: uid, task_id: taskId, period_date: period || '',
    progress_count: 0, completed_at: '', claimed_at: ''
  };
  for (var k in patch) base[k] = patch[k];
  appendRow_(sheet, base);
}

// ------------------------------------------------------------------
// Streak (reward_meta)
// ------------------------------------------------------------------
function streakState_(uid) {
  var row = findRow_(getSheet_('reward_meta'), 'user_id', uid);
  return row
    ? {
        current: Number(row.current_streak || 0),
        longest: Number(row.longest_streak || 0),
        last_checkin: row.last_checkin_date || ''
      }
    : { current: 0, longest: 0, last_checkin: '' };
}

function saveStreak_(uid, current, longest, last) {
  var sheet = getSheet_('reward_meta');
  if (getHeaders_(sheet).length === 0) {
    sheet.getRange(1, 1, 1, 4).setValues([
      ['user_id', 'current_streak', 'longest_streak', 'last_checkin_date']
    ]);
  }
  _ensureColumn_(sheet, 'last_checkin_date');
  var patch = {
    user_id: uid,
    current_streak: current,
    longest_streak: longest,
    last_checkin_date: last
  };
  if (findRow_(sheet, 'user_id', uid)) {
    updateRowByKey_(sheet, patch, 'user_id');
  } else {
    appendRow_(sheet, patch);
  }
}

// ------------------------------------------------------------------
// Hoàn thành nhiệm vụ (bump progress)
// ------------------------------------------------------------------
function bumpTask_(uid, code, period) {
  var t = findRow_(getSheet_('tasks'), 'code', code);
  if (!t) return false;
  if (String(t.is_active) !== 'true' && String(t.is_active) !== 'TRUE') return false;
  var p = progressRow_(uid, t.id, period);
  if (p && p.completed_at) return false;
  var count = (p ? Number(p.progress_count || 0) : 0) + 1;
  var completed = count >= Number(t.target_count || 1);
  upsertProgress_(uid, t.id, period, {
    progress_count: count,
    completed_at: completed ? isoNow() : ''
  });
  return completed;
}

/** Hoàn thành meta task (onboarding_complete / daily_all_4) nếu đủ điều kiện. */
function maybeCompleteMeta_(uid) {
  var tasks = readAll_(getSheet_('tasks'));
  var metaOnboard = null;
  var metaDaily = null;
  for (var i = 0; i < tasks.length; i++) {
    if (tasks[i].code === 'onboarding_complete') metaOnboard = tasks[i];
    if (tasks[i].code === 'daily_all_4') metaDaily = tasks[i];
  }
  if (metaOnboard) {
    var p = progressRow_(uid, metaOnboard.id, '');
    if (!p || !p.completed_at) {
      var allDone = true;
      for (i = 0; i < tasks.length; i++) {
        var t = tasks[i];
        if (t.category !== 'onboarding' || t.code === 'onboarding_complete') continue;
        var pp = progressRow_(uid, t.id, '');
        if (!pp || !pp.completed_at) { allDone = false; break; }
      }
      if (allDone) {
        upsertProgress_(uid, metaOnboard.id, '', { progress_count: 1, completed_at: isoNow() });
      }
    }
  }
  if (metaDaily) {
    var today = vnToday_();
    var p2 = progressRow_(uid, metaDaily.id, today);
    if (!p2 || !p2.completed_at) {
      var doneCount = 0;
      var total = 0;
      for (i = 0; i < tasks.length; i++) {
        var d = tasks[i];
        if (d.category !== 'daily' || d.code === 'daily_all_4') continue;
        total++;
        var pd = progressRow_(uid, d.id, today);
        if (pd && pd.completed_at) doneCount++;
      }
      if (total >= 2 && doneCount >= total - 1) {
        upsertProgress_(uid, metaDaily.id, today, { progress_count: 1, completed_at: isoNow() });
      }
    }
  }
}

// ------------------------------------------------------------------
// Tiền thưởng (chỉ cộng khi claim)
// ------------------------------------------------------------------
function creditCash_(uid, amount) {
  var sheet = getSheet_('users');
  var u = findRow_(sheet, 'id', uid);
  if (!u) return;
  var cash = (parseFloat(u.cash_balance || 0) || 0) + (parseFloat(amount || 0) || 0);
  var rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).getValues();
  var headers = getHeaders_(sheet);
  var idCol = headers.indexOf('id') + 1;
  var cashCol = headers.indexOf('cash_balance') + 1;
  for (var r = 0; r < rows.length; r++) {
    if (String(rows[r][idCol - 1]) === String(uid)) {
      sheet.getRange(r + 2, cashCol).setValue(String(cash));
      return;
    }
  }
}

function totalRewardEarned_(uid) {
  var rows = readAll_(getSheet_('reward_progress')).filter(function (r) {
    return r.user_id === uid && r.claimed_at;
  });
  var total = 0;
  for (var i = 0; i < rows.length; i++) {
    var t = findRow_(getSheet_('tasks'), 'id', rows[i].task_id);
    if (t) total += parseFloat(t.reward_amount || 0);
  }
  return total;
}

// ------------------------------------------------------------------
// API handlers (gọi từ Router.gs)
// ------------------------------------------------------------------
function tasksList_(q) {
  var uid = currentUserId_(q);
  var today = vnToday_();
  maybeCompleteMeta_(uid);
  var st = streakState_(uid);
  maybeCompleteStreaks_(uid, st.current);
  var activeTasks = readAll_(getSheet_('tasks')).filter(function (t) {
    return String(t.is_active) === 'true' || String(t.is_active) === 'TRUE';
  });
  // Sắp theo sort_order (parity with backend ORDER BY sort_order, code).
  activeTasks.sort(function (a, b) {
    var sa = parseInt(a.sort_order || '0', 10) || 0;
    var sb = parseInt(b.sort_order || '0', 10) || 0;
    if (sa !== sb) return sa - sb;
    return String(a.code).localeCompare(String(b.code));
  });
  var items = [];
  for (var i = 0; i < activeTasks.length; i++) {
    var task = activeTasks[i];
    var period = task.category === 'daily' ? today : '';
    var p = progressRow_(uid, task.id, period);
    var done = !!(p && p.completed_at);
    var claimed = !!(p && p.claimed_at);
    var count = p ? Number(p.progress_count || 0) : 0;
    if (task.category === 'streak' && !done) {
      count = Math.min(st.current, Number(task.target_count || 1));
    }
    items.push({
      task: taskItem_(task),
      progress_count: count,
      target_count: Number(task.target_count || 1),
      completed: done,
      claimable: done && !claimed,
      claimed: claimed,
      completed_at: p && p.completed_at ? p.completed_at : null
    });
  }
  return sendJson_({
    streak_current: st.current,
    streak_longest: st.longest,
    total_reward_earned: String(totalRewardEarned_(uid)),
    next_reset_at: vnNextResetIso_(),
    tasks: items
  });
}

function tasksCheckin_(q) {
  var uid = currentUserId_(q);
  var today = vnToday_();
  var st = streakState_(uid);
  if (st.last_checkin === today) {
    return sendJson_({
      already_checked_in: true,
      current_streak: st.current,
      longest_streak: st.longest,
      reward_earned: '0'
    });
  }
  var current = vnDaySerial_(st.last_checkin) === vnDaySerial_(today) - 1 ? st.current + 1 : 1;
  var longest = current > st.longest ? current : st.longest;
  taskRewardSetStreak_(uid, current, longest, today);
  maybeCompleteStreaks_(uid, current);
  return sendJson_({
    already_checked_in: false,
    current_streak: current,
    longest_streak: longest,
    reward_earned: '0'
  });
}

/** Check-in: cập nhật streak + đánh dấu hoàn thành nhiệm vụ daily_checkin. */
function taskRewardSetStreak_(uid, current, longest, today) {
  saveStreak_(uid, current, longest, today);
  bumpTask_(uid, 'daily_checkin', today);
}

function tasksEvent_(body, q) {
  var uid = currentUserId_(q);
  var event = body.event || '';
  var today = vnToday_();
  var completedNow = 0;
  if (event === 'mentor_chat') {
    completedNow += bumpTask_(uid, 'first_mentor_chat', '') ? 1 : 0;
    completedNow += bumpTask_(uid, 'mentor_3_chats', '') ? 1 : 0;
    completedNow += bumpTask_(uid, 'daily_mentor_1', today) ? 1 : 0;
  } else if (event === 'scenario_complete') {
    completedNow += bumpTask_(uid, 'scenario_1_done', '') ? 1 : 0;
  }
  return sendJson_({ accepted: true, rewarded: completedNow > 0 });
}

/** Đọc một bài tin → bump các nhiệm vụ đọc tin (parity với backend FastAPI news_read). */
function tasksEventNewsRead_(uid) {
  var today = vnToday_();
  bumpTask_(uid, 'first_news_read', '');
  bumpTask_(uid, 'read_10_news', '');
  bumpTask_(uid, 'daily_read_2_news', today);
}

/** Xem hồ sơ công ty → bump các nhiệm vụ phân tích công ty (parity với backend company_view). */
function tasksEventCompanyView_(uid) {
  bumpTask_(uid, 'first_company_view', '');
  bumpTask_(uid, 'analyze_3_companies', '');
}

/** Hoàn thành các nhiệm vụ streak khi đã đạt target (parity FastAPI _maybe_complete_streaks). */
function maybeCompleteStreaks_(uid, current) {
  var tasks = readAll_(getSheet_('tasks')).filter(function (t) {
    return t.category === 'streak' && (String(t.is_active) === 'true' || String(t.is_active) === 'TRUE');
  });
  for (var i = 0; i < tasks.length; i++) {
    var t = tasks[i];
    if (current < Number(t.target_count || 1)) continue;
    var p = progressRow_(uid, t.id, '');
    if (!p || !p.completed_at) {
      upsertProgress_(uid, t.id, '', { progress_count: Number(t.target_count || 1), completed_at: isoNow() });
    }
  }
}

function tasksClaim_(id, q) {
  var uid = currentUserId_(q);
  var t = findRow_(getSheet_('tasks'), 'id', id);
  if (!t) return sendJson_({ detail: 'Không tìm thấy nhiệm vụ' }, 404);
  var period = t.category === 'daily' ? vnToday_() : '';
  var p = progressRow_(uid, t.id, period);
  if (!p || !p.completed_at) {
    // contest_top10: demo không verify rank — cho phép nhận khi đạt mốc tiêu chuẩn.
    if (t.code !== 'contest_top10') {
      return sendJson_({ detail: 'Nhiệm vụ chưa hoàn thành — chưa thể nhận thưởng' }, 400);
    }
    upsertProgress_(uid, t.id, period, {
      progress_count: Number(t.target_count || 1),
      completed_at: isoNow()
    });
    p = progressRow_(uid, t.id, period);
  }
  var reward = String(t.reward_amount || '0');
  if (p.claimed_at) {
    return sendJson_({
      task: taskItem_(t),
      progress_count: Number(p.progress_count || 0),
      target_count: Number(t.target_count || 1),
      completed: true,
      claimed: true,
      reward_earned: '0'
    });
  }
  creditCash_(uid, reward);
  upsertProgress_(uid, t.id, period, { claimed_at: isoNow() });
  return sendJson_({
    task: taskItem_(t),
    progress_count: Number(p.progress_count || 0),
    target_count: Number(t.target_count || 1),
    completed: true,
    claimed: true,
    reward_earned: reward
  });
}