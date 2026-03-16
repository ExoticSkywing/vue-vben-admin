# 空投包内容保护 — 三级优先级体系

**实现日期**: 2026-03-16  
**功能类型**: 细粒度访问控制  
**状态**: ✅ 已上线

---

## 功能概述

实现了基于 Telegram `protect_content` 参数的内容保护功能，采用三级优先级体系：
- **全局默认设置**: 管理员在前端设置全站默认保护策略
- **包级覆盖**: 单个空投包可覆盖全局设置
- **三种状态**: 继承全局 / 强制保护 / 强制公开

当用户收到受保护的消息时，Telegram 会禁止转发、下载、复制该消息。

---

## 技术实现

### 1. 数据库层 (Layer 1)

**新增表**: `bot_settings`
```sql
CREATE TABLE IF NOT EXISTS bot_settings (
    setting_key VARCHAR(64) PRIMARY KEY,
    setting_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
INSERT INTO bot_settings (setting_key, setting_value) VALUES ('protect_content', 'true');
```

**扩展表**: `resource_packs`
```sql
ALTER TABLE resource_packs ADD COLUMN protect_content BOOLEAN DEFAULT NULL;
```

**工具函数**: `database/database.py`
- `get_setting(key, default)` — 读取全局设置
- `set_setting(key, value)` — 更新全局设置
- `get_pack_protect_content(pack_id)` — 获取包级有效保护值（优先级合并）

### 2. Bot 投递逻辑 (Layer 2)

**文件**: `plugins/start.py`

```python
# 读取包级保护设置（自动处理 NULL 继承逻辑）
protect = get_pack_protect_content(pack_id)

# 传递给单条消息发送
copied = await msg.copy(
    chat_id=message.from_user.id,
    protect_content=protect  # 使用包级设置
)

# 传递给媒体组发送
sent_group = await client.send_media_group(
    chat_id=message.from_user.id,
    media=batch,
    protect_content=protect  # 使用包级设置
)
```

### 3. 内部 API (Layer 3)

**文件**: `internal_api/routes_packs.py`

**新增端点**:
- `GET /api/settings` — 获取全局设置
- `PUT /api/settings` — 更新全局设置（仅超管）

**扩展端点**:
- `GET /api/packs` — 列表响应新增 `protect_content` 字段
- `GET /api/packs/{pack_id}` — 详情响应新增 `protect_content` 字段
- `PUT /api/packs/{pack_id}` — 支持更新 `protect_content` (三态: `"true"` / `"false"` / `"inherit"`)

**数据规范化**: MySQL `BOOLEAN` 的 `0/1/NULL` 转为 JSON `true/false/null`

### 4. API Gateway (Layer 4)

**文件**: `api_gateway/routers/airdrop.py`

**新增端点**:
- `GET /airdrop/settings` → 转发到内部 API
- `PUT /airdrop/settings` → 转发到内部 API（校验超管权限）

**扩展模型**:
```python
class PackUpdateRequest(BaseModel):
    name: Optional[str] = None
    tags: Optional[str] = None
    protect_content: Optional[str] = None  # "true" | "false" | "inherit"
```

### 5. 前端 (Layer 5)

#### 数据层 (`api/airdrop.ts`)
```typescript
export interface Pack {
  protect_content: boolean | null;  // null=继承, true=强制保护, false=强制公开
  // ...
}

export interface Settings {
  protect_content: boolean;  // 全局默认值
}

// 新增 API 函数
getSettingsApi(): Promise<Settings>
updateSettingsApi(data: { protect_content?: boolean })
updatePackApi(packId, { protect_content?: 'true' | 'false' | 'inherit' })
```

#### UI 层 (`views/airdrop/`)

**全局开关** (`index.vue` 工具栏):
```vue
<ElTooltip content="全局内容保护：已开启 / 已关闭">
  <div class="global-protect-switch">
    <ElIcon><ShieldCheck v-if="globalProtect" /><ShieldOff v-else /></ElIcon>
    <ElSwitch v-model="globalProtect" @change="toggleGlobalProtect" />
  </div>
</ElTooltip>
```

