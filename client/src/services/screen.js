/**
 * 许愿池 · 屏幕信息
 *
 * 设计基准 960 宽（setViewPort(960)），逻辑高由物理分辨率反算：
 *   logicalHeight = round(960 × 短边 / 长边)
 * 参考：y02-1 物理 936×280 → 逻辑 960×287
 */
var DESIGN_W = 960

export function pageSize() {
  var pw = 0
  var ph = 0

  try {
    var env = ($falcon && $falcon.env) ? $falcon.env : null
    if (env) {
      pw = Number(env.deviceWidth) || 0
      ph = Number(env.deviceHeight) || 0
    }
  } catch (e) { /* ignore */ }

  if (!valid(pw) || !valid(ph)) {
    try {
      if (typeof window !== 'undefined' && window.innerWidth) {
        pw = window.innerWidth
        ph = window.innerHeight
      }
    } catch (e) { /* ignore */ }
  }
  if (!valid(pw) || !valid(ph)) {
    try {
      var de = document.documentElement
      if (de && de.clientWidth) { pw = de.clientWidth; ph = de.clientHeight }
    } catch (e) { /* ignore */ }
  }
  if (!valid(pw) || !valid(ph)) { pw = 936; ph = 280 }

  var shortSide = Math.min(pw, ph)
  var longSide = Math.max(pw, ph)
  var h = Math.round(DESIGN_W * shortSide / longSide)
  if (!valid(h) || h < 120) h = 266

  return {
    w: DESIGN_W,
    h: h,
    physicalW: pw,
    physicalH: ph,
    compact: h < 262,
    source: (pw && ph) ? 'env' : 'fallback'
  }
}

function valid(v) { return typeof v === 'number' && v >= 100 && v <= 5000 }

export function describeScreen(s) {
  return '逻辑 ' + s.w + '×' + s.h + ' · 物理 ' + s.physicalW + '×' + s.physicalH + ' · ' + s.source
}
