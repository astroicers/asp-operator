# ASP-Operator

> ASP 框架的**外部感知層**：每 30 分鐘輪詢 GitHub Issues，轉譯為各被治理專案的 `.asp-task-inbox.json`。

> ## ⏸️ FROZEN（AI-SOP-Protocol ADR-032，2026-08-05）
> asp-operator 感知層已**停用並凍結**：排程輪詢停止、GitHub App 卸載、私鑰封存、repo 即將 archive。
> 停凍原因：零實現價值（不用／會忘）+ 休眠 T-14 攻擊面。**可逆解凍** — 見 [AI-SOP-Protocol ADR-032](https://github.com/astroicers/AI-SOP-Protocol/blob/main/docs/adr/ADR-032-decommission-and-freeze-asp-operator-perception-pillar.md)。
> 蒸餾去向：inbox schema／GitHub App 最小權限樣式／生產者↔閘一致性教訓已蒸餾入 AI-SOP-Protocol（ADR-032 Locus D）。

[![Auth: GitHub App](https://img.shields.io/badge/auth-GitHub%20App-blue)](docs/github-app-setup.md)
[![Permissions: least-privilege](https://img.shields.io/badge/permissions-contents%3Awrite%20%2B%20issues%3Aread-green)](docs/adr/ADR-001-github-app-auth.md)

---

## 它是什麼

asp-operator 是 ASP（AI-SOP-Protocol）三支柱的第二支柱 —— **感知層**：

```
1. ASP（核心）        治理：ROADMAP.yaml、ADR、SPEC、inbox-ingest
2. ASP-Operator（本專案）  感知：GitHub Issues → .asp-task-inbox.json（每 30 分）
3. ASP-Infra         各專案 CI/CD
```

它把「外部世界發生的事」（目前是 GitHub Issues）翻譯成 ASP 看得懂的 inbox 任務，**只寫 inbox，不執行開發、不 merge PR**（鐵則，見 [CLAUDE.md](CLAUDE.md)）。

---

## 運作流程

```
GitHub Actions 排程（*/30 * * * *）
  └─ src/poll_issues.py
       ├─ 簽發 GitHub App installation token（見「認證」）
       ├─ list_installation_repos → /installation/repositories（公私有皆含）
       └─ for each repo（owner ∈ authorized_owners）:
            ├─ 讀 .ai_profile → 無 operator.enabled 則跳過（opt-in 第三層守門）
            ├─ 讀 open issues，依 label_filter 過濾
            ├─ translate_issue → ASP inbox task（priority / SLA 對應）
            └─ write_inbox → 去重後 commit .asp-task-inbox.json（409 retry）
```

下游：各專案的 ASP `session-audit.sh` 在 SessionStart 讀本機 `.asp-task-inbox.json` → `inbox-ingest.sh` 注入 `ROADMAP.yaml` → 人類確認 → autopilot 執行。**下游全用本機 gh CLI，與本專案憑證無關。**

---

## 認證（GitHub App）

憑證走 **GitHub App installation token**，非 classic PAT。

| 項目 | 值 |
|------|----|
| 最小權限 | `contents: write` + `issues: read`（metadata 自動） |
| 安裝廣度 | All repositories |
| Token 來源 | workflow 內 `actions/create-github-app-token` 簽發短效（1h）token，餵進 `OPERATOR_GITHUB_TOKEN`（介面不變） |
| repo 列舉 | `/installation/repositories`（`list_installation_repos`），公私有皆正確 |

- **帳號端設定 SOP（建 App / 裝 App / 設 secret / 切換 / 退役 PAT）** → **[docs/github-app-setup.md](docs/github-app-setup.md)**
- **決策背景與權衡** → [docs/adr/ADR-001](docs/adr/ADR-001-github-app-auth.md)

---

## 設定

中央設定 [`operator-config.yaml`](operator-config.yaml)：

```yaml
authorized_owners: ["astroicers"]      # 防禦縱深：只處理此 owner 的 repo
github_token_env: "OPERATOR_GITHUB_TOKEN"  # token 介面（由 App token 填入）
defaults:
  label_filter: ["ready-for-agent"]    # 預設只收這些標籤的 issue
  priority_map: { P0: [critical, urgent], P1: [high], P2: [medium], P3: [low] }
  sla_hours_map: { P0: 0, P1: 24, P2: 72, P3: 168 }
```

被治理專案 **opt-in** —— 在該 repo 的 `.ai_profile` 加：

```yaml
operator:
  enabled: true
  label_filter: ["ready-for-agent", "bug"]   # 選填，覆蓋預設
```

> All repositories 安裝下，新增 opt-in repo **只需改 `.ai_profile` 一行即生效**，無需再手動裝 App。

---

## 本機開發 / 測試

```bash
# 安裝依賴
pip install -r requirements.txt

# 跑測試
PYTHONPATH=. python -m pytest tests/ -v

# 手動觸發一次 poll（需有效的 installation token）
OPERATOR_GITHUB_TOKEN=<App installation token> PYTHONPATH=. python -m src.poll_issues
```

CI 手動觸發：`gh workflow run poll-issues.yml -R astroicers/asp-operator`

---

## 專案結構

```
src/
  config_loader.py     讀 operator-config.yaml + 從 env 取 token
  poll_issues.py       進入點：list_installation_repos + poll_repo + main
  task_translator.py   GitHub Issue → ASP inbox task（priority / SLA）
  inbox_writer.py      .asp-task-inbox.json 去重 + Contents API 寫入（409 retry）
tests/                 對應單元測試
docs/
  adr/ADR-001-github-app-auth.md   認證遷移決策
  github-app-setup.md              GitHub App 設定 SOP
.github/workflows/poll-issues.yml  排程 + token 簽發
operator-config.yaml   中央設定
CLAUDE.md              行為憲法（自治理 L1）
```

---

## 治理

本專案自身也受 ASP 治理（L1：ADR + 測試）。架構影響須先立 ADR（見 [CLAUDE.md](CLAUDE.md) 鐵則）。
