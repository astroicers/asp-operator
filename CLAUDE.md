# ASP-Operator — 行為憲法

> ASP v4.3 治理框架。此專案自身也受 ASP 治理。

## 鐵則（不可覆蓋）

| 鐵則 | 說明 |
|------|------|
| 破壞性操作防護 | `git push origin main / --force / rebase / rm -rf / gh pr merge` 必須人類確認 |
| 敏感資訊保護 | 禁止輸出 GITHUB_TOKEN、密碼、憑證 |
| Operator 職責邊界 | Operator 只寫 inbox，不執行開發任務，不直接 merge PR |

## 專案說明

ASP-Operator 感知外部世界（GitHub Issues）並轉譯為各被治理專案的 `.asp-task-inbox.json`。

- 執行環境：GitHub Actions schedule（每 30 分鐘）
- 語言：Python 3.12
- 核心模組：`src/config_loader.py`、`src/task_translator.py`、`src/inbox_writer.py`、`src/poll_issues.py`

## 認證（Auth）

憑證走 **GitHub App installation token**，非 classic PAT。

- 決策：`docs/adr/ADR-001-github-app-auth.md`
- **帳號端設定 SOP（建 App / 裝 App / 設 secret / 切換 / 退役 PAT）：`docs/github-app-setup.md`**
- workflow 用 `actions/create-github-app-token` 以 `vars.ASP_OPERATOR_APP_ID` + `secrets.ASP_OPERATOR_APP_PRIVATE_KEY` 簽發短效 token，餵進 `OPERATOR_GITHUB_TOKEN`（介面不變）。
- App 最小權限：`contents: write` + `issues: read`（不碰 PR/admin）；安裝廣度 All repositories。
- repo 列舉走 `/installation/repositories`（`list_installation_repos`），公私有皆正確。

## 常用指令

| 動作 | 指令 |
|------|------|
| 執行測試 | `PYTHONPATH=. python -m pytest tests/ -v` |
| 手動觸發 poll | `OPERATOR_GITHUB_TOKEN=<App installation token> PYTHONPATH=. python -m src.poll_issues` |
