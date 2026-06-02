# Security Policy

## Supported Versions

本仓库面向学习、演示和二次开发。正式环境上线前，请至少完成以下事项：

- 配置自定义 `DJANGO_SECRET_KEY`
- 配置强密码的管理员账号
- 配置 `DJANGO_ALLOWED_HOSTS`
- 配置 `DJANGO_CSRF_TRUSTED_ORIGINS`
- 启用 HTTPS
- 使用 MySQL 并建立备份策略
- 确认图片、动态、评论和审核入口都经过必要的风控与限制

## Reporting a Vulnerability

如果你发现安全问题，请不要直接公开提交可利用细节。

建议报告中至少包含：

- 问题类型
- 影响范围
- 复现路径
- 期望修复方式

如果仓库维护者提供了私下联系方式，请优先私下报告。
