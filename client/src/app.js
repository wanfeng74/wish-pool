/**
 * 许愿池 · 笔端 App 入口
 *
 * 设备：有道词典笔（YDPX7 / X7 Pro 等，RK3562）
 * 设计基准：960 × 266 逻辑分辨率（横屏超宽短屏）
 * 视口：setViewPort(960)，横向 1 设计 px ≈ 0.10417vw
 */
import { pageSize, describeScreen } from './services/screen.js'

class App extends $falcon.App {
  constructor() {
    super()
  }

  onLaunch(options) {
    super.onLaunch(options)

    // 把 960 设计宽映射到设备物理宽，容器据此等比缩放
    this.setViewPort(960)

    var s = pageSize()
    this.screenInfo = {
      designWidth: 960,
      renderWidth: s.w,
      renderHeight: s.h,
      screenWidth: s.w,
      screenHeight: s.h,
      physicalW: s.physicalW,
      physicalH: s.physicalH,
      compact: s.compact
    }

    console.log('[wish] launch ' + describeScreen(s) + ' compact=' + s.compact)
  }

  onShow() { super.onShow() }
  onHide() { super.onHide() }
  onDestroy() { super.onDestroy() }
}

// QuickJS 环境补齐：部分库会引用 window / process
try {
  globalThis['window'] = {
    requestAnimationFrame: typeof requestAnimationFrame !== 'undefined'
      ? requestAnimationFrame
      : function (cb) { return setTimeout(cb, 16) },
    cancelAnimationFrame: typeof cancelAnimationFrame !== 'undefined'
      ? cancelAnimationFrame
      : function (id) { clearTimeout(id) }
  }
} catch (err) { console.log(err) }

try {
  globalThis['process'] = { env: { NODE_ENV: 'production' } }
} catch (err) { console.log(err) }

export default App
