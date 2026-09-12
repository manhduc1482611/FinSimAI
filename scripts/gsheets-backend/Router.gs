/**
 * Capia Apps Script - REST Router (doGet / doPost)
 * ----------------------------------------------------
 * Frontend demo mode g\u1ecdi:
 *   GET  .../exec?path=/api/v1/companies&limit=20
 *   POST .../exec?path=/api/v1/auth/login   (body = JSON, Content-Type text/plain)
 */

function doGet(e) {
  seedIfEmpty_();
  var path = (e.parameter && e.parameter.path) || '/';
  var q = e.parameter || {};
  var body = {};
  try {
    return handleRequest_('GET', path, q, body);
  } catch (err) {
    return sendJson_({ detail: String(err) }, 500);
  }
}

function doPost(e) {
  seedIfEmpty_();
  var path = (e.parameter && e.parameter.path) || '/';
  var q = e.parameter || {};
  var body = {};
  if (e.postData && e.postData.contents) {
    try { body = JSON.parse(e.postData.contents); } catch (err) { body = {}; }
  }
  try {
    return handleRequest_('POST', path, q, body);
  } catch (err) {
    return sendJson_({ detail: String(err) }, 500);
  }
}

/**
 * Frontend demo mode g\u1ed9p query string v\u00e0o param `path`
 * (vd path=`/api/v1/companies?limit=20`). Ta t\u00e1ch ra v\u00e0 tr\u1ea3 query object.
 */
function splitPathQuery_(p) {
  var idx = p.indexOf('?');
  if (idx < 0) return { path: p, params: {} };
  var pathPart = p.substring(0, idx);
  var qs = p.substring(idx + 1);
  var params = {};
  if (qs) {
    var pairs = qs.split('&');
    for (var i = 0; i < pairs.length; i++) {
      var kv = pairs[i].split('=');
      if (kv.length >= 2) {
        params[decodeURIComponent(kv[0])] = decodeURIComponent(kv.slice(1).join('='));
      }
    }
  }
  return { path: pathPart, params: params };
}

function handleRequest_(method, path, q, body) {
  // split query out of path (frontend packs query into path param)
  var split = splitPathQuery_(path);
  path = split.path;
  for (var pk in split.params) { q[pk] = split.params[pk]; }

  // Apps Script web app chỉ nhận GET/POST — frontend demo giấu method thật
  // (PATCH/DELETE/...) qua query param `method` khi gửi POST.
  if ((method === 'POST' || method === undefined) && q.method) {
    method = String(q.method).toUpperCase();
  }

  // normalize path, e.g. /api/v1/companies/xyz
  var p = path.replace(/^\/+/, '').replace(/\/+$/, '');
  var seg = p.split('/').filter(function (x) { return x.length > 0; });
  // seg[0]='api', seg[1]='v1', seg[2]=resource...

  if (seg.length >= 3 && seg[0] === 'api' && seg[1] === 'v1') {
    var res = seg[2];
    var id = seg[3] || null;
    var sub = seg[4] || null;
    var deep = seg[5] || null; // hành động con: role / status

    // AUTH
    if (res === 'auth') {
      if (id === 'login') return authLogin_(body, q);
      if (id === 'register') return authRegister_(body, q);
      if (id === 'refresh') return authRefresh_(body, q);
      if (id === 'ws-ticket') return sendJson_({ ticket: 'demo-ticket', ttl_seconds: 3600, expires_at: isoNow() });
    }
    if (res === 'users' && id === 'me') return usersMe_(q);

    // META (kiem tra version & unicode escape da deploy chua)
    if (res === 'meta') return sendJson_({ version: 'escaped-v2', test: '\u0044\u00e2\u0075' });

    // COMPANIES
    if (res === 'companies') {
      if (id === null) return companiesList_(q);
      return companiesGet_(id, q);
    }

    // NEWS
    if (res === 'news') {
      if (id === null) return newsList_(q);
      return newsGet_(id, q);
    }

    // TRADES
    if (res === 'trades') {
      if (id === 'portfolio') return tradesPortfolio_(q);
      if (deep === 'cancel') return ordersCancel_(sub, q);
      if (id === 'orders') {
        if (method === 'POST') return ordersCreate_(body, q);
        return ordersList_(q);
      }
    }

    // SOCIAL
    if (res === 'social') {
      if (id === null) return socialList_(q);
      if (sub === 'like') return socialLike_(id, q);
      if (sub === 'comments') {
        if (method === 'POST') return socialCommentCreate_(id, body, q);
        return socialCommentsList_(id, q);
      }
      return socialGet_(id, q);
    }

    // SAVES (lưu tin tức / bài social — "Đã lưu" / Xem sau)
    if (res === 'saves') {
      if (id === 'toggle') return savesToggle_(body, q);
      return savesList_(q);
    }

    // TASKS
    if (res === 'tasks') {
      if (id === null) return tasksList_(q);
      if (id === 'checkin') return tasksCheckin_(q);
      if (id === 'events') return tasksEvent_(body, q);
      return tasksClaim_(id, q);
    }

    // CONTESTS
    if (res === 'contests') {
      if (id === null) {
        if (method === 'POST') return contestsCreate_(body, q);
        return contestsList_(q);
      }
      if (sub === 'join') return contestsJoin_(id, body, q);
      if (sub === 'companies') return contestsCompanies_(id, q);
      if (sub === 'news') return contestsNews_(id, q);
      if (sub === 'social-posts') return contestsSocial_(id, q);
      if (sub === 'activate') return contestsActivate_(id, q);
      if (method === 'PATCH') return contestsUpdate_(id, body, q);
      if (method === 'DELETE') return contestsDelete_(id, q);
      return contestsGet_(id, q);
    }

    // KNOWLEDGE
    if (res === 'knowledge' && id === 'match') return knowledgeMatch_(body, q);

    // MENTOR HISTORY
    if (res === 'mentor' && id === 'history') return mentorHistory_(q);

    // ADMIN (quản trị hệ thống — FR-9, FR-10)
    if (res === 'admin') {
      // Users
      if (id === 'users') {
        if (sub && deep === 'role') return adminUserRole_(sub, body, q);
        if (sub && deep === 'status') return adminUserStatus_(sub, body, q);
        return adminUsersList_(q);
      }
      // Contests
      if (id === 'contests') {
        if (sub && deep === 'status') return adminContestStatus_(sub, body, q);
        return adminContestsList_(q);
      }
      if (id === 'companies') return adminCompaniesList_(q);
      if (id === 'news') return adminNewsList_(q);
      if (id === 'social-posts') return adminSocialList_(q);
    }
  }

  return sendJson_({ detail: 'Not found: ' + path }, 404);
}

