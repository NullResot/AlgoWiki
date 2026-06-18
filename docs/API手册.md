# AlgoWiki API 手册

本文面向需要调用 AlgoWiki 数据接口的开发者，说明当前项目已有 API 的访问方式、权限边界、分页格式和主要接口。

> 说明：本文依据当前代码中的 `backend/wiki/urls.py`、`backend/wiki/views.py` 和序列化字段整理。现阶段这些接口主要服务 AlgoWiki 前端和管理后台，尚未提供独立的第三方开发者密钥、版本化 SLA 或公开 OpenAPI 页面。对外长期开放前，建议先增加 `/api/v1/`、访问令牌管理、调用频率说明和兼容性策略。

## 1. 基础约定

### 1.1 请求地址

所有业务接口统一以 `/api/` 为前缀：

```text
https://<ALGOWIKI_DOMAIN>/api/<resource>/
```

示例：

```http
GET /api/competition-schedules/?year=2026&order=desc
```

### 1.2 数据格式

- 请求体：`application/json`，图片上传等接口使用 `multipart/form-data`。
- 返回体：JSON。
- 时间：ISO 8601 字符串，例如 `2026-06-18T18:53:06+08:00`。
- 日期：`YYYY-MM-DD`，例如 `2026-06-18`。

### 1.3 认证方式

需要登录的接口使用 Token 认证：

```http
Authorization: Token <token>
```

Token 由登录接口返回：

```http
POST /api/auth/login/
```

当前项目使用带过期时间的 Token 认证，默认有效期由服务端环境配置控制，当前配置默认值为 168 小时。

### 1.4 分页格式

列表接口默认每页 20 条。分页响应通常如下：

```json
{
  "count": 123,
  "next": "https://example.com/api/competition-schedules/?page=2",
  "previous": null,
  "results": []
}
```

常用参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `page` | integer | 页码，从 1 开始 |

### 1.5 权限标记

本文使用以下权限标记：

| 标记 | 含义 |
| --- | --- |
| 公开 | 未登录也可读取 |
| 登录 | 需要登录且未被封禁 |
| 学校用户 | 学校用户、管理员或超级管理员可操作 |
| 管理员 | 管理员或超级管理员可操作 |
| 超级管理员 | 仅超级管理员可操作 |

### 1.6 常见错误

| HTTP 状态码 | 含义 |
| --- | --- |
| `400` | 请求参数格式错误或业务校验失败 |
| `401` | 未登录或 Token 无效 |
| `403` | 已登录但权限不足、账号被封禁或验证码不通过 |
| `404` | 资源不存在或当前用户不可见 |
| `429` | 请求过于频繁 |
| `500` | 服务端异常 |

错误响应通常包含 `detail` 字段：

```json
{
  "detail": "Authentication credentials were not provided."
}
```

表单校验错误可能按字段返回：

```json
{
  "title": ["This field is required."]
}
```

## 2. 赛事专区 API

赛事专区是当前最适合对外读取的接口组，包含赛事公告、锦标赛日程、补题链接、日历事件和专区菜单。

### 2.1 赛事公告列表

```http
GET /api/competition-notices/
```

权限：公开读取。创建、修改、删除需要登录且具备赛事内容编辑权限；审核需要管理员。

用途：获取 ICPC、CCPC、蓝桥杯、天梯赛等赛事公告。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `series` | string | 否 | 赛事系列，例如 `icpc`、`ccpc`、`lanqiao`、`tianti` |
| `year` | integer | 否 | 年份 |
| `stage` | string | 否 | 阶段，例如 `regional`、`invitational`、`provincial`、`network`、`national`、`popular`、`standard`、`general` |
| `search` | string | 否 | 按标题和正文搜索 |
| `order` | string | 否 | `oldest` 表示从旧到新，默认从新到旧 |
| `page` | integer | 否 | 页码 |

