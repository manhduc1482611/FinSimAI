/**
 * Capia - Google Apps Script Backend (demo)
 * ----------------------------------------------------------------
 * M\u1ee5c \u0111\u00edch: cho ph\u00e9p ch\u1ea1y b\u1ea3n demo tr\u00ean Vercel m\u00e0 KH\u00d4NG c\u1ea7n backend
 * FastAPI/Postgres/Redis. D\u00f9ng Google Sheets l\u00e0m database, doGet/doPost
 * l\u00e0m REST API tr\u1ea3 JSON.
 *
 * C\u00e1ch n\u1ed1i frontend:
 *   - Deploy script d\u01b0\u1edbi d\u1ea1ng Web App (Execute as: Me, Who has access: Anyone)
 *   - Frontend demo mode s\u1ebd g\u1ecdi URL web app n\u00e0y + route path.
 *
 * Ghi ch\u00fa CORS:
 *   - Web App v\u1edbi "Anyone" t\u1ef1 tr\u1ea3 `Access-Control-Allow-Origin: *`.
 *   - \u0110\u1ec3 tr\u00e1nh preflight OPTIONS (tr\u00ecnh duy\u1ec7t ch\u1eb7n), frontend demo mode
 *     g\u1eedi POST v\u1edbi Content-Type text/plain v\u00e0 KH\u00d4NG g\u1eafn Authorization header.
 */
var SHEET_NAMES = [
  'users', 'companies', 'news', 'social', 'social_comments', 'social_likes',
  'portfolio', 'orders', 'tasks', 'contests', 'contest_members', 'knowledge',
  'reward_progress', 'reward_meta', 'content_saves'
];

/**
 * ID c\u1ee7a Google Sheet d\u00f9ng l\u00e0m database cho b\u1ea3n demo.
 * Web app (execute as: Me) d\u00f9ng ch\u00ednh t\u00e0i kho\u1ea3n b\u1ea1n n\u00ean c\u00f3 quy\u1ec1n truy c\u1eadp sheet n\u00e0y.
 * C\u00e1ch l\u1ea5y: m\u1edf sheet \u2192 URL d\u1ea1ng .../spreadsheets/d/<ID>/edit \u2192 copy chu\u1ed7i gi\u1eefa /d/ v\u00e0 /edit.
 */
var SPREADSHEET_ID = '1OZxowdLas_royvQ3GMTDwDBOOmEuik0WhOwqal81GfM';

function ensureSheets_(ss) {
  SHEET_NAMES.forEach(function (name) {
    if (ss.getSheetByName(name) === null) {
      ss.insertSheet(name);
    }
  });
}

// ------------------------------------------------------------------
// Helper reading / writing rows using object keyed by first row headers
// ------------------------------------------------------------------

/** M\u1edf spreadsheet database. Kh\u00f4ng d\u00f9ng getActiveSpreadsheet (standalone web app tr\u1ea3 null). */
function openDb_() {
  if (!SPREADSHEET_ID || String(SPREADSHEET_ID).indexOf('DAN_VO') === 0) {
    throw new Error('Chua cau hinh SPREADSHEET_ID trong Code.gs');
  }
  return SpreadsheetApp.openById(SPREADSHEET_ID);
}

function getSheet_(name) {
  var ss = openDb_();
  ensureSheets_(ss);
  return ss.getSheetByName(name);
}

/** @return array of header names */
function getHeaders_(sheet) {
  var last = sheet.getLastColumn();
  if (last < 1) return [];
  var range = sheet.getRange(1, 1, 1, last).getValues()[0];
  return range.map(String);
}

/** @return array of objects, one per data row (starting row 2) */
function readAll_(sheet) {
  var headers = getHeaders_(sheet);
  if (!headers.length) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var out = [];
  for (var r = 0; r < values.length; r++) {
    var obj = {};
    for (var c = 0; c < headers.length; c++) {
      obj[headers[c]] = values[r][c];
    }
    out.push(obj);
  }
  return out;
}

function appendRow_(sheet, obj) {
  var headers = getHeaders_(sheet);
  if (!headers.length) return;
  var row = headers.map(function (h) { return obj[h] !== undefined ? obj[h] : ''; });
  sheet.appendRow(row);
}

function updateRowByKey_(sheet, obj, key) {
  var headers = getHeaders_(sheet);
  var kIdx = headers.indexOf(key);
  var values = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  for (var r = 0; r < values.length; r++) {
    if (String(values[r][kIdx]) === String(obj[key])) {
      for (var c = 0; c < headers.length; c++) {
        if (obj[headers[c]] !== undefined) {
          sheet.getRange(r + 2, c + 1).setValue(obj[headers[c]]);
        }
      }
      return true;
    }
  }
  return false;
}

function findRow_(sheet, key, value) {
  var rows = readAll_(sheet);
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i][key]) === String(value)) return rows[i];
  }
  return null;
}

function newId(prefix) {
  return prefix + '-' + Utilities.getUuid().slice(0, 8);
}

function isoNow() {
  return new Date().toISOString();
}

/** ISO timestamp sub (h)ours va (m)inutes truoc thoi diem hien tai. */
function agoISO_(h, m) {
  return new Date(Date.now() - ((h * 3600 + (m || 0)) * 1000)).toISOString();
}

// ------------------------------------------------------------------
// Trading engine: phí & thuế (parity với FastAPI trading_service)
// ------------------------------------------------------------------
var TRADING_FEE_RATE = 0.0015; // phí môi giới 0.15% (tính cả 2 chiều mua/bán)
var SELL_TAX_RATE = 0.001;     // thuế bán 0.1% (chỉ áp cho bên bán)

/** Chuyển value thành số thực an toàn (chuỗi rỗng / null / dấu phẩy). */
function num_(v) {
  var n = parseFloat(String(v === undefined || v === null ? '0' : v).replace(/,/g, ''));
  return isNaN(n) ? 0 : n;
}

/** Làm tròn về 2 chữ số thập phân (đơn vị VNĐ). */
function round2_(v) {
  return Math.round(v * 100) / 100;
}

/** Thêm cột cho sheet nếu chưa tồn tại (idempotent) — cho DB đã seed từ trước. */
function _ensureColumn_(sheet, colName) {
  var headers = getHeaders_(sheet);
  if (headers.indexOf(colName) >= 0) return;
  var last = headers.length + 1;
  sheet.getRange(1, last).setValue(colName);
  if (sheet.getLastRow() > 1) {
    sheet.getRange(2, last, sheet.getLastRow() - 1, 1).setValue('0');
  }
}

/** Ghi đồng thời nhiều cột của 1 user theo id (setValue theo từng cell, không đụng dòng khác). */
function setUserValues_(uid, patches) {
  var sheet = getSheet_('users');
  var headers = getHeaders_(sheet);
  var idCol = headers.indexOf('id');
  var values = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  for (var r = 0; r < values.length; r++) {
    if (String(values[r][idCol]) === String(uid)) {
      for (var c = 0; c < headers.length; c++) {
        var h = headers[c];
        if (patches[h] !== undefined && patches[h] !== null) {
          sheet.getRange(r + 2, c + 1).setValue(String(patches[h]));
        }
      }
      return;
    }
  }
}

/** Lấy dòng portfolio của (user, company); trả object mặc định nếu chưa có. */
function portfolioRowOrNew_(uid, company) {
  var rows = readAll_(getSheet_('portfolio'));
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].user_id === uid && String(rows[i].company_id) === String(company.id)) {
      return rows[i];
    }
  }
  return {
    user_id: uid, company_id: company.id, symbol: company.symbol, company_name: company.name,
    quantity: '0', average_buy_price: '0', current_price: String(company.current_price),
    market_value: '0', unrealized_pnl: '0', frozen_quantity: '0'
  };
}

/** Cập nhật (hoặc tạo) dòng portfolio theo (user, company) — an toàn khi trùng company_id giữa các user. */
function upsertPortfolioRow_(uid, company, patch) {
  var sheet = getSheet_('portfolio');
  var headers = getHeaders_(sheet);
  var uidCol = headers.indexOf('user_id');
  var cidCol = headers.indexOf('company_id');
  var values = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  for (var r = 0; r < values.length; r++) {
    if (String(values[r][uidCol]) === String(uid) && String(values[r][cidCol]) === String(company.id)) {
      for (var c = 0; c < headers.length; c++) {
        var h = headers[c];
        if (patch[h] !== undefined && patch[h] !== null) {
          sheet.getRange(r + 2, c + 1).setValue(String(patch[h]));
        }
      }
      return;
    }
  }
  // Chưa có dòng → chỉ tạo mới khi giữ cổ phiếu thật (quantity > 0).
  if (num_(patch.quantity) > 0) {
    var row = {
      user_id: uid, company_id: company.id, symbol: company.symbol, company_name: company.name,
      quantity: patch.quantity, average_buy_price: patch.average_buy_price,
      current_price: String(company.current_price),
      market_value: String(round2_(num_(patch.quantity) * num_(company.current_price))),
      unrealized_pnl: '0', frozen_quantity: '0'
    };
    appendRow_(sheet, row);
  }
}

/** Xóa dòng portfolio theo (user, company) khi hết cổ phiếu. */
function deletePortfolioRow_(uid, companyId) {
  var sheet = getSheet_('portfolio');
  var headers = getHeaders_(sheet);
  var uidCol = headers.indexOf('user_id');
  var cidCol = headers.indexOf('company_id');
  var values = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  for (var r = 0; r < values.length; r++) {
    if (String(values[r][uidCol]) === String(uid) && String(values[r][cidCol]) === String(companyId)) {
      sheet.deleteRow(r + 2);
      return true;
    }
  }
  return false;
}

