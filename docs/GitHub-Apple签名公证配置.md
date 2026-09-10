# GitHub Actions Apple 签名与公证配置

在仓库 **Settings → Secrets and variables → Actions** 中配置以下 Secrets：

- `APPLE_CERTIFICATE_BASE64`：Developer ID Application `.p12` 文件的 Base64 内容
- `APPLE_CERTIFICATE_PASSWORD`：导出 `.p12` 时设置的密码
- `APPLE_SIGNING_IDENTITY`：证书名称，例如 `Developer ID Application: Your Name (TEAMID)`
- `APPLE_TEAM_ID`：Apple Developer Team ID
- `APPLE_API_KEY_ID`：App Store Connect API Key ID
- `APPLE_API_ISSUER`：App Store Connect API Issuer ID
- `APPLE_API_KEY_BASE64`：App Store Connect API 私钥 `.p8` 文件的 Base64 内容

PowerShell 生成 Base64：

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("DeployMate.p12"))
[Convert]::ToBase64String([IO.File]::ReadAllBytes("AuthKey_ABC123.p8"))
```

工作流会在对应架构的 macOS runner 上构建 `.app`，使用 Hardened Runtime 签名，创建 `.dmg`，提交 Apple Notarization，完成后将票据 Staple 到 `.app` 和 `.dmg`，并执行 `codesign`、`stapler`、`spctl` 验证。

未配置 Apple Secrets 时，macOS 构建会明确失败，不会上传未签名的 DMG。
