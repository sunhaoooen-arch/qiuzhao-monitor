# 2027届秋招监控

每 12 小时自动巡检目标公司校招页,把**新增且匹配岗位**按甲/乙/丙分类汇总邮件推送。

## 本地运行
```bash
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env          # 填好 SMTP 授权码
python run.py --no-send       # 调试:抓取不发邮件
python run.py --only 奇安信    # 只跑某一家
python run.py                 # 正常一轮
```

## 配置
- `companies.yaml` — 121 家目标公司(`enabled: true` 才抓)。
- `.env` — SMTP 发件配置(QQ/163 授权码,见 `.env.example`)。
- 岗位关键词在 `monitor/matcher.py`(`DEFAULT_KEYWORDS`,从宽匹配)。

## 部署到 GitHub Actions(免费,7×24 不漏轮)
1. 把本目录作为一个仓库 push 到 GitHub(可设为 **Private**)。
2. 仓库 **Settings → Secrets and variables → Actions → New repository secret**,逐个添加:
   - `SMTP_HOST`(QQ: `smtp.qq.com`) `SMTP_PORT`(`465`)
   - `SMTP_USER`(发件邮箱) `SMTP_PASS`(SMTP 授权码)
   - `MAIL_TO`(收件邮箱,如 Gmail)
3. **Settings → Actions → General → Workflow permissions** 选 **Read and write**(让它能提交去重状态)。
4. 完成。`Actions` 页可手动 **Run workflow** 测试;之后每天北京时间 08:00 / 20:00 自动跑。

## 工作原理
渲染页面(Playwright)→ 按 ATS 提取职位 → 关键词匹配 → SQLite 去重(只推一次)→ 分组邮件。
首轮只建基线不打扰;某家连续抓取失败会在邮件里告警。
