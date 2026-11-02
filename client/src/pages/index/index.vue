<template>
  <div class="page"
       @touchstart="onDocTouchStart"
       @touchmove="onDocTouchMove"
       @touchend="onDocTouchEnd">

    <!-- ==================== 顶栏 ==================== -->
    <div class="hd">
      <div class="brand">
        <div class="logo">
          <image class="logo-img" src="assets/icons/star.png" mode="aspectFit"></image>
        </div>
        <div class="brand-txt">
          <text class="app-name">许愿池</text>
          <text class="app-sub">说吧，你想要什么</text>
        </div>
      </div>

      <div class="hd-mid">
        <div :class="online ? 'live live-on' : 'live'">
          <div :class="online ? 'live-dot live-dot-on' : 'live-dot'"></div>
          <text :class="online ? 'live-txt live-txt-on' : 'live-txt'">{{ online ? '实时' : '离线' }}</text>
        </div>
        <div class="stat-mini">
          <text class="stat-mini-n">{{ stats.votes }}</text>
          <text class="stat-mini-k">人支持</text>
        </div>
        <div class="stat-mini">
          <text class="stat-mini-n">{{ stats.wishes }}</text>
          <text class="stat-mini-k">个愿望</text>
        </div>
      </div>

      <div class="hd-right">
        <div class="seg">
          <div :class="sort === 'votes' ? 'seg-i seg-i-on' : 'seg-i'" @touchstart="setSort('votes')">
            <image class="seg-ico" src="assets/icons/fire.png" mode="aspectFit"></image>
            <text :class="sort === 'votes' ? 'seg-txt seg-txt-on' : 'seg-txt'">最想要</text>
          </div>
          <div :class="sort === 'new' ? 'seg-i seg-i-on' : 'seg-i'" @touchstart="setSort('new')">
            <image class="seg-ico" src="assets/icons/clock.png" mode="aspectFit"></image>
            <text :class="sort === 'new' ? 'seg-txt seg-txt-on' : 'seg-txt'">最新</text>
          </div>
        </div>
        <div :class="loading ? 'btn-refresh btn-refresh-on' : 'btn-refresh'" @touchstart="refresh">
          <image class="btn-refresh-img" src="assets/icons/refresh.png" mode="aspectFit"></image>
        </div>
      </div>
    </div>

    <!-- ==================== 列表 ==================== -->
    <scroller class="list-area" scrollDirection="vertical">
      <div v-if="loading && rows.length === 0" class="state">
        <text class="state-txt">正在加载愿望…</text>
      </div>

      <div v-if="!loading && rows.length === 0" class="state">
        <image class="state-img" src="assets/icons/moon.png" mode="aspectFit"></image>
        <text class="state-txt">{{ online ? '还没有愿望' : '连不上服务器' }}</text>
        <text class="state-sub">{{ online ? '点右下角「许愿」第一个上墙' : '点「日志」查看诊断信息' }}</text>
      </div>

      <div v-for="(w, i) in rows" :key="w.id" class="row">
        <div :class="cardClass(w, i)" @touchend="onCardTap(w, $event)">
          <div :class="rankBoxClass(i)">
            <image v-if="i === 0" class="rk-medal" src="assets/icons/crown.png" mode="aspectFit"></image>
            <image v-else-if="i === 1" class="rk-medal" src="assets/icons/medal2.png" mode="aspectFit"></image>
            <image v-else-if="i === 2" class="rk-medal" src="assets/icons/medal3.png" mode="aspectFit"></image>
            <text v-else class="rk-n">{{ i + 1 }}</text>
          </div>

          <div class="bd">
            <text :class="i === 0 ? 'tt tt-top' : 'tt'">{{ w.title }}</text>
            <div class="meta">
              <text class="who">{{ w.nick || '匿名笔友' }}</text>
              <text class="dot-sep">·</text>
              <div :class="'cat ' + catClass(w.category)">
                <text :class="'cat-txt ' + catTxtClass(w.category)">{{ catName(w.category) }}</text>
              </div>
              <div v-if="w.status && w.status !== 'open'" :class="'st ' + statusBg(w.status)">
                <text :class="'st-txt ' + statusTxt(w.status)">{{ statusName(w.status) }}</text>
              </div>
              <text class="dot-sep">·</text>
              <text class="ago">{{ ago(w.created_at) }}</text>
              <div v-if="w.claimed" :class="w.claim_mine ? 'claim claim-mine' : 'claim'">
                <image class="claim-img" src="assets/icons/flag.png" mode="aspectFit"></image>
                <text :class="w.claim_mine ? 'claim-txt claim-txt-mine' : 'claim-txt'">{{ w.claim_mine ? '我认领' : w.claimed_by }}</text>
              </div>
            </div>
          </div>

          <div :class="w.voted ? 'vote vote-voted' : 'vote'" @touchend.stop="onVoteTap(w, $event)">
            <image class="vote-img" :src="w.voted ? 'assets/icons/check.png' : 'assets/icons/plus.png'" mode="aspectFit"></image>
            <text :class="w.voted ? 'vote-n vote-n-voted' : 'vote-n'">{{ w.votes }}</text>
          </div>
        </div>
      </div>

      <div class="list-pad"></div>
    </scroller>

    <!-- ==================== 底栏 ==================== -->
    <div class="ft">
      <text class="ft-hint">所有人可见 · 一起 +1</text>
      <text class="ft-log" @touchend="openDiag">日志</text>
      <text class="ft-upd" @touchend="checkUpdate(false)">更新</text>
      <text class="ft-count">{{ rows.length }} 个愿望</text>
      <div class="btn-wish" @touchend="openCompose">
        <text class="btn-wish-txt">＋ 许愿</text>
      </div>
    </div>

    <!-- ==================== 许愿面板 ==================== -->
    <div class="mask" v-if="view === 'compose'" @touchstart="onMaskTouch" @touchmove="onMaskTouch" @touchend="onMaskTouch">
      <div class="compose">
        <div class="cp-hd">
          <image class="cp-title-img" src="assets/icons/star-sm.png" mode="aspectFit"></image>
          <text class="cp-title">许个愿</text>
          <text class="cp-sub">选一个最接近的，或自己写</text>
          <div class="cp-close" @touchstart="closeCompose">
            <image class="cp-close-img" src="assets/icons/close.png" mode="aspectFit"></image>
          </div>
        </div>

        <div class="cp-cats">
          <div v-for="(c, ci) in categories" :key="'c' + ci"
               :class="ci === catIdx ? 'cp-cat cp-cat-on' : 'cp-cat'"
               @touchstart="pickCat(ci)">
            <text :class="ci === catIdx ? 'cp-cat-txt cp-cat-txt-on' : 'cp-cat-txt'">{{ c.name }}</text>
          </div>
        </div>

        <scroller class="cp-list" scrollDirection="vertical">
          <div class="cp-grid">
            <div v-for="(p, pi) in presets" :key="'p' + pi"
                 :class="selTitle === p ? 'preset preset-on' : 'preset'"
                 @touchstart="pickPreset(p)">
              <text :class="selTitle === p ? 'preset-txt preset-txt-on' : 'preset-txt'">{{ p }}</text>
            </div>
            <div :class="customMode ? 'preset preset-on' : 'preset'" @touchstart="openKeyboard">
              <image class="preset-ico" src="assets/icons/pencil.png" mode="aspectFit"></image>
              <text :class="customMode ? 'preset-txt preset-txt-on' : 'preset-txt'">自己写</text>
            </div>
          </div>
        </scroller>

        <div class="cp-ft">
          <text class="cp-tip">{{ tipText }}</text>
          <div :class="submitting ? 'cp-submit cp-submit-dis' : 'cp-submit'" @touchstart="submit">
            <text :class="submitting ? 'cp-submit-txt cp-submit-txt-dis' : 'cp-submit-txt'">{{ submitting ? '发送中…' : '发布' }}</text>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 详情面板 ==================== -->
    <div class="mask" v-if="view === 'detail'" @touchstart="onMaskTouch" @touchmove="onMaskTouch" @touchend="onMaskTouch">
      <div class="detail">
        <div class="dt-hd">
          <text class="dt-title">{{ detail.title }}</text>
          <div class="cp-close" @touchstart="closeDetail">
            <image class="cp-close-img" src="assets/icons/close.png" mode="aspectFit"></image>
          </div>
        </div>
        <scroller class="dt-body" scrollDirection="vertical">
          <text class="dt-desc">{{ detail.desc || '（这位笔友没有留下更多描述）' }}</text>
          <div class="dt-meta-row">
            <div v-if="detail.status && detail.status !== 'open'" :class="'st ' + statusBg(detail.status)">
              <text :class="'st-txt ' + statusTxt(detail.status)">{{ statusName(detail.status) }}</text>
            </div>
            <text class="dt-meta">{{ detail.nick }} · {{ catName(detail.category) }} · {{ ago(detail.created_at) }}</text>
          </div>
        </scroller>
        <div class="dt-ft">
          <text class="dt-votes">{{ detail.votes }} 人支持</text>
          <div :class="detail.claimed ? 'dt-claim dt-claim-on' : 'dt-claim'" @touchend="toggleClaim">
            <image class="dt-claim-img" src="assets/icons/flag.png" mode="aspectFit"></image>
            <text :class="detail.claimed ? 'dt-claim-txt dt-claim-txt-on' : 'dt-claim-txt'">{{ claimBtnText }}</text>
          </div>
          <div :class="detail.voted ? 'dt-vote dt-vote-voted' : 'dt-vote'" @touchend="onVoteTap(detail, $event)">
            <image class="dt-vote-img" :src="detail.voted ? 'assets/icons/check.png' : 'assets/icons/plus.png'" mode="aspectFit"></image>
            <text :class="detail.voted ? 'dt-vote-txt dt-vote-txt-voted' : 'dt-vote-txt'">{{ detail.voted ? '已支持' : '1 支持' }}</text>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 内置输入法 ==================== -->
    <div class="kb-mask" v-if="kbOpen" @touchstart="onMaskTouch" @touchmove="onMaskTouch" @touchend="onMaskTouch">
      <div class="kb">
        <div class="kb-hd">
          <text class="kb-title">{{ kbTargetName }}</text>
          <div class="kb-valbox">
            <text :class="kbDisplay ? 'kb-val' : 'kb-val kb-val-ph'">{{ kbDisplay || kbPlaceholder }}</text>
          </div>
          <text class="kb-len">{{ kbLen }}/{{ kbLimit }}</text>
          <div class="kb-close" @touchend="kbClose">
            <image class="kb-close-img" src="assets/icons/close.png" mode="aspectFit"></image>
          </div>
        </div>
        <div class="kb-keys">
          <div v-for="(krow, ri) in kbKeysRows" :key="'k' + ri" class="kb-row">
            <div v-for="(k, ki) in krow" :key="'kk' + ki"
                 :class="'kb-key ' + k.cls"
                 @touchend="kbPress(k.v)">
              <text :class="'kb-txt ' + (k.txtCls || '')">{{ k.label }}</text>
            </div>
          </div>
        </div>
        <div class="kb-ft">
          <div class="kb-cancel" @touchend="kbClose">
            <text class="kb-cancel-txt">取消</text>
          </div>
          <div class="kb-ok" @touchend="kbDone">
            <text class="kb-ok-txt">确定</text>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 日志诊断 ==================== -->
    <div class="mask" v-if="view === 'diag'" @touchstart="onMaskTouch" @touchmove="onMaskTouch" @touchend="onMaskTouch">
      <div class="diag">
        <div class="cp-hd">
          <text class="cp-title">运行日志</text>
          <text class="cp-sub">{{ diagInfo }}</text>
          <div class="cp-close" @touchstart="closeDiag">
            <image class="cp-close-img" src="assets/icons/close.png" mode="aspectFit"></image>
          </div>
        </div>
        <scroller class="diag-list" scrollDirection="vertical">
          <text class="diag-line" v-for="(l, li) in logLines" :key="'l' + li">{{ l }}</text>
          <text class="diag-empty" v-if="logLines.length === 0">还没有日志</text>
        </scroller>
        <div class="cp-ft">
          <text class="cp-tip">{{ reportTip }}</text>
          <div class="dt-claim" @touchstart="doReport">
            <text class="dt-claim-txt">上报日志</text>
          </div>
          <div class="cp-submit" @touchstart="closeDiag">
            <text class="cp-submit-txt">关闭</text>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 更新提示 ==================== -->
    <div class="mask" v-if="updateState !== 'idle'"
         @touchstart="onMaskTouch" @touchmove="onMaskTouch" @touchend="onMaskTouch">
      <div class="upd">
        <div class="upd-hd">
          <text class="upd-title">{{ updateTitle }}</text>
          <text class="upd-ver">v{{ updateInfo.version || '' }}</text>
          <div v-if="updClosable" class="cp-close upd-close" @touchend="closeUpdate">
            <image class="cp-close-img" src="assets/icons/close.png" mode="aspectFit"></image>
          </div>
        </div>

        <div class="upd-meta">
          <text class="upd-meta-txt">{{ updateSizeText }}</text>
          <text class="upd-meta-txt" v-if="updateForced">强制更新</text>
        </div>

        <scroller class="upd-notes" scrollDirection="vertical">
          <text class="upd-notes-txt">{{ updateNotes }}</text>
        </scroller>

        <text class="upd-state">{{ updateMsg }}</text>

        <div class="upd-ft">
          <div v-if="updClosable" class="upd-later" @touchend="closeUpdate">
            <text class="upd-later-txt">稍后</text>
          </div>
          <div v-if="updateState === 'available' || updateState === 'error'" class="upd-go" @touchend="startUpdate">
            <text class="upd-go-txt">{{ updateState === 'error' ? '重试' : '立即更新' }}</text>
          </div>
          <div v-if="updateState === 'done'" class="upd-go" @touchend="restartApp">
            <text class="upd-go-txt">重启应用</text>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== Toast ==================== -->
    <div class="toast" v-if="toastShow">
      <text class="toast-txt">{{ toastText }}</text>
    </div>
  </div>
