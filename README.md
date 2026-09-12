# DNSHE 免费域名自动续期（GitHub Actions 方案）

每月自动检查 DNSHE 免费子域名的到期时间，进入"免费续期窗口"（到期前 180 天内）后自动续期（0 元），全程免费（GitHub Actions 免费额度）。

API 依据：<https://my.dnshe.com/knowledgebase/13/DNSHE-Free-Domain-API-User-Guide-V2.0.html>

---

## 一、原理

DNSHE 免费域名在**到期前 180 天即可续期**（免费窗口期内续费 `charged_amount: 0`；不续的话过期后进入赎回期，届时需扣余额）。

一个账号可能有多个域名、到期时间各不相同，所以每次运行都会**全量拉取所有域名**，按每个域名自己的剩余天数独立判断：

1. `GET endpoint=subdomains&action=list&sort_by=expires_at` 拉取全部域名及到期时间（自动翻页）；
2. 找出剩余天数 ≤ 180（进入免费窗口）的域名；
3. 逐个 `POST endpoint=subdomains&action=renew`：
   - `success: true` → 续期成功（0 元），到期日 +1 年，自动退出窗口（不会重复续）；
   - `422 renewal_not_yet_available` → 窗口还没开，跳过，留到下次；
   - 其它错误 → 记录并可选通知。

**检查频率**：180 天窗口下，每月跑一次即可；即使某次运行失败，也仍有约 150 天余量补救。也支持随时在 Actions 页面手动触发。

---

## 二、目录结构

```
dnshe_renew/
├── dnshe_renew.py                 # 检查+自动续期脚本
└── .github/workflows/domain-renew.yml   # 每月1号 02:00 UTC 自动运行
```

---

## 三、部署步骤

### 1. 获取 API Key / Secret

1. 登录 <https://my.dnshe.com> 客户区；
2. 进入 **Free Domain Management（免费域名管理）**；
3. 左侧导航找 **API Management（API 管理）**；
4. 点击 **Create API Key** 创建，得到 `X-API-Key` 和 `X-API-Secret` 两个字符串。

### 2. 建 GitHub 仓库并上传

```bash
git init
git add .
git commit -m "dnshe auto renew"
# 在 GitHub 新建私有仓库后:
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 3. 配置 Secrets（关键）

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加：

| Secret 名称 | 必填 | 说明 |
|---|---|---|
| `DNSHE_API_KEY` | ✅ | API 页面创建的 Key |
| `DNSHE_API_SECRET` | ✅ | API Secret |
| `SERVERCHAN_KEY` | 可选 | Server酱 SendKey，续期结果推微信 |
| `PUSHPLUS_TOKEN` | 可选 | PushPlus token，推微信 |
| `TG_BOT_TOKEN` | 可选 | Telegram Bot Token |
| `TG_CHAT_ID` | 可选 | Telegram 接收 Chat ID |

> ⚠️ GitHub 免费账户的 Actions 对私有仓库每月有免费分钟数（2000 分钟），每月跑 1 次用量可忽略；公开仓库不限。建议用**私有仓库**存放密钥。

### 4. 首次手动触发验证

回到仓库 **Actions** 页 → 左侧选 **DNSHE Domain Auto-Renew** → 右上角 **Run workflow** → 手动跑一次，查看日志是否正常列出域名和到期时间。

### 5. 之后每月自动执行

Cron 设定为 `0 2 1 * *`（每月1号 02:00 UTC，即北京时间 10:00）。如需改为每周/每天，把 cron 改掉即可，例如：
- 每周一：`0 2 * * 1`
- 每天：`0 2 * * *`

---

## 四、本地测试（可选）

```bash
# Windows PowerShell 示例（本地 Python 3）
$env:DNSHE_API_KEY = "cfsd_你的key"
$env:DNSHE_API_SECRET = "你的secret"

# 只检查，不续期
python dnshe_renew.py --check

# 列出 180 天内到期
python dnshe_renew.py --list-expiring --days 180

# 自动续期（到期前180天内, 窗口开了就续）
python dnshe_renew.py --auto-renew --days 180
```

---

## 五、常见问题

**Q: 为什么返回 `422 renewal_not_yet_available`？**
免费续期窗口还没打开。DNSHE 免费域名一般到期前 180 天即可续，若恰逢平台策略调整导致窗口推迟，脚本会自动跳过，留到下月再试；也可在 Actions 页面手动触发一次提早续上。

**Q: 续期要钱吗？**
免费窗口内（到期前 180 天起）续期 `charged_amount: 0`。若错过续期进入"赎回期"，则需要账户余额扣款，脚本会报 `402 insufficient balance`，此时请尽快登录后台手动处理或充值。

**Q: 怎么改提前天数？**
把 workflow 里 `--days 180` 改成你想要的天数即可。设置为 180 天时，域名一进入可续窗口就会被续上，续期后到期日自动延长一年，实现"永不掉线"。

**Q: 不想要通知？**
Secrets 里留空即可，脚本只在日志输出结果。

---

*脚本版本 v1.0 · 生成时间 2026-09-02*