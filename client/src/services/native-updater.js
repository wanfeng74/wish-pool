/**
 * 应用更新 · 下载与安装
 *
 * 平台没有把「安装」暴露成 JS 接口，唯一途径是命令行
 *     /usr/bin/miniapp_cli install <amr>
 * 而且平台的 jsapi.http.downloadFile 在这个固件上会挂住不 resolve。
 *
 * 所以走「三角洲摸金」验证过的原生模块 `updater`（libs/libjsapi_updater.so）：
 *     download(url, path) -> 0          # 内部用 /usr/bin/curl，会先建目录
 *     install(amrPath)    -> 0          # fork + execv miniapp_cli install
 *     start(appid)        -> 0          # miniapp_cli start
 *
 * 【重要】原生模块必须动态 require，禁止静态 import ——
 * 静态 import 在模块求值前就要解析，包内没有 .so 时整条链抛错、页面黑屏。
 *
 * 原生不可用时退回「手动安装」：把包下载到 userdisk 并提示用户点一下。
 */

import { logInfo, logWarn, logError } from './logger.js'

/* 纯 ASCII 路径：真机上中文路径会让下载永不 resolve */
export var DL_DIR = '/userdisk/wishpool'
export var APP_ID = '8001865309000101'

var _mod = null
var _probed = false

/** 懒加载原生 updater 模块，拿不到返回 null */
export function nativeModule() {
  if (_probed) return _mod
  _probed = true
  try {
    if (typeof require === 'function') {
      var m = require('updater')
      if (m) _mod = m
    }
  } catch (e) {
    logWarn('updater native module unavailable: ' + (e && e.message))
    _mod = null
  }
  logInfo('updater native: ' +
          (_mod
            ? ('download=' + typeof _mod.download + ' install=' + typeof _mod.install + ' start=' + typeof _mod.start)
            : 'none'))
  return _mod
}

export function canDownload() {
  var m = nativeModule()
  return !!(m && typeof m.download === 'function')
}

export function canInstall() {
  var m = nativeModule()
  return !!(m && typeof m.install === 'function')
}

export function canStart() {
  var m = nativeModule()
  return !!(m && typeof m.start === 'function')
}

function _toInt(v) {
  var n = Number(v)
  return isFinite(n) ? n : -999
}

/**
 * 下载安装包。
 * -> { ok, path, error }
 */
export function download(url, fileName) {
  var m = nativeModule()
  if (!m || typeof m.download !== 'function') {
    return { ok: false, error: 'native-unavailable' }
  }
  var name = fileName || ('wishpool-update.amr')
  var path = DL_DIR + '/' + name
  try {
    var r = _toInt(m.download(url, path))
    if (r === 0) {
      logInfo('download ok: ' + path)
      return { ok: true, path: path }
    }
    logError('download failed code=' + r + ' url=' + url)
    return { ok: false, error: 'code ' + r }
  } catch (e) {
    logError('download throw: ' + (e && e.message))
    return { ok: false, error: (e && e.message) || 'throw' }
  }
}

/** 安装已下载的包 -> { ok, error } */
export function install(path) {
  var m = nativeModule()
  if (!m || typeof m.install !== 'function') {
    return { ok: false, error: 'native-unavailable' }
  }
  try {
    var r = _toInt(m.install(path))
    if (r === 0) {
      logInfo('install ok: ' + path)
      return { ok: true }
    }
    logError('install failed code=' + r)
    return { ok: false, error: 'code ' + r }
  } catch (e) {
    logError('install throw: ' + (e && e.message))
    return { ok: false, error: (e && e.message) || 'throw' }
  }
}

/** 启动（或重启）应用 */
export function start() {
  var m = nativeModule()
  if (!m || typeof m.start !== 'function') return { ok: false, error: 'native-unavailable' }
  try {
    var r = _toInt(m.start(APP_ID))
    return { ok: r === 0, error: r === 0 ? '' : ('code ' + r) }
  } catch (e) {
    return { ok: false, error: (e && e.message) || 'throw' }
  }
}

export function capability() {
  return {
    download: canDownload(),
    install: canInstall(),
    start: canStart()
  }
}
