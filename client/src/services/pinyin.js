/**
 * 拼音输入（无系统输入法时的中文输入方案）
 *
 * 方案对齐「三角洲摸金」pinyin.js：
 *   1. 单音节（ni）      -> 该音节高频字
 *   2. 完整拼音（nihao） -> 词库命中优先，其次按音节切分做常用字组合
 *   3. 前缀（nih）       -> 词库前缀 + 音节前缀，边打边选
 *
 * 数据：pinyin-dict.js（万象拼音，CC-BY-4.0）
 *   PY_SYL   414 音节 × 12 高频字
 *   PY_WORDS 19790 条词
 *
 * 纯 ES5，不依赖任何原生库。
 */

import { PY_SYL, PY_KEYS, PY_WORDS } from './pinyin-dict.js'

/* 应用词频表：许愿池/词典笔场景的高频词。
 * 原词库是通用词，未必收录这些专有说法（如 cidianbi / wuziqi），
 * 这里钉死优先级，保证一打就出对的词。 */
var WORD_HINTS = {
  /* 本应用 */
  xuyuan: '许愿', yuanwang: '愿望', xuyuanchi: '许愿池', bishang: '笔上',
  cidianbi: '词典笔', shurufa: '输入法', gongneng: '功能', xitong: '系统',
  yingyong: '应用', ruanjian: '软件', jiekou: '接口', shuju: '数据',
  guanli: '管理', mima: '密码', shezhi: '设置', quanbu: '全部',
  zuixin: '最新', paixu: '排序', sousuo: '搜索', zhichi: '支持',
  renling: '认领', kaifa: '开发', shangxian: '上线', dairenling: '待认领',

  /* 阅读学习 */
  yuedu: '阅读', biji: '笔记', fanyi: '翻译', danci: '单词', shengci: '生词',
  cuoti: '错题', lianzi: '练字', dafen: '打分', kouyu: '口语',
  gendu: '跟读', langdu: '朗读', keben: '课本', xuexi: '学习', beisong: '背诵',

  /* 功能类 */
  xiazai: '下载', lixian: '离线', huancun: '缓存', shoucang: '收藏',
  zhuigeng: '追更', duandian: '断点', daochu: '导出',
  kuaichuan: '快传', juyuwang: '局域网', wenjian: '文件',
  jietu: '截图', changjietu: '长截图', ziping: '字幕',
  xuanfu: '悬浮', piliang: '批量',

  /* 桌面/系统 */
  zhuomian: '桌面', xiaozujian: '小组件', suoping: '锁屏', shizhong: '时钟',
  shense: '深色', zhuti: '主题', yinliang: '音量', bizhi: '壁纸',
  shoushi: '手势', kuijie: '快捷', caozuo: '操作',

  /* 游戏 */
  youxi: '游戏', wuziqi: '五子棋', eluosi: '俄罗斯', fangkuai: '方块',
  tanchishe: '贪吃蛇', doudizhu: '斗地主', saolei: '扫雷', renji: '人机',
  duizhan: '对战', lianji: '联机',

  /* 应用名 */
  bilibili: '哔哩哔哩', weixin: '微信', zhihu: '知乎', yinyue: '音乐',
  xiaoshuo: '小说', liulanqi: '浏览器', jisuanqi: '计算器',
  fanqie: '番茄', wangyiyun: '网易云',

  /* 通用高频 */
  nihao: '你好', zhongguo: '中国', pengyou: '朋友', xiexie: '谢谢',
  zaijian: '再见', shijie: '世界', diannao: '电脑', shouji: '手机',
  youdao: '有道', shijian: '时间', wenti: '问题',
  fankui: '反馈', jianyi: '建议', gonggao: '公告', xiaoxi: '消息',
  keyi: '可以', shenme: '什么', zenme: '怎么', xihuan: '喜欢',
  xuyao: '需要', xiwang: '希望'
}

var _wordKeys = null
var _keys = null

function _wordKeysAll() {
  if (_wordKeys === null) _wordKeys = Object.keys(PY_WORDS)
  return _wordKeys
}

function _sortedKeys() {
  if (_keys) return _keys
  _keys = PY_KEYS.slice(0).sort(function (a, b) {
    return b.length - a.length || (a < b ? -1 : 1)
  })
  return _keys
}

