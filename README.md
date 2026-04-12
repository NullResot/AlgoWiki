# AlgoWiki 项目（Django + Vue + MySQL）

本仓库是 AlgoWiki 的全栈第一版实现：

- 后端：Django REST API，包含基于角色的权限控制（默认 MySQL，保留 sqlite 仅作应急兼容）
- 前端：Vue 3 + Vite 单页应用，包含主页、Wiki、问答、个人中心、管理后台、扩展页面

## 文档入口

- 项目说明书：`docs/项目说明书.md`
- 详细使用手册：`docs/详细使用手册.md`
- 维护手册：`docs/维护手册.md`
- 远程部署指南：`docs/远程部署指南.md`
- GitHub 发布清单：`docs/GitHub发布清单.md`
- 文档索引：`docs/README.md`
- 贡献说明：`CONTRIBUTING.md`
- 安全策略：`SECURITY.md`

## 默认内容来源

- `backend/data/xcpc_readme_snapshot.md`
  - 这是仓库内随代码一起版本化的 XCPC 内容快照，来源于 `https://github.com/NullResot/xcpc`
- `frontend/public/wiki-assets/`
  - 这是与 XCPC 快照配套的静态图片资源
- `python manage.py seed_initial_data`
  - 负责初始化超管、公告、友链、赛事公告、赛程、默认技巧与基础站点内容
- `python manage.py seed_xcpc_reference_content`
  - 负责把 XCPC 快照同步成可浏览、可修订的 Wiki 文章

## 已实现的核心功能

- 五类用户角色
  - 匿名用户：仅可浏览
  - 普通用户：评论、提交 issue/request、提交修订建议、收藏文章、查看个人中心
  - 学校用户：具备普通用户能力，并在 `school` 作用域分类（赛事板块）拥有内容审核/编辑权限
  - 管理员用户：用户管理、内容管理、公告发布
  - 超级管理员用户：具备管理员全部能力，并可进行角色任命（`set_role`）

- 公告系统
  - 管理员/超级管理员可发布公告
  - 首页公告栏自动展示最新公告
  - 首次访问弹窗
    - 登录用户：基于未读公告接口 + acknowledge 接口
    - 匿名用户：基于 localStorage 的首次展示逻辑

- 知识库与协作
  - 结构化分类体系
  - Wiki 文章 CRUD 与可见性控制（`published` / `hidden` / `draft`）
  - 修订提议流程（`pending` / `approved` / `rejected`）
  - 评论与收藏（star），支持评论回复与用户自助删除评论

- 社区问答
  - 问题发布、回答、采纳回答、关闭/重开问题
  - 问题删除采用隐藏机制（软删除），回答可由作者或管理员隐藏
  - 问答页支持“全部/我的问题”筛选，问题与回答可由作者/管理员在线编辑
  - 问答输入支持本地草稿恢复（提问草稿与按问题区分的回答草稿）

- 站内 AI 助手
  - 右下角悬浮按钮打开聊天面板，支持拖动位置
  - 仅基于站内公开内容检索后回答，并返回来源链接
  - 管理后台新增 `AI 助手` 配置页，支持管理模型、Base URL、限额和欢迎语
  - 仅超级管理员可新增/修改/删除配置、切换默认配置和更新 API Key
  - API Key 只会以全星号掩码显示，不会在接口和前端中回显明文

- 个人中心
  - 个人信息展示与编辑（学校、简介、头像）
  - 邮箱验证码注册、邮箱找回密码、个人中心修改/验证邮箱
  - 支持在线修改登录密码（旧密码校验 + token 轮换）
  - 贡献统计、最近行为、收藏列表（支持分页加载与关键词筛选）
  - 我的提问历史、我的回答历史、我的评论历史、我的 issue/request 记录（支持分页加载与筛选）

- 站内通知中心
  - 登录用户支持查看通知列表、未读计数
  - 支持单条标记已读与全部标记已读
  - 关键协作事件自动触发通知（修订审核结果、工单分派与状态变更、问答互动、公告发布）

- 账号与系统安全（重点增强）
  - 登录失败锁定：同用户名 + IP 在时间窗口内多次失败会被临时锁定
  - Token 轮换：每次登录签发新 Token 并回收旧 Token
  - Token 过期：服务端校验 Token TTL，过期自动失效
  - 封禁/软删除即时下线：封禁或软删除用户时立刻回收 Token
  - 密码历史防复用：默认禁止复用最近 5 次密码
  - 邮箱唯一校验：注册与邮箱变更均校验邮箱唯一（忽略大小写）
  - 邮箱验证码链路：注册、找回密码、修改邮箱均通过验证码完成
  - 密码强度校验：注册与改密均接入 Django 密码校验器
  - 接口节流：登录/注册/找回密码/改密/改邮箱接口增加速率限制
  - 安全响应头：启用 `X-Frame-Options`、`nosniff`、`Referrer-Policy` 等基线配置
