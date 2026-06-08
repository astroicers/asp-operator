<!-- Last Updated: 2026-06-08 | Status: Active | Audience: asp-operator maintainers / 帳號管理者 -->
# SOP：建立並安裝 asp-operator 的 GitHub App

> 目的：把 asp-operator 的憑證從 **classic PAT** 遷移到 **GitHub App installation token**。
> 決策背景與權衡見 [ADR-001](adr/ADR-001-github-app-auth.md)。
> 程式 / workflow 變更已在分支 `asp/github-app-auth` 完成；**本文件是「人類專屬」的帳號設定步驟**（AI 無法代執行：無法建 App、無法上傳憑證）。

---

## 前置條件

- [ ] 你是 `astroicers` 帳號的擁有者（或具 Developer settings / repo secrets 權限）。
- [ ] 分支 `asp/github-app-auth` 的程式變更已 merge 進 `main`（或你接受先設定 App、最後再 merge —— 但 workflow 一旦 merge 就會用 App token，故建議「先設定好 App + secret，再 merge」）。
- [ ] 一個安全的私鑰保管處（password manager / vault）。

> **`astroicers` 是 user 還是 org？**
> 本 SOP 以**個人帳號（user）** 為主。若 `astroicers` 實為 organization，凡「Settings → Developer settings」改走 `https://github.com/organizations/astroicers/settings/apps`，安裝步驟相同。

---

## 權限總覽（先看這張，知道要勾什麼）

| GitHub App Repository permission | 設定 | 為什麼 | 對應程式 |
|---|---|---|---|
| **Contents** | **Read and write** | 讀 `.ai_profile`、讀/建/改 `.asp-task-inbox.json` | `poll_issues.py:_get_profile`、`inbox_writer.py` |
| **Issues** | **Read-only** | 讀 open issues + labels（**不** comment/close） | `poll_issues.py` `repo.get_issues` |
| **Metadata** | **Read-only**（自動，不可取消） | 列舉 installation repos | `list_installation_repos` |
| Pull requests / Administration / Actions / 其餘 | **No access** | Operator 鐵則：只寫 inbox，不碰 PR | — |

> 最小權限。比 classic PAT（帳號全域 + 全 scope）大幅收斂。

---

## 階段 1 — 建立 GitHub App

1. 開 `https://github.com/settings/apps` →右上 **New GitHub App**。
2. 填欄位：
   - **GitHub App name**：`asp-operator`（需全域唯一；若被占用用 `asp-operator-astroicers`）。
   - **Homepage URL**：`https://github.com/astroicers/asp-operator`（必填，任何有效 URL 即可）。
   - **Webhook → Active**：**取消勾選**（asp-operator 是輪詢，不收 webhook；取消後免填 Webhook URL）。
3. **Repository permissions** 依上方「權限總覽」設定：
   - Contents → **Read and write**
   - Issues → **Read-only**
   - （Metadata 會自動變 Read-only）
   - 其餘維持 **No access**。
4. **Where can this GitHub App be installed?** → 選 **Only on this account**。
5. 按 **Create GitHub App**。
6. 建立後進入 App 的 **General** 頁，記下 **App ID**（純數字，例 `123456`）。
   - [ ] App ID = `________`

---

## 階段 2 — 產生並保管 Private Key

1. 同一個 App 的 **General** 頁 →下捲到 **Private keys** → **Generate a private key**。
2. 瀏覽器會下載一個 `*.pem` 檔（例 `asp-operator.2026-06-08.private-key.pem`）。
3. 立刻把它存進 password manager / vault。
   - ⚠️ 這把私鑰 = App 的完整身分。**勿 commit、勿貼進聊天、勿留在 Downloads。**
   - [ ] 私鑰已安全保管

---

## 階段 3 — 安裝 App 到 All repositories

1. App 左側選單 → **Install App** → 對 `astroicers` 帳號按 **Install**。
2. 選 **All repositories**（涵蓋現有 + 未來新 repo → 新增 opt-in repo 免再手動裝）。
3. 按 **Install**。
   - [ ] 已安裝於 All repositories

> 為何 All repositories 仍安全：廣度雖大，但 scope 被鎖在 contents+issues 兩權限；且 opt-in 仍由程式內 `.ai_profile operator.enabled` 第三層守門。詳見 [ADR-001](adr/ADR-001-github-app-auth.md) 摩擦評估。

---

## 階段 4 — 設定 repo variable + secret

到 **asp-operator repo** → **Settings → Secrets and variables → Actions**：

1. **Variables** 分頁 → **New repository variable**
   - Name：`ASP_OPERATOR_APP_ID`
   - Value：階段 1 記下的 App ID（純數字）
   - [ ] 已建立 variable
2. **Secrets** 分頁 → **New repository secret**
   - Name：`ASP_OPERATOR_APP_PRIVATE_KEY`
   - Value：**整個 `.pem` 檔內容**，含首尾兩行 `-----BEGIN RSA PRIVATE KEY-----` … `-----END RSA PRIVATE KEY-----`（連換行一起貼）
   - [ ] 已建立 secret

> App ID 非敏感 → 放 variable；私鑰敏感 → 放 secret。`actions/create-github-app-token` 直接吃 PEM 文字。

---

## 階段 5 — 部署程式變更

- [ ] merge 分支 `asp/github-app-auth` 進 `main`（merge 由你執行，鐵則）。
  - 變更內容：workflow 加 `create-github-app-token` step、`main()` 改 installation 列舉、新增 `requests` 依賴、ADR-001、本 SOP。

> 順序建議：**階段 1–4 全部完成後**再 merge。一旦 merge，下一次排程（每 30 分）或手動 dispatch 就會用 App token 跑。

