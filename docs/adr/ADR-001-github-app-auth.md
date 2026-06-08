<!-- Last Updated: 2026-06-08 | Status: Accepted | Audience: asp-operator maintainers -->
# [ADR-001]: OPERATOR_GITHUB_TOKEN 由 Classic PAT 遷移至 GitHub App

| 欄位 | 內容 |
|------|------|
| **狀態** | `Accepted` |
| **日期** | 2026-06-08 |
| **決策者** | astroicers（**已核准 2026-06-08**，經計畫雙決策確認） |
| **觸發事件** | asp-operator V1 上線後以 classic PAT 跑 PyGithub；PAT 為帳號全域 + 全 scope，遠超實際所需，且綁定個人帳號 |
| **關聯** | `CLAUDE.md`「Operator 只寫 inbox，不 merge PR」鐵則；`.github/workflows/poll-issues.yml`；`src/poll_issues.py`；`src/config_loader.py` |

> **狀態說明：** `Draft`（初稿，禁止實作）→ `FIRM`（POC 驗證，允許 commit，需附驗證證據）→ `Accepted`（人類審核通過）

---

## 背景（Context）

asp-operator 是 ASP 框架的「外部感知層」：GitHub Actions 每 30 分鐘跑 `src/poll_issues.py`，讀各被治理 repo 的 GitHub Issues → 轉譯 → 透過 Contents API 寫 `.asp-task-inbox.json` 回各 repo。憑證為單一 Actions secret `OPERATOR_GITHUB_TOKEN`（classic PAT），由 PyGithub `Github(token)` 使用。

classic PAT 的問題：

1. **過度授權**：classic PAT 是帳號全域 + 全 scope（repo / workflow / admin…），但 asp-operator 實際只做三件事 → 只需 `contents: write`（讀 `.ai_profile` + 讀/建/改 inbox）與 `issues: read`（讀 open issues + labels）。CLAUDE.md 已明訂 Operator 不碰 PR，故**完全不需 pull_requests / actions / admin**。
2. **長效憑證**：PAT 不會自動過期，外洩風險窗口大。
3. **綁定個人身分**：PAT 掛在某個人帳號下，該人輪換 / 離開即失效，且稽核時無法與人類操作區分。
4. **私有 repo 列舉正確性**：現行 `gh.get_user(owner).get_repos()`（`/users/{owner}/repos`）僅回公開 repo；若以 App installation token 走此路徑，**私有 opt-in repo 會被漏掉**。

唯一憑證敏感耦合面是「透過 Contents API 寫 `.asp-task-inbox.json`」。ASP 下游消費端（`session-audit.sh` → `inbox-ingest.sh` → autopilot）全讀**本機檔案**、用**開發者本機 gh CLI**，與本遷移無關、不受影響。

---

## 評估選項（Options Considered）

### 軸一：Token 來源

**選項 A1：`actions/create-github-app-token`（建議）**
- **優點**：官方 action 於 workflow 內用 App ID + 私鑰簽發短效（1h）installation token，餵進現有 `OPERATOR_GITHUB_TOKEN` env var；**介面不變、Python 認證碼幾乎不動**；私鑰由 GitHub 管。
- **缺點**：僅限 GitHub Actions 環境（asp-operator 本就只跑在 Actions，可接受）。
- **風險**：低；token 1h 過期，但單次 run < 10 分鐘，無長跑風險。

**選項 A2：PyGithub 原生 App 認證（`Auth.AppAuth` + installation）**
- **優點**：可攜（本機 / 其他 CI 皆能跑）。
- **缺點**：`config_loader` / `poll_issues` 需改較多；多帶 `APP_ID` / `PRIVATE_KEY` / `INSTALLATION_ID`。
- **風險**：自管 JWT 簽發與 token 刷新，增加維護面。

### 軸二：安裝廣度（與權限 scope 正交）

**選項 B1：All repositories（建議）**
- **優點**：App 裝於帳號所有（含未來新）repo → 新增 opt-in repo 只改 `.ai_profile` 一行即生效，**順手度等同 PAT**；消除「漏裝某 opt-in repo 導致靜默停寫」的切換風險。scope 仍鎖最小兩權限。
- **缺點**：App 在「廣度」上能碰所有 repo 的 contents + issues（但被兩個窄權限框死，opt-in 仍由程式 `.ai_profile operator.enabled` 第三層守門）。
- **風險**：低；遠比 classic PAT 全 scope 安全。

**選項 B2：Only select repositories**
- **優點**：GitHub 在存取層強制 opt-in（最小權限頂點）。
- **缺點**：每新增 opt-in repo 都要有人到 GitHub 手動裝 App，opt-in 變兩步。
- **風險**：多機 / 團隊情境下易漏裝。

---

## 決策（Decision）

