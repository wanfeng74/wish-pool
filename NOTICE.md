# 第三方组件与数据来源

项目自身代码以 MIT 发布。以下为随项目分发的第三方内容及其许可。

## 1. 拼音字典 `client/src/services/pinyin-dict.js`

- 来源：[万象拼音](https://github.com/amzxyz/rime-wanxiang)（`amzxyz/rime-wanxiang`）
- 许可：**CC-BY-4.0**
- 用法：取单字音节表（414 音节 × 12 高频字）与词库（19790 条），去声调后转写为 JS 对象
- 文件头已保留来源与许可；二次分发请同样保留署名

## 2. 原生更新模块 `client/libs/libjsapi_updater.so` + `native/jsapi_updater.cpp`

- 作者：本项目作者自研（同作者另一项目的原生模块）
- 作用：导出 `download / install / start`，
  内部以 `fork + execv` 调用 `/usr/bin/miniapp_cli` 与 `/usr/bin/curl`
- 源码已随附，可参照 `native/README.md` 自行编译替换

## 3. 图标

`client/assets/icons/*.png` 与 `client/icon.png` 均由代码绘制生成，无第三方素材。