</template>

<script>
import { pageSize, describeScreen } from '../../services/screen.js'
import {
  get, send, sendAdmin, clientId, storageGet, storageSet,
  currentBase, ENDPOINTS, reportLogs, networkKind
} from '../../services/api.js'
import {
  logInfo, logWarn, logError, recent, setContext,
  loadHistory, exportLines, context
} from '../../services/logger.js'
import { pinyinCandidates } from '../../services/pinyin.js'
import { checkUpdate as updCheck, fmtSize, APP_VERSION } from '../../services/updater.js'
import {
  download as nativeDownload,
  install as nativeInstall,
  start as nativeStart,
  capability as nativeCapability
} from '../../services/native-updater.js'

var CATEGORIES = [
  { id: 'app', name: '新App' },
  { id: 'feat', name: '功能' },
  { id: 'game', name: '游戏' },
  { id: 'read', name: '学习' },
  { id: 'system', name: '系统' },
  { id: 'other', name: '其它' }
]

var PRESETS = {
  app: ['笔上哔哩哔哩', '笔上QQ音乐', '笔上微信', '笔上番茄小说', '笔上我的世界', '笔上浏览器', '笔上计算器', '笔上知乎'],
  feat: ['下载与离线缓存', '收藏与追更列表', '断点续读', '笔记一键导出', '局域网文件快传', '批量翻译', '长截图', '悬浮字幕'],
  game: ['五子棋人机对战', '俄罗斯方块', '贪吃蛇', '2048', '斗地主', '扫雷'],
  read: ['单词背诵计划', '错题本自动归档', '练字打分', '口语跟读评分', '课文朗读', '生词本同步'],
  system: ['桌面小组件', '锁屏时钟', '深色主题', '更好的音量控制', '自定义壁纸', '手势快捷操作'],
  other: ['我想要的功能', '这里缺了点什么']
}

var VERSION = APP_VERSION

// 愿望状态（与服务端 STATUSES 对应）
var STATUSES = {
  open: { name: '待认领', bg: 'st-open', txt: 'st-txt-open' },
  doing: { name: '开发中', bg: 'st-doing', txt: 'st-txt-doing' },
  done: { name: '已上线', bg: 'st-done', txt: 'st-txt-done' },
  rejected: { name: '暂不做', bg: 'st-rejected', txt: 'st-txt-rejected' }
}

var KB_KEYS_ABC = ['qwertyuiop', 'asdfghjkl', 'zxcvbnm']
var KB_KEYS_NUM = ['1234567890', '-_.@#!$%:/']

// 输入目标 -> 标题 / 占位 / 长度上限
var KB_TARGETS = {
  title: { name: '写愿望', ph: '一句话说清你的愿望', limit: 40 },
  nick: { name: '认领昵称', ph: '你的昵称', limit: 20 },
  pass: { name: '管理密码', ph: '输入管理密码', limit: 32 }
}

// 滚动防误触：位移超过该阈值（逻辑 px）视为滑动，不触发点击
var TAP_MOVE_LIMIT = 14
var TAP_MAX_MS = 900

// 自动刷新
var POLL_MS = 5000          // 轮询间隔
var BOOT_REFRESH_MS = 5000  // 启动后 5 秒再补刷一次（兜底首次失败）
var STALE_MS = 5000         // 关闭面板后超过该时长则补刷
var BOOT_RETRIES = 4        // 启动连接失败重试次数

/** 从触摸事件里取坐标，兼容 touches / changedTouches / clientX / pageX */
function pickTouch(e, phase) {
  var list = null
  if (e) {
    if (phase === 'move' || phase === 'start') list = e.touches || e.targetTouches
    if (!list || !list.length) list = e.changedTouches
  }
  var t = list && list.length ? list[0] : e
  var x = 0
  var y = 0
  if (t) {
    x = num(t.clientX, num(t.pageX, num(t.screenX, 0)))
    y = num(t.clientY, num(t.pageY, num(t.screenY, 0)))
  }
  return { x: x, y: y }
}

