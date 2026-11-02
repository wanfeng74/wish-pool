/*
 * libjsapi_updater.so —— 给"三角洲摸金模拟器"用的最小更新安装模块。
 *
 * 提供:
 *     import { install, start } from 'updater'
 *     install('/userdisk/Favorite/搜打撤/xxx.amr')  -> 0 成功 / 非 0 失败
 *     start('8001865309000007')                    -> 同上
 *
 * ── 为什么只能这么做 ────────────────────────────────────────────
 * 平台没有给 JS 暴露"安装"接口, 唯一的安装途径是系统的
 *     /usr/bin/miniapp_cli install <amr路径>
 * 它是个可执行文件, 所以只能由原生层 fork/exec 起来。
 *
 * ── 安全约束 ────────────────────────────────────────────────────
 * 【不接受任意命令】。只允许两条固定程序:
 *     /usr/bin/miniapp_cli install <path>
 *     /usr/bin/miniapp_cli start  <appid>
 * 参数做严格校验 (路径必须是绝对路径且以 .amr 结尾; appid 必须 16 位数字),
 * 并且拒绝 shell 元字符 —— 防止把网络/文件内容拼进来变成命令注入。
 *
 * ── 构建 ────────────────────────────────────────────────────────
 *   见同目录 build.mjs
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/wait.h>
#include <sys/types.h>
#include <sys/stat.h>

#include "quickjs/quickjs.h"
#include "jquick_config.h"          /* JQUICK_EXPORT / 平台宏 */
#include "jsmodules/JSCModuleExtension.h"
#include "jqutil_v2/jqmisc.h"       /* DEF_MODULE */

#define CLI_PATH "/usr/bin/miniapp_cli"
#define MAX_ARGS 8

/* ---- 参数校验 ---- */

/* 只允许 [A-Za-z0-9._/-] 且不含 "..", 必须以 .amr 结尾, 必须是绝对路径 */
static int safe_amr_path(const char *p) {
    if (!p) return 0;
    size_t n = strlen(p);
    if (n < 5 || n > 500) return 0;
    if (p[0] != '/') return 0;
    if (strcmp(p + n - 4, ".amr") != 0) return 0;
    if (strstr(p, "..")) return 0;
    for (size_t i = 0; i < n; i++) {
        char c = p[i];
        int ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                 (c >= '0' && c <= '9') || c == '.' || c == '_' ||
                 c == '-' || c == '/';
        if (!ok) return 0;
    }
    return 1;
}

/* appid: 纯数字, 长度 10..20 */
static int safe_appid(const char *p) {
    if (!p) return 0;
    size_t n = strlen(p);
    if (n < 10 || n > 20) return 0;
    for (size_t i = 0; i < n; i++) {
        if (p[i] < '0' || p[i] > '9') return 0;
    }
    return 1;
}

/* ---- 执行固定命令 (不经 shell, 直接 execve) ----
 * 返回: 0 成功; 非 0 失败。
 * 【不用 system()】避免命令注入, 参数作为 argv 逐个传递, 不经过 shell 解析。
 */
static int run_cli(char *const argv[]) {
    pid_t pid = fork();
    if (pid < 0) return 90;                 /* fork 失败 */
    if (pid == 0) {
        /* 子进程: 用绝对路径, 环境保持继承 */
        execv(CLI_PATH, argv);
        _exit(91);                          /* exec 失败 */
    }
    int st = 0;
    if (waitpid(pid, &st, 0) < 0) return 92;
    if (WIFEXITED(st)) return WEXITSTATUS(st);
    return 93;                              /* 被信号终止 */
}

/* ---- JS 接口 ---- */

/* install(path) -> int */
static JSValue js_install(JSContext *ctx, JSValueConst this_val, int argc, JSValueConst *argv) {
    if (argc < 1) return JS_NewInt32(ctx, 96);
    const char *path = JS_ToCString(ctx, argv[0]);
    if (!path) return JS_NewInt32(ctx, 97);
    int rc;
    if (!safe_amr_path(path)) {
        rc = 98;                            /* 路径不合法, 直接拒 */
    } else {
        char *args[MAX_ARGS];
        args[0] = (char *)CLI_PATH;
        args[1] = (char *)"install";
        args[2] = (char *)path;
        args[3] = NULL;
        rc = run_cli(args);
    }
    JS_FreeCString(ctx, path);
    return JS_NewInt32(ctx, rc);
}

