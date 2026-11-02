/**
 * 许愿池 · 日志系统
 *
 * 三层：
 *   1) console —— 便于接 Chrome/真机调试
 *   2) 本地持久化（storage KV，容量稳、不用碰 fs 权限）
 *   3) 上报服务端 POST /api/log —— 不用 adb 也能远程看日志
 *
 * 用法：
 *   import { log, logInfo, logWarn, logError, recent, report, setContext } from './logger.js'
 */

var LOG_KEY = 'wish_log_v1'
var MAX_LINES = 220          // 本地保留条数
var MAX_LINE_LEN = 400

var buf = []                 // [{t,l,m}]
var loaded = false
var persistTimer = null
var seq = 0
var ctx = { sn: '', client_id: '', version: '1.0.0' }

// ---------------- 基础 ----------------
function now() {
  return Math.floor(Date.now() / 1000)
}

function pad(n) {
  return n < 10 ? '0' + n : '' + n
}

function stamp(t) {
  var d = new Date(t * 1000)
  return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds())
}

function clip(s) {
  s = (s === null || s === undefined) ? '' : String(s)
  return s.length > MAX_LINE_LEN ? s.substring(0, MAX_LINE_LEN) + '…' : s
}

function storage() {
  try {
    if ($falcon && $falcon.jsapi && $falcon.jsapi.storage) return $falcon.jsapi.storage
  } catch (e) { /* ignore */ }
  try { return require('storage') } catch (e) { return null }
}

// ---------------- 持久化 ----------------
function persist() {
  var st = storage()
  if (!st || typeof st.setStorage !== 'function') return
  try {
    var payload = JSON.stringify(buf.slice(-MAX_LINES))
    st.setStorage(LOG_KEY, payload).catch(function () { /* ignore */ })
  } catch (e) { /* ignore */ }
}

function schedulePersist() {
  if (persistTimer) return
  persistTimer = setTimeout(function () {
    persistTimer = null
    persist()
  }, 1200)
}

export function loadHistory() {
  if (loaded) return Promise.resolve(buf)
  loaded = true
  var st = storage()
  if (!st || typeof st.getStorage !== 'function') return Promise.resolve(buf)
  return st.getStorage(LOG_KEY).then(function (v) {
    if (v && typeof v === 'string') {
      try {
        var arr = JSON.parse(v)
        if (arr && arr.length) buf = arr.slice(-MAX_LINES)
      } catch (e) { /* ignore */ }
    }
    return buf
  }).catch(function () { return buf })
}

// ---------------- 写日志 ----------------
function push(level, msg) {
  var line = { t: now(), l: level, m: clip(msg), s: ++seq }
  buf.push(line)
  if (buf.length > MAX_LINES) buf = buf.slice(-MAX_LINES)

  try {
    console.log('[' + stamp(line.t) + '][' + level + '] ' + line.m)
  } catch (e) { /* ignore */ }

  schedulePersist()
  return line
}

export function logInfo(msg) { return push('info', msg) }
export function logWarn(msg) { return push('warn', msg) }
export function logError(msg) { return push('error', msg) }
export var log = logInfo

export function setContext(o) {
  if (!o) return
  if (o.sn !== undefined) ctx.sn = o.sn
  if (o.client_id !== undefined) ctx.client_id = o.client_id
  if (o.version !== undefined) ctx.version = o.version
}

// ---------------- 读取 ----------------
export function recent(n) {
  n = n || 60
  return buf.slice(-n)
}

export function asText(n) {
  return recent(n).map(function (x) {
    return stamp(x.t) + ' [' + x.l + '] ' + x.m
  }).join('\n')
}

export function clear() {
  buf = []
  loaded = true
  persist()
}

// ---------------- 上报素材 ----------------
/**
 * 导出最近 n 条为 "t|l|m" 行，供 GET 上报用（真机 POST body 不可靠）。
 * 单行截断，避免 URL 过长。
 */
export function exportLines(n, maxLenPerLine) {
  n = n || 40
  maxLenPerLine = maxLenPerLine || 110
  var arr = recent(n).map(function (x) {
    var m = x.m.length > maxLenPerLine ? x.m.substring(0, maxLenPerLine) : x.m
    return x.t + '|' + x.l + '|' + m
  })
  return arr.join('\n')
}

export function context() {
  return { sn: ctx.sn || '', client_id: ctx.client_id || '', version: ctx.version || '' }
}
