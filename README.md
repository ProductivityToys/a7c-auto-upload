# A7C Auto Upload

给第一代 Sony A7C 补上 **Wi-Fi 视频自动上传**。

录完视频，相机通过家中 Wi-Fi 自动上传到普通 FTP 服务器，屏幕上显示上传进度。
**照片继续使用相机原厂 FTP。** 安装后不需要电脑或手机常驻，也不需要 NAS 专用接收程序。

**已验证：Sony A7C / ILCE-7C，固件 2.00。其他固件版本未测试。**

## For humans / 给人类看

**推荐使用 GUI 安装器。** 从 [Releases](https://github.com/ProductivityToys/a7c-auto-upload/releases) 下载对应平台的安装包：

| 电脑 | 安装包 | 打开方式 |
| --- | --- | --- |
| macOS · Apple Silicon | `*-macos-arm64.dmg` | 把 App 拖入「应用程序」后打开 |
| Windows · x64 | `*-windows-x64.zip` | 完整解压，打开「A7C 自动上传.exe」 |

GUI 自带运行环境，不需要安装 Python。

### 开始使用

先在相机中配置家中 Wi-Fi，并准备一个可用的普通 FTP 账号和上传目录。

1. **连接相机**：USB 选「海量存储器」，连接电脑，在 App 点「连接相机」。
2. **填写 FTP**：输入服务器、账号、密码和目录，点「测试连接」。
3. **安装并启动**：点「安装到相机」，等到「安装成功 · 服务正常」，拔掉 USB 即可使用。

之后正常拍摄视频即可：左下角小标记表示服务运行中，上传时变成进度条，完成后恢复小标记。
程序会补传旧视频、自动上传新增视频，保留卡上原文件，断网后重试。

已有安装会自动读取配置；更新时密码留空即可沿用。需要卸载时，连接相机，在主界面点 **「卸载相机服务」**。

[详细安装、更新与恢复说明 →](docs/README.md)

## For AI / 给 AI 看

**推荐使用 CLI。** macOS、Windows 的实机安装和卸载已验证。把下面这段复制给你的 AI 助手：

```text
请帮我安装并配置 A7C Auto Upload。
项目：https://github.com/ProductivityToys/a7c-auto-upload

它让第一代 Sony A7C / ILCE-7C 通过家庭 Wi-Fi 自动上传视频到普通 FTP，照片仍使用原厂 FTP。
请先阅读仓库 docs/README.md 与 docs/cli-guide.md，优先使用最新脚本包的 CLI。
先读取相机型号、固件和已有安装状态，再按需安装或更新。
缺少的 FTP 信息向我询问；密码通过隐藏输入处理，不要让我在聊天中发送。
固件 2.00 已验证，其他版本未测试，兼容性以当前安装器检测结果为准。

脚本包根目录使用：sh start.sh <action>
Windows 使用：powershell -NoProfile -ExecutionPolicy Bypass -File .\app\install.ps1 <action>
已有配置可用 install --reuse --yes；已有当前版本可用 start。

安装后检查 service_started、health.state 和 requires_power_cycle，再告诉我是否已可使用。
不要只根据退出码 0 报成功。只有需要接线、授权或安全输入时再请我操作。
```

[CLI 命令、返回值与技术文档 →](docs/README.md)