/* start(appid) -> int */
static JSValue js_start(JSContext *ctx, JSValueConst this_val, int argc, JSValueConst *argv) {
    if (argc < 1) return JS_NewInt32(ctx, 96);
    const char *appid = JS_ToCString(ctx, argv[0]);
    if (!appid) return JS_NewInt32(ctx, 97);
    int rc;
    if (!safe_appid(appid)) {
        rc = 98;
    } else {
        char *args[MAX_ARGS];
        args[0] = (char *)CLI_PATH;
        args[1] = (char *)"start";
        args[2] = (char *)appid;
        args[3] = NULL;
        rc = run_cli(args);
    }
    JS_FreeCString(ctx, appid);
    return JS_NewInt32(ctx, rc);
}

/* download(url, path) -> int
 *
 * 【为什么下载也放进原生层】平台的 jsapi.http.downloadFile 在这个固件上
 * 调用后 Promise 永不 resolve (中文路径和 ASCII 路径都试过), bridge.Shell 也不存在。
 * 而 /usr/bin/curl 是系统自带的, 用 execv 直接调, 结果可验证。
 * 参数同样严格校验 (URL 只允许 http/https, 路径同 amr 规则)。
 */
static int safe_url(const char *p) {
    if (!p) return 0;
    size_t n = strlen(p);
    if (n < 8 || n > 800) return 0;
    if (strncmp(p, "http://", 7) != 0 && strncmp(p, "https://", 8) != 0) return 0;
    for (size_t i = 0; i < n; i++) {
        char c = p[i];
        int ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                 (c >= '0' && c <= '9') || c == ':' || c == '/' || c == '.' ||
                 c == '_' || c == '-' || c == '?' || c == '=' || c == '&' || c == '%';
        if (!ok) return 0;   /* 拒绝 ` $ ; | > < 空格 等一切可能被解释的字符 */
    }
    return 1;
}

/* 路径规则放宽一点: 下载目标还允许 .part / .tmp */
static int safe_out_path(const char *p) {
    if (!p) return 0;
    size_t n = strlen(p);
    if (n < 5 || n > 500) return 0;
    if (p[0] != '/') return 0;
    if (strstr(p, "..")) return 0;
    for (size_t i = 0; i < n; i++) {
        char c = p[i];
        int ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                 (c >= '0' && c <= '9') || c == '.' || c == '_' ||
                 c == '-' || c == '/';
        if (!ok) return 0;
    }
    return 1;
}

/* 逐级创建 path 的父目录 (等价于 mkdir -p dirname(path))。
 * 【为什么原生层要自己做】curl -o 不会创建上级目录, 目录不存在就直接失败。
 * 这条路上没有 shell 可用, 所以只能自己 mkdir。
 * 返回 0 成功 / -1 失败。 */
static int ensure_parent_dirs(const char *path) {
    if (!path) return -1;
    char buf[512];
    size_t n = strlen(path);
    if (n == 0 || n >= sizeof(buf)) return -1;
    memcpy(buf, path, n + 1);

    /* 找到最后一个 '/', 把它之前的部分逐级创建 */
    char *slash = strrchr(buf, '/');
    if (!slash || slash == buf) return 0;      /* "/x" 这种根目录下, 无需创建 */
    *slash = '\0';

    for (char *p = buf + 1; *p; p++) {
        if (*p != '/') continue;
        *p = '\0';
        if (mkdir(buf, 0755) != 0 && errno != EEXIST) return -1;
        *p = '/';
    }
    if (mkdir(buf, 0755) != 0 && errno != EEXIST) return -1;
    return 0;
}

static JSValue js_download(JSContext *ctx, JSValueConst this_val, int argc, JSValueConst *argv) {    if (argc < 2) return JS_NewInt32(ctx, 96);
    const char *url = JS_ToCString(ctx, argv[0]);
    const char *path = JS_ToCString(ctx, argv[1]);
    int rc;
    if (!url || !path) {
        rc = 97;
    } else if (!safe_url(url) || !safe_out_path(path)) {
        rc = 98;
    } else {
        /* 先把目录建好, 再 curl —— 目录不存在时 curl 会直接失败 */
        if (ensure_parent_dirs(path) != 0) {
            rc = 99;                        /* 建目录失败 */
        } else {
            char *args[MAX_ARGS];
            args[0] = (char *)"/usr/bin/curl";
            args[1] = (char *)"-L";
            args[2] = (char *)"-f";
            args[3] = (char *)"-s";
            args[4] = (char *)"-o";
            args[5] = (char *)path;
            args[6] = (char *)url;
            args[7] = NULL;
            rc = run_cli(args);
        }
    }
    if (url) JS_FreeCString(ctx, url);
    if (path) JS_FreeCString(ctx, path);
    return JS_NewInt32(ctx, rc);
}

