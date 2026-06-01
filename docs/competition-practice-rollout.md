# 补题链接与 Issue 可见性上线说明

适用对象：上线竞赛补题链接、Issue 可见性调整和相关数据导入的维护者。

## 1. 功能范围

本次功能包含：

- 竞赛补题链接数据导入
- 竞赛专区补题面板展示
- Issue / Request 可见性调整
- 相关后台审核与管理入口

## 2. 代码与数据

相关文件：

- `backend/data/competition_practice_links_snapshot.json`
- `backend/wiki/management/commands/import_competition_practice_links.py`
- `backend/wiki/management/commands/build_competition_practice_snapshot.py`
- `frontend/src/components/CompetitionPracticePanel.vue`

## 3. 数据库迁移

上线前执行：

```bash
python backend/manage.py migrate
```

## 4. 导入数据

```bash
python backend/manage.py import_competition_practice_links
```

如果需要重新生成快照：

```bash
python backend/manage.py build_competition_practice_snapshot
```

## 5. 前端构建

```bash
cd frontend
npm run build
```

## 6. 上线后检查

- 竞赛专区能打开
- 补题链接列表能加载
- 链接搜索与分页正常
- Issue / Request 权限符合预期
- 审核台相关入口可用
- `/api/health/` 正常

## 7. 回滚

如前端异常：

- 回滚到上一版镜像
- 保留数据库数据，避免重复导入造成二次问题

如数据异常：

- 先备份当前数据库
- 在测试环境复现
- 再决定是否清理或重新导入