function sendJson_(obj, status) {
  status = status || 200;
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function sendText_(str) {
  return ContentService.createTextOutput(str).setMimeType(ContentService.MimeType.TEXT);
}

// ------------------------------------------------------------------
// Seed data (first run) - realistic Vietnamese stock sim content
// ------------------------------------------------------------------
function seedIfEmpty_() {
  var ss = openDb_();
  ensureSheets_(ss);

  var companies = getSheet_('companies');
  if (getSheet_('companies').getLastRow() <= 1) {
    var cHeaders = ['id', 'symbol', 'name', 'description', 'sector', 'current_price', 'volatility', 'shares_outstanding', 'market_cap', 'health_score', 'pe_ratio', 'roe', 'net_margin'];
    // Nguon du lieu: packages/database/seeds/companies.yaml (he thong cu)
    var cRows = [
      ["c-techa-1", "TECHA", "TechVision Corp", "Leading developer of AI-powered analytics platforms for enterprise clients.", "Technology", "156.8", "0.025", "500000000", "78400000000", "88", "24.5", "18.2", "14.3"],
      ["c-techb-2", "TECHB", "CloudSync Inc", "Cloud infrastructure and data synchronization solutions provider.", "Technology", "89.4", "0.03", "200000000", "17880000000", "72", "35.1", "9.8", "8.1"],
      ["c-techc-3", "TECHC", "QuantumByte Labs", "Quantum computing research and commercial application development.", "Technology", "215", "0.04", "80000000", "17200000000", "65", "52.3", "5.1", "3.2"],
      ["c-fina-4", "FINA", "BlueRock Financial", "Full-service investment banking and wealth management firm.", "Financial", "45.6", "0.015", "1000000000", "45600000000", "82", "11.2", "15.8", "22.4"],
      ["c-finb-5", "FINB", "NovaPay Holdings", "Digital payment processing and fintech infrastructure platform.", "Financial", "72.3", "0.02", "300000000", "21690000000", "90", "28.6", "21.3", "18.7"],
      ["c-finc-6", "FINC", "SecureVault Insurance", "Multi-line insurance provider with digital-first distribution.", "Financial", "34.5", "0.012", "400000000", "13800000000", "78", "9.8", "12.5", "16.9"],
      ["c-heala-7", "HEALA", "BioGenix Therapeutics", "Biotechnology firm specializing in mRNA-based treatments.", "Healthcare", "128.9", "0.035", "150000000", "19335000000", "55", "", "", "-5.2"],
      ["c-healb-8", "HEALB", "MedCore International", "Medical device manufacturer focused on diagnostic imaging.", "Healthcare", "67.2", "0.018", "250000000", "16800000000", "74", "19.4", "14.7", "11.3"],
      ["c-healc-9", "HEALC", "VitaCare Health", "Managed healthcare services and telemedicine platform.", "Healthcare", "52.4", "0.022", "350000000", "18340000000", "68", "15.7", "10.2", "7.6"],
      ["c-energa-10", "ENERGA", "GreenHydrogen Energy", "Renewable hydrogen production and fuel cell technology.", "Energy", "18.75", "0.045", "600000000", "11250000000", "45", "", "", "-12.8"],
      ["c-energb-11", "ENERGB", "Solaris Power Grid", "Solar energy farm operator and smart grid integrator.", "Energy", "41.2", "0.028", "400000000", "16480000000", "62", "22.8", "8.5", "6.1"],
      ["c-energc-12", "ENERGC", "TerraFuels Corp", "Traditional oil & gas exploration with transitioning renewable portfolio.", "Energy", "95.3", "0.02", "700000000", "66710000000", "58", "14.2", "11.6", "9.4"],
      ["c-consma-13", "CONSMA", "Premier Brands Group", "Consumer packaged goods conglomerate with global distribution.", "Consumer Goods", "63.5", "0.01", "800000000", "50800000000", "91", "18.3", "22.4", "15.1"],
      ["c-consmb-14", "CONSMB", "EcoLiving Products", "Sustainable home goods and eco-friendly consumer products.", "Consumer Goods", "28.9", "0.018", "220000000", "6358000000", "76", "31.5", "13.2", "10.8"],
      ["c-consmc-15", "CONSMC", "FreshFarm Organics", "Organic food production and farm-to-table supply chain.", "Consumer Goods", "14.6", "0.025", "180000000", "2628000000", "80", "26.7", "16.9", "12.5"],
      ["c-indusa-16", "INDUSA", "AeroDynamics Inc", "Aerospace components and defense systems manufacturer.", "Industrial", "187.4", "0.016", "120000000", "22488000000", "85", "20.1", "19.7", "13.5"],
      ["c-indusb-17", "INDUSB", "BuildMaster Construction", "Large-scale infrastructure and commercial construction contractor.", "Industrial", "55.3", "0.014", "450000000", "24885000000", "70", "13.6", "10.8", "7.2"],
      ["c-indusc-18", "INDUSC", "LogiChain Solutions", "Supply chain logistics and automated warehousing technology.", "Industrial", "78.6", "0.022", "300000000", "23580000000", "83", "27.4", "17.3", "11.9"],
      ["c-comma-19", "COMMA", "OmniLink Telecom", "Telecommunications infrastructure and 5G network deployment.", "Communications", "42.1", "0.019", "550000000", "23155000000", "67", "16.5", "9.1", "6.8"],
      ["c-commb-20", "COMMB", "SocialWave Media", "Social media platform and digital advertising network.", "Communications", "110.2", "0.032", "380000000", "41876000000", "73", "38.2", "12.4", "8.9"]
    ];
    // \u00c9p to\u00e0n b\u1ed9 c\u1ed9t v\u1ec1 d\u1ea1ng text tr\u01b0\u1edbc khi ghi \u2192 gi\u1eef nguy\u00ean chu\u1ed7i (tr\u00e1nh
    // Google Sheets t\u1ef1 \u0111\u1ed5i 0.015\u219215, 15.2\u2192ng\u00e0y...).
    var cAll = [cHeaders].concat(cRows);
    var cRange = companies.getRange(1, 1, cAll.length, cHeaders.length);
    cRange.setNumberFormat('@');
    cRange.setValues(cAll);
  }

  var news = getSheet_('news');
  if (news.getLastRow() <= 1) {
    var nHeaders = ['id', 'title', 'summary', 'content', 'source', 'category', 'sentiment', 'impact_score', 'company_id', 'is_ai_generated', 'simulated_at', 'created_at'];
    news.getRange(1, 1, 1, nHeaders.length).setValues([nHeaders]);
    var now = isoNow();
    // Nguon du lieu: su dung lai generator tin tuc cua he thong cu (seed_db.py _news_rows)
    var nRows = [
      ["n-1", "TechVision Corp c\u00f4ng b\u1ed1 k\u1ebft qu\u1ea3 kinh doanh qu\u00fd v\u01b0\u1ee3t k\u1ef3 v\u1ecdng, c\u1ed5 phi\u1ebfu TECHA t\u0103ng m\u1ea1nh phi\u00ean s\u00e1ng", "B\u00e1o c\u00e1o t\u00e0i ch\u00ednh m\u1edbi nh\u1ea5t c\u1ee7a {name} v\u01b0\u1ee3t d\u1ef1 b\u00e1o c\u1ee7a gi\u1edbi ph\u00e2n t\u00edch, \u0111\u1ea9y gi\u00e1 c\u1ed5 phi\u1ebfu {symbol} \u0111i l\u00ean trong phi\u00ean giao ", "B\u00e1o c\u00e1o t\u00e0i ch\u00ednh m\u1edbi nh\u1ea5t c\u1ee7a {name} v\u01b0\u1ee3t d\u1ef1 b\u00e1o c\u1ee7a gi\u1edbi ph\u00e2n t\u00edch, \u0111\u1ea9y gi\u00e1 c\u1ed5 phi\u1ebfu {symbol} \u0111i l\u00ean trong phi\u00ean giao d\u1ecbch \u0111\u1ea7u ng\u00e0y. Ban l\u00e3nh \u0111\u1ea1o cho bi\u1ebft s\u1ebd ti\u1ebfp t\u1ee5c \u0111\u1ea9y m\u1ea1nh m\u1ea3ng kinh doanh c\u1ed1t l\u00f5i.", "Capia News", "doanh nghi\u1ec7p", "positive", "2.5", "c-techa-1", true, agoISO_(0, 0), now],
      ["n-2", "CloudSync Inc \u0111\u1ea9y nhanh k\u1ebf ho\u1ea1ch m\u1edf r\u1ed9ng th\u1ecb ph\u1ea7n trong qu\u00fd t\u1edbi", "Ban \u0111i\u1ec1u h\u00e0nh {name} c\u00f4ng b\u1ed1 chi\u1ebfn l\u01b0\u1ee3c m\u1edf r\u1ed9ng m\u1edbi, t\u1eadp trung v\u00e0o c\u00e1c th\u1ecb tr\u01b0\u1eddng ti\u1ec1m n\u0103ng. Nhi\u1ec1u nh\u00e0 \u0111\u1ea7u t\u01b0 k\u1ef3 v\u1ecdng \u0111\u1ed9", "Ban \u0111i\u1ec1u h\u00e0nh {name} c\u00f4ng b\u1ed1 chi\u1ebfn l\u01b0\u1ee3c m\u1edf r\u1ed9ng m\u1edbi, t\u1eadp trung v\u00e0o c\u00e1c th\u1ecb tr\u01b0\u1eddng ti\u1ec1m n\u0103ng. Nhi\u1ec1u nh\u00e0 \u0111\u1ea7u t\u01b0 k\u1ef3 v\u1ecdng \u0111\u1ed9ng th\u00e1i n\u00e0y s\u1ebd c\u1ea3i thi\u1ec7n doanh thu d\u00e0i h\u1ea1n.", "Capia News", "th\u1ecb tr\u01b0\u1eddng", "positive", "1.8", "c-techb-2", true, agoISO_(7, 1), now],
      ["n-3", "C\u1ed5 \u0111\u00f4ng QuantumByte Labs b\u0103n kho\u0103n tr\u01b0\u1edbc bi\u1ebfn \u0111\u1ed9ng ng\u1eafn h\u1ea1n c\u1ee7a c\u1ed5 phi\u1ebfu TECHC", "M\u1eb7c d\u00f9 n\u1ec1n t\u1ea3ng c\u01a1 b\u1ea3n \u1ed5n \u0111\u1ecbnh, c\u1ed5 phi\u1ebfu {symbol} c\u1ee7a {name} ghi nh\u1eadn nh\u1eefng phi\u00ean \u0111i\u1ec1u ch\u1ec9nh, khi\u1ebfn m\u1ed9t b\u1ed9 ph\u1eadn c\u1ed5 \u0111\u00f4ng ", "M\u1eb7c d\u00f9 n\u1ec1n t\u1ea3ng c\u01a1 b\u1ea3n \u1ed5n \u0111\u1ecbnh, c\u1ed5 phi\u1ebfu {symbol} c\u1ee7a {name} ghi nh\u1eadn nh\u1eefng phi\u00ean \u0111i\u1ec1u ch\u1ec9nh, khi\u1ebfn m\u1ed9t b\u1ed9 ph\u1eadn c\u1ed5 \u0111\u00f4ng th\u1eadn tr\u1ecdng tr\u01b0\u1edbc xu h\u01b0\u1edbng ng\u1eafn h\u1ea1n.", "Capia News", "ph\u00e2n t\u00edch", "neutral", "1.2", "c-techc-3", true, agoISO_(14, 2), now],
      ["n-4", "\u00c1p l\u1ef1c c\u1ea1nh tranh ng\u00e0y c\u00e0ng l\u1edbn v\u1edbi BlueRock Financial, chuy\u00ean gia \u0111\u01b0a khuy\u1ebfn ngh\u1ecb th\u1eadn tr\u1ecdng", "S\u1ef1 xu\u1ea5t hi\u1ec7n c\u1ee7a nhi\u1ec1u \u0111\u1ed1i th\u1ee7 m\u1edbi c\u00f9ng bi\u00ean l\u1ee3i nhu\u1eadn b\u1ecb thu h\u1eb9p khi\u1ebfn tri\u1ec3n v\u1ecdng {name} tr\u1edf n\u00ean k\u00e9m r\u00f5 r\u00e0ng h\u01a1n. C\u00e1c c", "S\u1ef1 xu\u1ea5t hi\u1ec7n c\u1ee7a nhi\u1ec1u \u0111\u1ed1i th\u1ee7 m\u1edbi c\u00f9ng bi\u00ean l\u1ee3i nhu\u1eadn b\u1ecb thu h\u1eb9p khi\u1ebfn tri\u1ec3n v\u1ecdng {name} tr\u1edf n\u00ean k\u00e9m r\u00f5 r\u00e0ng h\u01a1n. C\u00e1c chuy\u00ean gia khuy\u1ebfn ngh\u1ecb theo d\u00f5i th\u00eam tr\u01b0\u1edbc khi ra quy\u1ebft \u0111\u1ecbnh.", "Capia News", "nh\u1eadn \u0111\u1ecbnh", "negative", "2.2", "c-fina-4", true, agoISO_(21, 3), now],
      ["n-5", "NovaPay Holdings c\u00f4ng b\u1ed1 k\u1ebft qu\u1ea3 kinh doanh qu\u00fd v\u01b0\u1ee3t k\u1ef3 v\u1ecdng, c\u1ed5 phi\u1ebfu FINB t\u0103ng m\u1ea1nh phi\u00ean s\u00e1ng", "B\u00e1o c\u00e1o t\u00e0i ch\u00ednh m\u1edbi nh\u1ea5t c\u1ee7a {name} v\u01b0\u1ee3t d\u1ef1 b\u00e1o c\u1ee7a gi\u1edbi ph\u00e2n t\u00edch, \u0111\u1ea9y gi\u00e1 c\u1ed5 phi\u1ebfu {symbol} \u0111i l\u00ean trong phi\u00ean giao ", "B\u00e1o c\u00e1o t\u00e0i ch\u00ednh m\u1edbi nh\u1ea5t c\u1ee7a {name} v\u01b0\u1ee3t d\u1ef1 b\u00e1o c\u1ee7a gi\u1edbi ph\u00e2n t\u00edch, \u0111\u1ea9y gi\u00e1 c\u1ed5 phi\u1ebfu {symbol} \u0111i l\u00ean trong phi\u00ean giao d\u1ecbch \u0111\u1ea7u ng\u00e0y. Ban l\u00e3nh \u0111\u1ea1o cho bi\u1ebft s\u1ebd ti\u1ebfp t\u1ee5c \u0111\u1ea9y m\u1ea1nh m\u1ea3ng kinh doanh c\u1ed1t l\u00f5i.", "Capia News", "doanh nghi\u1ec7p", "positive", "2.5", "c-finb-5", true, agoISO_(28, 4), now],
      ["n-6", "SecureVault Insurance \u0111\u1ea9y nhanh k\u1ebf ho\u1ea1ch m\u1edf r\u1ed9ng th\u1ecb ph\u1ea7n trong qu\u00fd t\u1edbi", "Ban \u0111i\u1ec1u h\u00e0nh {name} c\u00f4ng b\u1ed1 chi\u1ebfn l\u01b0\u1ee3c m\u1edf r\u1ed9ng m\u1edbi, t\u1eadp trung v\u00e0o c\u00e1c th\u1ecb tr\u01b0\u1eddng ti\u1ec1m n\u0103ng. Nhi\u1ec1u nh\u00e0 \u0111\u1ea7u t\u01b0 k\u1ef3 v\u1ecdng \u0111\u1ed9", "Ban \u0111i\u1ec1u h\u00e0nh {name} c\u00f4ng b\u1ed1 chi\u1ebfn l\u01b0\u1ee3c m\u1edf r\u1ed9ng m\u1edbi, t\u1eadp trung v\u00e0o c\u00e1c th\u1ecb tr\u01b0\u1eddng ti\u1ec1m n\u0103ng. Nhi\u1ec1u nh\u00e0 \u0111\u1ea7u t\u01b0 k\u1ef3 v\u1ecdng \u0111\u1ed9ng th\u00e1i n\u00e0y s\u1ebd c\u1ea3i thi\u1ec7n doanh thu d\u00e0i h\u1ea1n.", "Capia News", "th\u1ecb tr\u01b0\u1eddng", "positive", "1.8", "c-finc-6", true, agoISO_(35, 5), now],
      ["n-7", "C\u1ed5 \u0111\u00f4ng BioGenix Therapeutics b\u0103n kho\u0103n tr\u01b0\u1edbc bi\u1ebfn \u0111\u1ed9ng ng\u1eafn h\u1ea1n c\u1ee7a c\u1ed5 phi\u1ebfu HEALA", "M\u1eb7c d\u00f9 n\u1ec1n t\u1ea3ng c\u01a1 b\u1ea3n \u1ed5n \u0111\u1ecbnh, c\u1ed5 phi\u1ebfu {symbol} c\u1ee7a {name} ghi nh\u1eadn nh\u1eefng phi\u00ean \u0111i\u1ec1u ch\u1ec9nh, khi\u1ebfn m\u1ed9t b\u1ed9 ph\u1eadn c\u1ed5 \u0111\u00f4ng ", "M\u1eb7c d\u00f9 n\u1ec1n t\u1ea3ng c\u01a1 b\u1ea3n \u1ed5n \u0111\u1ecbnh, c\u1ed5 phi\u1ebfu {symbol} c\u1ee7a {name} ghi nh\u1eadn nh\u1eefng phi\u00ean \u0111i\u1ec1u ch\u1ec9nh, khi\u1ebfn m\u1ed9t b\u1ed9 ph\u1eadn c\u1ed5 \u0111\u00f4ng th\u1eadn tr\u1ecdng tr\u01b0\u1edbc xu h\u01b0\u1edbng ng\u1eafn h\u1ea1n.", "Capia News", "ph\u00e2n t\u00edch", "neutral", "1.2", "c-heala-7", true, agoISO_(42, 6), now],
      ["n-8", "\u00c1p l\u1ef1c c\u1ea1nh tranh ng\u00e0y c\u00e0ng l\u1edbn v\u1edbi MedCore International, chuy\u00ean gia \u0111\u01b0a khuy\u1ebfn ngh\u1ecb th\u1eadn tr\u1ecdng", "S\u1ef1 xu\u1ea5t hi\u1ec7n c\u1ee7a nhi\u1ec1u \u0111\u1ed1i th\u1ee7 m\u1edbi c\u00f9ng bi\u00ean l\u1ee3i nhu\u1eadn b\u1ecb thu h\u1eb9p khi\u1ebfn tri\u1ec3n v\u1ecdng {name} tr\u1edf n\u00ean k\u00e9m r\u00f5 r\u00e0ng h\u01a1n. C\u00e1c c", "S\u1ef1 xu\u1ea5t hi\u1ec7n c\u1ee7a nhi\u1ec1u \u0111\u1ed1i th\u1ee7 m\u1edbi c\u00f9ng bi\u00ean l\u1ee3i nhu\u1eadn b\u1ecb thu h\u1eb9p khi\u1ebfn tri\u1ec3n v\u1ecdng {name} tr\u1edf n\u00ean k\u00e9m r\u00f5 r\u00e0ng h\u01a1n. C\u00e1c chuy\u00ean gia khuy\u1ebfn ngh\u1ecb theo d\u00f5i th\u00eam tr\u01b0\u1edbc khi ra quy\u1ebft \u0111\u1ecbnh.", "Capia News", "nh\u1eadn \u0111\u1ecbnh", "negative", "2.2", "c-healb-8", true, agoISO_(49, 7), now],
      ["n-9", "VitaCare Health c\u00f4ng b\u1ed1 k\u1ebft qu\u1ea3 kinh doanh qu\u00fd v\u01b0\u1ee3t k\u1ef3 v\u1ecdng, c\u1ed5 phi\u1ebfu HEALC t\u0103ng m\u1ea1nh phi\u00ean s\u00e1ng", "B\u00e1o c\u00e1o t\u00e0i ch\u00ednh m\u1edbi nh\u1ea5t c\u1ee7a {name} v\u01b0\u1ee3t d\u1ef1 b\u00e1o c\u1ee7a gi\u1edbi ph\u00e2n t\u00edch, \u0111\u1ea9y gi\u00e1 c\u1ed5 phi\u1ebfu {symbol} \u0111i l\u00ean trong phi\u00ean giao ", "B\u00e1o c\u00e1o t\u00e0i ch\u00ednh m\u1edbi nh\u1ea5t c\u1ee7a {name} v\u01b0\u1ee3t d\u1ef1 b\u00e1o c\u1ee7a gi\u1edbi ph\u00e2n t\u00edch, \u0111\u1ea9y gi\u00e1 c\u1ed5 phi\u1ebfu {symbol} \u0111i l\u00ean trong phi\u00ean giao d\u1ecbch \u0111\u1ea7u ng\u00e0y. Ban l\u00e3nh \u0111\u1ea1o cho bi\u1ebft s\u1ebd ti\u1ebfp t\u1ee5c \u0111\u1ea9y m\u1ea1nh m\u1ea3ng kinh doanh c\u1ed1t l\u00f5i.", "Capia News", "doanh nghi\u1ec7p", "positive", "2.5", "c-healc-9", true, agoISO_(56, 8), now],
      ["n-10", "GreenHydrogen Energy \u0111\u1ea9y nhanh k\u1ebf ho\u1ea1ch m\u1edf r\u1ed9ng th\u1ecb ph\u1ea7n trong qu\u00fd t\u1edbi", "Ban \u0111i\u1ec1u h\u00e0nh {name} c\u00f4ng b\u1ed1 chi\u1ebfn l\u01b0\u1ee3c m\u1edf r\u1ed9ng m\u1edbi, t\u1eadp trung v\u00e0o c\u00e1c th\u1ecb tr\u01b0\u1eddng ti\u1ec1m n\u0103ng. Nhi\u1ec1u nh\u00e0 \u0111\u1ea7u t\u01b0 k\u1ef3 v\u1ecdng \u0111\u1ed9", "Ban \u0111i\u1ec1u h\u00e0nh {name} c\u00f4ng b\u1ed1 chi\u1ebfn l\u01b0\u1ee3c m\u1edf r\u1ed9ng m\u1edbi, t\u1eadp trung v\u00e0o c\u00e1c th\u1ecb tr\u01b0\u1eddng ti\u1ec1m n\u0103ng. Nhi\u1ec1u nh\u00e0 \u0111\u1ea7u t\u01b0 k\u1ef3 v\u1ecdng \u0111\u1ed9ng th\u00e1i n\u00e0y s\u1ebd c\u1ea3i thi\u1ec7n doanh thu d\u00e0i h\u1ea1n.", "Capia News", "th\u1ecb tr\u01b0\u1eddng", "positive", "1.8", "c-energa-10", true, agoISO_(3, 9), now],
      ["n-11", "C\u1ed5 \u0111\u00f4ng Solaris Power Grid b\u0103n kho\u0103n tr\u01b0\u1edbc bi\u1ebfn \u0111\u1ed9ng ng\u1eafn h\u1ea1n c\u1ee7a c\u1ed5 phi\u1ebfu ENERGB", "M\u1eb7c d\u00f9 n\u1ec1n t\u1ea3ng c\u01a1 b\u1ea3n \u1ed5n \u0111\u1ecbnh, c\u1ed5 phi\u1ebfu {symbol} c\u1ee7a {name} ghi nh\u1eadn nh\u1eefng phi\u00ean \u0111i\u1ec1u ch\u1ec9nh, khi\u1ebfn m\u1ed9t b\u1ed9 ph\u1eadn c\u1ed5 \u0111\u00f4ng ", "M\u1eb7c d\u00f9 n\u1ec1n t\u1ea3ng c\u01a1 b\u1ea3n \u1ed5n \u0111\u1ecbnh, c\u1ed5 phi\u1ebfu {symbol} c\u1ee7a {name} ghi nh\u1eadn nh\u1eefng phi\u00ean \u0111i\u1ec1u ch\u1ec9nh, khi\u1ebfn m\u1ed9t b\u1ed9 ph\u1eadn c\u1ed5 \u0111\u00f4ng th\u1eadn tr\u1ecdng tr\u01b0\u1edbc xu h\u01b0\u1edbng ng\u1eafn h\u1ea1n.", "Capia News", "ph\u00e2n t\u00edch", "neutral", "1.2", "c-energb-11", true, agoISO_(10, 10), now],
      ["n-12", "\u00c1p l\u1ef1c c\u1ea1nh tranh ng\u00e0y c\u00e0ng l\u1edbn v\u1edbi TerraFuels Corp, chuy\u00ean gia \u0111\u01b0a khuy\u1ebfn ngh\u1ecb th\u1eadn tr\u1ecdng", "S\u1ef1 xu\u1ea5t hi\u1ec7n c\u1ee7a nhi\u1ec1u \u0111\u1ed1i th\u1ee7 m\u1edbi c\u00f9ng bi\u00ean l\u1ee3i nhu\u1eadn b\u1ecb thu h\u1eb9p khi\u1ebfn tri\u1ec3n v\u1ecdng {name} tr\u1edf n\u00ean k\u00e9m r\u00f5 r\u00e0ng h\u01a1n. C\u00e1c c", "S\u1ef1 xu\u1ea5t hi\u1ec7n c\u1ee7a nhi\u1ec1u \u0111\u1ed1i th\u1ee7 m\u1edbi c\u00f9ng bi\u00ean l\u1ee3i nhu\u1eadn b\u1ecb thu h\u1eb9p khi\u1ebfn tri\u1ec3n v\u1ecdng {name} tr\u1edf n\u00ean k\u00e9m r\u00f5 r\u00e0ng h\u01a1n. C\u00e1c chuy\u00ean gia khuy\u1ebfn ngh\u1ecb theo d\u00f5i th\u00eam tr\u01b0\u1edbc khi ra quy\u1ebft \u0111\u1ecbnh.", "Capia News", "nh\u1eadn \u0111\u1ecbnh", "negative", "2.2", "c-energc-12", true, agoISO_(17, 11), now],
      ["n-m1", "Th\u1ecb tr\u01b0\u1eddng giao d\u1ecbch t\u00edch c\u1ef1c nh\u1edd d\u00f2ng ti\u1ec1n lu\u00e2n chuy\u1ec3n", "Phi\u00ean giao d\u1ecbch ghi nh\u1eadn d\u00f2ng ti\u1ec1n \u0111\u1ed5 v\u00e0o c\u00e1c nh\u00f3m ng\u00e0nh ch\u1ee7 ch\u1ed1t, gi\u00fap ch\u1ec9 s\u1ed1 duy tr\u00ec \u0111\u00e0 t\u0103ng. Thanh kho\u1ea3n c\u1ea3i thi\u1ec7n so", "Phi\u00ean giao d\u1ecbch ghi nh\u1eadn d\u00f2ng ti\u1ec1n \u0111\u1ed5 v\u00e0o c\u00e1c nh\u00f3m ng\u00e0nh ch\u1ee7 ch\u1ed1t, gi\u00fap ch\u1ec9 s\u1ed1 duy tr\u00ec \u0111\u00e0 t\u0103ng. Thanh kho\u1ea3n c\u1ea3i thi\u1ec7n so v\u1edbi c\u00e1c phi\u00ean tr\u01b0\u1edbc \u0111\u00f3.", "Capia News", "v\u0129 m\u00f4", "positive", "1.5", null, true, agoISO_(1, 0), now],
      ["n-m2", "M\u1eb7t b\u1eb1ng l\u00e3i su\u1ea5t ti\u1ebfp t\u1ee5c \u1ed5n \u0111\u1ecbnh, h\u1ed7 tr\u1ee3 \u0111\u1ecbnh gi\u00e1 c\u1ed5 phi\u1ebfu", "L\u00e3i su\u1ea5t gi\u1eef \u1edf m\u1ee9c \u1ed5n \u0111\u1ecbnh gi\u00fap chi ph\u00ed v\u1ed1n doanh nghi\u1ec7p kh\u00f4ng \u0111\u1ed5i, qua \u0111\u00f3 h\u1ed7 tr\u1ee3 m\u1eb7t b\u1eb1ng \u0111\u1ecbnh gi\u00e1 tr\u00ean th\u1ecb tr\u01b0\u1eddng ch\u1ee9n", "L\u00e3i su\u1ea5t gi\u1eef \u1edf m\u1ee9c \u1ed5n \u0111\u1ecbnh gi\u00fap chi ph\u00ed v\u1ed1n doanh nghi\u1ec7p kh\u00f4ng \u0111\u1ed5i, qua \u0111\u00f3 h\u1ed7 tr\u1ee3 m\u1eb7t b\u1eb1ng \u0111\u1ecbnh gi\u00e1 tr\u00ean th\u1ecb tr\u01b0\u1eddng ch\u1ee9ng kho\u00e1n.", "Capia News", "v\u0129 m\u00f4", "neutral", "1", null, true, agoISO_(1, 45), now],
      ["n-m3", "Nh\u00e0 \u0111\u1ea7u t\u01b0 th\u1eadn tr\u1ecdng ch\u1edd th\u00eam t\u00edn hi\u1ec7u v\u0129 m\u00f4 r\u00f5 r\u00e0ng", "Kh\u1ed1i l\u01b0\u1ee3ng giao d\u1ecbch s\u1ee5t gi\u1ea3m khi nh\u00e0 \u0111\u1ea7u t\u01b0 \u0111\u1ee9ng ngo\u00e0i quan s\u00e1t, ch\u1edd th\u00eam d\u1eef li\u1ec7u kinh t\u1ebf tr\u01b0\u1edbc khi gi\u1ea3i ng\u00e2n tr\u1edf l\u1ea1i.", "Kh\u1ed1i l\u01b0\u1ee3ng giao d\u1ecbch s\u1ee5t gi\u1ea3m khi nh\u00e0 \u0111\u1ea7u t\u01b0 \u0111\u1ee9ng ngo\u00e0i quan s\u00e1t, ch\u1edd th\u00eam d\u1eef li\u1ec7u kinh t\u1ebf tr\u01b0\u1edbc khi gi\u1ea3i ng\u00e2n tr\u1edf l\u1ea1i.", "Capia News", "v\u0129 m\u00f4", "negative", "1.3", null, true, agoISO_(1, 90), now]
    ];
    for (var i = 0; i < nRows.length; i++) news.appendRow(nRows[i]);
  }

  var users = getSheet_('users');
  if (users.getLastRow() <= 1) {
    var uHeaders = ['id', 'email', 'username', 'display_name', 'avatar_url', 'role', 'cash_balance', 'frozen_cash', 'risk_score', 'cooldown_until', 'is_active', 'created_at', 'password'];
    users.getRange(1, 1, 1, uHeaders.length).setValues([uHeaders]);
    var uRows = [
      ['u-demo', 'demo@finsim.ai', 'demo', 'Nh\u00e0 \u0111\u1ea7u t\u01b0 demo', null, 'user', '100000000', '0', 50, null, true, now, 'demo123'],
      ['u-admin', 'admin@finsim.ai', 'admin', 'Qu\u1ea3n tr\u1ecb vi\u00ean', null, 'admin', '100000000', '0', 50, null, true, now, 'admin123'],
      ['u-host-1', 'host@finsim.ai', 'host', 'Ban t\u1ed5 ch\u1ee9c', null, 'host', '100000000', '0', 50, null, true, now, 'host123']
    ];
    for (var i = 0; i < uRows.length; i++) users.appendRow(uRows[i]);
  }

  var social = getSheet_('social');
  if (social.getLastRow() <= 1) {
    var soHeaders = ['id', 'author_name', 'author_avatar', 'persona_type', 'content', 'sentiment', 'virality_score', 'likes_count', 'shares_count', 'comments_count', 'company_id', 'news_id', 'simulated_at', 'created_at'];
    social.getRange(1, 1, 1, soHeaders.length).setValues([soHeaders]);
    // Nguon du lieu: su dung lai generator social cua he thong cu (seed_db.py _social_rows)
    var soRows = [
      ["s-1", "F0 m\u1edbi t\u1eadp t\u00e0nh \u0111\u1ea7u t\u01b0", null, "f0_newbie", "M\u00ecnh m\u1edbi mua th\u00eam TECHA h\u00f4m nay, th\u1ea5y ti\u1ec1m n\u0103ng d\u00e0i h\u1ea1n r\u00f5 r\u00e0ng! Ai c\u00f9ng quan \u0111i\u1ec3m kh\u00f4ng?", "positive", "1.1", "20", "3", "1", "c-techa-1", null, agoISO_(0, 0), now],
      ["s-2", "Nh\u00e0 \u0111\u1ea7u t\u01b0 c\u00e1 nh\u00e2n gi\u00e0u kinh nghi\u1ec7m", null, "pro_trader", "Nh\u00ecn \u0111\u1ed3 th\u1ecb TECHB m\u00e0 ph\u00e1t ho\u1ea3ng, ng\u1eafn h\u1ea1n ch\u01b0a n\u00ean \u00f4m. Ki\u00ean nh\u1eabn ch\u1edd \u0111i\u1ec3m v\u00e0o t\u1ed1t h\u01a1n.", "negative", "1.3", "57", "16", "2", "c-techb-2", null, agoISO_(1, 17), now],
      ["s-3", "Chuy\u00ean gia ph\u00e2n t\u00edch k\u1ef9 thu\u1eadt", null, "ta_fa_kol", "C\u00f3 ai \u0111\u1ec3 \u00fd TECHC c\u1ee7a QuantumByte Labs kh\u00f4ng? Thanh kho\u1ea3n h\u00f4m nay t\u0103ng b\u1ea5t th\u01b0\u1eddng, c\u1ea9n th\u1eadn nh\u00e9.", "negative", "1.8", "94", "29", "4", "c-techc-3", null, agoISO_(2, 34), now],
      ["s-4", "Tin \u0111\u1ed3n t\u1eeb c\u1ed9ng \u0111\u1ed3ng", null, "rumor_birds", "BlueRock Financial v\u1ec1 c\u01a1 b\u1ea3n v\u1eabn t\u1ed1t, m\u00ecnh gi\u1eef quan \u0111i\u1ec3m t\u00edch l\u0169y d\u1ea7n FINA m\u1ed7i tu\u1ea7n.", "positive", "1", "131", "42", "6", "c-fina-4", null, agoISO_(3, 51), now],
      ["s-5", "C\u00f2 m\u1ed3i c\u1ea3m x\u00fac", null, "meme_entertain", "T\u00f4i ngh\u0129 gi\u00e1 FINB s\u1ebd sideway v\u00e0i tu\u1ea7n t\u1edbi tr\u01b0\u1edbc khi c\u00f3 t\u00edn hi\u1ec7u r\u00f5 r\u00e0ng. C\u00e1 nh\u00e2n \u0111\u1ee9ng ngo\u00e0i.", "neutral", "0.8", "168", "15", "8", "c-finb-5", null, agoISO_(4, 8), now],
      ["s-6", "F0 m\u1edbi t\u1eadp t\u00e0nh \u0111\u1ea7u t\u01b0", null, "f0_newbie", "M\u00ecnh m\u1edbi mua th\u00eam FINC h\u00f4m nay, th\u1ea5y ti\u1ec1m n\u0103ng d\u00e0i h\u1ea1n r\u00f5 r\u00e0ng! Ai c\u00f9ng quan \u0111i\u1ec3m kh\u00f4ng?", "positive", "1.1", "205", "28", "10", "c-finc-6", null, agoISO_(5, 25), now],
      ["s-7", "Nh\u00e0 \u0111\u1ea7u t\u01b0 c\u00e1 nh\u00e2n gi\u00e0u kinh nghi\u1ec7m", null, "pro_trader", "Nh\u00ecn \u0111\u1ed3 th\u1ecb HEALA m\u00e0 ph\u00e1t ho\u1ea3ng, ng\u1eafn h\u1ea1n ch\u01b0a n\u00ean \u00f4m. Ki\u00ean nh\u1eabn ch\u1edd \u0111i\u1ec3m v\u00e0o t\u1ed1t h\u01a1n.", "negative", "1.3", "242", "41", "12", "c-heala-7", null, agoISO_(6, 42), now],
      ["s-8", "Chuy\u00ean gia ph\u00e2n t\u00edch k\u1ef9 thu\u1eadt", null, "ta_fa_kol", "C\u00f3 ai \u0111\u1ec3 \u00fd HEALB c\u1ee7a MedCore International kh\u00f4ng? Thanh kho\u1ea3n h\u00f4m nay t\u0103ng b\u1ea5t th\u01b0\u1eddng, c\u1ea9n th\u1eadn nh\u00e9.", "negative", "1.8", "279", "14", "13", "c-healb-8", null, agoISO_(7, 59), now],
      ["s-9", "Tin \u0111\u1ed3n t\u1eeb c\u1ed9ng \u0111\u1ed3ng", null, "rumor_birds", "VitaCare Health v\u1ec1 c\u01a1 b\u1ea3n v\u1eabn t\u1ed1t, m\u00ecnh gi\u1eef quan \u0111i\u1ec3m t\u00edch l\u0169y d\u1ea7n HEALC m\u1ed7i tu\u1ea7n.", "positive", "1", "316", "27", "15", "c-healc-9", null, agoISO_(8, 16), now],
      ["s-10", "C\u00f2 m\u1ed3i c\u1ea3m x\u00fac", null, "meme_entertain", "T\u00f4i ngh\u0129 gi\u00e1 ENERGA s\u1ebd sideway v\u00e0i tu\u1ea7n t\u1edbi tr\u01b0\u1edbc khi c\u00f3 t\u00edn hi\u1ec7u r\u00f5 r\u00e0ng. C\u00e1 nh\u00e2n \u0111\u1ee9ng ngo\u00e0i.", "neutral", "0.8", "53", "40", "2", "c-energa-10", null, agoISO_(9, 33), now],
      ["s-11", "F0 m\u1edbi t\u1eadp t\u00e0nh \u0111\u1ea7u t\u01b0", null, "f0_newbie", "M\u00ecnh m\u1edbi mua th\u00eam ENERGB h\u00f4m nay, th\u1ea5y ti\u1ec1m n\u0103ng d\u00e0i h\u1ea1n r\u00f5 r\u00e0ng! Ai c\u00f9ng quan \u0111i\u1ec3m kh\u00f4ng?", "positive", "1.1", "90", "13", "4", "c-energb-11", null, agoISO_(10, 50), now],
      ["s-12", "Nh\u00e0 \u0111\u1ea7u t\u01b0 c\u00e1 nh\u00e2n gi\u00e0u kinh nghi\u1ec7m", null, "pro_trader", "Nh\u00ecn \u0111\u1ed3 th\u1ecb ENERGC m\u00e0 ph\u00e1t ho\u1ea3ng, ng\u1eafn h\u1ea1n ch\u01b0a n\u00ean \u00f4m. Ki\u00ean nh\u1eabn ch\u1edd \u0111i\u1ec3m v\u00e0o t\u1ed1t h\u01a1n.", "negative", "1.3", "127", "26", "6", "c-energc-12", null, agoISO_(11, 7), now],
      ["s-13", "Chuy\u00ean gia ph\u00e2n t\u00edch k\u1ef9 thu\u1eadt", null, "ta_fa_kol", "C\u00f3 ai \u0111\u1ec3 \u00fd CONSMA c\u1ee7a Premier Brands Group kh\u00f4ng? Thanh kho\u1ea3n h\u00f4m nay t\u0103ng b\u1ea5t th\u01b0\u1eddng, c\u1ea9n th\u1eadn nh\u00e9.", "negative", "1.8", "164", "39", "8", "c-consma-13", null, agoISO_(12, 24), now],
      ["s-14", "Tin \u0111\u1ed3n t\u1eeb c\u1ed9ng \u0111\u1ed3ng", null, "rumor_birds", "EcoLiving Products v\u1ec1 c\u01a1 b\u1ea3n v\u1eabn t\u1ed1t, m\u00ecnh gi\u1eef quan \u0111i\u1ec3m t\u00edch l\u0169y d\u1ea7n CONSMB m\u1ed7i tu\u1ea7n.", "positive", "1", "201", "12", "10", "c-consmb-14", null, agoISO_(13, 41), now]
    ];
    for (var i = 0; i < soRows.length; i++) social.appendRow(soRows[i]);
  }

  var tasks = getSheet_('tasks');
  if (tasks.getLastRow() <= 1) {
    var tHeaders = ['id', 'code', 'name', 'description', 'category', 'reward_amount', 'target_count', 'reset_frequency', 'is_active', 'sort_order', 'created_at', 'updated_at'];
    tasks.getRange(1, 1, 1, tHeaders.length).setValues([tHeaders]);
    // Nguon du lieu: su dung lai danh sach nhiem vu cua he thong cu (seed_db.py _TASKS)
    var tRows = [
      ["t-1", "profile_complete", "Ho\u00e0n thi\u1ec7n h\u1ed3 s\u01a1 c\u00e1 nh\u00e2n", "C\u1eadp nh\u1eadt \u0111\u1ea7y \u0111\u1ee7 th\u00f4ng tin h\u1ed3 s\u01a1 \u0111\u1ec3 b\u1eaft \u0111\u1ea7u h\u00e0nh tr\u00ecnh \u0111\u1ea7u t\u01b0.", "onboarding", "500000", "1", "none", true, "100", now, now],
      ["t-2", "first_trade", "\u0110\u1eb7t l\u1ec7nh giao d\u1ecbch \u0111\u1ea7u ti\u00ean", "\u0110\u1eb7t th\u00e0nh c\u00f4ng l\u1ec7nh mua ho\u1eb7c b\u00e1n \u0111\u1ea7u ti\u00ean c\u1ee7a b\u1ea1n.", "onboarding", "200000", "1", "none", true, "110", now, now],
      ["t-3", "first_knowledge_read", "\u0110\u1ecdc b\u00e0i ki\u1ebfn th\u1ee9c \u0111\u1ea7u ti\u00ean", "Kh\u00e1m ph\u00e1 kho ki\u1ebfn th\u1ee9c ch\u1ee9ng kho\u00e1n c\u1ee7a Capia.", "onboarding", "100000", "1", "none", true, "120", now, now],
      ["t-4", "first_news_read", "\u0110\u1ecdc tin t\u1ee9c \u0111\u1ea7u ti\u00ean", "C\u1eadp nh\u1eadt tin t\u1ee9c th\u1ecb tr\u01b0\u1eddng m\u1edbi nh\u1ea5t trong ng\u00e0y.", "onboarding", "100000", "1", "none", true, "130", now, now],
      ["t-5", "first_company_view", "Xem h\u1ed3 s\u01a1 c\u00f4ng ty \u0111\u1ea7u ti\u00ean", "T\u00ecm hi\u1ec3u th\u00f4ng tin m\u1ed9t doanh nghi\u1ec7p ni\u00eam y\u1ebft.", "onboarding", "100000", "1", "none", true, "140", now, now],
      ["t-6", "first_mentor_chat", "Tr\u00f2 chuy\u1ec7n Mentor l\u1ea7n \u0111\u1ea7u", "\u0110\u1eb7t c\u00e2u h\u1ecfi \u0111\u1ea7u ti\u00ean cho Mentor AI c\u1ee7a b\u1ea1n.", "onboarding", "200000", "1", "none", true, "150", now, now],
      ["t-7", "scenario_1_done", "Ho\u00e0n th\u00e0nh k\u1ecbch b\u1ea3n \u0111\u1ea7u ti\u00ean", "V\u01b0\u1ee3t qua k\u1ecbch b\u1ea3n m\u00f4 ph\u1ecfng \u0111\u1ea7u ti\u00ean trong ch\u1ebf \u0111\u1ed9 luy\u1ec7n t\u1eadp.", "onboarding", "300000", "1", "none", true, "160", now, now],
      ["t-8", "onboarding_complete", "Ho\u00e0n t\u1ea5t \u0111\u1ecbnh h\u01b0\u1edbng", "Ho\u00e0n th\u00e0nh T\u1ea4T C\u1ea2 nhi\u1ec7m v\u1ee5 \u0111\u1ecbnh h\u01b0\u1edbng \u0111\u1ec3 nh\u1eadn th\u01b0\u1edfng l\u1edbn.", "onboarding", "1000000", "1", "none", true, "190", now, now],
      ["t-9", "read_5_knowledge", "\u0110\u1ecdc 5 b\u00e0i ki\u1ebfn th\u1ee9c", "T\u00edch l\u0169y 5 b\u00e0i ki\u1ebfn th\u1ee9c \u0111\u00e3 \u0111\u1ecdc (c\u1ed9ng d\u1ed3n).", "learning", "300000", "5", "none", true, "200", now, now],
      ["t-10", "read_10_knowledge", "\u0110\u1ecdc 10 b\u00e0i ki\u1ebfn th\u1ee9c", "T\u00edch l\u0169y 10 b\u00e0i ki\u1ebfn th\u1ee9c \u0111\u00e3 \u0111\u1ecdc (c\u1ed9ng d\u1ed3n).", "learning", "500000", "10", "none", true, "210", now, now],
      ["t-11", "read_10_news", "\u0110\u1ecdc 10 tin t\u1ee9c", "C\u1eadp nh\u1eadt 10 tin t\u1ee9c th\u1ecb tr\u01b0\u1eddng (c\u1ed9ng d\u1ed3n).", "learning", "400000", "10", "none", true, "220", now, now],
      ["t-12", "analyze_3_companies", "Ph\u00e2n t\u00edch 3 c\u00f4ng ty", "Xem h\u1ed3 s\u01a1 chi ti\u1ebft c\u1ee7a 3 doanh nghi\u1ec7p (c\u1ed9ng d\u1ed3n).", "learning", "300000", "3", "none", true, "230", now, now],
      ["t-13", "mentor_3_chats", "Tr\u00f2 chuy\u1ec7n Mentor 3 l\u1ea7n", "Trao \u0111\u1ed5i 3 l\u01b0\u1ee3t v\u1edbi Mentor AI (c\u1ed9ng d\u1ed3n).", "learning", "400000", "3", "none", true, "240", now, now],
      ["t-14", "daily_checkin", "\u0110i\u1ec3m danh h\u1eb1ng ng\u00e0y", "\u0110\u0103ng nh\u1eadp v\u00e0 \u0111i\u1ec3m danh m\u1ed7i ng\u00e0y \u0111\u1ec3 gi\u1eef chu\u1ed7i ng\u00e0y li\u00ean ti\u1ebfp.", "daily", "50000", "1", "daily", true, "300", now, now],
      ["t-15", "daily_trade_1", "Giao d\u1ecbch trong ng\u00e0y", "\u0110\u1eb7t \u00edt nh\u1ea5t 1 l\u1ec7nh giao d\u1ecbch trong ng\u00e0y h\u00f4m nay.", "daily", "100000", "1", "daily", true, "310", now, now],
      ["t-16", "daily_read_3_knowledge", "\u0110\u1ecdc 3 b\u00e0i ki\u1ebfn th\u1ee9c trong ng\u00e0y", "\u0110\u1ecdc 3 b\u00e0i ki\u1ebfn th\u1ee9c trong ng\u00e0y h\u00f4m nay.", "daily", "100000", "3", "daily", true, "320", now, now],
      ["t-17", "daily_read_2_news", "\u0110\u1ecdc 2 tin t\u1ee9c trong ng\u00e0y", "\u0110\u1ecdc 2 tin t\u1ee9c trong ng\u00e0y h\u00f4m nay.", "daily", "100000", "2", "daily", true, "330", now, now],
      ["t-18", "daily_mentor_1", "Tr\u00f2 chuy\u1ec7n Mentor trong ng\u00e0y", "Tr\u00f2 chuy\u1ec7n v\u1edbi Mentor \u00edt nh\u1ea5t 1 l\u1ea7n trong ng\u00e0y.", "daily", "100000", "1", "daily", true, "340", now, now],
      ["t-19", "daily_all_4", "Ho\u00e0n th\u00e0nh 4/5 nhi\u1ec7m v\u1ee5 h\u1eb1ng ng\u00e0y", "Ho\u00e0n th\u00e0nh 4 trong 5 nhi\u1ec7m v\u1ee5 h\u1eb1ng ng\u00e0y \u0111\u1ec3 nh\u1eadn th\u01b0\u1edfng l\u1edbn.", "daily", "500000", "1", "daily", true, "390", now, now],
      ["t-20", "streak_3", "Chu\u1ed7i 3 ng\u00e0y li\u00ean ti\u1ebfp", "Duy tr\u00ec chu\u1ed7i \u0111i\u1ec3m danh 3 ng\u00e0y li\u00ean ti\u1ebfp.", "streak", "200000", "3", "none", true, "400", now, now],
      ["t-21", "streak_7", "Chu\u1ed7i 7 ng\u00e0y li\u00ean ti\u1ebfp", "Duy tr\u00ec chu\u1ed7i \u0111i\u1ec3m danh 7 ng\u00e0y li\u00ean ti\u1ebfp.", "streak", "500000", "7", "none", true, "410", now, now],
      ["t-22", "streak_30", "Chu\u1ed7i 30 ng\u00e0y li\u00ean ti\u1ebfp", "Duy tr\u00ec chu\u1ed7i \u0111i\u1ec3m danh 30 ng\u00e0y li\u00ean ti\u1ebfp.", "streak", "2000000", "30", "none", true, "420", now, now],
      ["t-23", "contest_join_1", "Tham gia cu\u1ed9c thi \u0111\u1ea7u ti\u00ean", "Gia nh\u1eadp m\u1ed9t cu\u1ed9c thi \u0111\u1ea7u t\u01b0 \u1ea3o \u0111\u1ec3 c\u1ea1nh tranh th\u1ee9 h\u1ea1ng.", "contest", "200000", "1", "none", true, "500", now, now],
      ["t-24", "contest_top10", "L\u1ecdt top 10 cu\u1ed9c thi", "\u0110\u1ee9ng trong top 10 b\u1ea3ng x\u1ebfp h\u1ea1ng m\u1ed9t cu\u1ed9c thi \u2014 nh\u1eadn th\u01b0\u1edfng th\u1ee7 c\u00f4ng.", "contest", "2000000", "1", "none", true, "510", now, now]
    ];
    for (var i = 0; i < tRows.length; i++) tasks.appendRow(tRows[i]);
  }

  // Portfolio demo - demo user holds some stocks
  var portfolio = getSheet_('portfolio');
  if (portfolio.getLastRow() <= 1) {
    var pHeaders = ['user_id', 'company_id', 'symbol', 'company_name', 'quantity', 'average_buy_price', 'current_price', 'market_value', 'unrealized_pnl', 'frozen_quantity'];
    portfolio.getRange(1, 1, 1, pHeaders.length).setValues([pHeaders]);
    // Nguon du lieu: danh muc demo duoc tai tao tu he thong cu (seed_db.py portfolio)
    var pRows = [
      ["u-demo", "c-techa-1", "TECHA", "TechVision Corp", "20", "150", "156.8", "3136", "136"],
      ["u-demo", "c-fina-4", "FINA", "BlueRock Financial", "100", "43", "45.6", "4560", "260"],
      ["u-demo", "c-heala-7", "HEALA", "BioGenix Therapeutics", "30", "140", "128.9", "3867", "-333"],
      ["u-demo", "c-energb-11", "ENERGB", "Solaris Power Grid", "120", "39", "41.2", "4944", "264"],
      ["u-demo", "c-consma-13", "CONSMA", "Premier Brands Group", "80", "61", "63.5", "5080", "200"]
    ];
    for (var i = 0; i < pRows.length; i++) portfolio.appendRow(pRows[i]);
  }

  // Orders demo (filled/pending)
  var orders = getSheet_('orders');
  if (orders.getLastRow() <= 1) {
    var oHeaders = ['id', 'user_id', 'company_id', 'side', 'type', 'status', 'price', 'quantity', 'filled_quantity', 'frozen_cash', 'frozen_quantity', 'created_at'];
    orders.getRange(1, 1, 1, oHeaders.length).setValues([oHeaders]);
    // start empty; demo creates orders
  }

  // Cho DB đã seed từ trước: đảm bảo các cột mới tồn tại (idempotent).
  _ensureColumn_(getSheet_('portfolio'), 'frozen_quantity');
  _ensureColumn_(getSheet_('orders'), 'frozen_cash');
  _ensureColumn_(getSheet_('orders'), 'frozen_quantity');

  var contests = getSheet_('contests');
  if (contests.getLastRow() <= 1) {
    var ccHeaders = ['id', 'slug', 'name', 'description', 'status', 'config', 'owner_id', 'starts_at', 'ends_at', 'is_active', 'created_at', 'updated_at', 'member_count'];
    contests.getRange(1, 1, 1, ccHeaders.length).setValues([ccHeaders]);
    var now2 = new Date();
    var startAt = new Date(now2.getTime() - 86400000).toISOString();
    var endAt = new Date(now2.getTime() + 6 * 86400000).toISOString();
    var ccRows = [
      ['co-1', 'vn30-challenge', 'Th\u1eed th\u00e1ch VN30', 'Giao d\u1ecbch c\u1ed5 phi\u1ebfu tr\u1ee5 c\u1ed9t v\u00e0 t\u0103ng tr\u01b0\u1edfng NAV.', 'active', JSON.stringify({ template: 'classic', industry: 'vn30', difficulty: 'normal', company_count: 6, rules: { start_cash: '100000000' } }), 'u-host-1', startAt, endAt, true, now, now, 1]
    ];
    for (var i = 0; i < ccRows.length; i++) contests.appendRow(ccRows[i]);
  }

  var knowledge = getSheet_('knowledge');
  if (knowledge.getLastRow() <= 1) {
    var kHeaders = ['id', 'keyword', 'concept', 'definition', 'category', 'difficulty', 'related_keywords', 'created_at'];
    knowledge.getRange(1, 1, 1, kHeaders.length).setValues([kHeaders]);
    // Nguon du lieu: packages/database/seeds/knowledge_base.yaml (he thong cu)
    var kRows = [
      ["k-1", "P/E ratio", "Price-to-Earnings Ratio", "A valuation ratio calculated by dividing the current stock price by its earnings per share (EPS). A high P/E may indicate overvaluation or high growth expectations; a low P/E may suggest undervaluation or low growth.", "fundamental_analysis", "1", "[\"EPS\",\"valuation\",\"earnings\"]", now],
      ["k-2", "market cap", "Market Capitalization", "The total market value of a company's outstanding shares, calculated as share price \u00d7 total shares outstanding. Companies are classified as Large-cap (>$10B), Mid-cap ($2B-$10B), or Small-cap (<$2B).", "fundamental_analysis", "1", "[\"large-cap\",\"mid-cap\",\"small-cap\",\"valuation\"]", now],
      ["k-3", "dividend", "Dividend", "A portion of a company's earnings distributed to shareholders, typically paid quarterly. Dividend yield is calculated as annual dividend \u00f7 share price.", "fundamental_analysis", "1", "[\"dividend yield\",\"payout ratio\",\"income investing\"]", now],
      ["k-4", "bull market", "Bull Market", "A period of rising asset prices, typically defined as a 20% increase from recent lows. Characterized by investor optimism, strong economic conditions, and increased buying activity.", "market_psychology", "1", "[\"bear market\",\"rally\",\"uptrend\"]", now],
      ["k-5", "bear market", "Bear Market", "A period of declining asset prices, typically defined as a 20% drop from recent highs. Associated with pessimism, economic slowdown, and selling pressure.", "market_psychology", "1", "[\"bull market\",\"downtrend\",\"correction\"]", now],
      ["k-6", "volatility", "Volatility", "A statistical measure of price dispersion over time. High volatility means large price swings; low volatility means stable prices. Commonly measured by standard deviation or the VIX index.", "risk_management", "2", "[\"standard deviation\",\"beta\",\"VIX\",\"risk\"]", now],
      ["k-7", "diversification", "Diversification", "A risk management strategy of spreading investments across different assets, sectors, or geographies to reduce exposure to any single risk factor.", "risk_management", "1", "[\"portfolio\",\"asset allocation\",\"correlation\"]", now],
      ["k-8", "margin call", "Margin Call", "A broker's demand that an investor deposits additional funds or securities when the equity in a margin account falls below the maintenance requirement. Failure to meet a margin call may result in forced liquidation.", "risk_management", "3", "[\"leverage\",\"margin trading\",\"liquidation\"]", now],
      ["k-9", "FOMO", "Fear Of Missing Out", "An emotional bias where investors rush to buy an asset after seeing rapid price increases, often buying at the peak. FOMO-driven trading typically results in poor entry points and increased risk.", "behavioral_finance", "2", "[\"herd mentality\",\"emotional trading\",\"greed\"]", now],
      ["k-10", "herd mentality", "Herd Mentality / B\u1ea7y \u0111\u00e0n", "The tendency of investors to follow the actions of a larger group rather than their own analysis. Herd behavior can amplify price movements and lead to asset bubbles or panic selling.", "behavioral_finance", "2", "[\"FOMO\",\"bubble\",\"panic selling\",\"groupthink\"]", now],
      ["k-11", "support level", "Support Level", "A price level where an asset tends to stop falling and may bounce higher. Support levels form when buyers historically step in at that price point.", "technical_analysis", "2", "[\"resistance level\",\"floor\",\"bounce\"]", now],
      ["k-12", "resistance level", "Resistance Level", "A price level where an asset tends to stop rising and may reverse downward. Resistance occurs when sellers historically outweigh buyers at that price.", "technical_analysis", "2", "[\"support level\",\"ceiling\",\"breakout\"]", now],
      ["k-13", "moving average", "Moving Average (MA)", "A lagging indicator that smooths price data by calculating the average price over a specified period. Common periods: 50-day MA, 200-day MA. Crossovers may signal trend changes.", "technical_analysis", "2", "[\"SMA\",\"EMA\",\"golden cross\",\"death cross\"]", now],
      ["k-14", "Sharpe ratio", "Sharpe Ratio", "A risk-adjusted return metric calculated as (portfolio return - risk-free rate) \u00f7 standard deviation of returns. Higher Sharpe ratios indicate better risk-adjusted performance.", "risk_management", "3", "[\"risk-adjusted return\",\"standard deviation\",\"alpha\"]", now],
      ["k-15", "liquidity", "Liquidity", "The ease with which an asset can be bought or sold without significantly affecting its price. Cash is the most liquid asset; real estate is less liquid. Low liquidity increases transaction costs and slippage.", "market_basics", "1", "[\"spread\",\"slippage\",\"trading volume\"]", now],
      ["k-16", "short selling", "Short Selling", "The practice of selling borrowed shares with the expectation of buying them back at a lower price. Short selling profits from price declines but carries unlimited theoretical risk.", "trading_strategies", "3", "[\"short squeeze\",\"cover\",\"margin\"]", now],
      ["k-17", "stop loss", "Stop-Loss Order", "A risk management order that automatically sells a security when it reaches a specified price. Stop-loss limits potential losses but does not guarantee the execution price in fast-moving markets.", "trading_strategies", "1", "[\"limit order\",\"market order\",\"risk management\"]", now],
      ["k-18", "RSI", "Relative Strength Index", "A momentum oscillator measuring the speed and magnitude of recent price changes on a scale of 0-100. RSI above 70 indicates overbought; below 30 indicates oversold conditions.", "technical_analysis", "2", "[\"overbought\",\"oversold\",\"momentum\",\"divergence\"]", now],
      ["k-19", "GDP", "Gross Domestic Product", "The total monetary value of all finished goods and services produced within a country's borders in a specific period. GDP growth rate is a key indicator of economic health.", "macroeconomics", "2", "[\"economic growth\",\"recession\",\"inflation\"]", now],
      ["k-20", "inflation", "Inflation", "The rate at which the general level of prices for goods and services is rising, eroding purchasing power. Central banks target ~2% inflation. High inflation often leads to tighter monetary policy.", "macroeconomics", "2", "[\"CPI\",\"interest rate\",\"purchasing power\"]", now],
      ["k-21", "cooldown", "Cooldown Penalty", "A disciplinary mechanism in Capia where reckless trading behavior triggers a temporary trading suspension. During cooldown, users can still access the Socratic Mentor for learning but cannot execute trades.", "finsimai_mechanics", "1", "[\"penalty\",\"risk_score\",\"discipline\"]", now],
      ["k-22", "virality", "Social Media Virality", "A measure of how rapidly and widely a social media post spreads. In Capia, high-virality posts can temporarily impact stock prices. Some viral posts may be traps designed to mislead traders.", "finsimai_mechanics", "2", "[\"social agent\",\"trap\",\"sentiment\",\"impact model\"]", now],
      ["k-23", "time compression", "Time Compression", "The core simulation mechanic where 1 real minute equals N virtual days. Capia uses time compression to simulate weeks and months of market activity in a single gaming session.", "finsimai_mechanics", "2", "[\"simulation\",\"market cycle\",\"compressor\"]", now]
    ];
for (var i = 0; i < kRows.length; i++) knowledge.appendRow(kRows[i]);
  }

  // Augment: bổ sung tin/bài mới + nội dung dài hơn cho các DB đã seed từ trước.
  augmentNewsSeed_();
  augmentSocialSeed_();

  // Đồng bộ mức thưởng mới theo code (idempotent) cho DB đã seed từ trước.
  patchTaskRewards_();
}

/**
 * Đồng bộ reward_amount theo code (idempotent) — parity với _seed_tasks
 * (ON CONFLICT DO UPDATE) của FastAPI, để DB đã seed trước đó được cập nhật
 * mức thưởng sau khi deploy mà không cần reset dữ liệu. Chạy mỗi request
 * nhưng chỉ ghi cell khi giá trị khác biệt.
 */
function patchTaskRewards_() {
  var sheet = getSheet_('tasks');
  var headers = getHeaders_(sheet);
  var codeIdx = headers.indexOf('code');
  var rewardIdx = headers.indexOf('reward_amount');
  if (codeIdx < 0 || rewardIdx < 0) return;
  var values = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  var map = {
    profile_complete: '500000', first_trade: '200000', first_knowledge_read: '100000',
    first_news_read: '100000', first_company_view: '100000', first_mentor_chat: '200000',
    scenario_1_done: '300000', onboarding_complete: '1000000', read_5_knowledge: '300000',
    read_10_knowledge: '500000', read_10_news: '400000', analyze_3_companies: '300000',
    mentor_3_chats: '400000', daily_checkin: '50000', daily_trade_1: '100000',
    daily_read_3_knowledge: '100000', daily_read_2_news: '100000', daily_mentor_1: '100000',
    daily_all_4: '500000', streak_3: '200000', streak_7: '500000', streak_30: '2000000',
    contest_join_1: '200000', contest_top10: '2000000'
  };
  for (var r = 0; r < values.length; r++) {
    var code = String(values[r][codeIdx]);
    if (map[code] !== undefined && String(values[r][rewardIdx]) !== map[code]) {
      sheet.getRange(r + 2, rewardIdx + 1).setValue(map[code]);
    }
  }
}

/**
 * Bổ sung thêm tin tức (idempotent): nếu số tin < ngưỡng và thiếu các id mới
 * thì chèn thêm các bài dài hơn. Chạy mỗi request nhưng vô hại (kiểm tra nhanh).
 */
function augmentNewsSeed_() {
  var news = getSheet_('news');
  var existing = readAll_(news);
  var have = {};
  existing.forEach(function (n) { have[n.id] = true; });
  var now = isoNow();

  // Mỗi phần tử: [id, title, summary, content, category, sentiment, impact, company_id, agoH, agoM]
  var extraRows = [
    ["n-x1", "Kim c\u01b0\u01a1ng ng\u00e0nh b\u00e1n l\u1ebb d\u1ea7n d\u1ea7n tr\u1ed9i d\u1eady", "S\u1ee9c mua n\u1ed9i \u0111\u1ecba h\u1ed3i ph\u1ee5c r\u00f5 n\u00e9t k\u00e9o theo \u0111\u00e0 t\u0103ng c\u1ee7a nh\u00f3m h\u00e0ng ti\u00eau d\u00f9ng khi d\u00f2ng ti\u1ec1n nh\u00e0 \u0111\u1ea7u t\u01b0 quay l\u1ea1i.", "Nh\u00f3m b\u00e1n l\u1ebb ghi nh\u1eadn s\u1ef1 kh\u1edfi s\u1eafc r\u00f5 r\u00e0ng trong hai tu\u1ea7n g\u1ea7n \u0111\u00e2y khi s\u1ee9c mua n\u1ed9i \u0111\u1ecba t\u0103ng tr\u1edf l\u1ea1i sau giai \u0111o\u1ea1n \u0111i\u1ec1u ch\u1ec9nh. \u0110\u00e2y l\u00e0 k\u1ebft qu\u1ea3 c\u1ee7a g\u00f3i k\u00edch c\u1ea7u v\u00e0 \u0111\u00e0 ph\u1ee5c h\u1ed3i c\u1ee7a th\u1ecb tr\u01b0\u1eddng lao \u0111\u1ed9ng.\n\nD\u00f2ng ti\u1ec1n t\u01b0\u01a1ng \u0111\u1ed1i d\u1ed3i d\u00e0o \u0111ang ch\u1ea3y d\u1ea7n v\u00e0o c\u00e1c c\u1ed5 phi\u1ebfu \u0111\u1ea7u ng\u00e0nh c\u00f3 \u0111\u1ecbnh gi\u00e1 h\u1ee3p l\u00fd. C\u00e1c chuy\u00ean gia cho r\u1eb1ng y\u1ebfu t\u1ed1 h\u1ed7 tr\u1ee3 l\u1edbn nh\u1ea5t \u0111\u1ebfn t\u1eeb k\u1ebft qu\u1ea3 kinh doanh qu\u00fd n\u00e0y kh\u1ea3 quan h\u01a1n d\u1ef1 ki\u1ebfn.\n\nNh\u00e0 \u0111\u1ea7u t\u01b0 c\u1ea7n ph\u00e2n bi\u1ec7t gi\u1eefa nh\u1eefng c\u00f4ng ty c\u00f3 t\u00e2m l\u00fd t\u0103ng tr\u01b0\u1edfng b\u1ec1n v\u1eefng v\u1edbi nh\u1eefng c\u00e1i t\u0103ng theo s\u00f3ng \u0111\u1ec3 tr\u00e1nh r\u1ee7i ro \u0111u \u0111\u1ec9nh khi th\u1ecb tr\u01b0\u1eddng \u0111\u1ea3o chi\u1ec1u.", "ng\u00e0nh", "positive", 2.0, null, 1, 5],
    ["n-x2", "C\u00e1c qu\u1ef9 ngo\u1ea1i \u0111\u1ea9y m\u1ea1nh gi\u1ea3i ng\u00e2n v\u00e0o c\u1ed5 phi\u1ebfu c\u00f4ng ngh\u1ec7", "Kh\u1ed1i ngo\u1ea1i mua r\u00f2ng m\u1ea1nh nh\u00f3m c\u00f4ng ngh\u1ec7, t\u00edn hi\u1ec7u d\u00f2ng v\u1ed1n qu\u1ed1c t\u1ebf \u0111ang quay tr\u1edf l\u1ea1i v\u1edbi c\u00e1c doanh nghi\u1ec7p s\u1ed1.", "D\u00f2ng v\u1ed1n ngo\u1ea1i quay tr\u1edf l\u1ea1i m\u1ea1nh m\u1ebd v\u1edbi nh\u00f3m c\u00f4ng ngh\u1ec7 khi c\u00e1c qu\u1ef9 \u0111\u00e1nh gi\u00e1 l\u1ea1i tri\u1ec3n v\u1ecdng t\u0103ng tr\u01b0\u1edfng c\u1ee7a m\u1ea3ng d\u1ecbch v\u1ee5 s\u1ed1 v\u00e0 tr\u00ed tu\u1ec7 nh\u00e2n t\u1ea1o.\n\nGi\u1edbi ph\u00e2n t\u00edch l\u01b0u \u00fd r\u1eb1ng m\u1ee9c \u0111\u1ecbnh gi\u00e1 hi\u1ec7n t\u1ea1i v\u1eabn \u1edf v\u00f9ng ph\u00f9 h\u1ee3p so v\u1edbi t\u1ed1c \u0111\u1ed9 t\u0103ng doanh thu k\u1ef3 v\u1ecdng. Nhi\u1ec1u c\u1ed5 phi\u1ebfu \u0111\u00e3 ph\u1ee5c h\u1ed3i \u0111\u00e1ng k\u1ec3 t\u1eeb \u0111\u00e1y.\n\nTuy nhi\u00ean r\u1ee7i ro v\u1eabn c\u00f2n khi thanh kho\u1ea3n th\u1ecb tr\u01b0\u1eddng ph\u00e2n h\u00f3a v\u00e0 c\u00e1c ch\u00ednh s\u00e1ch qu\u1ea3n l\u00fd ng\u00e0nh c\u00f4ng ngh\u1ec7 c\u00f3 th\u1ec3 thay \u0111\u1ed5i b\u1ea5t ng\u1edd theo di\u1ec5n bi\u1ebfn v\u0129 m\u00f4.", "th\u1ecb tr\u01b0\u1eddng", "positive", 1.9, "c-techa-1", 2, 15],
    ["n-x3", "Ng\u00e2n h\u00e0ng trung \u01b0\u01a1ng ph\u00e1t t\u00edn hi\u1ec7u gi\u1eef nguy\u00ean l\u00e3i su\u1ea5t \u0111i\u1ec1u h\u00e0nh", "L\u00e3i su\u1ea5t \u0111i\u1ec1u h\u00e0nh nhi\u1ec7m k\u1ef3 t\u1edbi d\u1ef1 ki\u1ebfn \u0111\u01b0\u1ee3c gi\u1eef \u1ed5n \u0111\u1ecbnh, gi\u00fap c\u00e2n b\u1eb1ng gi\u1eefa h\u1ed7 tr\u1ee3 t\u0103ng tr\u01b0\u1edfng v\u00e0 ki\u1ec3m so\u00e1t l\u1ea1m ph\u00e1t.", "Ng\u00e2n h\u00e0ng trung \u01b0\u01a1ng ph\u00e1t \u0111i th\u00f4ng \u0111i\u1ec7p gi\u1eef nguy\u00ean l\u00e3i su\u1ea5t \u0111i\u1ec1u h\u00e0nh trong k\u1ef3 h\u1ecdp s\u1eafp t\u1edbi, \u0111\u1ed3ng th\u1eddi theo d\u00f5i s\u00e1t di\u1ec5n bi\u1ebfn l\u1ea1m ph\u00e1t trong n\u01b0\u1edbc v\u00e0 qu\u1ed1c t\u1ebf.\n\nVi\u1ec7c gi\u1eef l\u00e3i su\u1ea5t \u1ed5n \u0111\u1ecbnh t\u1ea1o \u0111i\u1ec1u ki\u1ec7n thu\u1eadn l\u1ee3i cho doanh nghi\u1ec7p ti\u1ebfp c\u1eadn v\u1ed1n v\u1edbi chi ph\u00ed h\u1ee3p l\u00fd, \u0111\u1eb7c bi\u1ec7t trong b\u1ed1i c\u1ea3nh chu k\u1ef3 kinh t\u1ebf c\u00f2n nhi\u1ec1u bi\u1ebfn \u0111\u1ed9ng.\n\nGi\u1edbi \u0111\u1ea7u t\u01b0 k\u1ef3 v\u1ecdng \u0111\u1ed9ng th\u00e1i g\u1eedi t\u00edn hi\u1ec7u \u1ed5n \u0111\u1ecbnh s\u1ebd gi\u00fap th\u1ecb tr\u01b0\u1eddng gi\u1ea3m b\u1edbt lo ng\u1ea1i ng\u1eafn h\u1ea1n v\u00e0 c\u1ea3i thi\u1ec7n t\u00e2m l\u00fd n\u1eafm gi\u1eef t\u00e0i s\u1ea3n.", "v\u0129 m\u00f4", "neutral", 1.4, null, 3, 25],
    ["n-x4", "C\u1ea3nh b\u00e1o \u0111\u1ed9t bi\u1ebfn gi\u00e1 n\u0103ng l\u01b0\u1ee3ng \u0111\u1ea7u v\u00e0o s\u1eafp ph\u00e1t", "Di\u1ec5n bi\u1ebfn gi\u00e1 n\u0103ng l\u01b0\u1ee3ng th\u1ebf gi\u1edbi c\u00f3 th\u1ec3 t\u00e1c \u0111\u1ed9ng l\u00ean chi ph\u00ed s\u1ea3n xu\u1ea5t c\u1ee7a nhi\u1ec1u doanh nghi\u1ec7p trong n\u01b0\u1edbc.", "Gi\u00e1 n\u0103ng l\u01b0\u1ee3ng th\u1ebf gi\u1edbi \u0111\u00e3 t\u0103ng li\u00ean t\u1ee5c nhi\u1ec1u phi\u00ean, d\u1eabn \u0111\u1ebfn lo ng\u1ea1i chi ph\u00ed \u0111\u1ea7u v\u00e0o t\u0103ng s\u1ebd b\u00f9ng ph\u00e1t trong qu\u00fd t\u1edbi, \u0111\u1eb7c bi\u1ec7t v\u1edbi c\u00e1c ng\u00e0nh th\u00e9p, xi m\u0103ng v\u00e0 h\u00f3a ch\u1ea5t.\n\nC\u00e1c doanh nghi\u1ec7p \u0111\u00e3 ch\u1ee7 \u0111\u1ed9ng t\u0103ng t\u1ed3n kho nguy\u00ean li\u1ec7u nh\u1eb1m ch\u1eb1n chi ph\u00ed, tuy nhi\u00ean kh\u00f4ng th\u1ec3 duy tr\u00ec m\u00e3i n\u1ebfu gi\u00e1 \u1edf m\u1ee9c cao k\u00e9o d\u00e0i.\n\nNhi\u1ec1u chuy\u00ean gia khuy\u1ebfn ngh\u1ecb nh\u00e0 \u0111\u1ea7u t\u01b0 theo d\u00f5i ch\u1eb7t bi\u00ean l\u1ee3i nhu\u1eadn qu\u00fd sau v\u00e0 th\u1eadn tr\u1ecdng v\u1edbi c\u00e1c c\u1ed5 phi\u1ebfu c\u00f3 t\u1ef7 tr\u1ecdng chi ph\u00ed n\u0103ng l\u01b0\u1ee3ng l\u1edbn trong c\u01a1 c\u1ea5u gi\u00e1 th\u00e0nh.", "ng\u00e0nh", "negative", 1.8, "c-energc-12", 4, 35],
    ["n-x5", "D\u00f2ng ti\u1ec1n th\u00f4ng minh chuy\u1ec3n d\u1ecbch n\u1ed5i b\u1eadt gi\u1eefa c\u00e1c nh\u00f3m ng\u00e0nh", "Lu\u00e2n chuy\u1ec3n d\u00f2ng ti\u1ec1n gi\u1eefa c\u00e1c nh\u00f3m ng\u00e0nh \u0111ang l\u00e0 ch\u1ee7 \u0111\u1ec1 ch\u00ednh c\u1ee7a phi\u00ean giao d\u1ecbch h\u00f4m nay.", "Th\u1ecb tr\u01b0\u1eddng ghi nh\u1eadn s\u1ef1 lu\u00e2n chuy\u1ec3n d\u00f2ng ti\u1ec1n gi\u1eefa nh\u00f3m ng\u00e2n h\u00e0ng, c\u00f4ng ngh\u1ec7 v\u00e0 h\u00e0ng ti\u00eau d\u00f9ng. D\u00f2ng ti\u1ec1n th\u00f4ng minh c\u00f3 xu h\u01b0\u1edbng \u0111i t\u00ecm c\u00e1c c\u1ed5 phi\u1ebfu c\u00f3 n\u1ec1n t\u1ea3ng c\u01a1 b\u1ea3n t\u1ed1t v\u00e0 ch\u01b0a t\u0103ng nhi\u1ec1u.\n\nT\u00e2m l\u00fd nh\u00e0 \u0111\u1ea7u t\u01b0 ph\u1ea5n kh\u1edfi nh\u01b0ng v\u1eabn gi\u1eef s\u1ef1 th\u1eadn tr\u1ecdng nh\u1ea5t \u0111\u1ecbnh, th\u1ec3 hi\u1ec7n qua kh\u1ed1i l\u01b0\u1ee3ng giao d\u1ecbch \u1ed5n \u0111\u1ecbnh thay v\u00ec b\u00f9ng n\u1ed5 theo c\u1ea3m x\u00fac.\n\nChuy\u00ean gia cho r\u1eb1ng xu h\u01b0\u1edbng ph\u00e2n h\u00f3a s\u1ebd ti\u1ebfp di\u1ec5n, nh\u00e0 \u0111\u1ea7u t\u01b0 n\u00ean \u01b0u ti\u00ean ch\u1ecdn l\u1ecdc c\u1ed5 phi\u1ebfu c\u00f3 c\u00e2u chuy\u1ec7n t\u0103ng tr\u01b0\u1edfng r\u00f5 r\u00e0ng.", "th\u1ecb tr\u01b0\u1eddng", "positive", 1.2, null, 5, 45],
    ["n-x6", "Doanh nghi\u1ec7p s\u1ea3n xu\u1ea5t \u0111\u1ed1i m\u1eb7t \u00e1p l\u1ef1c \u0111\u01a1n h\u00e0ng qu\u00fd sau", "\u0110\u01a1n h\u00e0ng m\u1edbi c\u00f3 d\u1ea5u hi\u1ec7u ch\u1eadm l\u1ea1i khi th\u1ecb tr\u01b0\u1eddng xu\u1ea5t kh\u1ea9u ch\u00ednh ghi nh\u1eadn t\u0103ng tr\u01b0\u1edfng ch\u1eadm h\u01a1n k\u1ef3 v\u1ecdng.", "Nhi\u1ec1u doanh nghi\u1ec7p s\u1ea3n xu\u1ea5t b\u00e1o c\u00e1o gi\u00e1 tr\u1ecb \u0111\u01a1n h\u00e0ng m\u1edbi qu\u00fd sau c\u00f3 d\u1ea5u hi\u1ec7u ch\u1eadm l\u1ea1i, do nhu c\u1ea7u t\u1eeb c\u00e1c th\u1ecb tr\u01b0\u1eddng ch\u00ednh gi\u1ea3m nh\u1eb9 trong b\u1ed1i c\u1ea3nh l\u00e3i su\u1ea5t to\u00e0n c\u1ea7u duy tr\u00ec \u1edf m\u1ee9c cao.\n\nTuy nhi\u00ean c\u00e1c nh\u00e0 m\u00e1y trong n\u01b0\u1edbc v\u1eabn ho\u1ea1t \u0111\u1ed9ng \u1ed5n \u0111\u1ecbnh nh\u1edd c\u00e1c h\u1ee3p \u0111\u1ed3ng d\u00e0i h\u1ea1n \u0111\u00e3 k\u00fd, gi\u00fap san s\u1ebb r\u1ee7i ro tr\u01b0\u1edbc m\u1eaft.\n\nVi\u1ec7c theo d\u00f5i t\u00edn hi\u1ec7u ph\u1ee5c h\u1ed3i \u0111\u01a1n h\u00e0ng trong qu\u00fd t\u1edbi s\u1ebd l\u00e0 ch\u00eca kh\u00f3a \u0111\u1ec3 \u0111\u00e1nh gi\u00e1 l\u1ea1i tri\u1ec3n v\u1ecdng c\u1ee7a c\u00e1c c\u1ed5 phi\u1ebfu ng\u00e0nh s\u1ea3n xu\u1ea5t", "ng\u00e0nh", "negative", 1.5, "c-indusc-18", 6, 55],
    ["n-x7", "Chu\u1ed7i cung \u1ee9ng n\u00f4ng s\u1ea3n h\u1ed3i ph\u1ee5c t\u1ed1t h\u01a1n d\u1ef1 ki\u1ebfn", "D\u1eef li\u1ec7u b\u00e1n l\u1ebb cho th\u1ea5y chu\u1ed7i cung \u1ee9ng n\u00f4ng s\u1ea3n \u0111\u00e3 v\u01b0\u1ee3t qua giai \u0111o\u1ea1n kh\u00f3 kh\u0103n nh\u1ea5t, h\u1ed7 tr\u1ee3 nh\u00f3m c\u1ed5 phi\u1ebfu li\u00ean quan.", "Chu\u1ed7i cung \u1ee9ng n\u00f4ng s\u1ea3n ghi nh\u1eadn s\u1ef1 h\u1ed3i ph\u1ee5c t\u1ed1t h\u01a1n d\u1ef1 ki\u1ebfn nh\u1edd m\u00f9a v\u1ee5 thu\u1eadn l\u1ee3i v\u00e0 d\u00f2ng v\u1ed1n \u0111\u1ea7u t\u01b0 v\u00e0o c\u01a1 s\u1edf h\u1ea1 t\u1ea7ng logistics n\u00f4ng nghi\u1ec7p.\n\nDoanh thu c\u00e1c c\u00f4ng ty ph\u00e2n ph\u1ed1i n\u00f4ng s\u1ea3n t\u0103ng nh\u1edd gi\u00e1 b\u00e1n b\u00ecnh \u1ed5n v\u00e0 chi ph\u00ed v\u1eadn chuy\u1ec3n gi\u1ea3m.\n\nC\u00e1c chuy\u00ean gia cho r\u1eb1ng \u0111\u00e2y l\u00e0 nh\u00f3m c\u1ed5 phi\u1ebfu ph\u00f2ng th\u1ee7 t\u1ed1t, ph\u00f9 h\u1ee3p v\u1edbi nh\u00e0 \u0111\u1ea7u t\u01b0 \u01b0a th\u00edch s\u1ef1 \u1ed5n \u0111\u1ecbnh v\u00e0 d\u00f2ng c\u1ed5 t\u1ee9c \u0111\u1ec1u \u0111\u1eb7n.", "ng\u00e0nh", "positive", 1.1, "c-consmc-15", 7, 65],
    ["n-x8", "Th\u1ecb tr\u01b0\u1eddng ch\u1edd \u0111\u1ee3n d\u1eef li\u1ec7u vi\u1ec7c l\u00e0m tr\u01b0\u1edbc khi \u0111\u1ecbnh h\u01b0\u1edbng m\u1edbi", "C\u00e1c d\u1eef li\u1ec7u vi\u1ec7c l\u00e0m s\u1eafp c\u00f4ng b\u1ed1 \u0111\u01b0\u1ee3c xem l\u00e0 y\u1ebfu t\u1ed1 quy\u1ebft \u0111\u1ecbnh h\u01b0\u1edbng giao d\u1ecbch trong k\u1ef3 t\u1edbi.", "Th\u1ecb tr\u01b0\u1eddng b\u01b0\u1edbc v\u00e0o tr\u1ea1ng th\u00e1i ch\u1edd \u0111\u1ee3i khi c\u00e1c d\u1eef li\u1ec7u vi\u1ec7c l\u00e0m m\u1edbi s\u1eafp \u0111\u01b0\u1ee3c c\u00f4ng b\u1ed1. Nh\u00e0 \u0111\u1ea7u t\u01b0 c\u00f3 xu h\u01b0\u1edbng t\u1ea1m th\u1eddi \u0111\u1ee9ng ngo\u00e0i quan s\u00e1t \u0111\u1ec3 ch\u1edd x\u00e1c nh\u1eadn xu h\u01b0\u1edbng.\n\nN\u1ebfu d\u1eef li\u1ec7u kh\u1ea3 quan, k\u1ef3 v\u1ecdng l\u00e3i su\u1ea5t h\u1ea1 nhi\u1ec7t t\u0103ng l\u00ean v\u00e0 d\u00f2ng ti\u1ec1n c\u00f3 th\u1ec3 quay l\u1ea1i nhanh h\u01a1n d\u1ef1 b\u00e1o.\n\nNg\u01b0\u1ee3c l\u1ea1i, d\u1eef li\u1ec7u y\u1ebfu c\u00f3 th\u1ec3 khi\u1ebfn th\u1ecb tr\u01b0\u1eddng \u0111i\u1ec1u ch\u1ec9nh s\u00e2u h\u01a1n, v\u00ec v\u1eady vi\u1ec7c qu\u1ea3n tr\u1ecb r\u1ee7i ro danh m\u1ee5c tr\u1edf n\u00ean quan tr\u1ecdng h\u01a1n bao gi\u1edd.", "v\u0129 m\u00f4", "neutral", 1.3, null, 8, 75],
    ["n-x9", "S\u00f3ng \u0111\u1ea7u t\u01b0 h\u1ea1 t\u1ea7ng giao th\u00f4ng t\u0103ng nhi\u1ec7t", "H\u00e0ng lo\u1ea1t d\u1ef1 \u00e1n h\u1ea1 t\u1ea7ng giao th\u00f4ng tr\u1ecdng \u0111i\u1ec3m \u0111\u01b0\u1ee3c kh\u1edfi \u0111\u1ed9ng t\u1ea1o c\u01a1 h\u1ed9i l\u1edbn cho c\u00e1c doanh nghi\u1ec7p x\u00e2y l\u1eafp v\u00e0 v\u1eadt li\u1ec7u.", "Nhi\u1ec1u d\u1ef1 \u00e1n h\u1ea1 t\u1ea7ng giao th\u00f4ng tr\u1ecdng \u0111i\u1ec3m \u0111\u01b0\u1ee3c kh\u1edfi \u0111\u1ed9ng trong giai \u0111o\u1ea1n n\u00e0y, m\u1edf ra c\u01a1 h\u1ed9i l\u1edbn cho nh\u00f3m doanh nghi\u1ec7p x\u00e2y l\u1eafp, v\u1eadt li\u1ec7u x\u00e2y d\u1ef1ng v\u00e0 d\u1ecbch v\u1ee5 logistics.\n\nC\u00e1c d\u1ef1 \u00e1n \u0111\u01b0\u1ee3c k\u1ef3 v\u1ecdng th\u00f4ng qua nhanh gi\u00fap gi\u1ea3i ng\u00e2n v\u1ed1n \u0111\u1ea7u t\u01b0 c\u00f4ng hi\u1ec7u qu\u1ea3 v\u00e0 th\u00fac \u0111\u1ea9y t\u0103ng tr\u01b0\u1edfng kinh t\u1ebf.\n\nNh\u00f3m c\u1ed5 phi\u1ebfu n\u00e0y th\u01b0\u1eddng nh\u1ea1y c\u1ea3m v\u1edbi d\u00f2ng v\u1ed1n gi\u1ea3i ng\u00e2n, do \u0111\u00f3 nh\u00e0 \u0111\u1ea7u t\u01b0 c\u1ea7n theo d\u00f5i ti\u1ebfn \u0111\u1ed9 gi\u1ea3i ng\u00e2n th\u1ef1c t\u1ebf thay v\u00ec ch\u1ec9 tin v\u00e0o k\u1ebf ho\u1ea1ch \u0111\u01b0\u1ee3c c\u00f4ng b\u1ed1.", "ng\u00e0nh", "positive", 1.7, "c-indusb-17", 9, 85],
    ["n-x10", "T\u00edn d\u1ee5ng ng\u00e2n h\u00e0ng t\u0103ng t\u1ed1c t\u1ea1i c\u00e1c tr\u1ee5 \u0111\u1ed3ng kinh t\u1ebf", "T\u0103ng tr\u01b0\u1edfng t\u00edn d\u1ee5ng c\u1ea3i thi\u1ec7n r\u00f5 r\u1ec7t, h\u1ed7 tr\u1ee3 cho nh\u00f3m c\u1ed5 phi\u1ebfu ng\u00e2n h\u00e0ng trong trung h\u1ea1n.", "T\u0103ng tr\u01b0\u1edfng t\u00edn d\u1ee5ng t\u0103ng t\u1ed1c \u0111\u00e1ng k\u1ec3 t\u1ea1i c\u00e1c tr\u1ee5 \u0111\u1ed3ng kinh t\u1ebf l\u1edbn nh\u1edd nhu c\u1ea7u vay v\u1ed1n ph\u1ee5c v\u1ee5 s\u1ea3n xu\u1ea5t v\u00e0 ti\u00eau d\u00f9ng c\u1ea3i thi\u1ec7n.\n\nBi\u00ean l\u00e3i r\u00f2ng c\u1ee7a c\u00e1c ng\u00e2n h\u00e0ng \u0111\u01b0\u1ee3c duy tr\u00ec \u1ed5n \u0111\u1ecbnh v\u00e0 ch\u1ea5t l\u01b0\u1ee3ng t\u00e0i s\u1ea3n kh\u00f4ng c\u00f3 d\u1ea5u hi\u1ec7u x\u1ea5u \u0111i.\n\nGi\u1edbi ph\u00e2n t\u00edch \u0111\u00e1nh gi\u00e1 nh\u00f3m ng\u00e2n h\u00e0ng v\u1eabn l\u00e0 tr\u1ee5 \u0111\u1ee1 c\u1ee7a th\u1ecb tr\u01b0\u1eddng, nh\u01b0ng l\u01b0u \u00fd \u00e1p l\u1ef1c t\u1eeb chi ph\u00ed v\u1ed1n v\u00e0 n\u1ee3 x\u1ea5u ti\u1ec1m \u1ea9n c\u1ea7n theo d\u00f5i.", "ng\u00e0nh", "positive", 1.6, "c-fina-4", 10, 95],
    ["n-x11", "Nh\u00e0 \u0111\u1ea7u t\u01b0 c\u00e1 nh\u00e2n t\u0103ng c\u01b0\u1eddng nh\u1eadn di\u1ec7n th\u01b0\u01a1ng hi\u1ec7u t\u00e0i ch\u00ednh", "Kh\u1ea3o s\u00e1t m\u1edbi cho th\u1ea5y s\u1ed1 l\u01b0\u1ee3ng nh\u00e0 \u0111\u1ea7u t\u01b0 c\u00e1 nh\u00e2n ch\u1ee7 \u0111\u1ed9ng h\u1ecdc h\u1ecfi v\u00e0 ph\u00e2n t\u00edch c\u01a1 b\u1ea3n t\u0103ng nhanh.", "Kh\u1ea3o s\u00e1t m\u1edbi \u0111\u00e2y cho th\u1ea5y nh\u00e0 \u0111\u1ea7u t\u01b0 c\u00e1 nh\u00e2n ng\u00e0y c\u00e0ng ch\u1ee7 \u0111\u1ed9ng trau d\u1ed3i ki\u1ebfn th\u1ee9c n\u1ec1n t\u1ea3ng v\u00e0 c\u00e2n nh\u1eafc r\u1ee7i ro tr\u01b0\u1edbc m\u1ed7i quy\u1ebft \u0111\u1ecbnh giao d\u1ecbch.\n\n\u0110i\u1ec1u n\u00e0y ph\u1ea3n \u00e1nh s\u1ef1 tr\u01b0\u1edfng th\u00e0nh c\u1ee7a th\u1ecb tr\u01b0\u1eddng, t\u1eeb vi\u1ec7c ch\u1ea1y theo c\u1ea3m x\u00fac sang t\u1ed1i \u01b0u h\u00f3a danh m\u1ee5c d\u00e0i h\u1ea1n.\n\nT\u00e2m l\u00fd n\u00e0y gi\u00fap th\u1ecb tr\u01b0\u1eddng b\u1edbt d\u1ecb bi\u1ebfn trong ng\u1eafn h\u1ea1n v\u00e0 h\u1ed7 tr\u1ee3 xu h\u01b0\u1edbng t\u0103ng b\u1ec1n \u0111\u1ec3 c\u00e1c c\u1ed5 phi\u1ebfu c\u01a1 b\u1ea3n t\u1ed1t.", "th\u1ecb tr\u01b0\u1eddng", "positive", 0.9, null, 11, 105],
    ["n-x12", "R\u00e0o c\u1ea3n th\u01b0\u01a1ng m\u1ea1i ti\u1ebfp t\u1ee5c l\u00e0 \u1ea9n s\u1ed1 cho doanh nghi\u1ec7p xu\u1ea5t kh\u1ea9u", "C\u00e1c doanh nghi\u1ec7p xu\u1ea5t kh\u1ea9u \u0111ang theo d\u00f5i s\u00e1t di\u1ec5n bi\u1ebfn ch\u00ednh s\u00e1ch th\u01b0\u01a1ng m\u1ea1i qu\u1ed1c t\u1ebf tr\u01b0\u1edbc nguy c\u01a1 thay \u0111\u1ed5i quy \u0111\u1ecbnh b\u1ea5t ng\u1edd.", "R\u00e0o c\u1ea3n th\u01b0\u01a1ng m\u1ea1i ti\u1ebfp t\u1ee5c l\u00e0 \u1ea9n s\u1ed1 l\u1edbn v\u1edbi c\u00e1c doanh nghi\u1ec7p xu\u1ea5t kh\u1ea9u khi nhi\u1ec1u th\u1ecb tr\u01b0\u1eddng l\u1edbn c\u00f3 th\u1ec3 \u00e1p d\u1ee5ng quy \u0111\u1ecbnh m\u1edbi \u1ea3nh h\u01b0\u1edfng \u0111\u1ebfn chu\u1ed7i cung \u1ee9ng.\n\nC\u00e1c c\u00f4ng ty \u0111\u00e3 ch\u1ee7 \u0111\u1ed9ng \u0111a d\u1ea1ng h\u00f3a th\u1ecb tr\u01b0\u1eddng \u0111\u1ec3 gi\u1ea3m thi\u1ec3u ph\u1ee5 thu\u1ed9c v\u00e0o b\u1ea5t k\u1ef3 khu v\u1ef1c n\u00e0o.\n\nNh\u00e0 \u0111\u1ea7u t\u01b0 theo d\u00f5i nh\u00f3m n\u00e0y c\u1ea7n \u0111\u00e1nh gi\u00e1 c\u1ea3 kh\u1ea3 n\u0103ng ch\u1ed1ng ch\u1ecbu r\u1ee7i ro l\u1eabn c\u01a1 h\u1ed9i khi ch\u00ednh s\u00e1ch tr\u1edf n\u00ean thu\u1eadn l\u1ee3i h\u01a1n d\u1ef1 ki\u1ebfn.", "v\u0129 m\u00f4", "negative", 1.9, null, 12, 115]
  ];

  for (var i = 0; i < extraRows.length; i++) {
    var r = extraRows[i];
    if (have[r[0]]) continue;
    news.appendRow([
      r[0], r[1], r[2], r[3], 'Capia News', r[4], r[5], String(r[6]), r[7],
      true, agoISO_(r[8], r[9]), now
    ]);
  }
}

/** B\u1ed5 sung th\u00eam b\u00e0i x\u00e3 h\u1ed9i m\u1edbi (idempotent). */
function augmentSocialSeed_() {
  var social = getSheet_('social');
  var existing = readAll_(social);
  var have = {};
  existing.forEach(function (s) { have[s.id] = true; });
  var now = isoNow();
  var extraRows = [
    ["s-x1", "Nh\u00e0 \u0111\u1ea7u t\u01b0 c\u00e1 nh\u00e2n gi\u00e0u kinh nghi\u1ec7m", null, "pro_trader", "Theo d\u00f5i d\u00f2ng ti\u1ec1n ngo\u1ea1i c\u1ea3 tu\u1ea7n, m\u1ea5y phi\u00ean g\u1ea7n \u0111\u00e2y kh\u1ed1i ngo\u1ea1i quay l\u1ea1i gom TECHA kh\u00e1 r\u00f5. M\u00ecnh v\u1eabn gi\u1eef danh m\u1ee5c hi\u1ec7n t\u1ea1i, kh\u00f4ng v\u1ed9i b\u1eaft \u0111\u00e1y \u2014 ch\u1edd x\u00e1c nh\u1eadn \u0111\u1ec9nh r\u1ed3i m\u1edbi gi\u1ea3i ng\u00e2n th\u00eam.", "positive", "1.4", "28", "6", "1", "c-techa-1", agoISO_(0, 12), now],
    ["s-x2", "Tin \u0111\u1ed3n t\u1eeb c\u1ed9ng \u0111\u1ed3ng", null, "rumor_birds", "Nghe tin BlueRock Financial s\u1eafp tung g\u00f3i d\u1ecbch v\u1ee5 m\u1edbi cho kh\u1ed1i kh\u00e1ch h\u00e0ng t\u1ed5 ch\u1ee9c. N\u1ebfu \u0111\u00fang th\u00ec FINA c\u00f3 th\u1ec3 \u0111\u01b0\u1ee3c h\u01b0\u1edfng l\u1ee3i \u0111\u00e1ng k\u1ec3 trong qu\u00fd t\u1edbi. Ai c\u00f3 th\u00f4ng tin n\u1ed9i b\u1ed9 s\u1ecdc h\u01a1n chia s\u1ebb v\u1edbi m\u00ecnh nh\u00e9!", "positive", "1.9", "131", "22", "5", "c-fina-4", agoISO_(1, 30), now],
    ["s-x3", "Chuy\u00ean gia ph\u00e2n t\u00edch k\u1ef9 thu\u1eadt", null, "ta_fa_kol", "L\u01b0u \u00fd c\u1ea3 nh\u00e0: NEWS v\u1eeba ra ng\u00e0y h\u00f4m nay ph\u00e1t t\u00edn hi\u1ec7u c\u1ea3nh b\u00e1o ng\u1eafn h\u1ea1n cho nh\u00f3m n\u0103ng l\u01b0\u1ee3ng. \u0110\u1ecbnh gi\u00e1 hi\u1ec7n t\u1ea1i ph\u1ea3n \u00e1nh nhi\u1ec1u k\u1ef3 v\u1ecdng t\u1ed1t, ch\u01b0a ph\u1ea3n \u00e1nh chi ph\u00ed \u0111\u1ea7u v\u00e0o t\u0103ng. \u0110\u1eebng \u00f4m to\u00e0n b\u1ed9 v\u00e0o v\u00f9ng kh\u00e1ng c\u1ef1!", "negative", "1.7", "204", "31", "7", "c-energc-12", agoISO_(2, 5), now],
    ["s-x4", "F0 m\u1edbi t\u1eadp t\u00e0nh \u0111\u1ea7u t\u01b0", null, "f0_newbie", "M\u1ecdi ng\u01b0\u1eddi \u01a1i, m\u00ecnh m\u1edbi b\u1eaft \u0111\u1ea7u t\u00ecm hi\u1ec3u c\u1ed5 phi\u1ebfu h\u00e0ng ti\u00eau d\u00f9ng. \u0110\u1ecdc tin th\u00ec th\u1ea5y nh\u00f3m n\u00e0y ph\u1ee5c h\u1ed3i kh\u00e1 \u1ed5n \u0111\u1ecbnh, b\u00e1c n\u00e0o cho e xin \u00fd ki\u1ebfn v\u1edbi CONSM? E kh\u00f4ng mu\u1ed1n \u1ea5u t\u00edm nh\u01b0 tr\u01b0\u1edbc \u0111\u00e2y n\u1eefa.", "neutral", "1.0", "77", "12", "3", "c-consma-13", agoISO_(3, 20), now]
  ];
  for (var j = 0; j < extraRows.length; j++) {
    var row = extraRows[j];
    if (have[row[0]]) continue;
    social.appendRow([
      row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9],
      row[10], null, row[11], now
    ]);
  }
}