- 生产环境硬化：`DEBUG=0` 时强制要求自定义 `SECRET_KEY`，支持 HTTPS/HSTS 强制策略
- 请求追踪与运维观测：全站返回 `X-Request-ID`，支持应用日志、安全日志、慢请求日志、健康检查

- 审核台
  - 学校用户/管理员可进入审核台处理修订提议（支持筛选、批量通过/驳回、分页加载）
  - 管理员可在管理台继续处理 issue/request 与用户状态（支持批量处理）
  - 管理员可在管理台删除用户（软删除）并恢复用户（reactivate）
  - 管理员可在管理台进行内容治理（文章发布/隐藏/删除、评论隐藏，支持批量操作）
  - 管理员可在管理台治理问答内容（问题筛选、批量关闭/重开/隐藏）
  - 管理员可在管理台分派工单处理人（支持按提交者/处理人筛选，批量分派、清空分派）
  - 管理员可在管理台维护扩展页面（创建、编辑、启停）
  - 管理员可在管理台维护分类（创建、编辑、显示/隐藏、作用域切换、上移下移排序）
  - 管理员可在管理台查看操作日志（按事件类型/用户/目标类型/payload 关键词筛选，支持分页加载）
  - 管理员可在管理台查看安全审计日志（登录失败/锁定/改密/封禁等安全事件，支持筛选与导出）
  - 管理员可在管理台查看数据概览（用户、内容、工单/修订等统计）及近 7 天活跃趋势、事件类型分布

- 扩展页面
  - 支持多个预留页面，通过 `/extra/:slug` 访问

- 响应式与风格
  - 参考 OI-wiki 的信息布局（左侧目录 + 中央正文 + 右侧辅助栏）
  - 默认蓝色风格（已移除主题切换按钮）
  - 已完成桌面、平板、移动端三档布局适配（含移动端导航抽屉）
  - 已加入全局 Toast 提示反馈（管理台操作即时反馈）

## 后端启动说明（MySQL）

### 0. 前置条件

- 已安装并启动 MySQL（建议 8.0+）
- 有一个可创建数据库的账号（如 `root`）
- 已创建 Python 虚拟环境 `venv`

### 1. 安装依赖

```powershell
cd <project-root>
venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 2. 配置环境变量（推荐使用 `backend/.env`）

复制 `backend/.env.example` 为 `backend/.env`，至少配置：

```dotenv
DB_ENGINE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=algowiki
DB_USER=root
DB_PASSWORD=your-password
```

生产环境建议同时配置：

- `DJANGO_DEBUG=0`
- `DJANGO_SECRET_KEY`（必须自定义）
- `DJANGO_ALLOWED_HOSTS`（公网域名/IP）
- `DJANGO_CSRF_TRUSTED_ORIGINS`（https 域名）
- `DJANGO_SERVE_FRONTEND=1`（让 Django 直接托管 `frontend/dist`，公网同源访问）
- `DJANGO_USE_X_FORWARDED_HOST=1`、`DJANGO_USE_X_FORWARDED_PORT=1`
- `DJANGO_SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https`
- `MEDIA_ROOT=/srv/algowiki/media`
- `SECURE_SSL_REDIRECT=1`、`SECURE_HSTS_SECONDS=31536000`
- `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- `EMAIL_HOST=smtpdm.aliyun.com`
- `EMAIL_PORT=465`
- `EMAIL_HOST_USER=<你的阿里云发信地址>`
- `EMAIL_HOST_PASSWORD=<SMTP 密码>`
- `EMAIL_USE_SSL=1`
- `DEFAULT_FROM_EMAIL=AlgoWiki <你的阿里云发信地址>`
- `AI_ASSISTANT_ENCRYPTION_KEY=<建议显式配置的随机密钥>`
- `THROTTLE_ASSISTANT_ANON=15/hour`
- `THROTTLE_ASSISTANT_USER=60/hour`

AI 助手补充说明：

