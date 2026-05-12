# E2E 测评总报告（T-043）

- **run_id**：`eval_20260512_142951_2c6b33d5`
- **run 目录**：`F:\WHAT-TO-EAT-AGENT\docs\evals\runs\eval_20260512_142951_2c6b33d5`
- **manifest**：`docs/evals/runs/eval_20260512_142951_2c6b33d5/manifest.json`
- **用例数**：72
- **平均分 overall（§5.6）**：**0.802601**

## §5.0～5.4 汇总

| 维度 | 值 |
|------|-----|
| 检索层集级 MRR 均值（§5.1） | `0.568627` |
| 加权权重（§5.6，效率不计分） | 检索 0.35 · 生成 0.325 · 对话 0.325 |

## §5.4 效率观测汇总（**不计入** §5.6 加权 overall）

聚合自各用例 `scores.json` → `cases[].layers.efficiency.metrics`（与单用例报告 §5.4 行同源）。

| 指标 | 值 |
|------|-----|
| 有墙钟数据的用例数 / 报告内用例数 | `72` / `72` |
| 全 run 墙钟合计（ms） | `1312111.245` |
| 每用例墙钟算术均值（ms） | `18223.767` |
| 有 token 采样的用例数 | `0` |
| token 合计（仅计有采样的消息） | `—` |
| token 有采样时的每用例均值 | `—` |
| 有 MCP 推断计数的用例数 | `72` |
| MCP 推断次数合计（全 run） | `27` |
| MCP 有计数时的每用例均值 | `0.375` |

## 通过率与失败索引

- **可打分用例**：72/72
- **本报告「失败」索引条数**：6（执行错误 + 检索硬失败 + 总分过低）

  - `ambiguity_057（检索硬失败）`
  - `dietary_filter_058（检索硬失败）`
  - `edge_case_071（overall<0.35）`
  - `inventory_032（检索硬失败）`
  - `multi_turn_006（检索硬失败）`
  - `multi_turn_035（检索硬失败）`

## 单用例报告路径

每条 Markdown：`docs/evals/cases/<run_id>/<case_id>.md`（本 run 已生成）。下表 **wall_ms / tokens / mcp≈** 为 §5.4 观测，**不计入** overall。

