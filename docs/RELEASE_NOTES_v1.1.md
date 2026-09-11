# DeployMate V1.1 更新说明

## 本次更新

- 新增“生成共享包”功能：管理员可将当前程序和真实数据库打包为 ZIP，接收方解压后即可直接使用原有账号和数据。
- 共享数据包自动读取程序同目录的 `DeployMate-data.db`，无需重新创建管理员或手动导入数据库。
- 修复 Windows 生成共享包时 SQLite 文件句柄未及时释放导致临时目录清理失败的问题。
- 公开发布包仍使用独立、空白的生产数据库，避免将开发数据或业务数据带入安装包。
- 统一 Windows、macOS Intel 和 macOS Apple Silicon 三个平台的版本号与发布文件名为 `V1.1`。

## 发布文件

- `DeployMate-V1.1-windows-x64.exe`
- `DeployMate-V1.1-macos-intel-x64.dmg`
- `DeployMate-V1.1-macos-arm64.dmg`

共享数据包包含真实账号和业务数据，仅适合私下交付，不应上传到公开仓库。