主要返回字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 公告 ID |
| `title` | string | 公告标题 |
| `content_md` | string | Markdown 正文 |
| `series` | string | 赛事系列 |
| `series_label` | string | 系列展示名 |
| `year` | integer | 年份 |
| `stage` | string | 阶段 |
| `stage_label` | string | 阶段展示名 |
| `is_visible` | boolean | 是否前台可见 |
| `status` | string | 审核状态，公开读取通常只返回 `approved` |
| `published_at` | string | 发布时间 |
| `created_by` | object | 创建者公开信息 |
| `updated_by` | object | 最近编辑者公开信息 |
| `contributors` | array | 贡献者信息 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

示例：

```http
GET /api/competition-notices/?series=icpc&year=2026&stage=regional
```

### 2.2 赛事公告详情

```http
GET /api/competition-notices/{id}/
```

权限：公开读取。

用途：根据公告 ID 获取完整公告内容。

示例：

```http
GET /api/competition-notices/12/
```

### 2.3 赛事公告分类信息

```http
GET /api/competition-notices/taxonomy/
```

权限：公开读取。

用途：获取赛事公告的系列、年份和阶段聚合信息，适合生成筛选器。

返回结构：

```json
{
  "series": []
}
```

### 2.4 锦标赛日程列表

```http
GET /api/competition-schedules/
```

权限：公开读取。创建、修改、删除需要赛事内容编辑权限；审核需要管理员。

