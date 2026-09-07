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

  // normalize path, e.g. /api/v1/companies/xyz
  var p = path.replace(/^\/+/, '').replace(/\/+$/, '');
  var seg = p.split('/').filter(function (x) { return x.length > 0; });
  // seg[0]='api', seg[1]='v1', seg[2]=resource...

  if (seg.length >= 3 && seg[0] === 'api' && seg[1] === 'v1') {
    var res = seg[2];
    var id = seg[3] || null;
    var sub = seg[4] || null;

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
      if (id === 'orders') {
        if (method === 'POST') return ordersCreate_(body, q);
        return ordersList_(q);
      }
      if (sub === 'cancel') return ordersCancel_(id, q);
    }

    // SOCIAL
    if (res === 'social') {
      if (id === null) {
        if (method === 'POST') return socialCreate_(body, q);
        return socialList_(q);
      }
      if (sub === 'like') return socialLike_(id, q);
      if (sub === 'comments') {
        if (method === 'POST') return socialCommentCreate_(id, body, q);
        return socialCommentsList_(id, q);
      }
      return socialGet_(id, q);
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
function newsList_(q) {
  var news = readAll_(getSheet_('news'));
  var out = news.map(function (n) {
    return {
      id: n.id, title: n.title, summary: n.summary, content: n.content, source: n.source,
      category: n.category, sentiment: n.sentiment, impact_score: Number(n.impact_score),
      company_id: n.company_id, is_ai_generated: String(n.is_ai_generated) === 'true' || String(n.is_ai_generated) === 'TRUE',
      simulated_at: n.simulated_at, created_at: n.created_at
    };
  });
  if (q.category) out = out.filter(function (n) { return n.category === q.category; });
  if (q.sentiment) out = out.filter(function (n) { return n.sentiment === q.sentiment; });
  var total = out.length;
  var skip = parseInt(q.skip || '0', 10) || 0;
  var limit = parseInt(q.limit || '100', 10) || 100;
  return sendJson_({ items: out.slice(skip, skip + limit), total: total });
}

function newsGet_(id, q) {
  var n = findRow_(getSheet_('news'), 'id', id);
  if (!n) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y b\u00e0i b\u00e1o' }, 404);
  return sendJson_({
    id: n.id, title: n.title, summary: n.summary, content: n.content, source: n.source,
    category: n.category, sentiment: n.sentiment, impact_score: Number(n.impact_score),
    company_id: n.company_id, is_ai_generated: String(n.is_ai_generated) === 'true',
    simulated_at: n.simulated_at, created_at: n.created_at
  });
}

// ------------------------------------------------------------------
// TRADES
// ------------------------------------------------------------------
function tradesPortfolio_(q) {
  var uid = currentUserId_(q);
  var companies = readAll_(getSheet_('companies'));
  var priceMap = {};
  var compMap = {};
  companies.forEach(function (c) { priceMap[c.id] = c.current_price; compMap[c.id] = c; });

  var portfolio = readAll_(getSheet_('portfolio')).filter(function (p) { return p.user_id === uid; });
  var items = [];
  var totalCash = 0;
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
  totalCash = parseFloat(u ? u.cash_balance : 0);
  return sendJson_({ items: items, total_cash: String(totalCash), total_nav: String(totalCash + totalValue) });
}

function ordersList_(q) {
  var uid = currentUserId_(q);
  var orders = readAll_(getSheet_('orders')).filter(function (o) { return o.user_id === uid; });
  if (q.status) orders = orders.filter(function (o) { return o.status === q.status; });
  var out = orders.map(function (o) {
    return {
      id: o.id, company_id: o.company_id, side: o.side, type: o.type, status: o.status,
      price: o.price ? String(o.price) : null, quantity: String(o.quantity),
      filled_quantity: String(o.filled_quantity), created_at: o.created_at
    };
  });
  return sendJson_(out);
}

function ordersCreate_(body, q) {
  var uid = currentUserId_(q);
  var order = {
    id: newId('o'), user_id: uid, company_id: body.company_id, side: body.side,
    type: body.type || 'market', status: 'filled', price: body.price ? String(body.price) : null,
    quantity: String(body.quantity), filled_quantity: String(body.quantity), created_at: isoNow()
  };
  appendRow_(getSheet_('orders'), order);
  return sendJson_({
    id: order.id, company_id: order.company_id, side: order.side, type: order.type,
    status: order.status, price: order.price, quantity: order.quantity,
    filled_quantity: order.filled_quantity, created_at: order.created_at
  });
}

function ordersCancel_(id, q) {
  var uid = currentUserId_(q);
  var orders = readAll_(getSheet_('orders'));
  for (var i = 0; i < orders.length; i++) {
    if (orders[i].id === id && orders[i].user_id === uid) {
      orders[i].status = 'cancelled';
      updateRowByKey_(getSheet_('orders'), orders[i], 'id');
      return sendJson_({
        id: orders[i].id, company_id: orders[i].company_id, side: orders[i].side,
        type: orders[i].type, status: 'cancelled', price: orders[i].price ? String(orders[i].price) : null,
        quantity: String(orders[i].quantity), filled_quantity: String(orders[i].filled_quantity), created_at: orders[i].created_at
      });
    }
  }
  return sendJson_({ detail: 'L\u1ec7nh kh\u00f4ng t\u1ed3n t\u1ea1i' }, 404);
}

// ------------------------------------------------------------------
// SOCIAL
// ------------------------------------------------------------------
function socialItem_(s) {
  return {
    id: s.id, author_name: s.author_name, author_avatar: s.author_avatar,
    persona_type: s.persona_type, content: s.content, sentiment: s.sentiment,
    virality_score: Number(s.virality_score), likes_count: Number(s.likes_count),
    shares_count: Number(s.shares_count), comments_count: Number(s.comments_count),
    company_id: s.company_id, news_id: s.news_id, simulated_at: s.simulated_at,
    created_at: s.created_at, liked_by_me: false
  };
}

function socialList_(q) {
  var social = readAll_(getSheet_('social'));
  var out = social.map(socialItem_);
  if (q.persona_type) out = out.filter(function (s) { return s.persona_type === q.persona_type; });
  if (q.sentiment) out = out.filter(function (s) { return s.sentiment === q.sentiment; });
  var total = out.length;
  var skip = parseInt(q.skip || '0', 10) || 0;
  var limit = parseInt(q.limit || '100', 10) || 100;
  return sendJson_({ items: out.slice(skip, skip + limit), total: total });
}

function socialGet_(id, q) {
  var s = findRow_(getSheet_('social'), 'id', id);
  if (!s) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y b\u00e0i vi\u1ebft' }, 404);
  return sendJson_(socialItem_(s));
}

function socialCreate_(body, q) {
  var now = isoNow();
  var post = {
    id: newId('s'), author_name: 'B\u1ea1n', author_avatar: null, persona_type: 'user',
    content: body.content, sentiment: 'neutral', virality_score: 0,
    likes_count: 0, shares_count: 0, comments_count: 0,
    company_id: body.company_symbol ? companyBySymbol_(body.company_symbol) : null,
    news_id: null, simulated_at: now, created_at: now
  };
  appendRow_(getSheet_('social'), post);
  return sendJson_(socialItem_(post));
}

function companyBySymbol_(symbol) {
  var companies = readAll_(getSheet_('companies'));
  for (var i = 0; i < companies.length; i++) {
    if (companies[i].symbol === symbol) return companies[i].id;
  }
  return null;
}

function socialLike_(id, q) {
  var s = findRow_(getSheet_('social'), 'id', id);
  if (!s) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y b\u00e0i vi\u1ebft' }, 404);
  var current = Number(s.likes_count || 0);
  s.likes_count = current + 1;
  updateRowByKey_(getSheet_('social'), s, 'id');
  return sendJson_({ liked: true, likes_count: current + 1 });
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
// TASKS
// ------------------------------------------------------------------
function taskItem_(t) {
  return {
    id: t.id, code: t.code, name: t.name, description: t.description, category: t.category,
    reward_amount: t.reward_amount ? String(t.reward_amount) : '0', target_count: Number(t.target_count || 1),
    reset_frequency: t.reset_frequency || 'none'
  };
}

function tasksList_(q) {
  var tasks = readAll_(getSheet_('tasks')).filter(function (t) { return String(t.is_active) === 'true' || String(t.is_active) === 'TRUE'; });
  var items = tasks.map(function (t) {
    return {
      task: taskItem_(t), progress_count: 1, target_count: Number(t.target_count || 1),
      completed: Number(t.target_count || 1) <= 1, claimable: false
    };
  });
  return sendJson_({ streak_current: 1, streak_longest: 1, total_reward_earned: '25000', tasks: items });
}

function tasksCheckin_(q) {
  return sendJson_({ already_checked_in: false, current_streak: 1, longest_streak: 1, reward_earned: '5000' });
}

function tasksEvent_(body, q) {
  return sendJson_({ accepted: true, rewarded: false });
}

function tasksClaim_(id, q) {
  var t = findRow_(getSheet_('tasks'), 'id', id);
  if (!t) return sendJson_({ detail: 'Kh\u00f4ng t\u00ecm th\u1ea5y nhi\u1ec7m v\u1ee5' }, 404);
  return sendJson_({ task: taskItem_(t), progress_count: 1, target_count: Number(t.target_count || 1), completed: true, reward_earned: String(t.reward_amount || '0') });
}

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
    status: 'draft', config: JSON.stringify({ template: body.template || 'classic', industry: body.industry, difficulty: body.difficulty || 'normal' }),
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

// For testing: trigger via doGet /ping with no path
function doPing() {
  seedIfEmpty_();
  return sendText_('pong');
}