// ------------------------------------------------------------------
// AUTH
// ------------------------------------------------------------------
function currentUserId_(q) {
  // demo mode: frontend kh\u00f4ng g\u1eafn Bearer. D\u00f9ng token gi\u1ea3 ho\u1eb7c m\u1eb7c \u0111\u1ecbnh demo user.
  // \u0110\u01a1n gi\u1ea3n: tr\u1ea3 v\u1ec1 demo user tr\u1eeb khi c\u00f3 `demo_user` query.
  var u = (q && q.demo_user) || 'u-demo';
  return u;
}

function publicUser_(u) {
  return {
    id: u.id, email: u.email, username: u.username, display_name: u.display_name,
    avatar_url: u.avatar_url, role: u.role, cash_balance: u.cash_balance,
    frozen_cash: u.frozen_cash, risk_score: u.risk_score, cooldown_until: u.cooldown_until,
    is_active: String(u.is_active) === 'true' || String(u.is_active) === 'TRUE', created_at: u.created_at
  };
}

function authLogin_(body, q) {
  var users = readAll_(getSheet_('users'));
  var username = body.username || body.email || '';
  var password = body.password || '';
  for (var i = 0; i < users.length; i++) {
    var u = users[i];
    if ((u.username === username || u.email === username) && String(u.password) === String(password)) {
      var token = 'demo.' + Utilities.getUuid();
      return sendJson_({ access_token: token, refresh_token: token, token_type: 'bearer', expires_in: 3600 });
    }
  }
  return sendJson_({ detail: 'Sai t\u00ean \u0111\u0103ng nh\u1eadp ho\u1eb7c m\u1eadt kh\u1ea9u' }, 401);
}

function authRegister_(body, q) {
  var users = getSheet_('users');
  var username = body.username || '';
  // check duplicate
  var existing = readAll_(users);
  for (var i = 0; i < existing.length; i++) {
    if (existing[i].username === username || existing[i].email === body.email) {
      return sendJson_({ detail: 'T\u00ean \u0111\u0103ng nh\u1eadp ho\u1eb7c email \u0111\u00e3 t\u1ed3n t\u1ea1i' }, 409);
    }
  }
  var now = isoNow();
  var user = {
    id: newId('u'), email: body.email, username: username,
    display_name: body.display_name || username, avatar_url: null, role: 'user',
    cash_balance: '100000000', frozen_cash: '0', risk_score: 50, cooldown_until: null,
    is_active: 'true', created_at: now, password: body.password
  };
  appendRow_(users, user);
  return sendJson_(publicUser_(user));
}

function authRefresh_(body, q) {
  return sendJson_({ access_token: 'demo.' + Utilities.getUuid(), refresh_token: body.refresh_token, token_type: 'bearer', expires_in: 3600 });
}

function usersMe_(q) {
  var uid = currentUserId_(q);
  var u = findRow_(getSheet_('users'), 'id', uid) || findRow_(getSheet_('users'), 'id', 'u-demo');
  if (!u) return sendJson_({ detail: 'User not found' }, 404);
  return sendJson_(publicUser_(u));
}

// ------------------------------------------------------------------
// COMPANIES
// ------------------------------------------------------------------
function companiesList_(q) {
  // demo: n\u1ebfu c\u00f3 `tick=1`, ch\u1ea1y m\u00f4 ph\u1ecfng gi\u00e1 (random walk) r\u1ed3i tr\u1ea3 list
  if (q.tick === '1' || q.tick === 1) {
    simulatePriceTick_();
    // c\u1eadp nh\u1eadt portfolio theo gi\u00e1 m\u1edbi
    updatePortfolioValue_();
  }
  var companies = readAll_(getSheet_('companies'));
  var out = companies.map(function (c) {
    return {
      id: c.id, symbol: c.symbol, name: c.name, description: c.description,
      sector: c.sector, current_price: String(c.current_price), volatility: String(c.volatility),
      shares_outstanding: String(c.shares_outstanding), market_cap: c.market_cap ? String(c.market_cap) : null,
      health_score: Number(c.health_score), pe_ratio: c.pe_ratio ? String(c.pe_ratio) : null,
      roe: c.roe ? String(c.roe) : null, net_margin: c.net_margin ? String(c.net_margin) : null
    };
  });
  if (q.sector) out = out.filter(function (c) { return c.sector === q.sector; });
  if (q.search) {
    var s = String(q.search).toLowerCase();
    out = out.filter(function (c) { return (c.symbol || '').toLowerCase().indexOf(s) >= 0 || (c.name || '').toLowerCase().indexOf(s) >= 0; });
  }
  var total = out.length;
  var skip = parseInt(q.skip || '0', 10) || 0;
  var limit = parseInt(q.limit || '100', 10) || 100;
  return sendJson_({ items: out.slice(skip, skip + limit), total: total });
}

