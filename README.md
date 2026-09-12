<p align="center">
  <h1 align="center">🛡️ DNSHE 免费域名自动续期</h1>
  <p align="center">
    <strong>GitHub Actions 每月自动检查 + 免费续期，多账号并行，永久域名自动跳过</strong>
  </p>
  <p align="center">
    <!-- 把 YOUR_GITHUB_USERNAME / REPO_NAME 换成你的用户名和仓库名 -->
    <img alt="GitHub Actions" src="https://img.shields.io/github/actions/workflow/status/YOUR_GITHUB_USERNAME/REPO_NAME/domain-renew.yml?logo=github&label=Auto-Renew">
    <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white">
    <img alt="API" src="https://img.shields.io/badge/DNSHE%20API-V2.0-green">
    <img alt="License" src="https://img.shields.io/badge/License-MIT-yellow">
  </p>
</p>

---

## ✨ 功能特性

| 特性 | 说明 |
|---|---|
| 🗓️ **每月自动运行** | 每月 1 号 10:00（北京时间）自动检查，无需人工干预 |
| 💰 **全程免费** | 到期前 180 天进入免费续期窗口，续期 `charged_amount: 0` |
| 👥 **多账号并行** | 一个仓库管理 N 个 DNSHE 账号（matrix 并行，互不影响） |
| ♾️ **永久域名识别** | `never_expires` 域名显示"永久有效 ∞"，永远不会误触发续期 |
| 📋 **每日摘要** | Actions Step Summary 直接展示每个域名的到期状态表格 |
| 🔔 **可选通知** | Server酱 / PushPlus / Telegram 推送续期结果 |
| 🔧 **手动补跑** | 随时点 Run workflow 手动触发一次 |

---

## 🧠 原理

DNSHE 免费域名在**到期前 180 天即可续期**（免费窗口），脚本每次运行：

```
拉取全部域名(自动翻页) → 按各自剩余天数独立判断
     │
     ├─ 剩余 ≤ 180 天(窗口内) → POST renew → 成功则到期日+1年 ✅
     ├─ 剩余 > 180 天(窗口外) → 不动，留到下月
     ├─ 永久有效(never_expires) → 跳过，绝不再续
     └─ 窗口未开(422) → 跳过，下月再试
```

> 💡 180 天窗口 + 每月检查 1 次 = 即使某次运行失败，仍有约 **150 天**余量补救。

---

## 📁 目录结构

```
.
├── dnshe_renew.py                 # 检查 + 自动续期脚本（核心）
├── README.md                      # 本说明
└── .github/
    └── workflows/
        └── domain-renew.yml       # 每月1号 02:00 UTC 自动运行
```

---

## 🚀 部署步骤

### 1️⃣ 获取 API Key / Secret

1. 登录 **[my.dnshe.com](https://my.dnshe.com)** 客户区
2. 进入 **Free Domain Management（免费域名管理）**
3. 左侧导航 → **API Management（API 管理）**
4. 点击 **Create API Key**，得到 `X-API-Key` 和 `X-API-Secret` 两串

### 2️⃣ 上传到 GitHub（私有仓库）

```bash
git init
git add .
git commit -m "dnshe auto renew"
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

> 🔒 建议使用**私有仓库**，API Key 是敏感信息。

### 3️⃣ 配置 Secrets（关键）

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**。

**每个账号配一对 Key，按编号命名**（有几个账号配几对）：

| Secret 名称 | 必填 | 说明 |
|---|---|---|
| `DNSHE_API_KEY_1` / `DNSHE_API_SECRET_1` | ✅ | 账号 #1 的 Key/Secret |
| `DNSHE_API_KEY_2` / `DNSHE_API_SECRET_2` | 按需 | 账号 #2 的 Key/Secret |
| `DNSHE_API_KEY_3` / `DNSHE_API_SECRET_3` | 按需 | 账号 #3 的 Key/Secret |
| `SERVERCHAN_KEY` | 可选 | [Server酱](https://sct.ftqq.com/) SendKey，续期结果推微信 |
| `PUSHPLUS_TOKEN` | 可选 | [PushPlus](https://www.pushplus.plus/) token，推微信 |
| `TG_BOT_TOKEN` / `TG_CHAT_ID` | 可选 | Telegram Bot 通知 |

> ⚠️ Secret 名称只能包含 **字母数字和下划线**（`DNSHE_API_KEY_1` 合法），不要带空格/连字符/中文逗号。

### 4️⃣ 调整账号数量

打开 `.github/workflows/domain-renew.yml`，修改 matrix 的账号编号列表：

```yaml
matrix:
  account: [1, 2, 3]    # 👈 有几个账号就写几个编号
```

- 只有 1 个账号 → `account: [1]`
- 有 N 个账号 → `account: [1, 2, ..., N]`（配 N 对 Secrets）

### 5️⃣ 首次手动验证

**Actions** 页 → 选 **DNSHE Domain Auto-Renew** → **Run workflow** → 查看每个账号的 Step Summary：

| 域名 | 状态 | 到期时间 | 剩余天数 |
|---|---|---|---|
| `myapp.example` | 窗口外 | 2027-06-27 | 288天 |
| `cd1.cd` | **永久有效** | **永久** | **∞** |

看到永久域名正确显示"永久有效"即部署成功 ✅

### 6️⃣ 之后自动运行

每月 1 号 02:00 UTC（北京时间 10:00）自动执行。改频率只需改 cron：

| 频率 | cron |
|---|---|
| 每月1号（默认） | `0 2 1 * *` |
| 每周一 | `0 2 * * 1` |
| 每天 | `0 2 * * *` |

---

## 💻 本地测试（可选）

```bash
# Windows PowerShell（本地 Python 3.10+）
$env:DNSHE_API_KEY = "cfsd_你的key"
$env:DNSHE_API_SECRET = "你的secret"

# 只检查，不续期
python dnshe_renew.py --check

# 列出 180 天内到期
python dnshe_renew.py --list-expiring --days 180

# 自动续期（窗口内才续）
python dnshe_renew.py --auto-renew --days 180
```

---

## ❓ 常见问题

**Q: 为什么返回 `422 renewal_not_yet_available`？**
免费续期窗口还没打开（正常现象）。脚本会自动跳过，下月再试；也可手动 Run workflow 提早续上。

**Q: 续期要钱吗？**
免费窗口内（到期前 180 天起）续期 `charged_amount: 0`。错过续期进入赎回期才需余额扣款（`402 insufficient balance`），此时请登录后台处理。

**Q: 永久域名会被误续吗？**
不会。`never_expires=1` 的域名已从续期列表排除，只会显示"永久有效 ∞"。

**Q: 不想要通知？**
Secrets 里留空即可，脚本只输出到 Actions 日志。

**Q: 一个账号失败会影响其他账号吗？**
不会。workflow 设了 `fail-fast: false`，各账号独立并行。

---

## 📚 参考

- [DNSHE Free Domain API User Guide (V2.0)](https://my.dnshe.com/knowledgebase/13/DNSHE-Free-Domain-API-User-Guide-V2.0.html)
- [DNSHE 免费域名续期方法文档](https://my.dnshe.com/knowledgebase/5/DNSHE-Free-Domain-Renewal-and-API-Command-Renewal-Methods.html)

---

