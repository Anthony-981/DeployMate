# DeployMate - 运维实施工程师记录助手

## 简介
DeployMate 是面向软件实施、运维实施工程师的本地桌面效率工具。

主要功能：
- 项目管理
- 机器信息管理（按 IP 自动识别和合并）
- 历史资料导入（Excel `.xlsx` / CSV `.csv`）
- SOP问题记录：记录实施问题、解决方法和后续建议
- 出差费用管理
- 项目资料导出

## 安装依赖
```bash
pip install -r requirements.txt
```

## 运行
```bash
python src/main.py
```

## 技术栈
- Python 3.12
- PySide6（桌面界面）
- SQLite + SQLAlchemy（本地数据库）
- openpyxl（Excel 处理）
- python-docx（Word 处理）

## 数据存储

- 源码开发运行使用 `data/deploymate_dev.db`。
- Windows 免安装版使用 `%LOCALAPPDATA%/DeployMate/deploymate.db`。
- macOS 应用使用 `~/Library/Application Support/DeployMate/deploymate.db`。
- 所有新增和修改操作都会立即提交到本地 SQLite，关闭软件后数据不会丢失。
- 可通过 `DEPLOYMATE_DATA_DIR` 指定自定义数据目录。

## 免安装版本构建

PyInstaller 不支持跨平台编译，需要分别在 Windows 和 macOS 上构建。

- Windows：运行 `build-exe.bat`，输出免安装单文件 `dist-portable/DeployMate.exe`。
  构建脚本优先使用本地 PySide6 6.8.3 兼容环境，程序不需要 Python 或 Qt 安装；GitHub Actions 仍建议发布目录 ZIP，以便在不同安全策略的 Windows 环境中更稳定。
- 最新开发环境测试：运行 `launch-deploymate.bat`，优先使用项目内的 `build-env-68` 环境。新安装和新开发库默认为空，不会自动创建示例数据。
- macOS：安装 `requirements.txt` 和 `requirements-build.txt` 后运行 `bash build-macos.sh`，输出 `dist/DeployMate.app`。

开发阶段不执行正式打包，功能完成后再生成并验证两个平台的发布文件。
