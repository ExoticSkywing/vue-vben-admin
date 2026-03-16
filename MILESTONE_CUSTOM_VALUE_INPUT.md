# 里程碑：空投包自定义数值输入功能

**日期**: 2026-03-17  
**Commit**: `052d61137`  
**在线地址**: https://center.manyuzo.com

---

## 功能概述

在空投包卡片的 **"领取限制"** 和 **"自动删除"** 徽章中，新增自定义数值输入状态。用户可以通过点击徽章循环切换状态，当切换到自定义数值状态时，徽章内嵌 `ElInputNumber` 输入框，支持直接输入数值并确认保存。

---

## 状态循环逻辑

### 领取限制 (max_claims_per_user)
```
继承(null) → 不限(0) → [点击] 自定义输入(编辑器) → [确认] 限N次(N) → 继承(null)
                                    ↓ [ESC取消]
                                 不限(0)
```

- **继承** (`null`): 显示 "继承·X次"（X为全局设置值）
- **不限** (`0`): 显示 "不限次数"
- **自定义输入**: ElInputNumber 输入框，范围 1-999
- **限N次** (`N`): 显示 "限N次"

### 自动删除 (auto_delete_seconds)
```
继承(null) → 不删(0) → [点击] 自定义输入(编辑器) → [确认] N秒后删(N) → 继承(null)
                                    ↓ [ESC取消]
                                  不删(0)
```

- **继承** (`null`): 显示 "继承·Xs"（X为全局设置秒数）
- **不删** (`0`): 显示 "不自动删"
- **自定义输入**: ElInputNumber 输入框，范围 1-86400
- **N秒后删** (`N`): 显示 "Ns后删"

---

## 编辑器交互

### UI 组件
- **输入框**: `ElInputNumber`（Element Plus）
  - 控制按钮位置：右侧 (`controls-position="right"`)
  - 宽度：90px
  - 居中文本对齐
  - 单位显示：次 / 秒
- **确认按钮**: 绿色 ✓ 文字按钮 (`type="success"`)

### 键盘操作
- **Enter**: 保存并关闭编辑器
- **ESC**: 取消编辑，关闭编辑器，保持当前状态（不限/不删）

### 取消逻辑
- 点击 **ESC 取消** 后，编辑器关闭，徽章停留在 "不限/不删" 状态
- 此时会将该包加入 `skipEditorPacks` Set
- 再次点击 "不限/不删" 徽章时，跳过编辑器，直接切换到 "继承" 状态
- 第三次点击 "继承" 时，回到 "不限/不删" 状态，此时清除 skip 标记，再点击可进入编辑器

---

## 数值记忆机制

### localStorage 持久化
为了解决页面刷新后自定义值重置为默认值（1/60）的问题，引入 localStorage 持久化：

**存储键名**:
- `airdrop_lastClaimsValue`: 上次领取限制自定义值
- `airdrop_lastAutoDeleteValue`: 上次自动删除自定义值

**存储时机**:
1. **保存时**: 用户点击 ✓ 确认按钮，保存成功后写入 localStorage
2. **切换时**: 从自定义值切换到其他状态前，自动保存当前值到 localStorage

**读取时机**:
- 页面加载时，从 localStorage 读取上次值初始化 `editingClaimsValue` / `editingAutoDeleteValue`
- 进入编辑器时，优先使用当前包的值，如果为空则使用 localStorage 中的值

**效果**:
- 用户设置 "限6次" 后，刷新页面，再次进入编辑器时自动显示 6 而非 1

---

## 技术实现

### 父组件 (index.vue)
负责管理全局编辑状态和业务逻辑。

**状态变量**:
```javascript
const editingClaimsPackId = ref<string | null>(null);
const editingClaimsValue = ref<number>(
  Number(localStorage.getItem('airdrop_lastClaimsValue')) || 1,
);
const editingAutoDeletePackId = ref<string | null>(null);
const editingAutoDeleteValue = ref<number>(
  Number(localStorage.getItem('airdrop_lastAutoDeleteValue')) || 60,
);
const skipClaimsEditorPacks = ref(new Set<string>());
const skipAutoDeleteEditorPacks = ref(new Set<string>());
```

**关键函数**:
- `handleStartEditClaims(pack)`: 检查 skip Set，决定进入编辑器或跳到继承
- `saveClaimsEdit(pack)`: 校验范围 → 调用 API → 写入 localStorage → 关闭编辑器
- `cancelEditClaims()`: 关闭编辑器 → 加入 skip Set
- `handleUpdateMaxClaims(packId, value)`: 切换状态前保存当前值到 localStorage

### 子组件 (airdrop-pack-card.vue)
负责 UI 渲染和事件触发。

**模板结构**:
```vue
<template v-if="isEditingClaims">
  <span class="claims-badge claims-badge--editing">
    <ElInputNumber
      v-model="editingClaimsValue"
      :min="1"
      :max="999"
      size="small"
      controls-position="right"
      class="badge-input"
      @update:model-value="(v) => emit('update:editingClaimsValue', v || 1)"
      @keyup.enter="emit('saveClaimsEdit', pack)"
      @keyup.esc="emit('cancelEditClaims')"
      @click="() => claimsInputRef?.focus()"
    />
    <span class="setting-unit">次</span>
    <ElButton size="small" text type="success" class="badge-confirm-btn" 
      @click.stop="emit('saveClaimsEdit', pack)">✓</ElButton>
  </span>
</template>
```