function companiesGet_(id, q) {
  var c = findRow_(getSheet_('companies'), 'id', id);
  if (!c) return sendJson_({ detail: 'C\u00f4ng ty kh\u00f4ng t\u1ed3n t\u1ea1i' }, 404);
  // Hook: xem company view → bump nhiệm vụ phân tích công ty (first_company_view / analyze_3_companies).
  tasksEventCompanyView_(currentUserId_(q));
  return sendJson_({
    id: c.id, symbol: c.symbol, name: c.name, description: c.description, sector: c.sector,
    current_price: String(c.current_price), volatility: String(c.volatility),
    shares_outstanding: String(c.shares_outstanding), market_cap: c.market_cap ? String(c.market_cap) : null,
    health_score: Number(c.health_score), pe_ratio: c.pe_ratio ? String(c.pe_ratio) : null,
    roe: c.roe ? String(c.roe) : null, net_margin: c.net_margin ? String(c.net_margin) : null
  });
}

// ------------------------------------------------------------------
// NEWS
// ------------------------------------------------------------------
function newsItem_(n, savedkey) {
  var isSaved = false;
  if (savedkey && savedkey['news:' + n.id] === true) isSaved = true;
  return {
    id: n.id, title: n.title, summary: n.summary, content: n.content, source: n.source,
    category: n.category, sentiment: n.sentiment, impact_score: Number(n.impact_score),
    company_id: n.company_id, is_ai_generated: String(n.is_ai_generated) === 'true' || String(n.is_ai_generated) === 'TRUE',
    simulated_at: n.simulated_at, created_at: n.created_at, is_saved: isSaved
  };
}

function newsList_(q) {
  var news = readAll_(getSheet_('news'));
  var savedkey = savedIdsFor_(q);
  var out = news.map(function (n) { return newsItem_(n, savedkey); });
  if (q.category) out = out.filter(function (n) { return n.category === q.category; });
  if (q.sentiment) out = out.filter(function (n) { return n.sentiment === q.sentiment; });
  if (q.q) {
    var s = String(q.q).toLowerCase();
    out = out.filter(function (n) {
      return String(n.title).toLowerCase().indexOf(s) >= 0
        || String(n.summary).toLowerCase().indexOf(s) >= 0
        || String(n.content).toLowerCase().indexOf(s) >= 0;
    });
  }
  out.sort(function (a, b) { return String(b.simulated_at || '').localeCompare(String(a.simulated_at || '')); });
  var total = out.length;
  var skip = parseInt(q.skip || '0', 10) || 0;
  var limit = parseInt(q.limit || '100', 10) || 100;
  return sendJson_({ items: out.slice(skip, skip + limit), total: total });
}

function newsGet_(id, q) {
  var n = findRow_(getSheet_('news'), 'id', id);
  if (!n) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y b\u00e0i b\u00e1o' }, 404);
  // Đọc tin → hook tăng nhiệm vụ đọc tin (first_news_read / read_10_news / daily_read_2_news).
  tasksEventNewsRead_(currentUserId_(q));
  return sendJson_(newsItem_(n, savedIdsFor_(q)));
}

// ------------------------------------------------------------------
// TRADES (freeze → fill engine — parity với FastAPI trading_service)
// ------------------------------------------------------------------

/** Shape chuẩn OrderResponse (schema/trade.py) — hidden frozen fields. */
function orderResponse_(o) {
  return {
    id: o.id, company_id: o.company_id, side: o.side, type: o.type, status: o.status,
    price: o.price ? String(o.price) : null, quantity: String(o.quantity),
    filled_quantity: String(o.filled_quantity || 0), created_at: o.created_at
  };
}

function tradesPortfolio_(q) {
  var uid = currentUserId_(q);
  var companies = readAll_(getSheet_('companies'));
  var priceMap = {};
  companies.forEach(function (c) { priceMap[c.id] = c.current_price; });

  var portfolio = readAll_(getSheet_('portfolio')).filter(function (p) { return p.user_id === uid; });
  var items = [];
  var totalCash = 0;
  var totalFrozen = 0;
  var totalValue = 0;
  portfolio.forEach(function (p) {
    var cur = parseFloat(priceMap[p.company_id] || p.current_price || 0);
    var qty = parseFloat(p.quantity || 0);
    var avg = parseFloat(p.average_buy_price || 0);
    var mv = qty * cur;
    items.push({
      company_id: p.company_id, symbol: p.symbol, company_name: p.company_name,
      quantity: String(qty), average_buy_price: String(avg), current_price: String(cur),
      market_value: String(mv), unrealized_pnl: String(mv - qty * avg)
    });
    totalValue += mv;
  });
  var u = findRow_(getSheet_('users'), 'id', uid);
  if (u) {
    totalCash = parseFloat(u.cash_balance || 0);
    totalFrozen = parseFloat(u.frozen_cash || 0);
  }
  return sendJson_({
    items: items,
    total_cash: String(totalCash),
    total_nav: String(totalCash + totalFrozen + totalValue)
  });
}

