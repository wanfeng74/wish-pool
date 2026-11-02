# 接口文档

- 基地址：`http://<你的服务器>:17613`
- 响应统一 `application/json`，UTF-8
- 公开接口无需鉴权；管理接口需请求头 `X-Admin-Pass: <管理密码>`

> **为什么写操作是 GET**
> 词典笔真机上原生 `http` 的 `POST body` 会丢失，所以笔端所有写操作都走
> `GET + query`。服务端同时保留 POST 形式，方便浏览器 / 脚本调用。

---

## 公开接口

### `GET /healthz`

```json
{"ok": true, "rev": 1793621243, "clients": 2}
```

### `GET /api/meta`

分类、状态、字段上限、当前服务端版本号。

```json
{
  "ok": true,
  "categories": [{"id":"app","name":"想要新App","color":"#5B8CFF"}],
  "statuses": [{"id":"open","name":"待认领","color":"#8B95B0"}],
  "max_title": 40, "max_desc": 300, "max_nick": 20,
  "rev": 1793621243
}
```

### `GET /api/wishes`

| 参数 | 默认 | 说明 |
|---|---|---|
| `sort` | `votes` | `votes` 按支持度 / `new` 按时间 |
| `category` | 空 | 分类 id，空为全部 |
| `status` | 空 | `open` / `doing` / `done` / `rejected` |
| `q` | 空 | 标题/说明关键词 |
| `limit` | `200` | 1–500 |
| `offset` | `0` | 分页 |
| `client_id` / `sn` | 空 | 用于回填 `voted` / `claim_mine` |

```json
{
  "ok": true,
  "items": [{
    "id": 1, "title": "笔上哔哩哔哩", "desc": "…", "category": "app",
    "nick": "洛", "votes": 41, "status": "doing",
    "created_at": 1793600000,
    "voted": false,
    "claimed": true, "claimed_by": "洛", "claimed_at": 1793600100, "claim_mine": false
  }],
  "stats": {"wishes":7,"votes":7,"today":7,"contributors":2,
            "claimed":1,"doing":1,"done":0,"trashed":0},
  "rev": 1793621243
}
```

### `GET /api/stats`

```json
{"wishes":7,"votes":7,"today":7,"contributors":2,
 "claimed":1,"doing":1,"done":0,"trashed":0,"ok":true}
```

### `GET /api/wish/add`

| 参数 | 必填 | 说明 |
|---|---|---|
| `title` | 是 | 2–40 字 |
| `desc` | 否 | ≤300 字 |
| `nick` | 否 | ≤20 字，空为「匿名笔友」 |
| `category` | 否 | 非法值回落 `other` |
| `client_id` / `sn` | 否 | 创建者自动视为已支持 |

```json
{"ok": true, "wish": {...}, "stats": {...}}
```

### `GET /api/wish/{id}/vote` · `/unvote`

| 参数 | 说明 |
|---|---|
| `client_id` / `sn` | 投票者标识（去重用） |

同一人重复 +1 幂等（不重复累加）。

```json
{"ok": true, "status": "added", "wish": {...}, "my_votes": 1, "stats": {...}}
```

### `GET /api/wish/{id}/claim`（需管理密码）

| 参数 | 说明 |
|---|---|
| `nick` | 必填，服务端记录 |
| `client_id` / `sn` | 认领人标识 |

- 已被人认领 → `409`
- 缺昵称 → `400`
- 缺/错管理密码 → `401`（`{"need_pass": true}`）

```json
{"ok": true, "status": "claimed", "wish": {...}}
```

### `GET /api/wish/{id}/release`（需管理密码）

仅认领人本人可释放。`403` = 非本人，`400` = 未被认领。

### `GET /api/stream`（SSE）

`text/event-stream`，事件类型：

| event | 数据 |
|---|---|
| `snapshot` | 首帧全量 `{items, stats, rev}` |
| `wish_added` | `{wish, rev}` |
| `wish_voted` | `{wish:{id,votes}, status, rev}` |
| `wish_claimed` | `{wish:{id,claimed_by,votes}, action, rev}` |
| `wish_released` | `{wish:{id}, action, rev}` |
| `wish_status` | `{wish:{id,status}, rev}` |
| `wish_deleted` / `wish_restored` | `{id}` / `{wish}` |

每 15 秒发一次 `: ping` 保活。

### `GET /app-update`

| 参数 | 说明 |
|---|---|
| `version` | 当前版本，如 `1.3.0` |
| `platform` | `rk` / `cvis` / `rka` |

```json
{
  "ok": true, "hasUpdate": true, "force": 0,
  "latest": {"version":"1.3.0","url":"…/pkg/x.amr","size":354615,
             "md5":"…","notes":"…","platform":"rk"},
  "current": "1.2.1"
}
```

版本按数字段比较（`1.2.10 > 1.2.9`）。未发布时返回 `{"hasUpdate":false,"reason":"no-release"}`。

### `GET /pkg` · `GET /pkg/{name}`

安装包列表 / 下载。

### `GET /api/log`

笔端日志上报（GET 形式）：`sn`、`client_id`、`version`、`lines`（`t|l|m` 换行分隔）。

---

## 管理接口（`X-Admin-Pass`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/wishes[?deleted=1]` | 愿望列表 / 回收站 |
| GET | `/api/admin/claims` | 认领审计日志 |
| GET | `/api/admin/logs?sn=&limit=` | 客户端日志 |
| GET | `/api/admin/pkg` | 安装包列表 + 当前发布 |
| POST | `/api/admin/status?id=&status=` | 改状态 |
| POST | `/api/admin/restore?id=` | 恢复软删除 |
| DELETE | `/api/admin/wish/{id}[?hard=1]` | 删除 / 彻底删除 |
| POST | `/api/admin/purge` | 清空回收站 |
| PUT | `/api/admin/pkg/upload?name=x.amr` | 上传安装包（裸二进制） |
| POST | `/api/admin/release/save?version=&file=&notes=&force=&platform=` | 发布更新 |
| POST | `/api/admin/release/clear` | 撤销发布 |

未带 / 错误密码一律 `401`。

---

## 限流

按 IP 每 60 秒计数，超限返回 `429`：

| 动作 | 默认上限 | 环境变量 |
|---|---|---|
| 提交愿望 | 20 | `RATE_SUBMIT` |
| +1 / 取消 | 240 | `RATE_VOTE` |
| 认领 / 释放 | 60 | `RATE_CLAIM` |

## 校验与清洗

- 控制字符剥离，空白压缩，超长按显示宽度截断
- `title` < 2 字 → `400`
- 分类 / 状态非法值回落默认，不报错
- 请求日志对查询串脱敏（管理密码不落盘）
