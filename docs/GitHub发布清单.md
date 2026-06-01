# GitHub 发布清单

适用对象：准备将仓库公开、交付或长期维护的负责人。

## 1. 必须确认

- `.env` 没有提交
- 数据库文件没有提交
- 日志文件没有提交
- 上传文件没有提交
- 真实服务器 IP、密码、Token、AccessKey 没有写入文档
- 示例文件只包含占位符

## 2. 代码检查

```powershell
git status --short
git diff --check
venv\Scripts\python.exe backend\manage.py test wiki.tests
cd frontend
npm run build
```

## 3. 文档检查

- README 能说明项目是什么
- docs 索引能引导首次接手者
- 部署文档可复制执行
- 运维文档包含备份、回滚和故障处理
- 安全文档明确漏洞报告方式

## 4. 发布后检查

- Actions 正常运行
- 镜像构建成功
- release / tag 可追踪
- 测试环境可访问
- 正式环境健康检查正常
