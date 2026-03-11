# Contributing

## Scope

欢迎提交 issue 和 pull request。

提交前请先确认：

- 不提交 `.env`、数据库、日志、构建产物、上传文件
- 不在代码、截图、日志中泄露密码、Token、数据库地址等敏感信息
- 变更包含必要的说明
- 涉及后端行为改动时，优先补测试

## Development

### Backend

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.tests
```

### Frontend

```powershell
cd frontend
npm install
npm run build
```

## Pull Request Checklist

- 说明变更目的
- 说明影响范围
- 说明验证方式
- 若涉及安全、权限、数据库，请单独标注