function num(v, dflt) {
  var n = Number(v)
  return isFinite(n) ? n : dflt
}

export default {
  data() {
    return {
      screen: pageSize(),
      rows: [],
      stats: { wishes: 0, votes: 0, today: 0, contributors: 0, claimed: 0 },
      sort: 'votes',
      online: false,
      loading: false,

      view: 'list',
      detail: {},
      detailId: 0,

      categories: CATEGORIES,
      catIdx: 0,
      presets: PRESETS.app,
      selTitle: '',
      customMode: false,
      submitting: false,

      kbOpen: false,
      kbTarget: 'title',
      kbValue: '',
      kbShift: false,
      kbMode: 'abc',        // abc | py | num | cn
      kbPinyin: '',
      kbCand: [],
      kbCandActive: -1,

      nick: '',
      adminPass: '',
      toastShow: false,
      toastText: '',
      cid: '',

      logLines: [],
      diagInfo: '',
      reportTip: '',

      // 更新
      updateState: 'idle',      // idle | available | downloading | installing | done | error
      updateInfo: {},
      updateForced: false,
      updateMsg: '',
      updateNotes: '',

      lastLoadAt: 0
    }
  },

  computed: {
    /** 是否有面板打开（任意弹层）。打开时屏蔽列表触控，关闭后自动恢复。 */
    panelOpen() {
      return this.kbOpen || this.view !== 'list' || this.updateState !== 'idle'
    },

    updateTitle() {
      if (this.updateState === 'done') return '更新完成'
      if (this.updateState === 'downloading') return '正在下载'
      if (this.updateState === 'installing') return '正在安装'
      if (this.updateState === 'error') return '更新失败'
      return this.updateForced ? '必须更新' : '发现新版本'
    },

    updateSizeText() {
      var s = fmtSize(this.updateInfo && this.updateInfo.size)
      return s ? ('安装包 ' + s) : ''
    },

    /** 强制更新 / 正在下载安装时不可关闭 */
    updClosable() {
      if (this.updateForced) return false
      return this.updateState !== 'downloading' && this.updateState !== 'installing'
    },

    tipText() {
      if (this.submitting) return '正在发送…'
      if (this.selTitle) return '将发布：' + this.selTitle
      return '选一个，或点「自己写」'
    },

    claimBtnText() {
      var d = this.detail
      if (!d || !d.id) return '认领'
      if (!d.claimed) return '认领'
      if (d.claim_mine) return '释放'
      return d.claimed_by + ' 已认领'
    },

    // ---------------- 内置输入法 ----------------
    kbMeta() {
      return KB_TARGETS[this.kbTarget] || KB_TARGETS.title
    },

    kbTargetName() { return this.kbMeta.name },
    kbPlaceholder() { return this.kbMeta.ph },
    kbLimit() { return this.kbMeta.limit },
    kbLen() { return (this.kbValue || '').length },

    kbDisplay() {
      var v = this.kbValue || ''
      if (this.kbPinyin) {
        return (v ? v + ' ' : '') + '[' + this.kbPinyin + ']'
      }
      return v
    },

    kbKeysRows() {
      var self = this
      var rows = []

      function norm(list) {
        var out = []
        for (var i = 0; i < list.length; i++) {
          var it = list[i]
          if (typeof it === 'string') out.push({ v: it, label: it, cls: '' })
          else if (it && it.label !== null && it.label !== undefined && it.label !== '') out.push(it)
        }
        return out
      }

      function modeKeys(active) {
        return [
          { v: 'mode:abc', label: 'ABC', cls: active === 'abc' ? 'kb-fn kb-on' : 'kb-fn' },
          { v: 'mode:py', label: '拼音', cls: active === 'py' ? 'kb-fn kb-on' : 'kb-fn' },
          { v: 'mode:num', label: '123', cls: active === 'num' ? 'kb-fn kb-on' : 'kb-fn' }
        ]
      }

      var spaceKey = { v: 'space', label: '空格', cls: 'kb-wide' }
      var delKey = { v: 'del', label: '删除', cls: 'kb-fn' }

      /* 数字模式 */
      if (this.kbMode === 'num') {
        rows.push(norm(KB_KEYS_NUM[0].split('')))
        rows.push(norm(KB_KEYS_NUM[1].split('')))
        rows.push(norm(modeKeys('num').concat([spaceKey, delKey])))
        return rows
      }

      /* 拼音模式：3 行字母 + 候选行 + 功能行 */
      if (this.kbMode === 'py') {
        rows.push(norm(KB_KEYS_ABC[0].split('')))
        rows.push(norm(KB_KEYS_ABC[1].split('')))
        rows.push(norm(KB_KEYS_ABC[2].split('')).concat([delKey]))

        var cand = []
        for (var ci = 0; ci < self.kbCand.length && ci < 8; ci++) {
          cand.push({
            v: 'cand:' + ci,
            label: self.kbCand[ci],
            cls: ci === self.kbCandActive ? 'kb-cand kb-cand-on' : 'kb-cand',
            txtCls: ci === self.kbCandActive ? 'kb-txt-cand kb-txt-cand-on' : 'kb-txt-cand'
          })
        }
        if (!cand.length) {
          cand.push({
            v: 'noop',
            label: self.kbPinyin ? '无候选' : '输入拼音',
            cls: 'kb-page'
          })
        }
        rows.push(norm(cand))
        rows.push(norm(modeKeys('py').concat([spaceKey])))
        return rows
      }

      /* 字母模式 */
      var letters = function (s) {
        var out = []
        for (var i = 0; i < s.length; i++) {
          out.push(self.kbShift ? s.charAt(i).toUpperCase() : s.charAt(i))
        }
        return out
      }
      rows.push(norm(letters(KB_KEYS_ABC[0])))
      rows.push(norm(letters(KB_KEYS_ABC[1])))
      rows.push(norm([{ v: 'shift', label: self.kbShift ? '小写' : '大写', cls: self.kbShift ? 'kb-fn kb-on' : 'kb-fn' }])
        .concat(norm(letters(KB_KEYS_ABC[2])))
        .concat([delKey]))
      rows.push(norm(modeKeys('abc').concat([spaceKey])))
      return rows
    }
  },

  onLoad() {
    var self = this
    this.screen = pageSize()

    logInfo('==== app launch v' + VERSION + ' ====')
    logInfo('screen ' + describeScreen(this.screen) + ' compact=' + this.screen.compact)
    logInfo('endpoints: ' + ENDPOINTS.join(' , '))

    loadHistory().then(function () {
      return clientId()
    }).then(function (cid) {
      self.cid = cid
      setContext({ client_id: cid, version: VERSION })
      logInfo('client_id=' + cid)
      return storageGet('wish_nick')
    }).then(function (nick) {
      if (nick && typeof nick === 'string') self.nick = nick
      return storageGet('wish_admin_pass')
    }).then(function (ap) {
      if (ap && typeof ap === 'string') self.adminPass = ap
      self.bootConnect()
      self.startPoll()
    }).catch(function (e) {
      logError('onLoad failed: ' + (e && e.message ? e.message : e))
      self.bootConnect()
      self.startPoll()
    })
  },

  onShow() {
    logInfo('page show')
    // 打开/切回前台立即刷新
    this.load()
    this.startPoll()
  },

  onHide() {
    logInfo('page hide')
    this.stopPoll()
  },

  onUnload() {
    logInfo('page unload')
    this.stopPoll()
  },

  methods: {
    /**
     * 打开应用即连接服务器：
     *   立即拉一次，失败按 2s / 4s / 6s 重试；成功后 5 秒补刷一次，并检查更新。
     */
    bootConnect() {
      var self = this
      var tries = 0
      function attempt() {
        tries++
        self.load().then(function (ok) {
          if (ok) {
            logInfo('boot connect ok (try ' + tries + ')')
            if (!self._updateChecked) {
              self._updateChecked = true
              self.checkUpdate(true)
            }
            if (self._bootTimer) clearTimeout(self._bootTimer)
            self._bootTimer = setTimeout(function () {
              self._bootTimer = null
              logInfo('boot refresh (5s)')
              self.load()
            }, BOOT_REFRESH_MS)
            return
          }
          if (tries < BOOT_RETRIES) {
            var wait = 2000 * tries
            logWarn('boot connect fail (try ' + tries + '), retry in ' + wait + 'ms')
            setTimeout(attempt, wait)
          } else {
            logError('boot connect give up after ' + tries)
          }
        })
      }
      attempt()
    },

    load() {
      var self = this
      this.loading = true
      return get('/api/wishes', {
        sort: this.sort,
        limit: 100,
        client_id: this.cid || ''
      }, 8).then(function (d) {
        self.loading = false
        if (!d || !d.items) {
          self.online = false
          logWarn('load: unexpected payload')
          return false
        }
        self.rows = d.items
        if (d.stats) self.stats = d.stats
        self.lastLoadAt = Date.now()
        if (!self.online) logInfo('online (base=' + currentBase() + ')')
        self.online = true
        return true
      }).catch(function (e) {
        self.loading = false
        self.online = false
        logError('load failed: ' + (e && e.message ? e.message : e))
        return false
      })
    },

    startPoll() {
      var self = this
      this.stopPoll()
      this._poll = setInterval(function () {
        if (self.view !== 'list') return
        self.load()
      }, POLL_MS)
    },

    stopPoll() {
      if (this._poll) { clearInterval(this._poll); this._poll = null }
    },

    refresh() {
      logInfo('manual refresh')
      this.load()
      this.toast('正在刷新')
    },

    setSort(s) {
      if (this.sort === s) return
      this.sort = s
      logInfo('sort -> ' + s)
      this.load()
    },

    onVote(w) {
      if (!w || !w.id) return
      var self = this
      var wasVoted = !!w.voted
      var old = w.votes

      if (wasVoted) {
        w.voted = false
        w.votes = Math.max(0, old - 1)
        send('/api/wish/' + w.id + '/unvote', { client_id: this.cid }, 8)
          .then(function (d) {
            if (!d || !d.ok) { w.voted = true; w.votes = old; self.toast('操作失败'); return }
            w.votes = d.wish.votes
            if (d.stats) self.stats = d.stats
          }).catch(function (e) {
            w.voted = true; w.votes = old
            logError('unvote fail: ' + (e && e.message))
            self.toast('网络异常')
          })
        return
      }

      w.voted = true
      w.votes = old + 1
      if (this.stats.votes != null) this.stats.votes = this.stats.votes + 1

      send('/api/wish/' + w.id + '/vote', { client_id: this.cid }, 8)
        .then(function (d) {
          if (!d || !d.ok) {
            w.voted = false
            w.votes = old
            self.stats.votes = Math.max(0, self.stats.votes - 1)
            self.toast('操作失败')
            return
          }
          w.votes = d.wish.votes
          if (d.stats) self.stats = d.stats
        }).catch(function (e) {
          w.voted = false
          w.votes = old
          self.stats.votes = Math.max(0, self.stats.votes - 1)
          logError('vote fail: ' + (e && e.message))
          self.toast('网络异常')
        })
    },

    toggleClaim() {
      if (!this.isTapSimple()) return
      var d = this.detail
      if (!d || !d.id) return
      var self = this

      // 认领/释放都需要管理密码
      if (!this.adminPass) {
        this.askPass('pass', function () { self.toggleClaim() })
        return
      }

      if (d.claimed) {
        if (!d.claim_mine) {
          this.toast('已被「' + d.claimed_by + '」认领')
          return
        }
        sendAdmin('/api/wish/' + d.id + '/release', { client_id: this.cid },
          8, this.adminPass)
          .then(function (r) {
            if (!r || !r.ok) {
              self.handleAuthFail(r)
              return
            }
            d.claimed = false
            d.claimed_by = ''
            d.claim_mine = false
            logInfo('released wish ' + d.id)
            self.toast('已释放认领')
            self.load()
          }).catch(function (e) {
            logError('release fail: ' + (e && e.message))
            self.toast('网络异常')
          })
        return
      }

      // 先要有昵称，再认领
      if (!this.nick) {
        this.askPass('nick', function () { self.toggleClaim() })
        return
      }
      this.doClaim(this.nick)
    },

    /** 认证失败：清掉本地密码并重新输入 */
    handleAuthFail(r) {
      if (r && (r.need_pass || r.status === 401)) {
        this.adminPass = ''
        storageSet('wish_admin_pass', '')
        logWarn('claim auth failed, clearing pass')
        this.toast('管理密码不正确')
        var self = this
        this.askPass('pass', function () { self.toggleClaim() })
        return true
      }
      this.toast((r && r.error) || '操作失败')
      return false
    },

    /** 打开输入法：mode = 'nick' | 'pass'，完成后执行 after */
    askPass(mode, after) {
      this._afterKb = after || null
      if (mode === 'nick') this.openKb('nick', this.nick || '')
      else this.openKb('pass', '')
    },

    /** 「自己写」入口 */
    openKeyboard() {
      this._afterKb = null
      this.openKb('title', this.selTitle || '')
    },

    doClaim(nick) {
      var self = this
      var d = this.detail
      if (!d || !d.id) return
      sendAdmin('/api/wish/' + d.id + '/claim',
        { nick: nick, client_id: this.cid }, 8, this.adminPass)
        .then(function (r) {
          if (!r || !r.ok) {
            logWarn('claim rejected: ' + ((r && r.error) || '?'))
            self.handleAuthFail(r)
            self.load()
            return
          }
          self.nick = nick
          storageSet('wish_nick', nick)
          d.claimed = true
          d.claimed_by = r.wish.claimed_by
          d.claim_mine = true
          logInfo('claimed wish ' + d.id + ' as ' + nick)
          self.toast('已认领，服务端已记录「' + nick + '」')
          self.load()
        }).catch(function (e) {
          logError('claim fail: ' + (e && e.message))
          self.toast('网络异常')
        })
    },

    openDetail(w) {
      if (!w || !w.id) return
      this.detail = w
      this.detailId = w.id
      this.view = 'detail'
    },

    closeDetail() {
      if (!this.isTapSimple()) return
      this.view = 'list'
      this.detail = {}
      // 关闭后若数据已陈旧则刷新
      if (Date.now() - (this.lastLoadAt || 0) > STALE_MS) this.load()
    },

    openCompose() {
      if (!this.isTapSimple()) return
      this.view = 'compose'
      this.presets = PRESETS[CATEGORIES[this.catIdx].id] || PRESETS.other
      this.selTitle = ''
      this.customMode = false
    },

    closeCompose() {
      if (!this.isTapSimple()) return
      this.view = 'list'
      this.selTitle = ''
      this.kbOpen = false
    },

    pickCat(ci) {
      if (!this.isTapSimple()) return
      this.catIdx = ci
      this.presets = PRESETS[CATEGORIES[ci].id] || PRESETS.other
      this.selTitle = ''
      this.customMode = false
    },

    pickPreset(p) {
      if (!this.isTapSimple()) return
      this.selTitle = (this.selTitle === p) ? '' : p
      this.customMode = false
    },

    // ---------------- 内置输入法 ----------------
    /** 打开输入法：target = title | nick | pass */
    openKb(target, initial) {
      this.kbTarget = target || 'title'
      this.kbValue = (initial === null || initial === undefined) ? '' : String(initial)
      this.kbShift = /[A-Z]/.test(this.kbValue)
      // 智能默认：密码 -> 数字；其余 -> 拼音（打中文最常用）
      this.kbMode = (this.kbTarget === 'pass') ? 'num' : 'py'
      this.kbPinyin = ''
      this.kbCand = []
      this.kbCandActive = -1
      this.kbOpen = true
      logInfo('kb open target=' + this.kbTarget + ' mode=' + this.kbMode)
    },

    _kbRefreshCand() {
      try {
        this.kbCand = pinyinCandidates(this.kbPinyin).slice(0, 8)
      } catch (e) {
        this.kbCand = []
      }
    },

    _kbPickCand(idx) {
      var t = this.kbCand[idx]
      if (!t) return
      var lim = this.kbLimit
      if (this.kbValue.length + t.length <= lim) this.kbValue += t
      this.kbPinyin = ''
      this.kbCandActive = -1
      this._kbRefreshCand()
    },

    kbPress(v) {
      var lim = this.kbLimit

      if (v === 'del') {
        if (this.kbMode === 'py' && this.kbPinyin) {
          this.kbPinyin = this.kbPinyin.slice(0, -1)
          this._kbRefreshCand()
        } else {
          this.kbValue = this.kbValue.slice(0, Math.max(0, this.kbValue.length - 1))
        }
        return
      }

      if (v.indexOf('cand:') === 0) {
        this._kbPickCand(Number(v.slice(5)))
        return
      }

      if (v === 'shift') {
        this.kbShift = !this.kbShift
        return
      }

      if (v === 'noop') return

      if (v === 'space') {
        if (this.kbMode === 'py' && this.kbCand.length) this._kbPickCand(0)
        else if (this.kbValue.length < lim) this.kbValue += ' '
        return
      }

      if (v.indexOf('mode:') === 0) {
        this.kbMode = v.slice(5)
        this.kbPinyin = ''
        this.kbCand = []
        this.kbCandActive = -1
        return
      }

      if (v === 'ok') { this.kbDone(); return }

      if (this.kbMode === 'py') {
        if (this.kbPinyin.length < 24) {
          this.kbPinyin += String(v).toLowerCase()
          this._kbRefreshCand()
        }
        return
      }

      if (this.kbValue.length >= lim) {
        this.toast('最多 ' + lim + ' 个字')
        return
      }
      this.kbValue += v
    },

    kbDone() {
      var val = (this.kbValue || '').trim()
      var target = this.kbTarget
      var after = this._afterKb

      // 拼音还没选字：自动取第一个候选
      if (this.kbMode === 'py' && this.kbPinyin && this.kbCand.length) {
        this._kbPickCand(0)
        return
      }
      if (this.kbMode === 'py' && this.kbPinyin && !this.kbCand.length) {
        this.toast('没有候选，换个拼音或翻到汉字')
        return
      }

      if (target === 'pass') {
        if (!val) { this.toast('请输入管理密码'); return }
        this.adminPass = val
        storageSet('wish_admin_pass', val)
        logInfo('admin pass entered')
      } else if (target === 'nick') {
        if (!val) { this.toast('请输入昵称'); return }
        this.nick = val.substring(0, 20)
        storageSet('wish_nick', this.nick)
      } else {
        if (val.length < 2) { this.toast('至少 2 个字'); return }
        this.selTitle = val.substring(0, 40)
        this.customMode = true
      }

      this.kbOpen = false
      this._afterKb = null
      if (typeof after === 'function') after()
    },

    kbClose() {
      this.kbOpen = false
      this._afterKb = null
      this.kbPinyin = ''
      this.kbCand = []
      this.kbCandActive = -1
    },

    submit() {
      if (this.submitting) return
      var title = (this.selTitle || '').trim()
      if (!title || title.length < 2) { this.toast('先选一个愿望'); return }

      var self = this
      this.submitting = true
      var cat = CATEGORIES[this.catIdx].id

      send('/api/wish/add', {
        title: title.substring(0, 40),
        desc: '',
        nick: this.nick || '',
        category: cat,
        client_id: this.cid
      }, 10).then(function (d) {
        self.submitting = false
        if (!d || !d.ok) {
          logWarn('submit rejected: ' + ((d && d.error) || '?'))
          self.toast((d && d.error) || '提交失败')
          return
        }
        logInfo('wish submitted: ' + title)
        self.selTitle = ''
        self.customMode = false
        self.view = 'list'
        self.sort = 'new'
        self.toast('愿望已上墙')
        self.load()
      }).catch(function (e) {
        self.submitting = false
        logError('submit fail: ' + (e && e.message))
        self.toast('网络异常，请重试')
      })
    },

    // ---------------- 应用更新 ----------------
    checkUpdate(silent) {
      var self = this
      if (this.updateState === 'downloading' || this.updateState === 'installing') return
      updCheck(APP_VERSION).then(function (r) {
        if (!r.ok) {
          if (!silent) self.toast('检查更新失败')
          return
        }
        if (!r.hasUpdate) {
          if (!silent) self.toast('已是最新版本 v' + APP_VERSION)
          return
        }
        self.updateInfo = r.latest || {}
        self.updateForced = !!r.forced
        self.updateNotes = (r.latest && r.latest.notes) || '包含体验优化与问题修复。'
        self.updateState = 'available'
        self.updateMsg = self.updateForced ? '本次更新为强制更新' : '建议立即更新以获得最新体验'
        logInfo('update available v' + (r.latest && r.latest.version))
      })
    },

    startUpdate() {
      if (!this.isTapSimple()) return
      var self = this
      var info = this.updateInfo || {}
      if (!info.url) { this.toast('缺少下载地址'); return }

      var cap = nativeCapability()
      logInfo('update capability: ' + JSON.stringify(cap))
      if (!cap.download || !cap.install) {
        self.updateState = 'error'
        self.updateMsg = '本机不支持自动安装，请到面板下载：' + info.url
        logWarn('update: native unavailable')
        return
      }

      this.updateState = 'downloading'
      this.updateMsg = '正在下载…'
      setTimeout(function () {
        var d = nativeDownload(info.url, 'wishpool-' + (info.version || 'new') + '.amr')
        if (!d.ok) {
          self.updateState = 'error'
          self.updateMsg = '下载失败（' + d.error + '），请重试'
          return
        }
        self.updateState = 'installing'
        self.updateMsg = '正在安装…'
        setTimeout(function () {
          var ins = nativeInstall(d.path)
          if (!ins.ok) {
            self.updateState = 'error'
            self.updateMsg = '安装失败（' + ins.error + '），请重试'
            return
          }
          self.updateState = 'done'
          self.updateMsg = '已安装 v' + (info.version || '') + '，点击重启生效'
          logInfo('update installed v' + (info.version || ''))
        }, 80)
      }, 80)
    },

    restartApp() {
      if (!this.isTapSimple()) return
      var r = nativeStart()
      if (!r.ok) this.toast('重启失败：' + r.error)
    },

    closeUpdate() {
      if (!this.isTapSimple()) return
      if (!this.updClosable) return
      this.updateState = 'idle'
    },

    openDiag() {
      if (!this.isTapSimple()) return
      this.view = 'diag'
      this.refreshLogs()
      logInfo('open diagnostics')
      this.refreshLogs()
    },

    closeDiag() {
      if (!this.isTapSimple()) return
      this.view = 'list'
    },

    refreshLogs() {
      this.logLines = recent(80).map(function (x) {
        var d = new Date(x.t * 1000)
        var p = function (n) { return n < 10 ? '0' + n : '' + n }
        return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) +
          '  ' + x.m
      })
      this.diagInfo = networkKind() + ' · ' + currentBase() + ' · ' +
        (this.online ? '在线' : '离线')
    },

    doReport() {
      if (!this.isTapSimple()) return
      var self = this
      this.reportTip = '上报中…'
      logInfo('report logs requested')
      var ctx = context()
      var extra = 'online=' + this.online + ' base=' + currentBase() +
        ' rows=' + this.rows.length + ' screen=' + this.screen.w + 'x' + this.screen.h
      reportLogs(ctx.sn, this.cid, ctx.version, exportLines(40, 110), extra)
        .then(function (ok) {
          self.reportTip = ok ? '已上报' : '上报失败（检查网络）'
          self.refreshLogs()
        }).catch(function (e) {
          self.reportTip = '上报失败'
          logError('report error: ' + (e && e.message))
          self.refreshLogs()
        })
    },

    toast(msg) {
      var self = this
      this.toastText = msg
      this.toastShow = true
      if (this._tt) clearTimeout(this._tt)
      this._tt = setTimeout(function () {
        self.toastShow = false
      }, 2000)
    },

    // ---------------- 滚动防误触 ----------------
    // 记录按下位置；滑动超过阈值就标记为「滚动中」，抬手时不触发点击
    onDocTouchStart(e) {
      var t = pickTouch(e, 'start')
      this._t0x = t.x
      this._t0y = t.y
      this._t0 = Date.now()
      this._moved = false
    },

    onDocTouchMove(e) {
      if (this._t0 === undefined || this._t0 === null) return
      if (this._moved) return
      var t = pickTouch(e, 'move')
      var dx = Math.abs(t.x - this._t0x)
      var dy = Math.abs(t.y - this._t0y)
      if (dx > TAP_MOVE_LIMIT || dy > TAP_MOVE_LIMIT) {
        this._moved = true
      }
    },

    onDocTouchEnd(e) {
      // 保持 _moved 到下一次 touchstart，避免同一次滑动里多个 touchend 误触发
      if (this._moved || this._t0x === undefined) return
      var t = pickTouch(e, 'end')
      var dx = Math.abs(t.x - this._t0x)
      var dy = Math.abs(t.y - this._t0y)
      if (dx > TAP_MOVE_LIMIT || dy > TAP_MOVE_LIMIT) this._moved = true
    },

    /** 列表卡片：位移 + 长按都判为滑动 */
    isTap() {
      if (this._moved) return false
      if (this._t0 === undefined || this._t0 === null) return true
      if (Date.now() - this._t0 > TAP_MAX_MS) return false
      return true
    },

    /** 普通按钮（含滚动区内的）：只判位移，长按不算误触 */
    isTapSimple() {
      return !this._moved
    },

    onCardTap(w, e) {
      // 面板打开时屏蔽列表触控
      if (this.panelOpen) return
      if (!this.isTap()) {
        logInfo('tap ignored (scroll)')
        return
      }
      this.openDetail(w)
    },

    onVoteTap(w, e) {
      // 面板打开时屏蔽列表触控
      if (this.panelOpen) return
      if (!this.isTap()) {
        logInfo('vote ignored (scroll)')
        return
      }
      this.onVote(w)
    },

    /** 面板遮罩吞掉触摸，避免透传到下层 */
    onMaskTouch() {
      // 有意留空：只用于拦截
    },

    // ---------------- 状态 ----------------
    statusName(id) {
      var s = STATUSES[id]
      return s ? s.name : '待认领'
    },

    statusBg(id) {
      var s = STATUSES[id]
      return s ? s.bg : 'st-open'
    },

    statusTxt(id) {
      var s = STATUSES[id]
      return s ? s.txt : 'st-txt-open'
    },

    catName(id) {
      for (var i = 0; i < CATEGORIES.length; i++) {
        if (CATEGORIES[i].id === id) return CATEGORIES[i].name
      }
      return '其它'
    },

    catClass(id) {
      return 'cat-' + (id || 'other')
    },

    catTxtClass(id) {
      return 'cat-txt-' + (id || 'other')
    },

    cardClass(w, i) {
      var s = 'card c-' + (w.category || 'other')
      if (i === 0) s = s + ' card-top'
      return s
    },

    rankBoxClass(i) {
      if (i === 0) return 'rk rk-1'
      if (i === 1) return 'rk rk-2'
      if (i === 2) return 'rk rk-3'
      return 'rk'
    },

    ago(ts) {
      if (!ts) return ''
      var d = Math.floor(Date.now() / 1000) - ts
      if (d < 60) return '刚刚'
      if (d < 3600) return Math.floor(d / 60) + '分钟前'
      if (d < 86400) return Math.floor(d / 3600) + '小时前'
      return Math.floor(d / 86400) + '天前'
    }
  }
}
</script>

