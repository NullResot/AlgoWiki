# AlgoWiki CDN 与 HTTPS 上线蓝图

适用对象：准备将 AlgoWiki 接入正式公网域名、HTTPS 和 CDN 的维护者。

本文使用占位符：

- `<APEX_DOMAIN>`：裸域，例如 `example.com`
- `<WWW_DOMAIN>`：正式访问域名，例如 `www.example.com`

## 1. 推荐架构

第一阶段采用保守架构：

```text
User
  |
  v
CDN (<WWW_DOMAIN>)
  |
  v
Nginx HTTPS origin
  |
  v
Docker / Django / Gunicorn
```

规则：

- `<WWW_DOMAIN>` 是唯一正式入口
- `<APEX_DOMAIN>` 只做 301 跳转到 `<WWW_DOMAIN>`
- CDN 只缓存静态资源
- API、后台、HTML 壳页面不强缓存
- 用户上传图片低量级阶段仍可先走源站

## 2. 缓存策略

建议缓存：

- `/assets/*`
- `/static/*`
- `/wiki-assets/*`

不要强缓存：

- `/api/*`
- `/admin/*`
- `/manage/*`
- `/review/*`
- `/profile/*`
- `/moments/*`
- HTML 入口页面

如果 CDN 支持“遵循源站缓存头”，优先开启该策略，不要整站统一 TTL。

## 3. Nginx

参考模板：

- `deploy/nginx.algowiki.conf`

目标行为：

- HTTP 自动跳 HTTPS
- 裸域 301 到 `https://<WWW_DOMAIN>/`
- `www` 域名反向代理到本机 Web 容器
- 正确传递 `X-Forwarded-Proto`

修改后验证：

```bash
nginx -t
systemctl reload nginx
curl -I https://<APEX_DOMAIN>
curl -I https://<WWW_DOMAIN>
curl -fsS https://<WWW_DOMAIN>/api/health/
```

## 4. Django 环境变量

```env
DJANGO_ALLOWED_HOSTS=<APEX_DOMAIN>,<WWW_DOMAIN>,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://<APEX_DOMAIN>,https://<WWW_DOMAIN>
DJANGO_USE_X_FORWARDED_HOST=1
DJANGO_USE_X_FORWARDED_PORT=1
DJANGO_SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
SECURE_SSL_REDIRECT=1
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
PUBLIC_SITE_URL=https://<WWW_DOMAIN>
PUBLIC_APEX_URL=https://<APEX_DOMAIN>
```

## 5. 成本与风险控制

必须配置：

- CDN 用量封顶
- 高额消费预警
- 成本预警
- 预算提醒

不要只购买资源包。资源包降低单价，但不能阻止异常流量导致超额费用。

## 6. 上线检查

- 证书有效
- HTTP 到 HTTPS 跳转正确
- 裸域跳转正确
- API 不被 CDN 长缓存
- 静态资源命中 CDN
- 登录、评论、动态、图片上传、审核台正常
- `/api/health/` 正常

## 7. 第二阶段增强

流量稳定后再评估：

- OSS / 对象存储
- 上传图片短缓存
- Referer 防盗链
- URL 鉴权
- WAF / Bot 防护