**包级徽章** (`airdrop-pack-card.vue`):
```vue
<span class="protect-badge" :class="`protect-badge--${state}`" @click="cycleProtect">
  <ElIcon><ShieldCheck /></ElIcon>
  <span>{{ label }}</span>  <!-- "继承·保护" / "强制保护" / "强制公开" -->
</span>
```

---

## UI 设计

### 三色徽章系统

| 状态 | 视觉 | 样式 | 点击行为 |
|------|------|------|----------|
| **继承全局** | 虚线灰框 + 灰字 | `border: 1px dashed` + `color: var(--el-text-color-secondary)` | → 强制保护 |
| **强制保护** | 绿色实底 + 白字 | `background: var(--el-color-success)` | → 强制公开 |
| **强制公开** | 橙色实底 + 白字 | `background: var(--el-color-warning)` | → 继承全局 |

### 动态文本
- 继承状态根据全局值动态显示: `继承·保护` 或 `继承·公开`
- 强制状态显示固定文本: `强制保护` / `强制公开`

### 交互反馈
- 鼠标悬停: `transform: scale(1.05)` + `filter: brightness(0.95)`
- 点击切换: 三态循环 + ElMessage 成功提示

---

## Git 提交记录

### File-Sharing-Bot
```
commit 1569104
feat: 按包粒度内容保护控制（三级优先级）

- DB: 新增 bot_settings 表 + resource_packs.protect_content 列
- Bot: _deliver_pack 读取包级 protect_content 替代全局配置
- API: GET/PUT /api/settings 全局设置端点 + pack 返回/更新 protect_content
- 优先级: 包级(NULL/true/false) > 全局默认值
```

### vue-vben-admin
```
commit abcfbc9a2
feat: 按包粒度内容保护控制 — 前端+Gateway

- Gateway: 新增 GET/PUT /settings 端点，PackUpdateRequest 支持 protect_content 三态
- 前端: 工具栏全局保护开关(ShieldCheck/ShieldOff + ElSwitch)
- 卡片: 包级保护指示器(三态循环: 继承全局→强制保护→强制公开)
- API: Pack 接口加 protect_content, 新增 getSettingsApi/updateSettingsApi
- 图标: 新增 ShieldCheck, ShieldOff 到 lucide 导出

commit 7ec345130
style: 保护状态改为三色徽章标签 — 继承(虚线灰)·强制保护(绿底)·强制公开(橙底)
```

---

## 使用说明

### 管理员操作

1. **设置全局默认保护**:
   - 打开空投管理页面
   - 工具栏右侧找到盾牌图标 + 开关
   - 开启 = 全站新包默认受保护
   - 关闭 = 全站新包默认公开

2. **覆盖单个包的保护状态**:
   - 找到目标空投包卡片
   - 点击顶部左侧的保护徽章
   - 循环切换三种状态:
     - `继承·保护` / `继承·公开` → 跟随全局设置
     - `强制保护` → 无论全局如何，该包受保护
     - `强制公开` → 无论全局如何，该包公开

### 用户体验

- **受保护的消息**: 用户在 Telegram 中无法转发、下载、截图（部分客户端）
- **公开的消息**: 用户可以正常转发、下载
- **推荐策略**: 
  - 付费内容 → 强制保护
  - 公开宣传 → 强制公开
  - 普通资源 → 继承全局

---

## 技术亮点

1. **三级优先级**: 包级覆盖 > 全局默认 > 硬编码常量
2. **类型安全**: FastAPI Pydantic 模型 + TypeScript 接口
3. **数据规范化**: MySQL 0/1/NULL 自动转换为 JSON true/false/null
4. **视觉可辨识**: 三色徽章 + 动态文字 + 图标，无需悬停即可区分
5. **权限控制**: 仅超级管理员可修改全局设置
6. **向后兼容**: 旧包 `protect_content = NULL` 自动继承全局设置

---

## 后续优化方向

- [ ] 批量设置保护状态（勾选多个包后统一设置）
- [ ] 保护状态筛选（仅显示受保护/公开/继承的包）
- [ ] 保护状态统计（Dashboard 显示各状态包数量）
- [ ] 时间限定保护（某个包在特定时间后自动公开）
