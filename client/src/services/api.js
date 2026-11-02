/**
 * 许愿池 · 网络与存储封装
 *
 * 完全对齐「三角洲摸金」真机实测结论（ui/src/services/net.js）：
 *   1. API 是 $falcon.jsapi.http.request(...)，返回 Promise
 *   2. headers 必须是「字符串数组」形如 ['Accept:application/json']，不能传对象
 *   3. timeout 单位是「秒」
 *   4. resolve 的值可能是 {error, result} 包装，需解包；也可能是 ArrayBuffer/Uint8Array
 *   5. 【关键】原生 http 对 POST body 支持不可靠（真机会发空 body）
 *      —— 所以所有写操作一律走 GET + query 参数
 *   6. 原生 http 偶发挂起不回调 —— 必须自加看门狗超时
 *
 * QuickJS 约束：只用 var / function，不用箭头函数、模板字符串、class。
 */

import { logInfo, logWarn, logError } from './logger.js'

// 候选服务端地址：按顺序探测，第一个可用的记住
// ⚠️ 部署前请改成你自己的服务器地址（按顺序探测，第一个可用的会被记住）。
//    公网在前、局域网兜底；用不到的直接删掉。
export var ENDPOINTS = [
  'http://YOUR_SERVER_HOST:17613'
]

export var API_BASE = ENDPOINTS[0]

var DEFAULT_TIMEOUT_SEC = 10
var WATCHDOG_MS = 14000

var _chosen = ''
var _probing = null

export function setBase(url) { API_BASE = url; _chosen = url }
export function currentBase() { return API_BASE }
export function endpointList() { return ENDPOINTS.slice(0) }

// ---------------- 平台 API 探测 ----------------
var _api = null
var _apiTried = false

function _falconJsapi() {
  try { if (typeof $falcon !== 'undefined' && $falcon && $falcon.jsapi) return $falcon.jsapi } catch (e) { /* ignore */ }
  return null
}
function _globalJsapi() {
  try { if (typeof jsapi !== 'undefined' && jsapi) return jsapi } catch (e) { /* ignore */ }
  try { if (typeof window !== 'undefined' && window.jsapi) return window.jsapi } catch (e) { /* ignore */ }
  return null
}
function _tryRequire(name) {
  try {
    if (typeof require === 'function') {
      var m = require(name)
      if (m) return m
    }
  } catch (e) { /* ignore */ }
  return null
}

function detectApi() {
  if (_apiTried) return _api
  _apiTried = true

  var j = _falconJsapi()
  if (j && j.http && typeof j.http.request === 'function') {
    _api = { kind: 'jsapi.http.request', fn: j.http.request, owner: j.http }
    logInfo('net api: ' + _api.kind)
    return _api
  }
  if (j && typeof j.request === 'function') {
    _api = { kind: 'jsapi.request', fn: j.request, owner: j }
    logInfo('net api: ' + _api.kind)
    return _api
  }

  var g = _globalJsapi()
  if (g && g.http && typeof g.http.request === 'function') {
    _api = { kind: 'global.http.request', fn: g.http.request, owner: g.http }
    logInfo('net api: ' + _api.kind)
    return _api
  }

  try {
    if (typeof fetch === 'function') {
      _api = { kind: 'global.fetch', fn: fetch, owner: null }
      logInfo('net api: ' + _api.kind)
      return _api
    }
  } catch (e) { /* ignore */ }

  var names = ['net', 'http', 'request']
  for (var i = 0; i < names.length; i++) {
    var m = _tryRequire(names[i])
    if (!m) continue
    var cand = m.Request || m.request || (typeof m === 'function' ? m : null)
    if (typeof cand === 'function') {
      _api = { kind: 'native.' + names[i], fn: cand, owner: m }
      logInfo('net api: ' + _api.kind)
      return _api
    }
  }

  logError('net api: none found')
  _api = null
  return _api
}

export function networkKind() {
  var a = detectApi()
  return a ? a.kind : 'none'
}
export function resetProbe() { _apiTried = false; _api = null }

