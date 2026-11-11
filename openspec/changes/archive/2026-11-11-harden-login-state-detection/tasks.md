# Tasks — harden-login-state-detection

## 1. 微博判据改为页面用户态

- [x] 1.1 `docs_login.py::_detect` 微博分支改为 DOM 优先（`[class*="Nav_avatar"]` /
      `[class*="woo-avatar"]` / 发帖框 `textarea`），拿不到 DOM 才退回 URL
      **验收**：`_detect("weibo", page(url="/newlogin…", user_nodes=24))` → True；
      `user_nodes=0` → False
- [x] 1.2 微博移出 `HEADLESS_SAFE_CHECK`，并在集合处写明原因
      **验收**：`test_docs_headless_policy.py` 绿（源码级守卫要求 evaluate 判据不进白名单）
- [x] 1.3 `publish-docs/platforms/weibo.py::logged_in` 改为同口径
      **验收**：`test_weibo_publish_uses_same_url_reject_list` 绿；两处对不同 URL 结论一致

## 2. 面板解析 cookie 路径与发布侧同口径

- [x] 2.1 `login-manager.py` 新增 `account_path()`，含快手迁移回退；两处读取点
      （login-check、状态汇总）改用它
      **验收**：`account_path("kuaishou")` 指向真实存在的文件；`bilibili` 返回 `None`
- [x] 2.2 面板实测复原
      **验收**：`GET /api/status` → 快手 `has_cookie=true`，`cookie_path` 末段为
      `kuaishou_creator.json`；视频侧有 cookie 数从 7/10 回到 8/10

## 3. 守卫测试

- [x] 3.1 重写 `mcp-server/tests/test_docs_login_detect.py`：page 替身带 `evaluate`，
      覆盖「newlogin+有会话 ⇒ 已登录」「newlogin+无会话 ⇒ 未登录」
      「evaluate 抛错 ⇒ 退回 URL」「passport 域有节点也不算」
      **验收**：4 条全绿；把微博分支退回纯 URL 判据后 2 条转红（非恒真）
- [x] 3.2 新增 `mcp-server/tests/test_login_manager_account_path.py` 4 条
      **验收**：全绿；禁用回退后 2 条转红（非恒真）

## 4. 收口

- [x] 4.1 全量相关测试与一致性闸
      **验收**：`pytest test_docs_login_detect test_docs_headless_policy
      test_login_manager_interpreter test_login_manager_account_path` 全绿；
      `check-registry-consistency.py` EXIT=0
- [x] 4.2 归档并 `openspec validate --strict` 通过

## 挂账（不在本 change 范围）

- **同花顺财经号**：停在 `http://upass.10jqka.com.cn/media/index/?department=sns`，
  属账号媒体号资质问题而非判据缺陷；用户 2026-11-11 明确「没法现在给你」，不引入绕过。
- **YouTube**：无 cookie，需代理（7892 / `VAAS_YT_PROXY`）才能登录。
- **虎扑**：无 cookie，尚未登录过。