---

## 階段 6 — 驗證（canary）

1. 手動觸發一次：
   ```bash
   gh workflow run poll-issues.yml -R astroicers/asp-operator
   ```
2. 看最近一次 run：
   ```bash
   gh run list -R astroicers/asp-operator --workflow poll-issues.yml -L 1
   gh run watch <run-id> -R astroicers/asp-operator
   ```
3. 檢查 log，逐項確認：
   - [ ] **Mint GitHub App installation token** step 綠燈（成功簽發 token）
   - [ ] **Run tests** 綠燈
   - [ ] **Poll GitHub Issues** 綠燈、**無 403 / 404 噪音**（代表權限與安裝正確）
4. 端到端實測：
   - 在某 opt-in repo（`.ai_profile` 有 `operator.enabled: true`，如 `AI-SOP-Protocol`）開一個帶 `ready-for-agent` 標籤的 test issue。
   - 再 dispatch 一次 → 確認該 repo 的 `.asp-task-inbox.json` 出現對應任務、commit 作者是 App（`asp-operator[bot]`）。
   - [ ] inbox 正常寫入
5. 權限負驗：到 App General 頁確認 permissions 只有 Contents(RW) + Issues(R) + Metadata(R)，**無 Pull requests**。
   - [ ] 權限符合最小集

---

## 階段 7 — 退役舊 PAT（**只在階段 6 全綠後**）

1. asp-operator repo → Settings → Secrets → 刪除舊 secret `OPERATOR_GITHUB_TOKEN`。
   - [ ] 已刪 secret
2. 撤銷該 classic PAT：`https://github.com/settings/tokens` → 找到對應 token → **Delete**。
   - [ ] 已撤銷 PAT

> ⚠️ **順序不可顛倒**。先刪 PAT 再驗證 = 切換中斷且無回滾。務必「先裝 App + 設 secret → dispatch 驗綠 → 最後才撤 PAT」。

---

## 回滾計畫（Rollback）

若階段 6 失敗、且尚未做階段 7：
- 舊 `OPERATOR_GITHUB_TOKEN` secret 仍在 → `git revert` workflow 變更（恢復 `secrets.OPERATOR_GITHUB_TOKEN`）即可立即回到 PAT 模式，期間不中斷。
- 程式層（`list_installation_repos`）對 PAT 也可運作嗎？**否** —— installation 列舉端點需 installation token。故回滾須連 workflow + `poll_issues.py main()` 一起 revert（整個 `asp/github-app-auth` merge commit revert）。
- 因此建議：**階段 6 沒綠之前不要刪 PAT**，PAT 就是你的回滾保險。

---

## 私鑰輪換（Key Rotation，定期維運）

1. App General 頁 → Private keys → **Generate a private key**（可同時存在多把）。
2. 更新 repo secret `ASP_OPERATOR_APP_PRIVATE_KEY` 為新 PEM。
3. dispatch 驗綠（階段 6）。
4. 回 App 頁 **刪除舊私鑰**。
> App ID 不變、安裝不變 → 輪換只動 secret，零程式改動。

---

## 疑難排解

| 症狀 | 可能原因 | 處置 |
|------|---------|------|
| Mint step 失敗 `not found` / `Integration not found` | `ASP_OPERATOR_APP_ID` 錯、或 App 未裝在 `owner: astroicers` | 核對 App ID、確認階段 3 已安裝 |
| `404` on `/installation/repositories` | token 不是 installation token（app-id/key 不匹配） | 確認 secret 是「對應該 App」的 PEM、variable 是同一 App 的 ID |
| `403 Resource not accessible by integration` | 權限缺漏 | 到 App permissions 補對應權限 → 帳號需在 App「Install」頁重新核准權限變更 |
| Poll 大量 `404` / `Could not load .ai_profile` warning | 正常（該 repo 無 `.ai_profile` 或非 opt-in，會被跳過） | 無需處理；若**全部** 404 才是安裝/權限問題 |
| installation repos 回空清單 | App 裝在 0 個 repo、或 `authorized_owners` 與實際 owner 不符 | 確認階段 3 選了 All repositories；確認 `operator-config.yaml` 的 `authorized_owners` 含 `astroicers` |
| inbox commit 沒出現 | 該 repo `.ai_profile` 無 `operator.enabled: true`，或無 `ready-for-agent` issue | 檢查 `.ai_profile` opt-in 與 issue 標籤 |
| Poll log 出現 `451 ... "reason": "dmca"` 或單一 repo `GithubException` | 帳號內有被封鎖 / 空 repo（如 DMCA takedown） | **正常** —— 已 per-repo 容錯，該 repo 記 WARNING 後跳過，不影響其他 repo |
| Poll log 一堆 `.ai_profile absent ... skipping`（debug） | 多數 repo 非 opt-in | **正常** —— 已降為 debug，預設不顯示 |

---

## 附錄：本次遷移改了什麼（指向程式）

| 層 | 檔案 | 變更 |
|----|------|------|
| 決策 | `docs/adr/ADR-001-github-app-auth.md` | PAT→App 決策、最小權限、摩擦評估 |
| Workflow | `.github/workflows/poll-issues.yml` | `actions/create-github-app-token` 簽發 token → 餵 `OPERATOR_GITHUB_TOKEN` |
| 程式 | `src/poll_issues.py` | `list_installation_repos`（`/installation/repositories` + 分頁 + owner 過濾）；`main()` 改用之 |
| 依賴 | `requirements.txt` | 顯式 `requests` |
| 介面 | （不變） | `OPERATOR_GITHUB_TOKEN` env var、`config_loader.get_token()` 維持，只換來源 |