function ordersList_(q) {
  var uid = currentUserId_(q);
  var orders = readAll_(getSheet_('orders')).filter(function (o) { return o.user_id === uid; });
  if (q.status) orders = orders.filter(function (o) { return o.status === q.status; });
  // Sắp xếp mới nhất lên trên
  orders.sort(function (a, b) { return String(b.created_at || '').localeCompare(String(a.created_at || '')); });
  var out = orders.map(function (o) {
    return {
      id: o.id, company_id: o.company_id, side: o.side, type: o.type, status: o.status,
      price: o.price ? String(o.price) : null, quantity: String(o.quantity),
      filled_quantity: String(o.filled_quantity), created_at: o.created_at
    };
  });
  return sendJson_(out);
}

/** Xác định lệnh có thể khớp ngay tại thị trường hiện tại hay không. */
function isMarketable_(order, market) {
  if (order.type === 'market') return true;
  if (order.side === 'buy') return num_(order.price) >= market;
  return num_(order.price) <= market;
}

/** Khớp lệnh: cập nhật cash/portfolio/market_value & set status = filled. */
function fillOrderAtMarket_(order, company, market) {
  var uid = order.user_id;
  var qty = num_(order.quantity);
  var gross = round2_(qty * market);
  var fee = round2_(gross * TRADING_FEE_RATE);

  var u = findRow_(getSheet_('users'), 'id', uid);

  if (order.side === 'buy') {
    var totalDebit = round2_(gross + fee);
    var unfreeze = num_(order.frozen_cash);
    setUserValues_(uid, {
      cash_balance: round2_(num_(u.cash_balance) + unfreeze - totalDebit),
      frozen_cash: round2_(num_(u.frozen_cash) - unfreeze)
    });
    var p = portfolioRowOrNew_(uid, company);
    var oldQty = num_(p.quantity);
    var oldAvg = num_(p.average_buy_price);
    var newQty = round2_(oldQty + qty);
    var newAvg = round2_((oldQty * oldAvg + totalDebit) / newQty);
    upsertPortfolioRow_(uid, company, { quantity: String(newQty), average_buy_price: String(newAvg) });
    order.frozen_cash = '0';
  } else {
    var tax = round2_(gross * SELL_TAX_RATE);
    var netProceeds = round2_(gross - fee - tax);
    // Demo: ghi có cash ngay (FastAPI có T+2 settling — demo ưu tiên mượt mà).
    setUserValues_(uid, { cash_balance: round2_(num_(u.cash_balance) + netProceeds) });
    var s = portfolioRowOrNew_(uid, company);
    var heldQty = round2_(num_(s.quantity) - qty);
    var leftFrozen = round2_(num_(s.frozen_quantity) - num_(order.frozen_quantity));
    if (heldQty <= 0.0000001) {
      deletePortfolioRow_(uid, company.id);
    } else {
      upsertPortfolioRow_(uid, company, { quantity: String(heldQty), frozen_quantity: String(leftFrozen) });
    }
    order.frozen_quantity = '0';
  }
  order.status = 'filled';
  order.filled_quantity = String(qty);
  if (!order.price) order.price = String(market);
  updateRowByKey_(getSheet_('orders'), order, 'id');
  updatePortfolioValue_();
}

function ordersCreate_(body, q) {
  var uid = currentUserId_(q);
  var company = findRow_(getSheet_('companies'), 'id', body.company_id);
  if (!company) return sendJson_({ detail: 'C\u00f4ng ty kh\u00f4ng t\u1ed3n t\u1ea1i' }, 404);
  var side = body.side;
  var type = body.type || 'market';
  if (side !== 'buy' && side !== 'sell') return sendJson_({ detail: 'Lo\u1ea1i l\u1ec7nh kh\u00f4ng h\u1ee3p l\u1ec7' }, 400);
  if (type !== 'market' && type !== 'limit') return sendJson_({ detail: 'Lo\u1ea1i l\u1ec7nh kh\u00f4ng h\u1ee3p l\u1ec7' }, 400);
  var qty = num_(body.quantity);
  if (qty <= 0) return sendJson_({ detail: 'S\u1ed1 l\u01b0\u1ee3ng ph\u1ea3i l\u1edbn h\u01a1n 0' }, 400);
  if (type === 'limit' && num_(body.price) <= 0) return sendJson_({ detail: 'L\u1ec7nh gi\u1edbi h\u1ea1n c\u1ea7n gi\u00e1 h\u1ee3p l\u1ec7' }, 400);

  var market = num_(company.current_price);
  var u = findRow_(getSheet_('users'), 'id', uid);
  if (!u) return sendJson_({ detail: 'Ng\u01b0\u1eddi d\u00f9ng kh\u00f4ng t\u1ed3n t\u1ea1i' }, 404);

  var order = {
    id: newId('o'), user_id: uid, company_id: company.id, side: side, type: type,
    status: 'pending', price: body.price ? String(body.price) : null,
    quantity: String(qty), filled_quantity: '0',
    frozen_cash: '0', frozen_quantity: '0', created_at: isoNow()
  };

  // 1. Freeze vốn (buy) / shares (sell) — parity với FastAPI _freeze_buy_cash / portfolio freeze.
  if (side === 'buy') {
    var reqPrice = type === 'limit' ? num_(body.price) : market;
    var requiredCash = round2_(qty * reqPrice * (1 + TRADING_FEE_RATE));
    var available = round2_(num_(u.cash_balance) - num_(u.frozen_cash));
    if (requiredCash > available) {
      return sendJson_({ detail: 'S\u1ed1 d\u01b0 kh\u1ea3 d\u1ee5ng kh\u00f4ng \u0111\u1ee7 \u0111\u1ec3 \u0111\u1eb7t l\u1ec7nh' }, 400);
    }
    setUserValues_(uid, {
      cash_balance: round2_(num_(u.cash_balance) - requiredCash),
      frozen_cash: round2_(num_(u.frozen_cash) + requiredCash)
    });
    order.frozen_cash = String(requiredCash);
  } else {
    var p = portfolioRowOrNew_(uid, company);
    var availQty = round2_(num_(p.quantity) - num_(p.frozen_quantity));
    if (qty > availQty + 0.0000001) {
      return sendJson_({ detail: 'Kh\u00f4ng \u0111\u1ee7 c\u1ed5 phi\u1ebfu kh\u1ea3 d\u1ee5ng \u0111\u1ec3 b\u00e1n' }, 400);
    }
    var newFrozen = round2_(num_(p.frozen_quantity) + qty);
    upsertPortfolioRow_(uid, company, { frozen_quantity: String(newFrozen) });
    order.frozen_quantity = String(qty);
  }

  appendRow_(getSheet_('orders'), order);

  // Hook nhiệm vụ giao dịch (first_trade / daily_trade_1).
  taskOnTradeFilled_(uid);

  // 2. Khớp ngay nếu lệnh ăn khớp thị trường hiện tại (market luôn khớp; limit có điều kiện).
  if (isMarketable_(order, market)) {
    fillOrderAtMarket_(order, company, market);
  }

  return sendJson_(orderResponse_(order));
}