- 若未配置 `AI_ASSISTANT_ENCRYPTION_KEY`，后端会基于 `DJANGO_SECRET_KEY` 派生一把可用密钥
- 生产环境建议显式配置 `AI_ASSISTANT_ENCRYPTION_KEY`，避免未来更换 `DJANGO_SECRET_KEY` 后无法解密旧的 API Key
- 当前接入方式为 OpenAI 兼容 `chat/completions` 协议，默认可直接用于 DeepSeek
- 超级管理员在后台 `/manage/assistant` 中录入 API Key，录入后只显示掩码，不支持明文回看

### 3. 初始化 MySQL 数据库并导入基础数据

```powershell
cd <project-root>
powershell -ExecutionPolicy Bypass -File .\scripts\init_database.ps1 `
  -DbEngine mysql `
  -DbHost 127.0.0.1 `
  -DbPort 3306 `
  -DbName algowiki `
  -DbUser root `
  -DbPassword "<your-db-password>" `
  -SuperadminPassword "<set-a-strong-superadmin-password>"
```

如果你要把旧 sqlite 数据整体迁移到 MySQL：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init_database.ps1 `
  -DbEngine mysql `
  -DbHost 127.0.0.1 `
  -DbPort 3306 `
  -DbName algowiki `
  -DbUser root `
  -DbPassword "<your-db-password>" `
  -SourceSqlitePath "<project-root>\\storage\\db_live.sqlite3" `
  -SuperadminPassword "<set-a-strong-superadmin-password>"
```

### 4. 后台启动后端（不阻塞当前终端）

```powershell
cd <project-root>
powershell -ExecutionPolicy Bypass -File .\scripts\start_backend.ps1 `
  -DbEngine mysql `
  -DbHost 127.0.0.1 `
  -DbPort 3306 `
  -DbName algowiki `
  -DbUser root `
  -DbPassword "<your-db-password>" `
  -ServerHost 127.0.0.1 `
  -Port 8001 `
  -Background `
  -HealthCheck `
  -PidFile ".\storage\backend.pid"
