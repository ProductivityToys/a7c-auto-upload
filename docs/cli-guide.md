# CLI 操作指南

CLI 与 GUI 共用安装核心。推荐 AI 助手使用发行脚本包，按任务选择命令；详细用户操作见[安装说明](../installer/START_HERE.md)。

当前验收状态：macOS、Windows CLI 实机卸载、全新安装及默认启动通过；Windows 驱动自动准备与恢复、新视频上传、SD 回执已验证。Windows 打包 GUI 的连接、已安装识别、FTP 测试和断开另有验证；详见[版本与验收](../installer/validation.json)。

## 入口

脚本包需要 Python 3.11+，首次运行会准备环境和依赖。

| 工作目录 | macOS / Linux | Windows PowerShell |
| --- | --- | --- |
| 解压后的脚本包根目录 | `sh start.sh <action>` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\app\install.ps1 <action>` |
| 源码仓库根目录 | `sh installer/install.sh <action>` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\installer\install.ps1 <action>` |

带参数的 Windows 设备操作在管理员 PowerShell 中运行；macOS 入口会为设备操作调用 sudo。Linux 入口需要相应 USB 访问权限，尚无完整实机验收记录。

以下例子以发行脚本包根目录为工作目录。

## 命令

| 任务 | 命令 |
| --- | --- |
| 只枚举 USB | `sh start.sh detect` |
| 读取型号、安装版本、配置与健康状态 | `sh start.sh inspect` |
| 首次安装或设置新 FTP 配置 | `sh start.sh install --host 192.168.1.20 --port 21 --username camera-upload --directory /Camera --yes` |
| 沿用本上传器保存的配置更新程序 | `sh start.sh install --reuse --yes` |
| 启动已安装的当前版本 | `sh start.sh start` |
| 读取固定白名单诊断记录 | `sh start.sh diagnose` |
| 关闭自定义显示 | `sh start.sh configure --reuse --no-display --yes` |
| 恢复最近一次操作前的应用状态 | `sh start.sh restore --yes` |
| 卸载服务 | `sh start.sh uninstall --yes` |

按任务选择一项，不要将表中命令全部顺序执行。`detect` 不切换模式；其他设备操作通常建立并结束一次 USB 服务会话。安装内部已有完整固件校验，只有单独审查依赖时才需要 `inspect --full`。

Windows 卸载默认联动恢复本工具修改的 USB 驱动；需要保留时使用 `--keep-driver`。驱动恢复也可单独运行 `driver-restore --yes`。

## 密码与输出

新密码通过隐藏交互输入；已有配置可使用 `--reuse`。当前没有 `--password`、`--password-stdin` 或环境变量密码接口。
复用的是本上传器的配置，不是相机原厂 FTP 配置；密码不回填界面，也不持久保存到电脑。

安装核心 CLI 向 stdout 输出 JSON，向 stderr 输出操作日志；首次准备环境还可能输出依赖安装日志。

**安装文件提交成功后，即使服务启动未就绪，CLI 仍可能返回退出码 0。** 按字段判断结果：

| 字段 | 含义 |
| --- | --- |
| `supported` | `inspect` 的固件适配判断 |
| `pending_recovery` | 存在未完成事务，进入恢复流程 |
| `installed_version` / `enabled` | 已安装版本与是否启用 |
| `service_started` | 安装/启动动作是否确认服务已启动；`false` 时不能报告服务正常 |
| `health.state` | `ready` 为健康；开启显示时 upload/display 均应 ready，关闭显示时 display=disabled 为预期 |
| `requires_power_cycle` | 需按提示完整重启，重复调用 start 不会清除旧显示会话 |

失败结果可能不带 `health`。出现 `pending_recovery` 时按[恢复说明](../installer/RECOVERY.md)处理；服务健康与实际收到视频分别核对。

## 固件版本说明

对外兼容性标注为：**2.00 已验证，其他固件版本未测试。**

实现是否可复用取决于新版是否保留所依赖的原厂接口和程序布局。目前 preview.23 使用 2.00 适配清单：
检查固件版本、内部接口布局及 9 项原厂依赖文件摘要，因此其他版本可能直接被当前安装器拦截。
“未测试”不代表当前包已经允许安装所有新版，安装器会先检查实际兼容性。

## 实现入口

- `installer/a7c_installer/`：共享安装核心、CLI、GUI、USB 与 Windows 驱动适配。
- `camera/uploader/plainftp/`：相机端调度、普通 FTP、重试和 SD 回执。
- `camera/display/`：屏幕服务标记与上传进度。

去重使用文件名、大小和时间戳匹配 SD 回执；完成确认使用 FTP 响应与远端长度，不完整读回视频或计算视频正文 SHA256。
更多资料见[文档索引](README.md)。