// ---------------- 响应解码 ----------------
/**
 * 字节数组 / ArrayBuffer / 字符串 -> 字符串。
 * 与三角洲摸金 bytesToStr 同款，并额外兼容 {data}/{bytes} 包装。
 */
export function decodeUtf8(payload) {
  if (payload === null || payload === undefined) return ''
  if (typeof payload === 'string') return payload

  // 1) ArrayBuffer / TypedArray（有 byteLength）
  try {
    if (typeof payload === 'object' && payload.byteLength !== null && payload.byteLength !== undefined) {
      var u8 = new Uint8Array(payload)
      var out = ''
      for (var i = 0; i < u8.length; i++) out += String.fromCharCode(u8[i])
      try { return decodeURIComponent(escape(out)) } catch (e) { return out }
    }
  } catch (e) { /* ignore */ }

  // 2) { data: [...] } / { bytes: [...] } / 普通数组
  try {
    if (typeof payload === 'object') {
      var arr = payload.data || payload.bytes || payload
      if (arr && arr.length !== null && arr.length !== undefined) {
        var s = ''
        for (var k = 0; k < arr.length; k++) s += String.fromCharCode(arr[k])
        try { return decodeURIComponent(escape(s)) } catch (e2) { return s }
      }
    }
  } catch (e3) { /* ignore */ }

  return String(payload)
}

