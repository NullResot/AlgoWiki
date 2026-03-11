# GitHub 发布清单

本清单用于在将项目公开发布到 GitHub 前做最后检查。

## 1. 代码与文件

- 确认未提交 `.env`
- 确认未提交数据库文件
- 确认未提交 `frontend/dist`
- 确认未提交 `backend/staticfiles`
- 确认未提交 `backend/media` 的真实上传文件
- 确认未提交 `storage/` 下的日志、导出文件、PID 文件
- 确认未提交本地 IDE、临时测试和个人说明文件

## 2. 安全

- 确认所有密码都为占位符或运行时生成
- 确认 README 中没有真实服务器 IP、口令、Token、邮箱账号
- 确认 `backend/.env.example` 与 `deploy/env.production.example` 只保留示例值
- 确认默认超级管理员密码不是固定公开口令

## 3. 文档

- README 能独立说明项目用途、技术栈、运行方式
- 项目说明书、使用手册、维护手册齐全
- 贡献说明和安全策略已补齐
- License 已明确

## 4. 仓库结构

当前工作区有一个嵌套的 `backend/.git`。

发布前必须在下面两种方案里二选一：

### 方案 A：以根目录作为新的 GitHub 仓库

适合你要把整个项目作为一个完整仓库发布的情况。

需要人工处理：

1. 备份当前仓库历史
2. 移除或迁移 `backend/.git`
3. 在根目录重新初始化 Git 仓库

### 方案 B：保留 `backend` 作为独立仓库

适合你只想公开后端，或明确要做子仓库/子模块管理。

不建议当前项目采用这个方案，因为你的前后端和部署文件都在根目录。

## 5. 发布前建议命令

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.tests
cd frontend
npm run build
```

## 6. 发布后建议

- 开启 GitHub 仓库的安全扫描
- 开启 Dependabot
- 打开 issue / pull request
- 在仓库首页说明项目现状和维护范围