用途：获取锦标赛、区域赛、省赛、邀请赛等赛事日程。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` 或 `schedule` | integer | 否 | 按日程 ID 精确查询 |
| `year` | integer | 否 | 按开始日期年份筛选 |
| `competition_type` | string | 否 | 按比赛类型模糊搜索 |
| `series` | string | 否 | 按关联公告系列筛选 |
| `order` | string | 否 | `desc` 表示从新到旧，默认从旧到新 |
| `page` | integer | 否 | 页码 |

主要返回字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 日程 ID |
| `event_date` | string | 开始日期 |
| `end_date` | string | 结束日期 |
| `competition_time_range` | string | 比赛时间段 |
| `competition_type` | string | 比赛类型或名称 |
| `location` | string | 地点 |
| `qq_group` | string | QQ 群信息 |
| `announcement` | integer | 关联公告 ID |
| `announcement_title` | string | 关联公告标题 |
| `announcement_series` | string | 关联公告系列 |
| `announcement_year` | integer | 关联公告年份 |
| `announcement_stage` | string | 关联公告阶段 |
| `status` | string | 审核状态 |
| `is_past` | boolean | 是否已经结束 |
| `contributors` | array | 贡献者信息 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

示例：

```http
GET /api/competition-schedules/?year=2026&series=icpc&order=desc
```

### 2.5 锦标赛日程详情

```http
GET /api/competition-schedules/{id}/
```

权限：公开读取。

### 2.6 锦标赛日程年份

```http
GET /api/competition-schedules/years/
```

权限：公开读取。

用途：获取已有日程年份，适合前端年份筛选器。

### 2.7 补题链接列表

```http
GET /api/competition-practice-links/
```

权限：公开读取。

用途：获取赛事补题、题面、榜单、题解等练习链接。

主要返回字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 记录 ID |
| `source_key` | string | 来源键 |
| `year` | integer | 年份 |
| `series` | string | 赛事系列 |
| `series_label` | string | 系列展示名 |
| `stage` | string | 阶段 |
| `stage_label` | string | 阶段展示名 |
| `short_name` | string | 简称 |
| `official_name` | string | 官方名称 |
| `official_url` | string | 官方链接 |
| `event_date` | string | 比赛日期 |
| `event_date_text` | string | 日期文本 |
| `organizer` | string | 主办方 |
| `practice_links` | array | 结构化补题链接 |
| `practice_links_note` | string | 链接备注 |
| `practice_links_text` | string | 文本化链接 |
| `display_order` | integer | 展示顺序 |
| `contributors` | array | 贡献者 |

### 2.8 补题链接详情

```http
GET /api/competition-practice-links/{id}/
```

权限：公开读取。

### 2.9 补题链接提案

```http
GET /api/competition-practice-proposals/
POST /api/competition-practice-proposals/
```

权限：登录用户可提交，管理员审核。

用途：用户提交补题链接修改建议。个人中心接口也提供当前用户自己的提案列表：

```http
GET /api/me/competition-practice-proposals/
```

### 2.10 比赛日历

```http
GET /api/competition-calendar/
GET /api/competition-calendar/{id}/
```

权限：公开读取。

用途：获取日历事件，适合外部日历页或聚合展示。

### 2.11 赛事专区菜单

```http
GET /api/competition-zone-sections/
GET /api/competition-zone-sections/{id}/
```

权限：公开读取。管理操作需要管理员。

用途：获取赛事专区的子页面、菜单显示顺序和可见性。

## 3. 公告 API

### 3.1 公告列表

```http
GET /api/announcements/
```

权限：公开读取。创建、编辑、删除、发布、撤回、归档需要管理员。

请求参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `page` | integer | 页码 |
| `all` | string | 管理员传 `1` 可查看草稿、撤回和归档公告 |

主要返回字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 公告 ID |
| `title` | string | 标题 |
| `summary` | string | 摘要 |
| `content_md` | string | Markdown 正文 |
| `level` | string | `emergency`、`important`、`normal`、`low` |
| `target_audience` | string | `all`、`logged_in`、`school`、`admin` |
| `priority` | integer | 优先级 |
| `show_on_home` | boolean | 是否显示在首页 |
| `show_in_list` | boolean | 是否显示在公告页 |
| `show_as_popup` | boolean | 是否弹窗 |
| `show_as_banner` | boolean | 是否顶部横幅 |
| `requires_ack` | boolean | 是否要求用户确认 |
| `status` | string | `published`、`scheduled`、`draft`、`withdrawn`、`expired`、`archived` |

### 3.2 公告辅助接口

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/announcements/published-history/` | 公开 | 首页公告历史 |
| `GET` | `/api/announcements/banner/` | 公开 | 当前顶部横幅公告 |
| `GET` | `/api/announcements/popup-candidate/` | 公开 | 当前弹窗候选公告 |
| `GET` | `/api/announcements/unread/` | 登录 | 当前用户未读弹窗公告 |
| `POST` | `/api/announcements/{id}/acknowledge/` | 登录 | 标记已读或已确认 |
| `POST` | `/api/announcements/{id}/publish/` | 管理员 | 发布公告 |
| `POST` | `/api/announcements/{id}/withdraw/` | 管理员 | 撤回公告 |
| `POST` | `/api/announcements/{id}/archive/` | 管理员 | 归档公告 |
| `POST` | `/api/announcements/{id}/restore-archive/` | 管理员 | 恢复归档公告 |
| `GET` | `/api/announcements/stats/` | 管理员 | 公告统计 |

## 4. 竞赛 Wiki API

### 4.1 分类

```http
GET /api/categories/
GET /api/categories/{id}/
```

权限：公开读取。创建、修改、删除、移动需要管理员。

常用参数：

| 参数 | 说明 |
| --- | --- |
| `top_level=1` | 仅获取顶级分类 |
| `parent=<id>` | 获取某个父分类下的子分类 |
| `include_hidden=1` | 管理员查看隐藏分类 |

### 4.2 文章

```http
GET /api/articles/
GET /api/articles/{id}/
```

权限：公开读取已发布文章。创建和编辑需要登录，发布和批量审核需要相应权限。

常用参数：

| 参数 | 说明 |
| --- | --- |
| `category=<id 或 slug>` | 按分类筛选 |
| `search=<keyword>` | 搜索标题和摘要 |
| `featured=1` | 仅精选文章 |
| `order=created_newest` | 按创建时间倒序 |
| `order=updated_newest` | 按更新时间倒序 |

相关接口：

| 路径 | 说明 |
| --- | --- |
| `/api/comments/` | 文章评论 |
| `/api/revisions/` | 文章修订提案 |
| `/api/issues/` | 工单或反馈 |

