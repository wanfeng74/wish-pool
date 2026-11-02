# 原生模块 `updater`

预编译产物 `libjsapi_updater.so`（rk / aarch64），源码见 `jsapi_updater.cpp`。

## 为什么需要原生层

笔端固件没有把"安装应用"暴露成 JS 接口，唯一途径是命令行：

```bash
/usr/bin/miniapp_cli install <amr 路径>
```

同时平台自带的 `jsapi.http.downloadFile` 在该固件上会挂住不 resolve，
所以下载也放进原生层（内部用 `/usr/bin/curl`，并会先建目录）。

## 导出

| 函数 | 说明 | 返回 |
|---|---|---|
| `download(url, path)` | 下载到 path | `0` 成功 |
| `install(amrPath)` | 安装包 | `0` 成功 |
| `start(appid)` | 启动 / 重启应用 | `0` 成功 |

JS 侧通过**动态** `require('updater')` 访问。**禁止静态 import** ——
静态 import 在模块求值前就要解析，包内缺少 `.so` 时会整页黑屏。

## 自行编译

需要 aarch64 glibc 交叉工具链：

```bash
aarch64-linux-gnu-g++ -shared -fPIC -O2 \
  -o libjsapi_updater.so jsapi_updater.cpp \
  -I<quickjs 头文件目录>
```

编译后替换 `client/libs/libjsapi_updater.so`。
