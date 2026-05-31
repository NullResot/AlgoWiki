# GHCR 部署与一键更新

本文档说明如何使用 GitHub Container Registry (`ghcr.io`) 作为 AlgoWiki 的正式环境镜像仓库，并让服务器通过一条命令更新到最新版本。测试环境和快部署路径请看《分支与测试环境部署》。

如果你要执行日常发布、更新、回滚，请优先看：

- [发布与更新操作手册](./发布与更新操作手册.md)

## 方案概览

- 代码仓库：`https://github.com/NullResot/AlgoWiki`
- 镜像仓库：`ghcr.io/nullresot/algowiki-web`
- GitHub Actions 自动构建并推送镜像
- 服务器只执行一条更新命令，不再手动上传大体积镜像 tar

## 安全说明

这个方案可以安全使用，前提是维持当前项目的边界不变。

- 公开的是镜像和源码，不是服务器上的运行时密钥。
- 数据库密码、Django 密钥、管理员密码仍然只保存在服务器的 `deploy/.env.production`。
- 当前 [`Dockerfile`](../Dockerfile) 只复制 `backend/`、`frontend/dist` 和 `deploy/docker-entrypoint.sh`，不会把整个仓库打包进镜像。
- 当前 [`.dockerignore`](../.dockerignore) 已排除 `storage/`、`backend/.env`、`frontend/node_modules/`、`deploy/*` 等本地或敏感内容。

需要坚持的规则：

- 不要把 `.env.production`、私钥、数据库备份放进 `backend/` 或 `frontend/` 目录。
- 不要把服务器专用密钥提交到 Git。
- 不要把 `Dockerfile` 改成 `COPY . .` 这种把整个仓库全部复制进镜像的写法。

如果项目代码仓库本身就是公开的，那么公开镜像一般不会新增本质上的保密风险。它主要暴露的是“可运行产物”，不是运行时凭据。

## 仓库内已增加的内容

- GitHub Actions 工作流：
  - [`publish-ghcr-image.yml`](../.github/workflows/publish-ghcr-image.yml)
- 服务器一键更新脚本：
  - [`server-update-from-registry.sh`](../deploy/server-update-from-registry.sh)

## 第一次配置

### 1. 推送代码到 GitHub

把当前仓库推送到：

- `git@github.com:NullResot/AlgoWiki.git`

工作流会在 `main` 分支 push 后自动执行。

### 2. 等待 GitHub Actions 首次构建完成

首次成功后，镜像会出现在：

- `ghcr.io/nullresot/algowiki-web:latest`
- `ghcr.io/nullresot/algowiki-web:sha-<commit>`
- `ghcr.io/nullresot/algowiki-web:main`

### 3. 把 GHCR 镜像设为 Public

如果 GitHub 首次创建出的 package 默认不是公开的，需要在 GitHub 页面中手动改一次：

1. 打开仓库主页
2. 进入 `Packages`
3. 打开 `algowiki-web`
4. 在 package 设置里把可见性改成 `Public`

这一步通常只需要做一次。

## 服务器首次切换到 GHCR

在服务器 `/srv/algowiki` 目录执行：

```bash
cd /srv/algowiki
chmod +x deploy/*.sh
./deploy/server-update-from-registry.sh --image ghcr.io/nullresot/algowiki-web:latest --release ghcr-latest
```

脚本会自动完成这些事：

- 备份 `deploy/.env.production`
- 把 `APP_IMAGE` 改为 GHCR 镜像
- 拉取最新镜像
- 删除旧的 `algowiki_web_1` 容器，绕开 `docker-compose v1` 的 `ContainerConfig` 重建问题
- 启动新容器
- 直接执行健康检查

## 日常更新

第一次切到 GHCR 后，后续更新只要一条命令：

```bash
cd /srv/algowiki
./deploy/server-update-from-registry.sh
```

前提是：

- `deploy/.env.production` 里的 `APP_IMAGE` 已经是 `ghcr.io/nullresot/algowiki-web:latest`

## 指定版本更新

如果你想固定到某个提交镜像，而不是 `latest`，可以执行：

```bash
cd /srv/algowiki
./deploy/server-update-from-registry.sh --image ghcr.io/nullresot/algowiki-web:sha-<commit> --release <release-name>
```

这也可以用于回滚。

## 回滚示例

```bash
cd /srv/algowiki
./deploy/server-update-from-registry.sh --image ghcr.io/nullresot/algowiki-web:sha-abc1234 --release rollback-sha-abc1234
```

## 常见问题

### 1. 服务器需要保存 GitHub Token 吗

如果镜像是 `Public`，通常不需要。服务器可以直接 `docker pull`。

### 2. 这个方案会不会暴露数据库密码

不会。数据库密码在服务器的 `deploy/.env.production`，不在镜像里。

### 3. 为什么不直接服务器 `git pull`

因为当前生产部署是“镜像启动”，不是“源码挂载运行”。只更新服务器上的源码目录，并不会直接更新正在运行的容器。

### 4. 为什么脚本里要先删除旧容器

因为你的服务器当前使用 `docker-compose 1.29.2`，反复出现：

- `KeyError: 'ContainerConfig'`

先删旧容器再 `up` 是目前最稳的规避方式。