function _norm(s) {
  s = String(s === null || s === undefined ? '' : s).toLowerCase()
  s = s.replace(/[^a-z]/g, '')
  return s.slice(0, 24)
}

function _chars(syl, n) {
  var t = PY_SYL[syl] || ''
  return t.slice(0, n || 12).split('')
}

function _pushUniq(out, arr, max) {
  for (var i = 0; i < arr.length && out.length < max; i++) {
    if (out.indexOf(arr[i]) < 0) out.push(arr[i])
  }
}

/* 词库查询：精确命中优先，否则做前缀匹配 */
function _wordsFor(s) {
  var direct = PY_WORDS[s]
  if (direct && direct.length) return direct.slice(0, 8)

  var keys = _wordKeysAll()
  var out = []
  for (var i = 0; i < keys.length && out.length < 8; i++) {
    var k = keys[i]
    if (k.indexOf(s) !== 0) continue
    var arr = PY_WORDS[k]
    if (!arr) continue
    _pushUniq(out, arr, 8)
  }
  return out
}

/* 音节前缀候选 */
function _prefix(raw) {
  var out = []
  var keys = PY_KEYS
  for (var i = 0; i < keys.length && out.length < 16; i++) {
    var k = keys[i]
    if (k.indexOf(raw) !== 0) continue
    _pushUniq(out, _chars(k, 4), 16)
  }
  return out
}

/* 词频表前缀（应用词优先） */
function _hintPrefix(raw) {
  var out = []
  var keys = Object.keys(WORD_HINTS)
  for (var i = 0; i < keys.length && out.length < 8; i++) {
    if (keys[i].indexOf(raw) !== 0) continue
    var w = WORD_HINTS[keys[i]]
    if (w && out.indexOf(w) < 0) out.push(w)
  }
  return out
}

/* 把连续拼音切成音节；失败返回 null */
function _segment(raw) {
  var keys = _sortedKeys()
  var out = []
  var i = 0
  while (i < raw.length) {
    var hit = ''
    for (var k = 0; k < keys.length; k++) {
      var key = keys[k]
      if (raw.substr(i, key.length) === key) { hit = key; break }
    }
    if (!hit) return null
    out.push(hit)
    i += hit.length
    if (out.length > 12) return null
  }
  return out
}

/* 多音节：每音节取前 N 字做笛卡尔组合，用字表顺序当权重 */
function _combo(syls) {
  var limit = syls.length <= 2 ? 3 : 2
  var groups = []
  for (var i = 0; i < syls.length; i++) {
    var cs = _chars(syls[i], limit)
    if (!cs.length) return []
    groups.push(cs)
  }
  var out = []
  function rec(idx, cur, score) {
    if (out.length >= 24) return
    if (idx >= groups.length) { out.push({ text: cur, score: score }); return }
    var g = groups[idx]
    for (var j = 0; j < g.length && out.length < 24; j++) {
      rec(idx + 1, cur + g[j], score + (12 - j))
    }
  }
  rec(0, '', 0)
  out.sort(function (a, b) { return b.score - a.score })
  return out.map(function (x) { return x.text })
}

function _rawCandidates(s) {
  if (!s) return []

  /* 单音节优先给单字，避免 ni 先出「你还」这类词 */
  if (PY_SYL[s]) return _chars(s, 12)

  var out = []

  /* 1) 原词库 */
  _pushUniq(out, _wordsFor(s), 10)

  /* 2) 音节组合兜底（词库没收的词也能打出来） */
  var sg = _segment(s)
  if (sg && sg.length >= 2) {
    _pushUniq(out, _combo(sg), 12)
  }

  /* 3) 还没打完：应用词前缀 + 音节前缀 */
  if (out.length < 8) _pushUniq(out, _hintPrefix(s), 12)
  if (out.length < 8) _pushUniq(out, _prefix(s), 12)

  return out
}

/** 对外：根据拼音串返回候选（字符串数组，最多 24 个） */
export function pinyinCandidates(raw) {
  var s = _norm(raw)
  if (!s) return []

  var hint = WORD_HINTS[s]
  if (hint) {
    var list = [hint]
    _pushUniq(list, _rawCandidates(s), 12)
    return list
  }
  return _rawCandidates(s)
}

export function pinyinKnown(s) {
  return !!PY_SYL[_norm(s)]
}
