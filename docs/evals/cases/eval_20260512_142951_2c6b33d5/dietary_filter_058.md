# E2E 单用例报告：`dietary_filter_058`

- **场景分类**：`dietary_filter`
- **来源**：`recipe_adopt.json`

## §5.5 业务链路树

```text
用户输入："我做饭习惯少油少盐。西红柿炒鸡蛋我就按你推荐的版本定了，采纳这道菜。"
  ├── 意图识别：主意图 期望 `recipe_adopt` · 实际 `profile_sync` ✗；多意图 期望去重=['recipe_adopt', 'profile_sync'] ⊆ 实际（顺序无关）`['profile_sync', 'recipe_adopt']` 召回=1.00 ✓
  ├── 槽位提取：recipe_adoption≈匹配, recipe_name≈匹配 ✓
  ├── 检索调用：候选标题线索 0 条 ✗
  ├── 过滤排序：—（未实现）
  └── 生成回复：末轮可见文本片段「好的，我已记录您的饮食偏好，以后推荐菜谱时会注意。  太好了！少油少盐的饮食习惯对健康非常有益。西红柿炒鸡蛋是一道既简单又美味的选择，很适合这样的烹饪方式。记得挑选新鲜的食材哦，这样做出来的菜肴会更加鲜美。如果你需要更多类似的健康食谱推荐，…」✗；检索硬失败封顶
```

## 期望 vs 实际摘要

| 项 | 期望 | 实际 |
|---|------|------|
| primary_intent | `recipe_adopt` | `profile_sync` |
| intents（多意图子集召回） | `['recipe_adopt', 'profile_sync']` | `['profile_sync', 'recipe_adopt']` |
| needs_clarification | `False` | `False` |
| golden_recipe_ids | `['recipe_id_西红柿炒鸡蛋']` | `recipe_id_西红柿炒鸡蛋:未命中` |

## §5.1～5.4 分项与用例总分

- **overall（§5.6 加权）**：`0.35`（检索硬失败封顶）

- **检索层 §5.1**：aggregate=`0.0000`
- **生成层 §5.2**：aggregate=`—`
- **对话层 §5.3**：aggregate=`0.8465`
- **效率 §5.4（观测，不计入 overall）**：`metrics` wall_ms=17825.445 tokens=None mcp≈0

机器可读全量见同 run 目录 **`scores.json`** → `cases[]` 对应本 `case_id`。
