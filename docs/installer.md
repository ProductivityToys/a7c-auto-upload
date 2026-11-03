# 安装器实现

GUI 和 CLI 共用 `installer/a7c_installer/operations.py`：核对机型／固件和依赖，保存单槽备份，提交应用文件，启动服务并检查健康状态。

- `transport/sony_usb.py`：临时 USB 服务会话、文件操作和退出处理；相机目录始终使用 POSIX 路径。
- `drivers/`：Windows libusb 驱动准备、原驱动记录与恢复；按实际内核驱动选择访问库。
- `configuration.py`：FTP 参数校验；读取已有配置，密码留空沿用、新值替换。
- `gui.py`：连接、已安装识别、就地 FTP 测试结果、安装和卸载；日志可展开、复制。
- `cli.py`：命令行参数、隐藏密码输入、JSON 输出。
- `resources/camera.zip`：22 个已验收的相机应用文件与清单，不含 Sony 库、字体或个人配置。
- `packaging/`：原生平台构建、桌面内置说明与三种发行包。

相机端通过原厂媒体接口读取视频，使用普通 FTP 传输，确认远端长度后写 SD 成功回执。录像状态轻量采样触发新片扫描，空闲低频兜底；上传时保持唤醒，收尾释放。左下角图标和进度条由原厂绘制线程处理。

详细命令见 [CLI 指南](cli-guide.md)，用户操作见 [安装说明](../installer/START_HERE.md)，恢复见 [恢复与卸载](../installer/RECOVERY.md)。

验证结果见 [validation.json](../installer/validation.json)；最终包摘要和入口检查见 [distributions.json](../installer/distributions.json)。