## 5. Trick API

```http
GET /api/tricks/
GET /api/tricks/{id}/
GET /api/trick-terms/
GET /api/trick-terms/{id}/
```

权限：Trick 列表和详情公开读取；创建、点赞、点踩、编辑、删除需要登录；审核需要管理员。

常用参数：

| 参数 | 说明 |
| --- | --- |
| `status=approved` | 状态筛选，非管理员只能查看自己有权限的状态 |
| `search=<keyword>` | 搜索标题、正文和关键词 |
| `term=<id>` | 按术语 ID 筛选 |
| `term_slug=<slug>` | 按术语 slug 筛选 |
| `order=likes_desc` | 按点赞数排序 |
| `order=created_newest` | 按创建时间倒序 |

相关动作：

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/api/tricks/{id}/like/` | 登录 | 点赞 |
| `POST` | `/api/tricks/{id}/unlike/` | 登录 | 取消点赞 |
| `POST` | `/api/tricks/{id}/downvote/` | 登录 | 点踩 |
| `POST` | `/api/tricks/{id}/undownvote/` | 登录 | 取消点踩 |

## 6. 高校问卷调研 API

### 6.1 学校列表

```http
GET /api/school-survey-schools/
```

权限：公开读取。管理员可新增学校。

请求参数：

| 参数 | 说明 |
| --- | --- |
| `search=<keyword>` | 搜索学校名称、缩写、省份或城市 |

主要返回字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 学校 ID |
| `name` | 学校名称 |
| `abbreviation` | 缩写 |
| `province` | 省份 |
| `city` | 城市 |
| `school_type` | 学校类型 |
| `logo_url` | 校徽链接 |
| `submissions_count` | 已提交问卷数 |
| `latest_submitted_at` | 最近提交时间 |

排序规则：默认先按已提交问卷数从大到小，再按缩写、学校名称和 ID 排序。

### 6.2 问卷提交

```http
GET /api/school-survey-submissions/
POST /api/school-survey-submissions/
GET /api/school-survey-submissions/{id}/
PATCH /api/school-survey-submissions/{id}/
DELETE /api/school-survey-submissions/{id}/
```

权限：需要登录。普通用户可查看已提交问卷和自己的草稿；管理员可查看全部。

常用参数：

| 参数 | 说明 |
| --- | --- |
| `school=<id>` | 按学校筛选 |
| `status=draft` 或 `submitted` | 按状态筛选 |
| `mine=1` | 只看当前用户自己的问卷 |

隐私说明：公开或普通登录用户读取已提交问卷时，私密字段会脱敏；只有提交者本人和管理员可查看完整私密信息。

## 7. 动态社区 API

动态社区接口主要服务站内朋友圈功能，不建议作为公开数据源直接开放。

| 路径 | 权限 | 说明 |
| --- | --- | --- |
| `/api/moments/` | 登录 | 动态列表、发布、删除、恢复、精选等 |
| `/api/moment-images/` | 登录 | 动态图片 |
| `/api/moment-comments/` | 登录 | 动态评论 |
| `/api/moment-reports/` | 登录 | 举报 |
| `/api/moment-settings/` | 管理员 | 动态功能开关和限制 |
| `/api/moment-restrictions/` | 管理员 | 用户限制 |
| `/api/moment-audit-logs/` | 管理员 | 审计日志 |
| `/api/moments/overview/` | 管理员 | 动态管理概览 |

## 8. AI 助手 API

```http
GET /api/assistant/config/
POST /api/assistant/chat/
```

权限：配置接口公开读取；对话接口按服务端配置进行限流。当前 AI 助手对话不走 Cloudflare Turnstile 验证。

请求示例：

```http
POST /api/assistant/chat/
Content-Type: application/json

