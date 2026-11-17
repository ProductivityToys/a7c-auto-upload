# A7C Installer 0.1.0-preview.29

相机载荷为 `0.4.2-photos.15-preview`，已验证第一代 **ILCE-7C / 固件 2.00**。
桌面 App 和脚本共用安装核心，不升级固件，不安装 NAS 专用接收器，不处理 Photos 索引。

本批修复安装／卸载／恢复时的暂存文件残留、内核日志干扰 USB 回复，以及长命令输入丢字节。相机载荷、显示模块与 Windows 驱动实现保持不变。打包前已完成 2.00 实机卸载、重复卸载、中断恢复、34 项文件一致性和完整断电自启验收；本次重建与发布不再操作相机。三个平台包统一为 preview.29，详见[补测记录](https://github.com/ProductivityToys/a7c-auto-upload/blob/main/docs/installer-testing.md)、`validation.json` 和 `distributions.json`。

本版新增 JPEG／ARW 图片上传开关、拍照待机支持和按时间排序的混合媒体队列。CLI 可用 `install --reuse --photos --yes` 开启，`--no-photos` 关闭；更新时默认沿用已有选择。

本版包含：

- 简化主界面，连接后识别已安装版本；卡片直接提供「卸载相机服务」。
- 读取、FTP 测试及安装复用 USB 会话；测试结果就地显示，运行日志带时间戳并可复制。
- 安装后默认启动，核对上传器初始化和实际显示模块健康状态；通过后拔 USB 即可使用。
- 已保存密码留空沿用、新值替换，不回填密码到界面或持久保存到电脑。
- 复用近期目录、区分源等待与网络退避、取消补传间固定等待；连续补传准备均值由9.69降至7.66秒。
- 检测已退出的显示模块及旧显示暂存版本，需要重启时明确提示，避免反复启动。

本机GUI卸载、28项残留核对、干净会话首次安装、默认启动、真实FTP及SD回执验收通过。
完整记录见[安装器设计](DESIGN.md)。单个新片选中到复制6.47→6.27秒（各1样本），未宣称明显改善录制停止到进度条的等待。
分享与平台验收范围见[分享范围](SHARING.md)。

先读[安装说明](START_HERE.md)；撤销见[恢复与卸载](RECOVERY.md)，异常用[反馈模板](FEEDBACK.md)。
同包`validation.json`记录源码/实机验收范围，最终三个包的摘要与入口检查在发行目录的`packages.json`及当前发行清单中。
旧preview.11成品保持原字节，不能混用旧包摘要。默认不安装无线调试服务，不包含个人FTP配置或Sony库/字体。

## 桌面 App

macOS下载并打开 `*-macos-arm64.dmg`，将「A7C 自动上传.app」拖入「应用程序」，再从应用程序打开。
DMG内仅有App和应用程序入口；使用、卸载、反馈与许可说明都在App的「使用帮助」中。
Windows完整解压 `*-windows-x64.zip`，直接双击根目录「A7C 自动上传.exe」，旁边的_internal目录必须保留。
两端自带Python、Qt、USB运行库与安装载荷，无需另外安装Python或运行脚本。
当前是开发签名/未公证预览包，未配置发行签名。

1. 相机开机、USB 连接选「海量存储器」，接到电脑；关闭照片导入等占用程序。
2. macOS 点击「连接相机」时按系统提示授权；Windows App 请求管理员权限。
3. 点击「连接相机」，临时进入USB服务模式读取配置，并保持会话供测试和安装使用。安装前另核对机型、2.00固件及原厂接口文件；不符不写入程序。
4. 在相机原厂菜单配置家庭 Wi-Fi，再填写普通 FTP 的 IPv4、端口、用户名、密码、目录。
   目录须预先存在，账号须有写入、读取长度、改名、删除权限。建议专用账号。
   已有配置会自动填入；密码显示「已保存」，留空沿用、填写新密码才替换。首次安装须填写密码。
   读取的是**本上传器**已有配置，不是相机原厂FTP账号；密码不回填到界面、不持久保存到电脑。
5. 可先点「测试连接」，随后「安装到相机」或「更新配置」。测试仅创建、确认长度、改名、删除小文件。
6. 按需勾选「同时上传图片（JPEG 和 RAW）」，默认关闭。安装后自动启动并检查健康状态，通过后拔 USB、回到实时拍摄画面即可使用。
   自动补传未成功的视频及已启用的图片，保留卡上原件；之后使用无需电脑常驻。

开机入口通过动态加载器运行；安装器也能直接启动当前会话的服务，不强行重启。
更换已加载的显示模块或恢复旧版时，按具体提示断电；普通安装不例行取电池。
普通 FTP 沿用局域网明文协议；密码保存在相机 root 私有文件，未声称硬件加密。

## Windows USB 驱动：自动准备与恢复

桌面包自带libwdi 1.5.1和libusb-win32 1.4.0.2，无需另外下载Zadig。
以管理员权限打开App，点击「准备 Windows 驱动」，或直接执行安装、诊断等相机操作。
工具用Windows PnP读取设备型号，仅处理报告为ILCE-7C的普通模式054C:0D28/0D29；
经该相机进入服务模式后，再自动准备054C:0336驱动。脚本detect保持仅枚举；桌面「连接并读取配置」会建立临时服务会话。
不处理固件更新模式054C:03E2、多台相机或未知型号。

更换前保存原驱动信息、导出原第三方驱动包，持久记录在
`%ProgramData%/A7CInstaller/drivers`；操作中断后可单独恢复，不必重新安装相机服务。
「恢复普通 USB 导入」仅撤销本工具记录的驱动变更；已有手工驱动直接复用，未认领的驱动不会自动删除。
卸载相机服务默认勾选恢复Windows驱动，先退出相机服务会话，再恢复电脑驱动。
恢复完成后重新插拔USB检查普通导入。更换驱动期间资源管理器可能无法读取相机卷。

Windows 普通/服务模式驱动的实际安装和恢复已在同机 CLI 验收，范围见 validation.json；本次照片更新不改变驱动实现。
不因签名策略或组织策略受阻而关闭系统保护。libwdi会生成设备范围的签名证书；
恢复撤销驱动包，暂不清理Windows证书存储。源码、许可和重建脚本随包提供。

## 脚本

脚本包根目录提供明显入口：

- Mac：双击「开始使用.command」。
- Windows：双击「开始使用.cmd」，由系统请求管理员权限。
- Linux／终端：运行 `sh start.sh`。

进入数字菜单后，选1读取配置、选2安装或更新、选5卸载、选6恢复；9查看说明，0退出。
首次需要Python 3.11+及联网，入口会自动准备私有Python环境和固定依赖，失败后可重试。
密码通过隐藏输入填写，空密码可沿用刚读取的已有配置；不必编辑脚本或手工组合参数。
macOS启动菜单使用系统sudo，管理员密码不由程序保存。

高级命令仍可使用：

```sh
sh start.sh detect
sh start.sh inspect --full
sh start.sh diagnose
sh start.sh configure --reuse --yes
sh start.sh uninstall --yes
sh start.sh restore --yes
```

Windows高级命令在根目录执行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\app\install.ps1 <动作> ...`。
在源码目录直接使用install.sh / install.ps1；app目录保存程序与开发说明，用户无需进入或修改。

密码通过隐藏输入读取，没有 `--password` 参数。`--port` 默认 21，`--directory` 默认 `/`，
`--no-display` 可关闭进度显示。`configure` 与安装共用文件事务；显示组件已在内存中且有变更时，按提示完整重启。普通首次安装通过健康检查后直接使用。

## 中断恢复与卸载

桌面入口为相机卡片上的「卸载相机服务」，脚本为 `uninstall --yes`。
卸载停止现有任务并移除自启、程序与当前FTP配置；完成后按提示完整断电释放已映射的显示模块。
同一次开机中立即重装，可能需要先完成这一收尾步骤；首次安装不例行取电池。
Windows驱动恢复是独立的第二阶段，失败可单独重试，不必重复卸载相机服务。

只备份清单中的应用文件，不递归复制 RAM 挂载点、不访问 SD 原始块。
备份保存在相机 `/setting/a7c-installer/backup`，模式 0700/0600，可能含旧 FTP 密码。
这是单槽应用备份，每次安装、配置修改或卸载会覆盖；恢复后不等于恢复出厂。先按[回退说明](RECOVERY.md)判断，不要反复安装覆盖目标备份。
逐文件暂存并读回，最后启用启动项；替换启动库使用 rename，不覆盖已映射的 inode。

USB 中断后重新检测，选择「恢复上次安装」或 `restore --yes`。
恢复验证备份后还原应用状态，保留其他程序当前的 preload 项。
卸载移除安装器管理的程序、启用标记与当前 FTP 配置；保留媒体、SD 回执和私有回退备份。
上一代家庭研究文件不会被递归删除。
`diagnose` / App「读取运行日志」只读取固定启动/显示日志白名单，不读取密码或媒体。

## 开发与构建

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python app.py --demo
.venv/bin/python packaging/build.py --output /path/to/output
```

普通 FTP 组件测试可从仓库根目录运行（需要 C 编译器、POSIX shell 和测试 FTP 服务依赖）：

```sh
python3 -m pip install pyftpdlib==2.2.0
python3 -m unittest discover -s camera/uploader/plainftp/tests -v
python3 -m unittest discover -s camera/uploader/discovery/tests -v
```

测试资料已包含在 `camera/uploader/plainftp/tests/fixtures/`，不依赖历史 NAS 接收器或私人工作区。

Windows 使用 `.venv\Scripts\python.exe`。PyInstaller 必须在目标系统构建；
Mac 构建不会产生 Windows exe，也不把 arm64 当作 Intel Mac 通用包。

`a7c_installer/resources/camera.zip` 不含 Sony 库、字体、视频或个人配置。
重建载荷需要应用归档包、指定 PMCA 上游提交，以及 `camera/display/module/build.py --rect-service-trial --service-lifecycle-ack --ram-module-path /tmp_bt/a7X.so` 生成并通过 ARM 合约测试的显示构建：

```sh
python3 packaging/prepare.py --pmca /path/to/Sony-PMCA-RE --camera-build /path/to/camera-build --native-display /path/to/native-service-build
```

目录边界及实测见[安装器设计](DESIGN.md)；第三方来源见
[THIRD_PARTY.md](THIRD_PARTY.md) 及 `vendor/` 许可证。


## 离线发行自检

打包后的程序支持以下命令，仅校验内置载荷并加载依赖，不枚举或连接USB：

```sh
"A7C 自动上传.app/Contents/MacOS/A7C Installer" --self-check report.json --offline
```

Windows 对应 `& '.\A7C 自动上传.exe' --self-check report.json --offline`。
报告包含载荷版本、22项文件清单验证结果及camera.zip的SHA256，可与同包 `validation.json` 比较。
`--demo --screenshot preview.png` 可生成演示界面，演示模式不执行相机操作。

Mac构建缓存使用已挂载外置盘的固定目录，例如：

```sh
PYINSTALLER_CONFIG_DIR=/Volumes/ExtWorkspace/build-cache/a7c-installer/pyinstaller \
  /path/to/venv/bin/python packaging/build.py --output /path/to/output \
  --work-root /Volumes/ExtWorkspace/build-cache/a7c-installer/macos
```

Windows在本机使用同一个构建环境和固定work目录。`packaging/release.py` 在打包前比对两端
App内的camera.zip与源码字节一致，并检查validation版本；最终包附README、DESIGN、验证记录与许可证。
`--mac-app` 指向已构建App，`--windows-zip` 提供原生构建归档，`--output` 指向外置盘发行目录。

用户说明已内置App，文档变更也需要重新构建桌面包；不再生成仅替换外部README的说明补订包。
发布脚本核对两端App内的帮助和载荷与源码一致，再生成Mac DMG、Windows ZIP及脚本包。