```

停止后端：

```powershell
Stop-Process -Id (Get-Content .\storage\backend.pid) -Force
```

健康检查：

```text
GET /api/health/
```

### 5. 导入附件图片（Markdown 的 `assets/*.png`）

```powershell
cd <project-root>
New-Item -ItemType Directory -Path frontend\public\wiki-assets -Force | Out-Null
Expand-Archive -LiteralPath "<path-to-your-assets.zip>" -DestinationPath frontend\public\wiki-assets -Force
```

### 6. 服务器部署（推荐）

当前版本已支持：

- 后端自动读取 `backend/.env`
- MySQL 作为默认生产数据库
- Django 直接托管 `frontend/dist`，前后端同源公网访问
- Docker 多阶段构建，支持把前端静态产物直接打进后端镜像
- `gunicorn + nginx` 反向代理部署
- `/media/` 上传文件在生产环境下可直接由 Django 暴露
- 请求日志、安全日志与慢请求监控
- 容器启动前自动等待数据库并执行 Django `check`

如果你是“本地电脑 + VS Code Remote-SSH + 国内 ECS”的场景，推荐按《`docs/远程部署指南.md`》执行。当前仓库已经补齐了以下远程部署文件：

- 生产环境变量示例：`deploy/env.production.example`
- 私有验证环境示例：`deploy/env.private-validation.example`
- Docker Compose：`docker-compose.server.yml`
- Docker 入口脚本：`deploy/docker-entrypoint.sh`
- 服务器基线脚本：`deploy/server-bootstrap.sh`
- 服务器启动脚本：`deploy/server-compose-up.sh`
- 服务器验收脚本：`deploy/server-verify.sh`
- 本地验证库导出脚本：`deploy/export-local-db.sh`
- SQL 导入 RDS 脚本：`deploy/import-sql-to-rds.sh`
- 本地镜像导出脚本：`scripts/build_server_image.ps1`
- 本地源码打包脚本：`scripts/package_server_source.ps1`

推荐顺序：

1. 用 `Remote-SSH: Open Folder on Host...` 打开 `/srv/algowiki`
2. 在服务器执行 `deploy/server-bootstrap.sh` 安装 Docker、Compose、swap
3. 在本地执行 `scripts/build_server_image.ps1` 和 `scripts/package_server_source.ps1`
4. 把源码包和镜像包上传到服务器
5. RDS 未准备好前，使用 `deploy/env.private-validation.example` 和 `--profile local-db` 做私有验证
6. RDS 就绪后，改用 `deploy/env.production.example`，不再启用 `local-db` profile
7. 备案通过后，再接 Nginx、域名和 HTTPS

本地构建镜像：

```powershell
cd <project-root>
powershell -ExecutionPolicy Bypass -File .\scripts\build_server_image.ps1 -Tag 20260312
powershell -ExecutionPolicy Bypass -File .\scripts\package_server_source.ps1
```

服务器基线：

```bash
cd /srv/algowiki
chmod +x deploy/server-bootstrap.sh
SWAP_MB=4096 CONFIGURE_UFW=1 ./deploy/server-bootstrap.sh
```

私有验证部署：

```bash
cd /srv/algowiki
cp deploy/env.private-validation.example deploy/.env.private-validation
chmod +x deploy/server-compose-up.sh
./deploy/server-compose-up.sh --env-file deploy/.env.private-validation --profile local-db --image-archive /root/algowiki-web-20260312.tar
```

说明：

- `docker-compose.server.yml` 中的 `db` 服务仅在 `--profile local-db` 时启动
- `web` 服务支持 `APP_IMAGE=<prebuilt-image>`，适合本地构建后上传到服务器
- `deploy/server-compose-up.sh` 默认使用 `docker compose up -d --no-build`
- 如果这一次发布不想等服务器从海外镜像仓库慢拉镜像，可直接在本地执行 `scripts/quick-release-to-server.ps1`，走“本地构建 -> 上传镜像包 -> 服务器直接加载”这条链路
- 如果服务器只有 `docker-compose` v1，请优先使用 `deploy/server-compose-up.sh`/`deploy/server-verify.sh`，不要直接手写 `docker-compose up`，否则 `APP_IMAGE` 等变量可能不会按预期生效
- 容器启动时会自动等待数据库、执行 `check`、`migrate` 和 `collectstatic`
- `APP_BIND` 默认是 `127.0.0.1`，公网访问应通过 Nginx 转发，而不是直接暴露 8001
- 正式环境请使用 `deploy/env.production.example`，并将 `DB_HOST` 指向 RDS 私网地址
- 备案通过前，只建议做私有验证，不建议正式开放公网站点

正式环境临时快速上线示例：

```powershell
cd D:\AlgoWiki_Project
powershell -ExecutionPolicy Bypass -File .\scripts\quick-release-to-server.ps1 `
  -ServerHost 139.224.212.247 `
  -ServerUser root
```

说明：

- 该脚本会自动构建 `algowiki-web:quick-<git-sha>` 镜像
- 自动上传镜像包、`docker-compose.server.yml`、`deploy/server-compose-up.sh` 和 `deploy/server-update-from-archive.sh`
- 然后在服务器执行归档镜像更新
- 这条链路通常比服务器直接从 `ghcr.io` 拉镜像更快，适合当前过渡期使用

从私有验证库切换到 RDS 的最短路径：

```bash
cd /srv/algowiki
chmod +x deploy/export-local-db.sh deploy/import-sql-to-rds.sh
./deploy/export-local-db.sh --env-file deploy/.env.private-validation
./deploy/import-sql-to-rds.sh --env-file deploy/.env.production --sql-file storage/backups/<dump-file>.sql
./deploy/server-compose-up.sh --env-file deploy/.env.production --image-archive /root/algowiki-web-<tag>.tar
```

公网访问建议：

- 域名写入 `DJANGO_ALLOWED_HOSTS`
- HTTPS 域名写入 `DJANGO_CSRF_TRUSTED_ORIGINS`
- 若走反向代理，启用 `DJANGO_SECURE_PROXY_SSL_HEADER`
- MySQL 使用 `utf8mb4`
- RDS 可按需开启 TLS（`DB_SSL_CA` 等）

## 前端启动说明

```powershell
cd <project-root>\frontend
npm install
npm run dev
```

Vite 开发服务器会将 `/api` 代理到 `http://127.0.0.1:8001`。

如果已经执行 `npm run build`，并在后端环境中设置 `DJANGO_SERVE_FRONTEND=1`，则部署时可直接通过 Django/Gunicorn 访问首页 `/`，不需要再单独暴露 Vite 开发服务。

## 关键 API 路径

- 健康检查：`/api/health/`
- 鉴权：
  - `/api/auth/register-challenge/`
  - `/api/auth/register-email-code/`
  - `/api/auth/register/`
  - `/api/auth/password-reset-code/`
  - `/api/auth/password-reset/`
  - `/api/auth/login/`
  - `/api/auth/logout/`
- 首页：`/api/home/summary/`
- 个人中心：`/api/me/`
- 邮箱验证与修改：`/api/me/email-code/`、`/api/me/change-email/`
- 个人贡献历史：`/api/me/events/`
- 个人安全历史：`/api/me/security-events/`（仅当前用户）
- 个人安全概览：`/api/me/security-summary/`（失败登录/锁定/改密统计）
- 密码修改：`/api/me/change-password/`
- 管理概览：`/api/admin/overview/`
- AI 助手：
  - `/api/assistant/config/`
  - `/api/assistant/chat/`
  - `/api/assistant-configs/`
  - `/api/assistant-configs/stats/`
  - `/api/assistant-configs/{id}/set-default/`
  - `/api/assistant-configs/{id}/test-connection/`
- 个人历史：`/api/questions/mine/`、`/api/answers/mine/`、`/api/comments/mine/`
- 通知中心：
  - `/api/notifications/`
  - `/api/notifications/unread-count/`
  - `/api/notifications/{id}/mark-read/`
  - `/api/notifications/mark-all-read/`
- Wiki：`/api/categories/`、`/api/articles/`、`/api/comments/`、`/api/revisions/`
- 内容批量治理：
  - `/api/articles/bulk-moderate/`（`ids + action(publish/hide/delete)`）
  - `/api/comments/bulk-hide/`（`ids`）
  - `/api/questions/bulk-moderate/`（`ids + action(close/reopen/hide)`）
- 修订批量审核：`/api/revisions/bulk-review/`（`ids + action(approve/reject) + review_note`）
- 收藏条目：`/api/articles/starred/`
- 社区：`/api/questions/`、`/api/answers/`、`/api/issues/`
- 工单筛选：`/api/issues/?status=&kind=&author=&assignee=&order=`
- 工单批量处理：`/api/issues/bulk-set-status/`（`ids + status + assign_to(可选) + resolution_note(可选)`）
- 问题筛选：`/api/questions/?mine=1`（仅看当前用户问题）
- 管理筛选：`/api/questions/?author=<username或id>&status=<open|closed|hidden>`
- 公告：`/api/announcements/`、`/api/announcements/unread/`、`/api/announcements/{id}/acknowledge/`
- 用户管理：`/api/users/`、`/api/users/assignees/`、`/api/users/{id}/ban/`、`/api/users/{id}/reactivate/`、`/api/users/{id}/set_role/`
- 用户批量治理：`/api/users/bulk-action/`（`ids + action`，支持 `ban/unban/soft_delete/reactivate/set_role`）
- 操作日志：`/api/events/`、`/api/events/export/`（支持时间区间筛选 `start_at` / `end_at`）
- 安全审计日志：`/api/security-logs/`（管理员可按事件类型/用户名/IP/成功状态/detail/时间筛选）
- 安全审计导出：`/api/security-logs/export/`（CSV）
- 安全审计概览：`/api/security-logs/summary/`（近窗口失败事件统计与高频异常 IP）
- 问答操作：`/api/questions/{id}/close/`、`/api/questions/{id}/reopen/`、`/api/answers/{id}/accept/`
- 扩展页面：`/api/pages/`、`/api/pages/{slug}/`

## 备注

- 后端默认按 MySQL 模式运行（`DB_ENGINE=mysql`）。
- 若需要临时切换 sqlite，可设置 `DB_ENGINE=sqlite`，默认数据库文件为 `storage\\db_live.sqlite3`。
- Django、`manage.py`、`gunicorn`、`wsgi/asgi` 入口现在都会自动读取 `backend/.env`。
- 默认应用日志位于 `storage/logs/algowiki.log`，安全日志位于 `storage/logs/security.log`。
- 每个请求都会返回 `X-Request-ID`，建议在排障和用户反馈时一并记录。
- 发布到 GitHub 前请勿提交 `.env`、数据库文件、`frontend/dist`、`backend/staticfiles`、`backend/media` 中的运行时上传内容，以及 `storage/` 下的日志/导出文件。
- 若前端出现 `分类加载失败` / `条目加载失败` 且响应为 `500`，通常是数据库结构落后：请在后端目录重新执行一次 `python manage.py migrate`。
- 若遇到 `mysqlclient ... is required` 或 `MySQLdb` 版本冲突：
  - 确认使用项目虚拟环境安装依赖：`venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt`
  - 该项目已内置 PyMySQL 兼容适配，可直接使用 MySQL，无需单独安装 `mysqlclient`。
- 若遇到 sqlite `disk I/O error`：
  - 建议改用可写目录数据库文件，例如：
    - `$env:DB_ENGINE='sqlite'`
    - `$env:SQLITE_NAME=\"$env:TEMP\\algowiki_dev.sqlite3\"`
    - `venv\\Scripts\\python.exe backend\\manage.py migrate`