function companySheetWrite_(rows) {
  var companies = getSheet_('companies');
  rows.forEach(function (row) { companies.appendRow(row); });
}

// Update company price by id (used by price ticker simulation)
function setCompanyPrice_(id, price) {
  var headers = getHeaders_(getSheet_('companies'));
  if (headers.length) {
    getSheet_('companies').getRange(1, 1, 1, headers.length).setValues([headers]);
  }
  var sheet = getSheet_('companies');
  var rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  var idCol = headers.indexOf('id') + 1;
  var priceCol = headers.indexOf('current_price') + 1;
  for (var r = 0; r < rows.length; r++) {
    if (String(rows[r][idCol - 1]) === String(id)) {
      sheet.getRange(r + 2, priceCol).setValue(String(price));
      return;
    }
  }
}

// ------------------------------------------------------------------
// Simulated price tick (for polling from frontend demo)
// ------------------------------------------------------------------
function simulatePriceTick_() {
  var companies = readAll_(getSheet_('companies'));
  // mutate current_price by small random walk and update cells
  var sheet = getSheet_('companies');
  var headers = getHeaders_(sheet);
  var idCol = headers.indexOf('id') + 1;
  var priceCol = headers.indexOf('current_price') + 1;
  var volCol = headers.indexOf('volatility') + 1;
  var rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  for (var r = 0; r < rows.length; r++) {
    var id = rows[r][idCol - 1];
    var price = parseFloat(rows[r][priceCol - 1]);
    var vol = parseFloat(rows[r][volCol - 1] || 0.01);
    var drift = (Math.random() - 0.5) * 2 * price * vol;
    var newPrice = Math.max(price + drift, price * 0.9);
    sheet.getRange(r + 2, priceCol).setValue(String(Math.round(newPrice * 100) / 100));
  }
}