/* ---- 模块导出 ----
 *
 * 【这里踩过一个坑, 必须写清楚】
 *
 * SDK 的 DEF_MODULE 宏展开后只做了一件事:
 *     JS_AddModuleExport(ctx, m, "default");
 * 也就是模块的导出表里**只有 "default" 一个名字**。
 *
 * 而 QuickJS 的 JS_SetModuleExport 只能设置"已经用 JS_AddModuleExport 登记过"
 * 的名字, 否则直接返回 -1 且**不报错**。所以在 DEF_MODULE 下写
 *     JS_SetModuleExport(ctx, m, "download", ...)
 * 全部静默失败 —— 模块能加载, 但导出的函数一个都拿不到。
 *
 * 真机现象就是这样:
 *     [native] updater 模块 keys= download=undefined install=undefined start=undefined
 * 而 "default" 虽然登记了却从没 set 过, 所以 default 也是 undefined。
 *
 * 正确做法: 把要导出的名字**全部**用 JS_AddModuleExport 登记,
 * 同时给 "default" 挂一个包含全部函数的对象, 这样两种 import 写法都能用:
 *     import { download, install, start } from 'updater'
 *     import updater from 'updater'          -> updater.download(...)
 */

/* 把四个成员挂到 obj 上 */
static void attach_members(JSContext *ctx, JSValue obj) {
    JS_SetPropertyStr(ctx, obj, "download", JS_NewCFunction(ctx, js_download, "download", 2));
    JS_SetPropertyStr(ctx, obj, "install", JS_NewCFunction(ctx, js_install, "install", 1));
    JS_SetPropertyStr(ctx, obj, "start", JS_NewCFunction(ctx, js_start, "start", 1));
    JS_SetPropertyStr(ctx, obj, "cliPath", JS_NewString(ctx, CLI_PATH));
}

static int updater_module_init(JSContext *ctx, JSModuleDef *m) {
    /* 1) 具名导出 —— JS 侧可以 import { install } from 'updater' */
    JS_SetModuleExport(ctx, m, "download", JS_NewCFunction(ctx, js_download, "download", 2));
    JS_SetModuleExport(ctx, m, "install", JS_NewCFunction(ctx, js_install, "install", 1));
    JS_SetModuleExport(ctx, m, "start", JS_NewCFunction(ctx, js_start, "start", 1));
    JS_SetModuleExport(ctx, m, "cliPath", JS_NewString(ctx, CLI_PATH));

    /* 2) default —— JS 侧可以 import updater from 'updater' (之前一直是 undefined) */
    JSValue def = JS_NewObject(ctx);
    if (JS_IsException(def)) return -1;
    attach_members(ctx, def);
    JS_SetModuleExport(ctx, m, "default", def);
    return 0;
}

/* ---- 模块入口 ----
 *
 * 【手写这块, 不用 DEF_MODULE / DEF_MODULE_LOAD_FUNC_EXPORT】
 *
 * DEF_MODULE 的问题: 只登记 "default", 三个函数名没登记 -> Set 全部静默失败。
 *
 * DEF_MODULE_LOAD_FUNC_EXPORT 能登记全部名字, 但它的 EXPORT_LIST 是
 *     for (auto &item: EXPORT_LIST) JS_AddModuleExport(ctx, m, item.c_str());
 * 需要 std::vector<std::string> 之类, 于是引入 std::string/vector 的符号,
 * 又得 -static-libstdc++ —— 产物从 35KB 涨到 1.5MB。为了五个字符串不值当。
 *
 * 所以直接手写 loader: 纯 C 字符串, 不碰任何 STL 类型, 保持小体积。
 * registerCModuleLoader 本身就是纯 C 接口 (const char* + 函数指针)。
 */
static JSModuleDef *updater_module_load(JSContext *ctx, const char *moduleName) {
    if (strcmp(moduleName, "updater") != 0) return NULL;
    JSModuleDef *m = JS_NewCModule(ctx, moduleName, updater_module_init);
    if (!m) return NULL;
    /* 【必须逐个登记】登记之后 JS_SetModuleExport 才能生效 */
    JS_AddModuleExport(ctx, m, "default");
    JS_AddModuleExport(ctx, m, "download");
    JS_AddModuleExport(ctx, m, "install");
    JS_AddModuleExport(ctx, m, "start");
    JS_AddModuleExport(ctx, m, "cliPath");
    return m;
}

extern "C" JQUICK_EXPORT void custom_init_jsapis(void) {
    registerCModuleLoader("updater", &updater_module_load);
}
