# GHCR 部署与一键更新

适用对象：使用 GitHub Container Registry 发布生产镜像的维护者。

## 1. 方案

```text
GitHub push
  |
  v
GitHub Actions
  |
  v
ghcr.io/<owner>/algowiki-web:<tag>
  |
  v
Server docker pull
```

服务器只保存运行时环境变量，不保存 GitHub 源码工作区中的私密文件。

## 2. 安全边界

- 镜像可以公开，前提是镜像内不包含 `.env`、数据库、日志和上传文件
- 运行时密钥只放在服务器 `deploy/.env.production`
- 不要把 `Dockerfile` 改成无差别 `COPY . .`
- 不要把数据库备份或私钥放进 `backend/`、`frontend/`、`deploy/`

## 3. 首次配置

1. 确认仓库启用了 Actions
2. 确认 workflow 可以推送 GHCR
3. 推送 `main`
4. 在 GitHub Packages 中确认镜像可见性
5. 在服务器执行更新脚本

服务器命令：

```bash
cd <SERVER_PROJECT_DIR>
chmod +x deploy/*.sh
./deploy/server-update-from-registry.sh \
  --image ghcr.io/<owner>/algowiki-web:latest \
  --release ghcr-latest
```

## 4. 日常更新

```bash
cd <SERVER_PROJECT_DIR>
./deploy/server-update-from-registry.sh
```

如果需要严格跟随 GitHub 分支最新提交：

```bash
./deploy/server-update-from-registry.sh \
  --sync-github-branch \
  --github-branch main
```

## 5. 指定版本和回滚

```bash
cd <SERVER_PROJECT_DIR>
./deploy/server-update-from-registry.sh \
  --image ghcr.io/<owner>/algowiki-web:sha-<commit> \
  --release <release-name>
```

同一命令也用于回滚到已知可用镜像。

## 6. 常见问题

| 问题 | 处理 |
| --- | --- |
| 服务器需要 GitHub Token 吗 | Public 镜像通常不需要 |
| 镜像拉取失败 | 检查镜像可见性、tag、网络 |
| 网站没更新 | 检查当前容器镜像 ID 和 release |
| 容器重建失败 | 查看 Docker Compose 日志和 `.env` |
