/**
 * 应用更新 · 检查与版本比较
 *
 * 参照「三角洲摸金」updater.js：
 *   - 版本号按数字段比较（避免 '1.2.9' > '1.2.10' 的字符串比较陷阱）
 *   - 是否强制以服务端为准，客户端不加码
 *   - 永不 throw，失败一律返回结构化结果
 */

import { logInfo, logWarn } from './logger.js'
import { get } from './api.js'

export var APP_VERSION = '1.3.0'
export var PLATFORM = 'rk'

/** '1.2.10' -> [1,2,10] */
export function verTuple(v) {
  var s = String(v === null || v === undefined ? '' : v)
  var parts = s.split('.')
  var out = []
  for (var i = 0; i < parts.length && i < 4; i++) {
    var n = 0
    var p = parts[i]
    for (var k = 0; k < p.length; k++) {
      var c = p.charAt(k)
      if (c >= '0' && c <= '9') n = n * 10 + (c.charCodeAt(0) - 48)
      else break
    }
    out.push(n)
  }
  while (out.length < 3) out.push(0)
  return out.slice(0, 3)
}

/** a 比 b 新 -> 正数；相同 -> 0；更旧 -> 负数 */
export function compareVer(a, b) {
  var x = verTuple(a)
  var y = verTuple(b)
  for (var i = 0; i < 3; i++) {
    if (x[i] !== y[i]) return x[i] - y[i]
  }
  return 0
}

export function hasUpdate(resp, currentVersion) {
  if (!resp || resp.ok === false || !resp.hasUpdate) return false
  var latest = resp.latest && resp.latest.version
  if (!latest) return false
  return compareVer(latest, currentVersion) > 0
}

export function isForced(resp, currentVersion) {
  if (!hasUpdate(resp, currentVersion)) return false
  return Number(resp.force) === 1
}

export function fmtSize(bytes) {
  var n = Number(bytes) || 0
  if (n <= 0) return ''
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(2) + ' MB'
}

/**
 * 查询更新。永不 reject。
 * -> { ok, hasUpdate, forced, latest }
 */
export function checkUpdate(currentVersion) {
  var cv = currentVersion || APP_VERSION
  return get('/app-update', { version: cv, platform: PLATFORM }, 8)
    .then(function (d) {
      if (!d) return { ok: false, hasUpdate: false }
      var up = hasUpdate(d, cv)
      var forced = up && Number(d.force) === 1
      logInfo('update check: current=' + cv + ' latest=' +
              ((d.latest && d.latest.version) || '-') + ' hasUpdate=' + up + ' force=' + forced)
      return { ok: true, hasUpdate: up, forced: forced, latest: d.latest || null }
    })
    .catch(function (e) {
      logWarn('update check failed: ' + (e && e.message))
      return { ok: false, hasUpdate: false }
    })
}