function ordersCancel_(id, q) {
  var uid = currentUserId_(q);
  var orders = readAll_(getSheet_('orders'));
  for (var i = 0; i < orders.length; i++) {
    var o = orders[i];
    if (o.id === id && o.user_id === uid) {
      if (o.status !== 'pending' && o.status !== 'partially_filled') {
        return sendJson_({ detail: 'L\u1ec7nh \u0111\u00e3 k\u1ebft th\u00fac, kh\u00f4ng th\u1ec3 h\u1ee7y' }, 400);
      }
      // Giải phóng vốn / shares đã khóa khi đặt lệnh.
      if (o.side === 'buy' && num_(o.frozen_cash) > 0) {
        var u = findRow_(getSheet_('users'), 'id', uid);
        setUserValues_(uid, {
          cash_balance: round2_(num_(u.cash_balance) + num_(o.frozen_cash)),
          frozen_cash: round2_(num_(u.frozen_cash) - num_(o.frozen_cash))
        });
        o.frozen_cash = '0';
      } else if (o.side === 'sell' && num_(o.frozen_quantity) > 0) {
        var company = findRow_(getSheet_('companies'), 'id', o.company_id) || { id: o.company_id, symbol: '', name: '' };
        var p = portfolioRowOrNew_(uid, company);
        var returnedQty = round2_(num_(o.frozen_quantity));
        var leftFrozen = round2_(num_(p.frozen_quantity) - returnedQty);
        upsertPortfolioRow_(uid, company, { frozen_quantity: String(Math.max(0, leftFrozen)) });
        o.frozen_quantity = '0';
      }
      o.status = 'cancelled';
      updateRowByKey_(getSheet_('orders'), o, 'id');
      return sendJson_(orderResponse_(o));
    }
  }
  return sendJson_({ detail: 'L\u1ec7nh kh\u00f4ng t\u1ed3n t\u1ea1i' }, 404);
}

// ------------------------------------------------------------------
// SOCIAL
// ------------------------------------------------------------------
function socialItem_(s, opts) {
  opts = opts || {};
  var key = 'social:' + s.id;
  return {
    id: s.id, author_name: s.author_name, author_avatar: s.author_avatar,
    persona_type: s.persona_type, content: s.content, sentiment: s.sentiment,
    virality_score: Number(s.virality_score), likes_count: Number(s.likes_count),
    shares_count: Number(s.shares_count), comments_count: Number(s.comments_count),
    company_id: s.company_id, news_id: s.news_id, simulated_at: s.simulated_at,
    created_at: s.created_at,
    liked_by_me: !!opts.likekey && opts.likekey[key] === true,
    is_saved: !!opts.savedkey && opts.savedkey[key] === true
  };
}

function socialList_(q) {
  var social = readAll_(getSheet_('social'));
  var opts = { likekey: likedIdsFor_(q), savedkey: savedIdsFor_(q) };
  var out = social.map(function (s) { return socialItem_(s, opts); });
  if (q.persona_type) out = out.filter(function (s) { return s.persona_type === q.persona_type; });
  if (q.sentiment) out = out.filter(function (s) { return s.sentiment === q.sentiment; });
  if (q.q) {
    var s = String(q.q).toLowerCase();
    out = out.filter(function (p) {
      return String(p.content).toLowerCase().indexOf(s) >= 0
        || String(p.author_name).toLowerCase().indexOf(s) >= 0;
    });
  }
  out.sort(function (a, b) { return String(b.simulated_at || '').localeCompare(String(a.simulated_at || '')); });
  var total = out.length;
  var skip = parseInt(q.skip || '0', 10) || 0;
  var limit = parseInt(q.limit || '100', 10) || 100;
  return sendJson_({ items: out.slice(skip, skip + limit), total: total });
}

function socialGet_(id, q) {
  var s = findRow_(getSheet_('social'), 'id', id);
  if (!s) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y b\u00e0i vi\u1ebft' }, 404);
  return sendJson_(socialItem_(s, { likekey: likedIdsFor_(q), savedkey: savedIdsFor_(q) }));
}