{
  "message": "如何学习动态规划？",
  "session_id": "optional-session-id"
}
```

## 9. 账户与个人中心 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/api/auth/register-email-code/` | 公开 | 注册邮箱验证码 |
| `POST` | `/api/auth/register/` | 公开 | 注册 |
| `POST` | `/api/auth/login/` | 公开 | 登录，支持用户名、邮箱、手机号 |
| `POST` | `/api/auth/logout/` | 登录 | 登出 |
| `GET` | `/api/me/` | 登录 | 当前用户信息 |
| `PATCH` | `/api/me/` | 登录 | 修改个人资料 |
| `POST` | `/api/me/cancel-account/` | 登录 | 注销账户 |
| `GET` | `/api/me/tricks/` | 登录 | 我的 Trick |
| `GET` | `/api/me/trick-contribution/` | 登录 | Trick 贡献统计 |
| `GET` | `/api/me/competition-notices/` | 登录 | 我的赛事公告 |
| `GET` | `/api/me/events/` | 登录 | 我的操作事件 |
| `GET` | `/api/me/security-events/` | 登录 | 我的安全事件 |
| `GET` | `/api/me/security-summary/` | 登录 | 安全摘要 |

手机号验证：

```http
GET /api/phone-verifications/
POST /api/phone-verifications/start/
POST /api/phone-verifications/check/
```

## 10. 搜索、首页和通用内容 API

| 路径 | 权限 | 说明 |
| --- | --- | --- |
| `/api/search/` | 公开 | 全站搜索 |
| `/api/home/summary/` | 公开 | 首页摘要 |
| `/api/friendly-links/` | 公开 | 友情链接 |
| `/api/team-members/` | 公开 | 贡献者和团队成员 |
| `/api/pages/` | 按页面访问级别 | 文档扩展页 |
| `/api/document-page-sections/` | 公开 | 文档页侧边栏结构 |
| `/api/header-nav/` | 公开 | 顶部导航 |
| `/api/uploads/image/` | 登录 | 通用图片上传 |
| `/api/health/` | 公开 | 健康检查 |
| `/api/captcha/config/` | 公开 | 验证码公开配置 |

## 11. 管理与审计 API

以下接口不建议对第三方开放，仅供站内后台使用。

| 路径 | 权限 | 说明 |
| --- | --- | --- |
| `/api/users/` | 管理员 | 用户管理 |
| `/api/notifications/` | 登录 | 站内通知 |
| `/api/deleted-content-archives/` | 管理员 | 删除内容归档 |
| `/api/events/` | 管理员 | 操作日志 |
| `/api/security-logs/` | 管理员 | 安全日志 |
| `/api/captcha-audit-logs/` | 管理员 | 验证码审计日志 |
| `/api/admin/overview/` | 管理员 | 管理概览 |
| `/api/site-visits/stats/` | 超级管理员 | 访问量统计 |
| `/api/assistant-configs/` | 管理员 | AI 助手配置 |
| `/api/ai-moderation-configs/` | 管理员 | AI 审核配置 |
| `/api/ai-moderation-records/` | 管理员 | AI 审核记录 |
| `/api/gallery-folders/` | 管理员 | 图库文件夹 |
| `/api/gallery-images/` | 管理员 | 图库图片 |

## 12. 外部调用建议

如果要把 AlgoWiki API 正式提供给他人，建议先完成以下工作：

1. 增加 `/api/v1/` 版本前缀，避免未来内部接口调整影响第三方。
2. 为外部调用方提供独立只读 Token，不复用站内用户登录 Token。
3. 为公开数据接口增加稳定字段说明和废弃策略。
4. 为第三方调用设置独立限流，例如按 IP 或 Token 限制 QPS 和每日总量。
5. 提供 OpenAPI JSON 或 Swagger 页面。
6. 明确版权、缓存周期、署名要求和禁止批量抓取条款。
7. 对手机号、邮箱、实名、问卷私密字段、删除归档等接口保持默认不可开放。

## 13. 变更记录

| 日期 | 说明 |
| --- | --- |
| 2026-06-18 | 初版 API 手册，整理当前站内路由、权限和赛事专区主要接口。 |