<style lang="less">
/* ==========================================================================
   设计基准 960 × 266（横屏超宽短屏）
   横向：1 设计 px = 0.10417vw ；纵向：1 设计 px = 0.37594vh
   平台限制：只支持单类名选择器；无 border/box-shadow 简写；
             文字必须在 <text> 内；图标一律用 <image> 贴图
   ========================================================================== */

.page {
  width: 960px; width: 100vw;
  height: 266px; height: 100vh;
  background-color: #070A14;
  position: relative;
  overflow: hidden;
}

/* ---------- 顶栏 ---------- */
.hd {
  position: absolute;
  left: 0; right: 0; top: 0;
  height: 52px; height: 19.5vh;
  padding-left: 16px; padding-left: 1.46vw;
  padding-right: 14px; padding-right: 1.46vw;
  flex-direction: row;
  align-items: center;
  background-color: #0C1020;
}
.brand { flex-direction: row; align-items: center; }
.logo {
  width: 36px; width: 3.75vw;
  height: 36px; height: 13.5vh;
  border-radius: 11px; border-radius: 1.15vw;
  background-color: #1B2547;
  align-items: center;
  justify-content: center;
  margin-right: 9px; margin-right: 0.94vw;
}
.logo-img { width: 24px; width: 2.5vw; height: 24px; height: 9vh; }
.brand-txt { flex-direction: column; justify-content: center; }
.app-name { font-size: 17px; font-size: 1.77vw; color: #EDF1FF; font-weight: bold; }
.app-sub { font-size: 9px; font-size: 0.94vw; color: #6C7794; margin-top: 1px; }

.hd-mid { flex: 1; flex-direction: row; align-items: center; justify-content: center; }

.live {
  flex-direction: row; align-items: center;
  height: 24px; height: 9vh;
  padding-left: 10px; padding-right: 11px;
  padding-left: 0.83vw; padding-right: 0.94vw;
  border-radius: 12px; border-radius: 1.25vw;
  background-color: #1A2034;
  margin-right: 12px; margin-right: 1.04vw;
}
.live-on { background-color: #10261F; }
.live-dot {
  width: 7px; width: 0.73vw; height: 7px; height: 2.6vh;
  border-radius: 3px; border-radius: 0.31vw;
  background-color: #FF6B8A;
  margin-right: 5px; margin-right: 0.52vw;
}
.live-dot-on { background-color: #22D3B8; }
.live-txt { font-size: 11px; font-size: 1.15vw; color: #A8B2CC; }
.live-txt-on { color: #7FE9D4; font-weight: bold; }

.stat-mini { flex-direction: column; align-items: center; margin-left: 14px; margin-left: 1.46vw; }
.stat-mini-n { font-size: 18px; font-size: 1.88vw; color: #EDF1FF; font-weight: bold; }
.stat-mini-k { font-size: 9px; font-size: 0.94vw; color: #6C7794; margin-top: 1px; }

.hd-right { flex-direction: row; align-items: center; }
.seg {
  flex-direction: row; align-items: center;
  height: 30px; height: 11.3vh;
  padding: 3px;
  border-radius: 8px; border-radius: 0.83vw;
  background-color: #1A2034;
  margin-right: 8px; margin-right: 0.83vw;
}
.seg-i {
  flex-direction: row;
  height: 24px; height: 9vh;
  padding-left: 11px; padding-right: 11px;
  padding-left: 0.94vw; padding-right: 0.94vw;
  border-radius: 6px; border-radius: 0.63vw;
  align-items: center;
  justify-content: center;
}
.seg-i-on { background-color: #2B3A66; }
.seg-ico {
  width: 13px; width: 1.35vw;
  height: 13px; height: 4.9vh;
  margin-right: 4px; margin-right: 0.42vw;
}
.seg-txt { font-size: 12px; font-size: 1.25vw; color: #A8B2CC; }
.seg-txt-on { color: #FFFFFF; font-weight: bold; }

.btn-refresh {
  width: 30px; width: 3.13vw;
  height: 30px; height: 11.3vh;
  border-radius: 8px; border-radius: 0.83vw;
  background-color: #1A2034;
  align-items: center;
  justify-content: center;
}
.btn-refresh-on { background-color: #23305A; }
.btn-refresh-img { width: 17px; width: 1.77vw; height: 17px; height: 6.4vh; }

/* ---------- 列表 ---------- */
.list-area {
  position: absolute;
  left: 0; right: 0;
  top: 52px; top: 19.5vh;
  bottom: 48px; bottom: 18vh;
}
.row { padding-left: 14px; padding-left: 1.46vw; padding-right: 14px; padding-right: 1.46vw; }

.card {
  flex-direction: row;
  align-items: center;
  height: 60px; height: 22.6vh;
  margin-top: 6px; margin-top: 2.3vh;
  border-radius: 13px; border-radius: 1.35vw;
  background-color: #131828;
  padding-left: 12px; padding-left: 1.25vw;
  padding-right: 9px; padding-right: 0.94vw;
}
.card-top { background-color: #1D1B2A; }

.rk {
  width: 30px; width: 3.13vw;
  height: 30px; height: 11.3vh;
  border-radius: 10px; border-radius: 1.04vw;
  background-color: #1E2440;
  align-items: center;
  justify-content: center;
  margin-right: 11px; margin-right: 1.15vw;
}
.rk-1 { background-color: #4A3D18; }
.rk-2 { background-color: #2C3247; }
.rk-3 { background-color: #3A2E22; }
.rk-medal { width: 19px; width: 1.98vw; height: 19px; height: 7.1vh; }
.rk-n { font-size: 14px; font-size: 1.46vw; color: #A8B2CC; font-weight: bold; }

.bd { flex: 1; flex-direction: column; justify-content: center; }
.tt {
  font-size: 17px; font-size: 1.77vw;
  color: #EDF1FF;
  font-weight: bold;
  lines: 1;
  text-overflow: ellipsis;
}
.tt-top { color: #FFE9A8; }

.meta { flex-direction: row; align-items: center; margin-top: 5px; margin-top: 1.9vh; }
.who { font-size: 11px; font-size: 1.15vw; color: #8B95B0; }
.dot-sep { font-size: 11px; font-size: 1.15vw; color: #414A66; margin-left: 4px; margin-right: 4px; }
.ago { font-size: 11px; font-size: 1.15vw; color: #6C7794; }

.cat {
  padding-left: 7px; padding-right: 7px;
  padding-left: 0.73vw; padding-right: 0.73vw;
  padding-top: 2px; padding-bottom: 2px;
  border-radius: 5px; border-radius: 0.52vw;
  background-color: #1E2440;
  align-items: center;
  justify-content: center;
}
.cat-txt { font-size: 10px; font-size: 1.04vw; color: #8B95B0; }
.cat-txt-app { color: #8FB0FF; }
.cat-txt-feat { color: #5CF0D6; }
.cat-txt-game { color: #C79BFF; }
.cat-txt-read { color: #FFC962; }
.cat-txt-system { color: #FF9BAE; }
.cat-txt-other { color: #8B95B0; }
.cat-app { background-color: #1B2547; }
.cat-feat { background-color: #122E2A; }
.cat-game { background-color: #241A3A; }
.cat-read { background-color: #2E2412; }
.cat-system { background-color: #2E1620; }
.cat-other { background-color: #1E2440; }

/* 愿望状态徽标 */
.st {
  flex-direction: row;
  align-items: center;
  margin-left: 5px; margin-left: 0.52vw;
  padding-left: 7px; padding-right: 7px;
  padding-left: 0.73vw; padding-right: 0.73vw;
  padding-top: 2px; padding-bottom: 2px;
  border-radius: 5px; border-radius: 0.52vw;
  background-color: #1E2440;
}
.st-open { background-color: #1E2440; }
.st-doing { background-color: #16264F; }
.st-done { background-color: #10312B; }
.st-rejected { background-color: #22283A; }
.st-txt { font-size: 10px; font-size: 1.04vw; color: #8B95B0; }
.st-txt-open { color: #8B95B0; }
.st-txt-doing { color: #8FB0FF; }
.st-txt-done { color: #5CF0D6; }
.st-txt-rejected { color: #6C7794; }

/* 认领徽标 */
.claim {
  flex-direction: row;
  align-items: center;
  margin-left: 6px; margin-left: 0.63vw;
  padding-left: 7px; padding-right: 7px;
  padding-left: 0.73vw; padding-right: 0.73vw;
  padding-top: 2px; padding-bottom: 2px;
  border-radius: 5px; border-radius: 0.52vw;
  background-color: #241A3A;
}
.claim-mine { background-color: #122E2A; }
.claim-img { width: 12px; width: 1.25vw; height: 12px; height: 4.5vh; margin-right: 2px; margin-right: 0.21vw; }
.claim-txt { font-size: 10px; font-size: 1.04vw; color: #C79BFF; }
.claim-txt-mine { color: #5CF0D6; }

/* +1 */
.vote {
  width: 66px; width: 6.88vw;
  height: 48px; height: 18vh;
  border-radius: 12px; border-radius: 1.25vw;
  background-color: #1C2340;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin-left: 10px; margin-left: 1.04vw;
}
.vote-voted { background-color: #14352F; }
.vote-img { width: 16px; width: 1.67vw; height: 16px; height: 6vh; }
.vote-n {
  font-size: 20px; font-size: 2.08vw;
  color: #C9D6FF;
  font-weight: bold;
  margin-top: 1px;
}
.vote-n-voted { color: #8FF5E4; }

.list-pad { height: 6px; height: 2.3vh; }

/* ---------- 状态 ---------- */
.state {
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 150px; height: 56.4vh;
}
.state-img { width: 46px; width: 4.79vw; height: 46px; height: 17.3vh; margin-bottom: 6px; }
.state-txt { font-size: 13px; font-size: 1.35vw; color: #6C7794; }
.state-sub { font-size: 11px; font-size: 1.15vw; color: #4A5270; margin-top: 4px; }

/* ---------- 底栏 ---------- */
.ft {
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 48px; height: 18vh;
  padding-left: 16px; padding-left: 1.67vw;
  padding-right: 16px; padding-right: 1.67vw;
  flex-direction: row;
  align-items: center;
  background-color: #0C1020;
}
.ft-hint { flex: 1; font-size: 11px; font-size: 1.15vw; color: #4A5270; }
.ft-log {
  font-size: 11px; font-size: 1.15vw;
  color: #8FB0FF;
  padding-left: 10px; padding-right: 10px;
  padding-left: 1.04vw; padding-right: 1.04vw;
  height: 24px; height: 9vh;
  margin-right: 6px; margin-right: 0.63vw;
  border-radius: 7px; border-radius: 0.73vw;
  background-color: #17203A;
  text-align: center;
}
.ft-upd {
  font-size: 11px; font-size: 1.15vw;
  color: #8FF5E4;
  padding-left: 10px; padding-right: 10px;
  padding-left: 1.04vw; padding-right: 1.04vw;
  height: 24px; height: 9vh;
  margin-right: 6px; margin-right: 0.63vw;
  border-radius: 7px; border-radius: 0.73vw;
  background-color: #12302B;
  text-align: center;
}
.ft-count { font-size: 11px; font-size: 1.15vw; color: #4A5270; margin-right: 12px; margin-right: 1.25vw; }
.btn-wish {
  height: 34px; height: 12.8vh;
  padding-left: 20px; padding-right: 20px;
  padding-left: 2.08vw; padding-right: 2.08vw;
  border-radius: 10px; border-radius: 1.04vw;
  background-color: #5B8CFF;
  align-items: center;
  justify-content: center;
}
.btn-wish-txt { font-size: 14px; font-size: 1.46vw; color: #FFFFFF; font-weight: bold; }

/* ---------- 遮罩 ---------- */
.mask {
  position: absolute;
  left: 0; right: 0; top: 0; bottom: 0;
  background-color: #070A14;
  align-items: center;
  justify-content: center;
}

/* ---------- 许愿面板 ---------- */
.compose {
  width: 720px; width: 75vw;
  height: 230px; height: 86.5vh;
  border-radius: 12px; border-radius: 1.25vw;
  background-color: #10162A;
  padding: 10px; padding: 1.04vw;
  flex-direction: column;
}
.cp-hd { flex-direction: row; align-items: center; margin-bottom: 7px; margin-bottom: 2.6vh; }
.cp-title-img { width: 14px; width: 1.46vw; height: 14px; height: 5.3vh; margin-right: 5px; margin-right: 0.52vw; }
.cp-title { font-size: 15px; font-size: 1.56vw; color: #EDF1FF; font-weight: bold; }
.cp-sub { font-size: 11px; font-size: 1.15vw; color: #6C7794; margin-left: 8px; margin-left: 0.83vw; flex: 1; }
.cp-close {
  width: 34px; width: 3.54vw;
  height: 34px; height: 12.8vh;
  border-radius: 10px; border-radius: 1.04vw;
  background-color: #1A2034;
  align-items: center;
  justify-content: center;
}
.cp-close-img { width: 18px; width: 1.88vw; height: 18px; height: 6.8vh; }

.cp-cats { flex-direction: row; align-items: center; margin-bottom: 7px; margin-bottom: 2.6vh; }
.cp-cat {
  height: 28px; height: 10.5vh;
  padding-left: 12px; padding-right: 12px;
  padding-left: 1.25vw; padding-right: 1.25vw;
  border-radius: 8px; border-radius: 0.83vw;
  background-color: #1A2034;
  align-items: center;
  justify-content: center;
  margin-right: 8px; margin-right: 0.83vw;
}
.cp-cat-on { background-color: #2B3A66; }
.cp-cat-txt { font-size: 11px; font-size: 1.15vw; color: #A8B2CC; }
.cp-cat-txt-on { color: #FFFFFF; font-weight: bold; }

.cp-list { flex: 1; }
.cp-grid { flex-direction: row; flex-wrap: wrap; }
.preset {
  flex-direction: row;
  width: 170px; width: 17.71vw;
  height: 38px; height: 14.3vh;
  border-radius: 9px; border-radius: 0.94vw;
  background-color: #1A2034;
  align-items: center;
  justify-content: center;
  margin-right: 7px; margin-right: 0.73vw;
  margin-bottom: 7px; margin-bottom: 2.6vh;
  padding-left: 8px; padding-right: 8px;
}
.preset-on { background-color: #2B3A66; }
.preset-ico { width: 13px; width: 1.35vw; height: 13px; height: 4.9vh; margin-right: 4px; margin-right: 0.42vw; }
.preset-txt {
  font-size: 12px; font-size: 1.25vw;
  color: #A8B2CC;
  lines: 1;
  text-overflow: ellipsis;
}
.preset-txt-on { color: #FFFFFF; font-weight: bold; }

.cp-ft { flex-direction: row; align-items: center; margin-top: 4px; margin-top: 1.5vh; }
.cp-tip {
  flex: 1;
  font-size: 11px; font-size: 1.15vw;
  color: #6C7794;
  lines: 1;
  text-overflow: ellipsis;
}
.cp-submit {
  height: 34px; height: 12.8vh;
  padding-left: 26px; padding-right: 26px;
  padding-left: 2.71vw; padding-right: 2.71vw;
  border-radius: 10px; border-radius: 1.04vw;
  background-color: #5B8CFF;
  align-items: center;
  justify-content: center;
}
.cp-submit-dis { background-color: #2B3556; }
.cp-submit-txt { font-size: 13px; font-size: 1.35vw; color: #FFFFFF; font-weight: bold; }
.cp-submit-txt-dis { color: #6C7794; }

/* ---------- 详情 ---------- */
.detail {
  width: 690px; width: 71.88vw;
  height: 240px; height: 90.2vh;
  border-radius: 12px; border-radius: 1.25vw;
  background-color: #10162A;
  padding: 10px; padding: 1.04vw;
  flex-direction: column;
}
.dt-hd { flex-direction: row; align-items: center; margin-bottom: 6px; margin-bottom: 2.3vh; }
.dt-title {
  flex: 1;
  font-size: 16px; font-size: 1.67vw;
  color: #EDF1FF;
  font-weight: bold;
  lines: 1;
  text-overflow: ellipsis;
}
.dt-body { flex: 1; }
.dt-meta-row { flex-direction: row; align-items: center; margin-top: 8px; margin-top: 3vh; }
.dt-desc { font-size: 14px; font-size: 1.46vw; color: #A8B2CC; line-height: 18px; line-height: 6.8vh; }
.dt-meta { font-size: 11px; font-size: 1.15vw; color: #6C7794; margin-left: 4px; margin-left: 0.42vw; }
.dt-ft { flex-direction: row; align-items: center; margin-top: 6px; margin-top: 2.3vh; }
.dt-votes { flex: 1; font-size: 12px; font-size: 1.25vw; color: #8B95B0; }

.dt-claim {
  flex-direction: row;
  height: 32px; height: 12vh;
  padding-left: 14px; padding-right: 14px;
  padding-left: 1.46vw; padding-right: 1.46vw;
  border-radius: 8px; border-radius: 0.83vw;
  background-color: #2A1E42;
  align-items: center;
  justify-content: center;
  margin-right: 6px; margin-right: 0.63vw;
}
.dt-claim-on { background-color: #12302B; }
.dt-claim-img { width: 13px; width: 1.35vw; height: 13px; height: 4.9vh; margin-right: 4px; margin-right: 0.42vw; }
.dt-claim-txt { font-size: 12px; font-size: 1.25vw; color: #C79BFF; font-weight: bold; }
.dt-claim-txt-on { color: #8FF5E4; }

.dt-vote {
  flex-direction: row;
  height: 32px; height: 12vh;
  padding-left: 16px; padding-right: 16px;
  padding-left: 1.67vw; padding-right: 1.67vw;
  border-radius: 8px; border-radius: 0.83vw;
  background-color: #5B8CFF;
  align-items: center;
  justify-content: center;
}
.dt-vote-voted { background-color: #14352F; }
.dt-vote-img { width: 13px; width: 1.35vw; height: 13px; height: 4.9vh; margin-right: 4px; margin-right: 0.42vw; }
.dt-vote-txt { font-size: 12px; font-size: 1.25vw; color: #FFFFFF; font-weight: bold; }
.dt-vote-txt-voted { color: #8FF5E4; }

/* ---------- 内置键盘 ---------- */
.kb-mask {
  position: absolute;
  left: 0; right: 0; top: 0; bottom: 0;
  background-color: #070A14;
  align-items: center;
  justify-content: center;
}
.kb {
  width: 660px; width: 68.75vw;
  height: 252px; height: 94.7vh;
  border-radius: 12px; border-radius: 1.25vw;
  background-color: #10162A;
  padding: 10px; padding: 1.04vw;
  flex-direction: column;
}
.kb-hd { flex-direction: row; align-items: center; margin-bottom: 6px; margin-bottom: 2.3vh; }
.kb-title { font-size: 13px; font-size: 1.35vw; color: #EDF1FF; font-weight: bold; margin-right: 8px; margin-right: 0.83vw; }
.kb-valbox {
  flex: 1;
  height: 30px; height: 11.3vh;
  border-radius: 7px; border-radius: 0.73vw;
  background-color: #1A2034;
  padding-left: 10px; padding-right: 10px;
  padding-left: 1.04vw; padding-right: 1.04vw;
  justify-content: center;
}
.kb-val { font-size: 13px; font-size: 1.35vw; color: #8FB0FF; lines: 1; text-overflow: ellipsis; }
.kb-len { font-size: 10px; font-size: 1.04vw; color: #4A5270; margin-left: 6px; margin-left: 0.63vw; }

.kb-keys { flex: 1; justify-content: center; }
.kb-row { flex-direction: row; justify-content: center; }
.kb-key {
  width: 54px; width: 5.63vw;
  height: 30px; height: 11.3vh;
  border-radius: 7px; border-radius: 0.73vw;
  background-color: #1A2034;
  align-items: center;
  justify-content: center;
  margin-right: 4px; margin-right: 0.42vw;
  margin-bottom: 3px; margin-bottom: 1.1vh;
}
.kb-fn { width: 58px; width: 6.04vw; background-color: #2B3556; }
.kb-wide { width: 106px; width: 11.04vw; background-color: #232B47; }
.kb-page { width: 62px; width: 6.46vw; background-color: transparent; }
.kb-on { background-color: #3B5BD6; }
.kb-cand { width: 58px; width: 6.04vw; background-color: #14304A; }
.kb-cand-on { background-color: #1E6B5A; }
.kb-txt { font-size: 12px; font-size: 1.25vw; color: #DCE4FF; }
.kb-txt-cand { font-size: 14px; font-size: 1.46vw; color: #9FE8FF; }
.kb-txt-cand-on { color: #8FF5E4; font-weight: bold; }
.kb-val-ph { color: #4A5270; }

.kb-close {
  width: 36px; width: 3.75vw;
  height: 36px; height: 13.5vh;
  border-radius: 10px; border-radius: 1.04vw;
  background-color: #1A2034;
  align-items: center;
  justify-content: center;
  margin-left: 8px; margin-left: 0.83vw;
}
.kb-close-img { width: 20px; width: 2.08vw; height: 20px; height: 7.5vh; }

.kb-ft { flex-direction: row; align-items: center; justify-content: flex-end; margin-top: 4px; margin-top: 1.5vh; }
.kb-cancel {
  height: 32px; height: 12vh;
  padding-left: 20px; padding-right: 20px;
  padding-left: 2.08vw; padding-right: 2.08vw;
  border-radius: 8px; border-radius: 0.83vw;
  background-color: #1A2034;
  align-items: center;
  justify-content: center;
  margin-right: 6px; margin-right: 0.63vw;
}
.kb-cancel-txt { font-size: 12px; font-size: 1.25vw; color: #A8B2CC; }
.kb-ok {
  height: 32px; height: 12vh;
  padding-left: 24px; padding-right: 24px;
  padding-left: 2.5vw; padding-right: 2.5vw;
  border-radius: 8px; border-radius: 0.83vw;
  background-color: #5B8CFF;
  align-items: center;
  justify-content: center;
}
.kb-ok-txt { font-size: 12px; font-size: 1.25vw; color: #FFFFFF; font-weight: bold; }

/* ---------- 日志诊断 ---------- */
.diag {
  width: 800px; width: 83.33vw;
  height: 246px; height: 92.5vh;
  border-radius: 12px; border-radius: 1.25vw;
  background-color: #10162A;
  padding: 10px; padding: 1.04vw;
  flex-direction: column;
}
.diag-list { flex: 1; }
.diag-line {
  font-size: 11px; font-size: 1.15vw;
  color: #8B95B0;
  line-height: 16px; line-height: 6vh;
  lines: 1;
  text-overflow: ellipsis;
}
.diag-empty { font-size: 12px; font-size: 1.25vw; color: #4A5270; }

/* ---------- 更新面板 ---------- */
.upd {
  width: 660px; width: 68.75vw;
  height: 218px; height: 82vh;
  border-radius: 14px; border-radius: 1.46vw;
  background-color: #10162A;
  padding: 14px; padding: 1.46vw;
  flex-direction: column;
}
.upd-hd { flex-direction: row; align-items: center; margin-bottom: 6px; margin-bottom: 2.3vh; }
.upd-title { font-size: 16px; font-size: 1.67vw; color: #EDF1FF; font-weight: bold; }
.upd-ver {
  font-size: 12px; font-size: 1.25vw;
  color: #8FF5E4;
  margin-left: 8px; margin-left: 0.83vw;
  padding-left: 8px; padding-right: 8px;
  padding-left: 0.83vw; padding-right: 0.83vw;
  padding-top: 2px; padding-bottom: 2px;
  border-radius: 5px; border-radius: 0.52vw;
  background-color: #12302B;
}
.upd-close { margin-left: auto; }

.upd-meta { flex-direction: row; align-items: center; margin-bottom: 6px; margin-bottom: 2.3vh; }
.upd-meta-txt { font-size: 11px; font-size: 1.15vw; color: #8B95B0; margin-right: 10px; margin-right: 1.04vw; }

.upd-notes { flex: 1; }
.upd-notes-txt { font-size: 13px; font-size: 1.35vw; color: #A8B2CC; line-height: 20px; line-height: 7.5vh; }

.upd-state {
  font-size: 11px; font-size: 1.15vw;
  color: #FFC962;
  margin-top: 6px; margin-top: 2.3vh;
  lines: 2;
}

.upd-ft { flex-direction: row; align-items: center; justify-content: flex-end; margin-top: 8px; margin-top: 3vh; }
.upd-later {
  height: 34px; height: 12.8vh;
  padding-left: 22px; padding-right: 22px;
  padding-left: 2.29vw; padding-right: 2.29vw;
  border-radius: 10px; border-radius: 1.04vw;
  background-color: #1A2034;
  align-items: center; justify-content: center;
  margin-right: 10px; margin-right: 1.04vw;
}
.upd-later-txt { font-size: 13px; font-size: 1.35vw; color: #A8B2CC; }
.upd-go {
  height: 34px; height: 12.8vh;
  padding-left: 26px; padding-right: 26px;
  padding-left: 2.71vw; padding-right: 2.71vw;
  border-radius: 10px; border-radius: 1.04vw;
  background-color: #5B8CFF;
  align-items: center; justify-content: center;
}
.upd-go-txt { font-size: 13px; font-size: 1.35vw; color: #FFFFFF; font-weight: bold; }

/* ---------- Toast ---------- */
.toast {
  position: absolute;
  left: 300px; left: 31.25vw;
  width: 360px; width: 37.5vw;
  bottom: 58px; bottom: 21.8vh;
  height: 34px; height: 12.8vh;
  border-radius: 10px; border-radius: 1.04vw;
  background-color: #232B47;
  align-items: center;
  justify-content: center;
}
.toast-txt { font-size: 12px; font-size: 1.25vw; color: #EDF1FF; }
</style>