function socialLike_(id, q) {
  var s = findRow_(getSheet_('social'), 'id', id);
  if (!s) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y b\u00e0i vi\u1ebft' }, 404);
  var uid = currentUserId_(q);
  var sheet = ensureUserActionSheet_('social_likes', ['user_id', 'post_id', 'created_at']);
  var rows = readAll_(sheet);
  var foundIdx = -1;
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i].user_id) === String(uid) && String(rows[i].post_id) === String(id)) {
      foundIdx = i;
      break;
    }
  }
  var liked;
  if (foundIdx >= 0) {
    sheet.deleteRow(foundIdx + 2);
    s.likes_count = Math.max(0, Number(s.likes_count || 0) - 1);
    liked = false;
  } else {
    appendRow_(sheet, { user_id: uid, post_id: id, created_at: isoNow() });
    s.likes_count = Number(s.likes_count || 0) + 1;
    liked = true;
  }
  updateRowByKey_(getSheet_('social'), s, 'id');
  return sendJson_({ liked: liked, likes_count: s.likes_count });
}

function socialCommentsList_(id, q) {
  var comments = readAll_(getSheet_('social_comments')).filter(function (c) { return c.post_id === id; });
  var out = comments.map(function (c) {
    return { id: c.id, post_id: c.post_id, author_name: c.author_name, author_avatar: c.author_avatar, content: c.content, created_at: c.created_at };
  });
  return sendJson_({ items: out, total: out.length });
}

function socialCommentCreate_(id, body, q) {
  var comment = {
    id: newId('sc'), post_id: id, author_name: 'B\u1ea1n', author_avatar: null,
    content: body.content, created_at: isoNow()
  };
  appendRow_(getSheet_('social_comments'), comment);
  // increment comments_count
  var s = findRow_(getSheet_('social'), 'id', id);
  if (s) { s.comments_count = Number(s.comments_count || 0) + 1; updateRowByKey_(getSheet_('social'), s, 'id'); }
  return sendJson_({
    id: comment.id, post_id: comment.post_id, author_name: comment.author_name,
    author_avatar: comment.author_avatar, content: comment.content, created_at: comment.created_at
  });
}

// ------------------------------------------------------------------
// TASKS (thực thi trong Rewards.gs — bản full state, manual claim)
// ------------------------------------------------------------------
// tasksList_ / tasksCheckin_ / tasksEvent_ / tasksClaim_ được định nghĩa
// trong Rewards.gs (router này chỉ dẫn route tới đó).

// ------------------------------------------------------------------
// CONTESTS
// ------------------------------------------------------------------
function contestItem_(c) {
  var config = {};
  try { config = JSON.parse(c.config || '{}'); } catch (e) { config = {}; }
  var rawConfig = config;
  return {
    id: c.id, slug: c.slug, name: c.name, description: c.description,
    status: c.status, config: rawConfig, owner_id: c.owner_id,
    starts_at: c.starts_at, ends_at: c.ends_at,
    is_active: String(c.is_active) === 'true' || String(c.is_active) === 'TRUE',
    created_at: c.created_at, updated_at: c.updated_at, member_count: Number(c.member_count || 0)
  };
}

function contestsList_(q) {
  var contests = readAll_(getSheet_('contests'));
  var out = contests.map(contestItem_);
  var total = out.length;
  var skip = parseInt(q.skip || '0', 10) || 0;
  var limit = parseInt(q.limit || '100', 10) || 100;
  return sendJson_({ items: out.slice(skip, skip + limit), total: total });
}

function contestsGet_(slug, q) {
  var c = findRow_(getSheet_('contests'), 'slug', slug) || findRow_(getSheet_('contests'), 'id', slug);
  if (!c) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y cu\u1ed9c thi' }, 404);
  return sendJson_(contestItem_(c));
}

function contestsCreate_(body, q) {
  var now = isoNow();
  var slug = body.slug || (body.name || 'contest').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  var contest = {
    id: newId('co'), slug: slug, name: body.name, description: body.description || null,
    status: 'draft', config: JSON.stringify({ template: body.template || 'classic', industry: body.industry, difficulty: body.difficulty || 'normal', company_count: body.company_count || 6 }),
    owner_id: currentUserId_(q), starts_at: null, ends_at: null, is_active: 'false',
    created_at: now, updated_at: now, member_count: 0
  };
  appendRow_(getSheet_('contests'), contest);
  return sendJson_(contestItem_(contest));
}

function contestsJoin_(slug, body, q) {
  var c = findRow_(getSheet_('contests'), 'slug', slug);
  if (!c) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y cu\u1ed9c thi' }, 404);
  c.member_count = Number(c.member_count || 0) + 1;
  updateRowByKey_(getSheet_('contests'), c, 'id');
  return sendJson_({ joined: true, contest_id: c.id });
}

function contestsCompanies_(slug, q) {
  // Reuse all companies for demo contest
  return companiesList_(q);
}

function contestsNews_(slug, q) {
  return newsList_(q);
}

function contestsSocial_(slug, q) {
  return socialList_(q);
}

function contestsActivate_(slug, q) {
  var c = findRow_(getSheet_('contests'), 'slug', slug);
  if (!c) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y cu\u1ed9c thi' }, 404);
  c.status = 'active'; c.is_active = 'true'; c.updated_at = isoNow();
  updateRowByKey_(getSheet_('contests'), c, 'id');
  return sendJson_(contestItem_(c));
}

