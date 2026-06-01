# Contributing to AlgoWiki

欢迎提交 issue、讨论和 pull request。

## 提交前要求

- 不提交 `.env`、数据库文件、日志、上传文件和构建产物
- 不在代码、截图、日志和文档里泄露密码、Token、密钥、个人账号或私有地址
- 变更应包含必要说明，涉及行为变化时补充验证结果
- 后端逻辑变更优先补测试

## 推荐工作流

1. 从正确的分支开始开发
2. 小步提交，保持提交信息可追踪
3. 先本地验证，再推送到远端
4. 涉及部署脚本或文档时一并检查可复制性

## 常用验证

### 后端

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.tests
```

### 前端

```powershell
cd frontend
npm install
npm run build
```

## PR 清单

- 变更目的
- 影响范围
- 验证方式
- 回滚方式
- 若涉及权限、审核、部署或数据库，请单独标注