/** 有些平台会把 HTTP 头一起返回，剥掉只留 body */
function stripHeaders(text) {
  var t = text || ''
  var i = t.indexOf('\r\n\r\n')
  if (i >= 0) return t.slice(i + 4)
  var j = t.indexOf('\n\n')
  if (j >= 0 && /^\s*HTTP\//.test(t)) return t.slice(j + 2)
  return t
}

function statusFromText(text) {
  var m = /^\s*HTTP\/1\.[01]\s+(\d{3})/.exec(text || '')
  return m ? parseInt(m[1], 10) : 0
}

/** 把 {error,result} 包装解开 */
function unwrap(payload) {
  var res = payload
  try {
    if (res && typeof res === 'object' && (res.result !== undefined || res.error !== undefined)) {
      res = res.result !== undefined ? res.result : res.error
    }
  } catch (e) { /* ignore */ }
  return res
}

function describe(payload) {
  try {
    if (payload === null) return 'null'
    if (payload === undefined) return 'undefined'
    var t = typeof payload
    if (t === 'string') return 'string(' + payload.length + ')'
    if (t === 'object') {
      var keys = []
      for (var k in payload) {
        if (Object.prototype.hasOwnProperty.call(payload, k)) keys.push(k)
        if (keys.length > 6) break
      }
      var extra = ''
      if (payload.byteLength !== undefined) extra += ' byteLength=' + payload.byteLength
      if (payload.length !== undefined) extra += ' length=' + payload.length
      return 'object{' + keys.join(',') + '}' + extra
    }
    return t
  } catch (e) { return '?' }
}

// ---------------- 底层请求 ----------------
/**
 * request({ url, method, headers, body, timeout })
 * -> Promise<{ ok, status, text, data, error }>  永不 reject
 */
export function request(opts) {
  opts = opts || {}
  var timeoutSec = opts.timeout > 0 ? opts.timeout : DEFAULT_TIMEOUT_SEC
  var method = (opts.method || 'GET').toUpperCase()

  var headers = opts.headers
  if (!headers) headers = ['Accept:application/json']
  else if (typeof headers === 'object' && !headers.length) {
    var tmp = []
    for (var k in headers) {
      if (!Object.prototype.hasOwnProperty.call(headers, k)) continue
      tmp.push(k + ':' + headers[k])
    }
    headers = tmp
  }

  return new Promise(function (resolve) {
    var a = detectApi()
    if (!a) { resolve({ ok: false, error: 'no-network-api' }); return }

    var done = false
    var t0 = Date.now()

    // 看门狗：原生 http 偶发不回调
    var watchdog = setTimeout(function () {
      if (done) return
      done = true
      logError('watchdog ' + method + ' ' + opts.url)
      resolve({ ok: false, error: 'watchdog-timeout' })
    }, WATCHDOG_MS)

    function finish(r) {
      if (done) return
      done = true
      clearTimeout(watchdog)
      r.ms = Date.now() - t0
      resolve(r)
    }

    var arg = {
      url: opts.url,
      method: method,
      headers: headers,
      timeout: timeoutSec
    }
    if (opts.body !== null && opts.body !== undefined) arg.data = opts.body

    try {
      var r = a.fn.call(a.owner, arg)
      if (!r || typeof r.then !== 'function') {
        logError(method + ' ' + opts.url + ' not-a-promise type=' + (typeof r))
        finish({ ok: false, error: 'not-a-promise' })
        return
      }

      r.then(function (payload) {
        // 先记原始形态，诊断时非常关键
        var raw = unwrap(payload)
        var full = decodeUtf8(raw)
        // 状态码必须在剥头之前取
        var status = statusFromText(full)
        var text = stripHeaders(full)

        if (!text) {
          logWarn('empty ' + method + ' ' + opts.url +
                  ' payload=' + describe(payload) + ' raw=' + describe(raw))
          finish({ ok: false, error: 'empty response', status: status, text: '' })
          return
        }

        var data = null
        try {
          data = JSON.parse(text)
        } catch (e) {
          logError('badjson ' + opts.url + ' head=' + text.substring(0, 100))
          finish({ ok: false, error: 'bad json', status: status, text: text })
          return
        }

        // 成功判定：能解析出 JSON 就算成功，除非显式 ok:false 或状态码 >= 400。
        // 注意有的接口（如 /api/wishes）不带 ok 字段，且响应可能没有 HTTP 状态行。
        var okFlag = true
        if (data && typeof data === 'object' && data.ok === false) okFlag = false
        else if (status >= 400) okFlag = false

        finish({ ok: okFlag, status: status, text: text, data: data })
      }, function (err) {
        var msg = (err && (err.message || err.msg)) ? (err.message || err.msg) : String(err)
        var code = err && (err.code || err.status)
        logError(method + ' ' + opts.url + ' rejected ' + msg + (code ? ' code=' + code : ''))
        finish({ ok: false, error: 'rejected:' + msg })
      })
    } catch (e) {
      logError(method + ' ' + opts.url + ' throw ' + (e && e.message))
      finish({ ok: false, error: 'throw:' + ((e && e.message) || e) })
    }
  })
}

// ---------------- URL 拼接 ----------------
export function buildUrl(base, path, params) {
  var u = String(base || '').replace(/\/+$/, '') + path
  if (!params) return u
  var parts = []
  for (var k in params) {
    if (!Object.prototype.hasOwnProperty.call(params, k)) continue
    if (params[k] === null || params[k] === undefined) continue
    try {
      parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(String(params[k])))
    } catch (e) {
      parts.push(k + '=' + params[k])
    }
  }
  if (parts.length) u += (u.indexOf('?') >= 0 ? '&' : '?') + parts.join('&')
  return u
}

// ---------------- 业务层：GET 优先 ----------------
function once(base, path, params, timeout, headers) {
  var url = buildUrl(base, path, params)
  var opts = { url: url, method: 'GET', timeout: timeout }
  if (headers) opts.headers = headers
  return request(opts).then(function (r) {
    if (r.ok) {
      logInfo('GET ' + path + ' -> ' + (r.text ? r.text.length : 0) + 'B ' + r.ms + 'ms')
    } else {
      logWarn('GET ' + path + ' failed: ' + (r.error || ('status ' + r.status)) + ' ' + r.ms + 'ms')
    }
    return r
  })
}