function contestsUpdate_(slug, body, q) {
  var c = findRow_(getSheet_('contests'), 'slug', slug);
  if (!c) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y cu\u1ed9c thi' }, 404);
  if (body.name) c.name = body.name;
  if (body.description !== undefined) c.description = body.description;
  c.updated_at = isoNow();
  updateRowByKey_(getSheet_('contests'), c, 'id');
  return sendJson_(contestItem_(c));
}

function contestsDelete_(slug, q) {
  var c = findRow_(getSheet_('contests'), 'slug', slug);
  if (!c) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y cu\u1ed9c thi' }, 404);
  c.status = 'ended'; c.is_active = 'false'; c.updated_at = isoNow();
  updateRowByKey_(getSheet_('contests'), c, 'id');
  return sendJson_(contestItem_(c));
}

// ------------------------------------------------------------------
// KNOWLEDGE
// ------------------------------------------------------------------
function knowledgeMatch_(body, q) {
  var text = (body.text || '').toLowerCase();
  var knowledge = readAll_(getSheet_('knowledge'));
  var matches = [];
  var scored = [];
  knowledge.forEach(function (k) {
    var kw = (k.keyword || '').toLowerCase();
    // simple score: contains keyword or concept
    var score = 0;
    if (text.indexOf(kw) >= 0) score += 3;
    if (text.indexOf((k.concept || '').toLowerCase()) >= 0) score += 2;
    if (score > 0) scored.push({ k: k, score: score });
  });
  scored.sort(function (a, b) { return b.score - a.score; });
  scored.slice(0, 5).forEach(function (item) {
    matches.push({
      id: item.k.id, keyword: item.k.keyword, concept: item.k.concept, definition: item.k.definition,
      category: item.k.category, difficulty: Number(item.k.difficulty || 1),
      related_keywords: (function () { try { return JSON.parse(item.k.related_keywords || '[]'); } catch (e) { return []; } })(),
      created_at: item.k.created_at
    });
  });
  return sendJson_({ matches: matches });
}

// ------------------------------------------------------------------
// MENTOR HISTORY
// ------------------------------------------------------------------
function mentorHistory_(q) {
  // demo: return empty history
  return sendJson_({ items: [], total: 0 });
}

// ------------------------------------------------------------------
// ADMIN handlers — shapes parity với schemas/admin.py
// ------------------------------------------------------------------
function adminUser_(u) {
  return {
    id: u.id, email: u.email, username: u.username, display_name: u.display_name,
    role: u.role,
    is_active: String(u.is_active) === 'true' || String(u.is_active) === 'TRUE',
    created_at: u.created_at
  };
}

function adminUsersList_(q) {
  var users = readAll_(getSheet_('users')).map(adminUser_);
  if (q.role) users = users.filter(function (u) { return u.role === q.role; });
  if (q.search) {
    var s = String(q.search).toLowerCase();
    users = users.filter(function (u) {
      return (u.email || '').toLowerCase().indexOf(s) >= 0
        || (u.username || '').toLowerCase().indexOf(s) >= 0
        || (u.display_name || '').toLowerCase().indexOf(s) >= 0;
    });
  }
  users.sort(function (a, b) { return String(b.created_at || '').localeCompare(String(a.created_at || '')); });
  var total = users.length;
  var skip = parseInt(q.skip || '0', 10) || 0;
  var limit = parseInt(q.limit || '100', 10) || 100;
  return sendJson_({ items: users.slice(skip, skip + limit), total: total });
}

function adminUserRole_(uid, body, q) {
  var targetUser = findRow_(getSheet_('users'), 'id', uid);
  if (!targetUser) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y ng\u01b0\u1eddi d\u00f9ng' }, 404);
  var role = body.role;
  if (role !== 'user' && role !== 'host' && role !== 'admin') return sendJson_({ detail: 'Role kh\u00f4ng h\u1ee3p l\u1ec7' }, 400);
  if (String(targetUser.id) === String(currentUserId_(q))) return sendJson_({ detail: 'Kh\u00f4ng th\u1ec3 t\u1eeb \u0111\u1ed5i role c\u1ee7a ch\u00ednh m\u00ecnh' }, 400);
  updateRowByKey_(getSheet_('users'), { id: uid, role: role }, 'id');
  return sendJson_(adminUser_({ id: uid, email: targetUser.email, username: targetUser.username, display_name: targetUser.display_name, role: role, is_active: targetUser.is_active, created_at: targetUser.created_at }));
}

function adminUserStatus_(uid, body, q) {
  var targetUser = findRow_(getSheet_('users'), 'id', uid);
  if (!targetUser) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y ng\u01b0\u1eddi d\u00f9ng' }, 404);
  if (String(targetUser.id) === String(currentUserId_(q))) {
    return sendJson_({ detail: 'Kh\u00f4ng th\u1ec3 t\u1eeb v\u00f4 hi\u1ec7u ho\u1ea1 t\u00e0i kho\u1ea3n c\u1ee7a ch\u00ednh m\u00ecnh' }, 400);
  }
  var active = body.is_active;
  if (active === undefined || active === null) return sendJson_({ detail: 'Thi\u1ebfu tr\u1ea1ng th\u00e1i' }, 400);
  updateRowByKey_(getSheet_('users'), { id: uid, is_active: String(active) }, 'id');
  return sendJson_(adminUser_({ id: uid, email: targetUser.email, username: targetUser.username, display_name: targetUser.display_name, role: targetUser.role, is_active: active, created_at: targetUser.created_at }));
}