| case_id | overall | wall_ms | tokens | mcp≈ | 单报告 |
|---------|---------|---------|--------|------|--------|
| `ambiguity_004` | 0.7602 | 16902.2 | — | 1 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/ambiguity_004.md` |
| `ambiguity_042` | 0.4690 | 10448.1 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/ambiguity_042.md` |
| `ambiguity_057` | 0.3305 | 8721.2 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/ambiguity_057.md` |
| `ambiguity_067` | 0.4065 | 10617.1 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/ambiguity_067.md` |
| `ambiguity_068` | 0.4065 | 5580.3 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/ambiguity_068.md` |
| `dietary_filter_002` | 0.9025 | 16572.9 | — | 1 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/dietary_filter_002.md` |
| `dietary_filter_058` | 0.3500 | 17825.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/dietary_filter_058.md` |
| `dietary_filter_063` | 0.9365 | 10550.2 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/dietary_filter_063.md` |
| `edge_case_012` | 0.9500 | 5968.1 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_012.md` |
| `edge_case_018` | 0.8740 | 6987.5 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_018.md` |
| `edge_case_021` | 0.8600 | 23899.7 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_021.md` |
| `edge_case_024` | 1.0000 | 25588.2 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_024.md` |
| `edge_case_030` | 0.9647 | 11100.2 | — | 2 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_030.md` |
| `edge_case_036` | 0.7115 | 7136.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_036.md` |
| `edge_case_037` | 0.7065 | 18910.2 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_037.md` |
| `edge_case_038` | 0.9500 | 17690.3 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_038.md` |
| `edge_case_041` | 0.9865 | 23706.3 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_041.md` |
| `edge_case_043` | 0.9865 | 2741.6 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_043.md` |
| `edge_case_044` | 1.0000 | 6350.0 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_044.md` |
| `edge_case_046` | 0.6815 | 19360.5 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_046.md` |
| `edge_case_048` | 0.9865 | 8465.6 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_048.md` |
| `edge_case_049` | 0.9865 | 4512.2 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_049.md` |
| `edge_case_050` | 0.9865 | 3780.3 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_050.md` |
| `edge_case_051` | 0.9865 | 7349.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_051.md` |
| `edge_case_052` | 1.0000 | 5034.2 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_052.md` |
| `edge_case_054` | 0.9365 | 7145.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_054.md` |
| `edge_case_060` | 0.5465 | 8697.5 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_060.md` |
| `edge_case_062` | 0.9365 | 9789.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_062.md` |
| `edge_case_066` | 0.4300 | 9705.1 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_066.md` |
| `edge_case_071` | 0.2175 | 12130.8 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_071.md` |
| `edge_case_072` | 0.7265 | 12025.7 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/edge_case_072.md` |
| `inventory_007` | 0.9500 | 4008.6 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_007.md` |
| `inventory_008` | 0.9865 | 4577.8 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_008.md` |
| `inventory_009` | 0.9500 | 5852.6 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_009.md` |
| `inventory_010` | 0.7965 | 17270.3 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_010.md` |
| `inventory_013` | 0.9365 | 4692.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_013.md` |
| `inventory_014` | 0.9365 | 8694.9 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_014.md` |
| `inventory_015` | 0.9500 | 8518.7 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_015.md` |
| `inventory_016` | 0.6165 | 5884.0 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_016.md` |
| `inventory_031` | 0.8215 | 10018.0 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_031.md` |
| `inventory_032` | 0.3500 | 6145.5 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_032.md` |
| `inventory_033` | 0.8665 | 6383.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_033.md` |
| `inventory_034` | 0.5715 | 8772.2 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_034.md` |
| `inventory_045` | 0.7965 | 18701.6 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/inventory_045.md` |
| `multi_turn_006` | 0.2708 | 17096.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_006.md` |
| `multi_turn_011` | 1.0000 | 13408.1 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_011.md` |
| `multi_turn_017` | 0.9500 | 14777.6 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_017.md` |
| `multi_turn_023` | 0.9050 | 25436.2 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_023.md` |
| `multi_turn_029` | 0.9211 | 97038.6 | — | 2 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_029.md` |
| `multi_turn_035` | 0.3500 | 17448.2 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_035.md` |
| `multi_turn_040` | 0.9165 | 45261.1 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_040.md` |
| `multi_turn_047` | 0.7065 | 24123.8 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_047.md` |
| `multi_turn_053` | 0.9365 | 22279.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_053.md` |
| `multi_turn_059` | 0.9030 | 61361.7 | — | 2 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_059.md` |
| `multi_turn_061` | 0.9500 | 13788.0 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_061.md` |
| `multi_turn_065` | 0.9365 | 13051.0 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_065.md` |
| `multi_turn_069` | 0.8575 | 46933.9 | — | 3 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/multi_turn_069.md` |
| `nutrition_query_005` | 0.9694 | 19036.7 | — | 1 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/nutrition_query_005.md` |
| `nutrition_query_019` | 0.9865 | 30705.6 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/nutrition_query_019.md` |
| `nutrition_query_020` | 0.8665 | 21905.4 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/nutrition_query_020.md` |
| `nutrition_query_022` | 0.9865 | 24349.5 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/nutrition_query_022.md` |
| `nutrition_query_039` | 0.7900 | 24050.3 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/nutrition_query_039.md` |
| `nutrition_query_064` | 0.8665 | 6994.0 | — | 0 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/nutrition_query_064.md` |
| `recipe_query_001` | 0.9935 | 16584.8 | — | 1 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/recipe_query_001.md` |
| `recipe_query_003` | 0.7342 | 19142.7 | — | 1 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/recipe_query_003.md` |
| `recipe_query_055` | 0.8973 | 75023.1 | — | 2 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/recipe_query_055.md` |
| `recipe_query_056` | 0.8404 | 58884.5 | — | 2 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/recipe_query_056.md` |
| `recipe_query_070` | 0.6211 | 17994.3 | — | 1 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/recipe_query_070.md` |
| `shopping_list_025` | 0.8554 | 62757.3 | — | 2 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/shopping_list_025.md` |
| `shopping_list_026` | 0.8258 | 6561.9 | — | 2 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/shopping_list_026.md` |
| `shopping_list_027` | 0.8941 | 37263.0 | — | 2 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/shopping_list_027.md` |
| `shopping_list_028` | 0.5556 | 14042.0 | — | 2 | `docs/evals/cases/eval_20260512_142951_2c6b33d5/shopping_list_028.md` |

## 原始采集与机器成绩

- captures：`docs/evals/runs/eval_20260512_142951_2c6b33d5/captures/`
- scores：`docs/evals/runs/eval_20260512_142951_2c6b33d5/scores.json`

---

与 `docs/test_report.md` 职责划分见规格 §10.6 / 开发计划 §6。