採 **A1（create-github-app-token）+ All repositories 安裝 + 最小 scope `contents:write` + `issues:read`**，並 **`main()` 改用 `GET /installation/repositories` 列舉**（取代 `get_user(owner).get_repos()`）。

**摩擦評估（採納前必做）**：「安裝廣度」與「權限 scope」是兩個獨立軸。後續麻煩只集中在廣度（每新增 repo 要手動裝 App）→ 故放寬為 All repositories；scope 收緊幾乎零後續成本（asp-operator 職責穩定，V2 roadmap 的 Slack/LINE/監控告警皆非 GitHub，不需新增 GitHub 權限）→ 故維持最小集。此組合拿到約 90% 安全收益、約 0 後續摩擦。

**設計原則**：保留 `OPERATOR_GITHUB_TOKEN` env var 作為穩定介面，只換「填它的來源」（PAT → App 簽發的 installation token）→ 最小爆炸半徑。`config_loader.get_token()`、`build_github_client()` 不動。

---

## 後果（Consequences）

**正面影響：**
- 權限由「帳號全域 + 全 scope」收斂為 `contents:write` + `issues:read`（metadata 自動）。
- token 短效（1h）、獨立 App 身分可單獨撤銷 / 稽核、不綁個人帳號。
- `/installation/repositories` 列舉對公私有 repo 皆正確，且只回 App 可存取的 repo（效率較全帳號掃描佳）。

**負面影響 / 技術債：**
- 新增對 `/installation/repositories` REST 端點的依賴（需處理分頁）；新增 `requests` 為顯式依賴（PyGithub 既有遞移依賴，僅顯式化）。
- 人類一次性設定：建 App、產私鑰、裝 All repositories、設 `ASP_OPERATOR_APP_ID` variable 與 `ASP_OPERATOR_APP_PRIVATE_KEY` secret。
- 若未來 asp-operator 需新 GitHub 能力（如 comment issue），須改 App 權限集並由 installation 重新核准（All repositories 安裝為「改一次核准一次」）。

**後續追蹤：**
- [x] 人類核准本 ADR → astroicers 於 2026-06-08 核准升 `Accepted`。
- [x] 實作 `list_installation_repos`（TDD）+ 改寫 `main()` 列舉。
- [x] workflow 加 `create-github-app-token` step、env 改取 `steps.app-token.outputs.token`。
- [ ] **人類專屬**（依 SOP `docs/github-app-setup.md`）：建 App（權限 contents:write + issues:read）、裝 All repositories、設 var/secret。
- [ ] POC：`workflow_dispatch` 實測 token 簽發 + inbox 寫入正常後，刪舊 PAT secret 並撤銷 PAT。

---

## 成功指標（Success Metrics）

| 指標 | 目標值 | 驗證方式 | 檢查時間 |
|------|--------|----------|----------|
| 單元測試通過 | 100%（含新增 `list_installation_repos` 測試） | `PYTHONPATH=. python3 -m pytest tests/ -q` | 實作完成時 |
| App 權限最小集 | 僅 contents:write + issues:read，無 pull_requests/admin | GitHub App settings 人工核對 | App 建立後 |
| token 簽發成功 | workflow 綠燈、無 403/404 噪音 | `workflow_dispatch` + `gh run watch` | 人類設定後 |
| 耦合面正常 | 某 opt-in repo 開 `ready-for-agent` issue 後 `.asp-task-inbox.json` 出現對應任務 | 端到端實測 | 人類設定後 |
| 下游無回歸 | AI-SOP-Protocol session-audit 仍正常注入 ROADMAP | 開新 session 觀察 | 切換後 |

> 重新評估條件：若 asp-operator 職責擴張需新 GitHub 權限，或 GitHub 改變 installation token / `/installation/repositories` 行為，須重審本決策。

---

## 關聯（Relations）

- 取代：（無）
- 被取代：（無）
- 參考：`docs/github-app-setup.md`（帳號端設定 SOP）；`CLAUDE.md`（Operator 職責邊界鐵則）；`.github/workflows/poll-issues.yml`；`src/poll_issues.py` `main()`；`src/config_loader.py` `get_token()`。

---

## Verification Evidence（升級至 FIRM 時必填）

> 本 ADR 已由人類直接核准為 `Accepted`（決策層）。下表記錄落地驗證進度。

| 欄位 | 內容 |
|------|------|
| **POC 分支 / 測試結果** | 分支 `asp/github-app-auth`；單元測試全綠（含 `list_installation_repos` 分頁 + authorized_owners 過濾測試） |
| **驗證日期** | 2026-06-08（單元層）；端到端待人類完成 App 設定後 `workflow_dispatch` |
| **驗證者** | astroicers |
| **驗證摘要** | 程式 / workflow / 文件層遷移完成且單元測試通過；token 簽發與 inbox 寫入之端到端 POC 待人類建立 App 後執行 |
