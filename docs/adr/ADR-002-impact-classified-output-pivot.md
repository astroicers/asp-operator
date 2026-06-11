<!-- Last Updated: 2026-06-11 | Status: Draft | Audience: asp-operator maintainers -->
# [ADR-002]: 依架構影響分類產出 — 架構級 issue 改吐 Draft ADR PR，並擷取 issue author

| 欄位 | 內容 |
|------|------|
| **狀態** | `Draft` |
| **日期** | 2026-06-11 |
| **決策者** | astroicers（待人類審核） |
| **觸發事件** | AI-SOP-Protocol [ADR-012](https://github.com/astroicers/AI-SOP-Protocol/blob/main/docs/adr/ADR-012-define-operator-autopilot-interaction-trust-model.md)（Accepted 2026-06-11）DP5 要求 operator 重定位；一致性審計揭露 C1（asp-op 與 autopilot ADR 閘從未對齊）與 C3（直推 main 無證成 + 丟失 issue author） |
| **關聯** | ADR-012 DP1/DP2/DP5；AI-SOP-Protocol SPEC-007（inbox held）/ SPEC-008（provenance 閘）/ SPEC-009（triage 通道）；`src/task_translator.py`；`src/inbox_writer.py`；`src/poll_issues.py` |

> **狀態說明：** `Draft`（初稿，禁止實作）→ `FIRM`（POC 驗證，允許 commit，需附驗證證據）→ `Accepted`（人類審核通過）

---

## 背景（Context）

ADR-012 確立了 provenance-scoped 信任模型，下游（AI-SOP-Protocol）已落地三層：

- **SPEC-007**：`inbox-ingest.sh` 改 held-mode——inbox 內容不再自動進 ROADMAP（inbox 從「執行進料」降為「待授權佇列」，投毒無效）。
- **SPEC-008**：autopilot provenance 閘——外部任務須人類授權才執行。
- **SPEC-009**：`make inbox-triage`——外部**非架構**任務的人類核准通道（核准者的 commit 即授權記號）。

這改變了 asp-op 的處境：

1. **非架構 issue**：現行「issue → inbox」流程**已經安全**（held + triage + 閘三層把關），不需改變傳輸方式。
2. **架構級 issue**：inbox 路徑對它是 dead-end（C1）——下游 autopilot 要求 Accepted ADR，而 inbox 任務無 ADR、又因 SPEC-008 設計**不會**替外部任務自動建 Draft ADR（避免無 approver 的 skeleton ADR 噪音）。架構級外部需求需要一條「生出 Draft ADR 提案」的路。
3. **author 遺失（C3）**：`task_translator.py:51` 硬編 `triggered_by: "customer"`，不擷取 `issue.user` / `author_association` → triage 時人類看不到提案者、audit 無身分軌跡。
4. **直推 main 無證成（C3）**：`inbox_writer.py:30,61` 直接 commit `.asp-task-inbox.json` 到 main，從未有 ADR 證成。SPEC-007 後此風險已大幅降低（inbox 是惰性佇列），但「無證成」本身需要被正式決定。

---

## 評估選項（Options Considered）

### 選項 A：全面 pivot——所有 issue 一律改吐 Draft ADR / triage PR（branch+PR），廢除 inbox

- **優點**：單一產出機制；徹底解決直推 main。
- **缺點**：非架構路徑（inbox→held→triage）**剛建好且安全**，重做等於丟棄下游三個 SPEC 的成果；GitHub PR 型 triage 已在 ADR-012 SPEC-009 設計討論中被否決（squash 混淆 authorship、YAML blame 脆弱）。
- **風險**：過度設計；asp-op 改動面最大。

### 選項 B：影響分類 pivot——架構級吐 Draft ADR PR、非架構維持 inbox（+ author 擷取）← 建議

- **優點**：精準補 C1 缺口（架構級終於有路）；非架構沿用已驗證安全的 inbox 鏈；author 擷取讓 triage 與 audit 有身分；改動面最小。
- **缺點**：asp-op 需新增影響分類啟發式（label/關鍵詞），有誤判可能。
- **風險**：誤判緩解 = ADR-012 DP5「不確定往高一級回退」（誤升架構級只是多一道人審，不破壞安全）。

### 選項 C：維持現狀（不 pivot）

- **優點**：零改動。
- **缺點**：架構級外部 issue 永遠 dead-end（C1 未解）；author 持續遺失（C3 未解）；ADR-012 DP5 成為空文。
- **風險**：外部架構需求只能由人類全手工搬運，operator 價值受限。

---

## 決策（Decision）

採 **選項 B：影響分類 pivot**。

1. **影響分類（DP5）**：`task_translator.py` 新增 `classify_impact(issue)` —— 以 label（如 `architecture`、`breaking-change`）與標題/內文關鍵詞（new module / schema / API contract / auth / tech stack）判定 `architectural | non-architectural`；**不確定一律升為 architectural**（DP5 回退規則：誤升只多一道人審）。
2. **架構級 issue → Draft ADR PR**：以 issue 內容填 ADR 模板（Context=issue 描述、提案者=issue author）、開 branch `asp-op/adr-proposal-<issue#>`、發 **draft PR** 到目標 repo。**asp-op 永不標 Accepted、永不 merge**（沿用 CLAUDE.md 鐵則；人類 Accept 該 ADR 才構成 ADR-012 的架構級授權）。
3. **非架構 issue → inbox（不變）**：傳輸機制照舊；安全由下游 held（SPEC-007）+ triage（SPEC-009）+ 閘（SPEC-008）保證。
4. **author 擷取（修 C3）**：translated task 新增 `author`（issue.user.login）與 `author_association`（OWNER/MEMBER/COLLABORATOR/NONE…）；`triggered_by` 不再硬編，改為 `issue:<login>`。inbox schema 對應擴充（向後相容：舊欄位保留）。
5. **inbox 直推 main：正式接受並證成**（解 C3 的「無證成」）：在 SPEC-007 held-mode 下，inbox 為**惰性佇列**（寫入不產生任何執行效果），直推 main 的剩餘風險 = 髒 commit 歷史；相對 branch+PR 的維運成本（每 30 分鐘 cron 產 PR 噪音），**保留直推**。若日後 held 機制被移除，本項必須重審。

---

## 後果（Consequences）

**正面影響：**
- C1 終結：架構級外部需求有正式路徑（Draft ADR 提案 → 人類 Accept → autopilot 可執行）。
- C3 終結：author/author_association 進入 triage 與 audit 視野；直推 main 從「未證成捷徑」變為「已證成決策」。
- 與 ADR-012 三個下游 SPEC 完整咬合，全鏈路：弱 label 至多產生「需人類放行的提案」（Draft ADR 或 held task）。

**負面影響 / 技術債：**
- 影響分類啟發式需迭代（誤判率待觀察；先以保守升級緩解）。
- Draft ADR PR 的模板填充品質有限（issue 內容稀疏時 Context 單薄）——人類 Accept 前本就須補審。
- inbox schema 擴充需同步 `task-inbox-schema.json` 與下游 triage 顯示。

**後續追蹤（gated on Accept）：**
- [ ] SPEC：`classify_impact()` + 關鍵詞/label 規則 + 「不確定升級」測試
- [ ] SPEC：Draft ADR PR 產生器（模板填充 + branch + draft PR；永不 Accept/merge）
- [ ] SPEC：author/author_association 擷取 + schema 擴充（含 AI-SOP-Protocol 端 triage 顯示）
- [ ] 文件：CLAUDE.md 邊界更新（「只寫 inbox」→「寫 inbox 或開 Draft ADR 提案 PR，永不執行/merge/Accept」）

---

## 成功指標（Success Metrics）

| 指標 | 目標值 | 驗證方式 | 檢查時間 |
|------|--------|----------|----------|
| 架構級測試 issue 產生 Draft ADR PR（非 inbox） | 1 例端到端 | 測試 issue + 觀察 PR | pivot 實作完成時 |
| asp-op 永不 Accept/merge | 0 例違反 | code review + 權限稽核 | 持續 |
| inbox 任務帶 author/author_association | 100% 新任務 | inbox JSON 抽查 | author 擷取上線後 |
| 不確定 issue 升級為 architectural | 100%（無靜默降級） | classify_impact 單元測試 | SPEC 實作時 |

> 重新評估時機：若 Draft ADR PR 噪音過高（誤判率 > ~30%）或 held 機制被下游移除（直推 main 風險回升）。

---

## 關聯（Relations）

- 取代：（無）
- 被取代：（無）
- 參考：
  - AI-SOP-Protocol ADR-012（信任模型；本 ADR 為其 DP5 的 operator 側落地）
  - AI-SOP-Protocol SPEC-007/008/009（下游三層；本 ADR 依賴其已落地）
  - 本 repo ADR-001（GitHub App 認證；Draft ADR PR 沿用同一 App 身分）

---

## Verification Evidence（升級至 FIRM 時必填）

| 欄位 | 內容 |
|------|------|
| **POC 分支 / 測試結果** | （待填） |
| **驗證日期** | （待填） |
| **驗證者** | （待填） |
| **驗證摘要** | （待填） |