**CSS 关键样式**:
```css
/* 覆盖父容器的 user-select: none，确保输入框可交互 */
.claims-badge--editing :deep(input),
.autodel-badge--editing :deep(input) {
  user-select: auto !important;
  pointer-events: auto !important;
  -webkit-user-select: auto !important;
}

.badge-input {
  width: 90px;
}

.badge-input :deep(.el-input__inner) {
  text-align: center;
  padding: 0 8px;
}
```

---

## 修复的问题

### 1. 运行时错误
- **问题**: `ElInputNumber` 组件未导入，导致页面崩溃
- **解决**: 在 `airdrop-pack-card.vue` 中添加 `import { ElInputNumber } from 'element-plus'`

### 2. 图标不存在
- **问题**: 使用了 `@vben/icons` 中不存在的 `CheckCheck` 图标
- **解决**: 移除图标导入，改用文字 ✓ 符号作为确认按钮

### 3. 输入框无法交互
- **问题**: 父容器 CSS 设置了 `user-select: none` 和 `pointer-events: none`
- **解决**: 在编辑状态的 input 元素上强制覆盖为 `auto !important`

### 4. 内部服务器错误
- **问题**: Gateway 服务（端口 8555）在服务器重启后未自动启动
- **解决**: 创建 systemd 服务 `/etc/systemd/system/center-gateway.service`，设置开机自启动

### 5. 数值刷新丢失
- **问题**: 页面刷新后，上次输入的自定义值（如6）重置为默认值（1）
- **解决**: 使用 localStorage 持久化上次自定义值

---

## 文件变更

### 修改文件
1. **`apps/web-ele/src/views/airdrop/index.vue`**
   - 新增编辑状态变量 + skip Set
   - localStorage 读取/写入逻辑
   - handleStartEditClaims/AutoDelete 函数（判断 skip）
   - saveClaimsEdit/AutoDeleteEdit 函数（校验 + 保存）
   - cancelEditClaims/AutoDelete 函数（加入 skip Set）

2. **`apps/web-ele/src/views/airdrop/airdrop-pack-card.vue`**
   - 导入 ElInputNumber 组件
   - 添加编辑模板（两处：领取限制 + 自动删除）
   - 添加编辑状态 CSS 样式
   - 添加 user-select/pointer-events 覆盖

### 系统服务
创建 `/etc/systemd/system/center-gateway.service` — Gateway API 自动启动服务

---

## 用户体验改进

### Before
- 徽章只能在 3 个固定状态间循环：继承 → 不限/不删 → 继承
- 如需自定义值（如限6次），需要通过其他方式手动设置

### After
- 徽章循环中新增 "自定义输入" 状态
- 点击即可弹出输入框，输入任意数值（1-999 / 1-86400）
- Enter 确认或点击 ✓ 保存
- 数值自动记忆，刷新不丢失
- ESC 取消，再次点击跳过编辑器直接到下一状态

---

## 开发范式总结

### 父子组件编辑状态管理
```
Parent (index.vue)
  ├── 管理编辑状态: editingXxxPackId, editingXxxValue
  ├── 处理业务逻辑: API 调用、校验、提示
  └── 传递 props/events 给子组件

Child (airdrop-pack-card.vue)
  ├── 接收 props: isEditingXxx, editingXxxValue
  ├── 渲染 UI: 根据 props 切换显示/编辑模板
  └── emit events: startEdit, save, cancel, update:value
```

### localStorage 持久化范式
```javascript
// 初始化时读取
const value = ref(Number(localStorage.getItem('key')) || defaultValue);

// 保存时写入
localStorage.setItem('key', String(value));

// 切换前保存
if (currentValue > 0) {
  localStorage.setItem('key', String(currentValue));
}
```

### 跳过编辑器范式 (skip Set)
```javascript
const skipSet = ref(new Set<string>());

function handleStart(id) {
  if (skipSet.value.has(id)) {
    skipSet.value.delete(id);
    // 跳过编辑器，直接执行下一状态
    handleUpdate(id, nextStateValue);
  } else {
    // 进入编辑器
    editingId.value = id;
  }
}

function cancel() {
  const id = editingId.value;
  editingId.value = null;
  if (id) skipSet.value.add(id);
}
```

---

## 测试验证

### 测试场景
1. ✅ 点击 "不限" → 进入编辑器 → 输入 6 → Enter 确认 → 显示 "限6次"
2. ✅ 点击 "限6次" → 继承 → 不限 → 进入编辑器 → 显示 6（而非1）
3. ✅ 刷新页面 → 点击 "不限" → 进入编辑器 → 显示 6（localStorage 生效）
4. ✅ 编辑器中输入 999 → Enter → 保存成功
5. ✅ 编辑器中输入 1000 → Enter → 提示 "请输入1-999之间的数值"
6. ✅ 编辑器中 ESC 取消 → 关闭编辑器 → 再点击 "不限" → 跳到 "继承"

### 线上验证
- URL: https://center.manyuzo.com
- 功能: 空投包列表 → 任意卡片 → 领取限制/自动删除徽章

---

## 后续优化建议

1. **全局配置页面同步**：全局设置中也添加自定义输入，保持一致性
2. **批量编辑**：选中多个空投包，批量设置自定义数值
3. **预设快捷值**：提供常用值快捷按钮（如 1次、3次、5次、10次）
4. **数值单位智能转换**：自动删除秒数支持分钟/小时输入，自动转换为秒

---

**文档版本**: 1.0  
**维护者**: Cascade AI  
**最后更新**: 2026-03-17