export function ensureBase() {
  if (_chosen) return Promise.resolve(_chosen)
  if (_probing) return _probing

  var idx = 0
  var list = ENDPOINTS.slice(0)

  function next() {
    if (idx >= list.length) {
      _probing = null
      logError('all endpoints unreachable')
      return Promise.reject(new Error('no reachable endpoint'))
    }
    var base = list[idx++]
    return once(base, '/healthz', null, 6).then(function (r) {
      // 能解析出 JSON 就算该地址可用（不强求 body 里带 ok 字段）
      if (r.ok && r.data && r.data.ok !== false) {
        _chosen = base
        API_BASE = base
        _probing = null
        logInfo('endpoint chosen: ' + base)
        return base
      }
      logWarn('endpoint rejected: ' + base + ' (' + (r.error || 'bad payload') + ')')
      return next()
    })
  }

  _probing = next()
  return _probing
}

/**
 * 统一的 GET 调用（写操作也走这里，因为 POST body 不可靠）。
 * 返回 data；失败 throw。
 */
export function call(path, params, timeout, headers) {
  return ensureBase().then(function (base) {
    return once(base, path, params, timeout, headers)
  }).then(function (r) {
    if (r.ok && r.data) return r.data
    if (r.ok) return {}

    // 地址可能失效：重选后重试一次
    if (!r.data) {
      logWarn('retry ' + path + ' reason=' + (r.error || ''))
      _chosen = ''
      return ensureBase().then(function (base) {
        return once(base, path, params, timeout, headers)
      }).then(function (r2) {
        if (r2.ok && r2.data) return r2.data
        throw new Error(r2.error || 'request failed')
      })
    }
    throw new Error(r.error || 'request failed')
  })
}

export function get(path, params, timeout) { return call(path, params, timeout) }

/** 写操作：GET + query（真机 POST body 会丢） */
export function send(path, params, timeout, headers) {
  return call(path, params, timeout, headers)
}

/** 带管理密码的写操作 */
export function sendAdmin(path, params, timeout, adminPass) {
  var headers = ['Accept:application/json', 'X-Admin-Pass:' + (adminPass || '')]
  return call(path, params, timeout, headers)
}

// ---------------- 本地存储 ----------------
function getStorage() {
  try {
    if ($falcon && $falcon.jsapi && $falcon.jsapi.storage) return $falcon.jsapi.storage
  } catch (e) { /* ignore */ }
  try { return require('storage') } catch (e) { return null }
}

export function storageGet(key) {
  var s = getStorage()
  if (!s || typeof s.getStorage !== 'function') return Promise.resolve('')
  return s.getStorage(key).then(function (v) {
    return v === null || v === undefined ? '' : v
  }).catch(function () { return '' })
}

export function storageSet(key, val) {
  var s = getStorage()
  if (!s || typeof s.setStorage !== 'function') return Promise.resolve(false)
  return s.setStorage(key, val).then(function () { return true }).catch(function () { return false })
}

// ---------------- 设备标识 ----------------
var _cid = ''

export function clientId() {
  if (_cid) return Promise.resolve(_cid)
  return storageGet('wish_cid').then(function (v) {
    if (v && typeof v === 'string' && v.length > 3) {
      _cid = v
      return v
    }
    var nid = 'pen_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
    _cid = nid
    storageSet('wish_cid', nid)
    return nid
  })
}

export function cachedClientId() { return _cid }

// ---------------- 日志上报 ----------------
/**
 * 走 GET + query 上报最近日志（真机 POST body 会丢）。
 * 限 40 行、每行 110 字符，保证 URL 不超长。
 */
export function reportLogs(sn, cid, version, linesText, extra) {
  var text = linesText || ''
  if (extra) {
    var t = Math.floor(Date.now() / 1000)
    text += '\n' + t + '|info|meta: ' + extra
  }
  var params = {
    sn: sn || '',
    client_id: cid || '',
    version: version || '',
    lines: text
  }
  return call('/api/log', params, 15).then(function (d) {
    logInfo('logs reported ok=' + (d && d.ok ? d.received : '?'))
    return !!(d && d.ok)
  }).catch(function (e) {
    logWarn('logs report failed: ' + (e && e.message))
    return false
  })
}