function adminContestsList_(q) {
  var contests = readAll_(getSheet_('contests')).map(contestItem_);
  if (q.status) contests = contests.filter(function (c) { return c.status === q.status; });
  contests.sort(function (a, b) { return String(b.created_at || '').localeCompare(String(a.created_at || '')); });
  var total = contests.length;
  var skip = parseInt(q.skip || '0', 10) || 0;
  var limit = parseInt(q.limit || '100', 10) || 100;
  return sendJson_({ items: contests.slice(skip, skip + limit), total: total });
}

function adminContestStatus_(idOrSlug, body, q) {
  var c = findRow_(getSheet_('contests'), 'id', idOrSlug) || findRow_(getSheet_('contests'), 'slug', idOrSlug);
  if (!c) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y cu\u1ed9c thi' }, 404);
  var status = body.status;
  if (status !== 'draft' && status !== 'active' && status !== 'ended') return sendJson_({ detail: 'Tr\u1ea1ng th\u00e1i kh\u00f4ng h\u1ee3p l\u1ec7' }, 400);
  c.status = status;
  c.is_active = status === 'active' ? 'true' : 'false';
  c.updated_at = isoNow();
  updateRowByKey_(getSheet_('contests'), c, 'id');
  return sendJson_(contestItem_(c));
}

function adminCompaniesList_(q) {
  // Reuse companiesList_ nhưng bỏ tick để tránh chạy giá random.
  var qq = {};
  for (var k in q) { if (q[k] !== undefined) qq[k] = q[k]; }
  delete qq.tick;
  return companiesList_(qq);
}

function adminNewsList_(q) { return newsList_(q); }
function adminSocialList_(q) { return socialList_(q); }

// ------------------------------------------------------------------
// SAVES - lưu/Xem sau (tin tức + bài xã hội)
// ------------------------------------------------------------------

/** Bảo đảm sheet hành động user có header chuẩn (số dư thừa an toàn). */
function ensureUserActionSheet_(name, headers) {
  var sheet = getSheet_(name);
  if (getHeaders_(sheet).length === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
  return sheet;
}

function deleteRowByKey_(sheet, key, keyName) {
  var headers = getHeaders_(sheet);
  var kIdx = headers.indexOf(keyName);
  if (kIdx < 0) return false;
  var values = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  for (var r = 0; r < values.length; r++) {
    if (String(values[r][kIdx]) === String(key)) {
      sheet.deleteRow(r + 2);
      return true;
    }
  }
  return false;
}

/** Map "type:id" -> true cho các content user ĐÃ LƯU (news / social). */
function savedIdsFor_(q) {
  var uid = currentUserId_(q);
  var key = {};
  var rows = readAll_(getSheet_('content_saves'));
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i].user_id) === String(uid)) {
      key[String(rows[i].content_type) + ':' + String(rows[i].content_id)] = true;
    }
  }
  return key;
}

/** Map "social:id" -> true cho các bài user ĐÃ LIKE. */
function likedIdsFor_(q) {
  var uid = currentUserId_(q);
  var key = {};
  var rows = readAll_(getSheet_('social_likes'));
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i].user_id) === String(uid)) {
      key['social:' + String(rows[i].post_id)] = true;
    }
  }
  return key;
}

function savesToggle_(body, q) {
  var uid = currentUserId_(q);
  var sheet = ensureUserActionSheet_('content_saves', ['user_id', 'content_type', 'content_id', 'created_at']);
  var type = body.content_type;
  var id = body.content_id;
  var rows = readAll_(sheet);
  var foundIdx = -1;
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i].user_id) === String(uid)
      && String(rows[i].content_type) === String(type)
      && String(rows[i].content_id) === String(id)) {
      foundIdx = i;
      break;
    }
  }
  if (foundIdx >= 0) {
    sheet.deleteRow(foundIdx + 2);
    return sendJson_({ saved: false });
  }
  appendRow_(sheet, { user_id: uid, content_type: type, content_id: id, created_at: isoNow() });
  return sendJson_({ saved: true });
}

function savesList_(q) {
  var uid = currentUserId_(q);
  var sheet = ensureUserActionSheet_('content_saves', ['user_id', 'content_type', 'content_id', 'created_at']);
  var rows = readAll_(sheet).filter(function (r) { return String(r.user_id) === String(uid); });
  if (q.content_type) rows = rows.filter(function (r) { return r.content_type === q.content_type; });
  rows.sort(function (a, b) { return String(b.created_at).localeCompare(String(a.created_at)); });
  var total = rows.length;
  var skip = parseInt(q.skip || '0', 10) || 0;
  var limit = parseInt(q.limit || '100', 10) || 100;
  rows = rows.slice(skip, skip + limit);

  var newsRows = readAll_(getSheet_('news'));
  var socialRows = readAll_(getSheet_('social'));
  var newsMap = {};
  var socialMap = {};
  newsRows.forEach(function (n) { newsMap[n.id] = n; });
  socialRows.forEach(function (s) { socialMap[s.id] = s; });

  var items = rows.map(function (r) {
    var resp = {
      content_type: r.content_type,
      content_id: r.content_id,
      saved_at: r.created_at,
      news: null,
      social: null
    };
    if (r.content_type === 'news' && newsMap[r.content_id]) {
      resp.news = newsItem_(newsMap[r.content_id], savedIdsFor_(q));
    } else if (r.content_type === 'social' && socialMap[r.content_id]) {
      resp.social = socialItem_(socialMap[r.content_id], { likekey: likedIdsFor_(q), savedkey: savedIdsFor_(q) });
    }
    return resp;
  });
  return sendJson_({ items: items, total: total });
}

// For testing: trigger via doGet /ping with no path
function doPing() {
  seedIfEmpty_();
  return sendText_('pong');
}