// Cap nhat gia hien tai + gia tri cua portfolio demo theo gia moi cua companies
function updatePortfolioValue_() {
  var companies = readAll_(getSheet_('companies'));
  var priceMap = {};
  companies.forEach(function (c) { priceMap[c.id] = c.current_price; });

  var sheet = getSheet_('portfolio');
  var headers = getHeaders_(sheet);
  if (!headers.length) return;
  var idCol = headers.indexOf('company_id') + 1;
  var priceCol = headers.indexOf('current_price') + 1;
  var mvCol = headers.indexOf('market_value') + 1;
  var pnlCol = headers.indexOf('unrealized_pnl') + 1;
  var qtyCol = headers.indexOf('quantity') + 1;
  var avgCol = headers.indexOf('average_buy_price') + 1;
  var rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  for (var r = 0; r < rows.length; r++) {
    var companyId = rows[r][idCol - 1];
    var price = priceMap[companyId];
    if (price !== undefined) {
      var cur = parseFloat(price);
      var qty = parseFloat(rows[r][qtyCol - 1] || 0);
      var avg = parseFloat(rows[r][avgCol - 1] || 0);
      sheet.getRange(r + 2, priceCol).setValue(String(cur));
      sheet.getRange(r + 2, mvCol).setValue(String(qty * cur));
      sheet.getRange(r + 2, pnlCol).setValue(String(qty * cur - qty * avg));
    }
  }
}

// ------------------------------------------------------------------
// Reset & reseed database (chay THU CONG 1 lan tu editor de sua du lieu hong)
// Cach dung: trong Apps Script editor, chon ham resetDemoData roi bam Run.
// ------------------------------------------------------------------
function resetDemoData() {
  var ss = openDb_();
  ensureSheets_(ss);
  SHEET_NAMES.forEach(function (name) {
    var sheet = ss.getSheetByName(name);
    var lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.deleteRows(2, lastRow - 1);
    }
  });
  seedIfEmpty_();
  return 'Done: du lieu da duoc xoa het va seed lai tu dau.';
}
