# Security Policy

## Supported Use

本仓库面向学习、演示和二次开发。
生产部署前，请至少完成以下配置：

- 设置自定义 `DJANGO_SECRET_KEY`
- 设置强密码的超级管理员账号
- 配置 `DJANGO_ALLOWED_HOSTS`
- 配置 `DJANGO_CSRF_TRUSTED_ORIGINS`
- 启用 HTTPS
- 使用 MySQL 并定期备份

## Reporting a Vulnerability

如果你发现安全问题，请不要直接公开提交包含可利用细节的 issue。

建议至少提供：

- 问题类型
- 影响范围
- 复现步骤
- 可能的修复建议

如果仓库所有者提供了私下联系方式，请优先私下报告。
