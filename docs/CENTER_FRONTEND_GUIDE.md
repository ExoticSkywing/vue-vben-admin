# Nebuluxe Center 前端开发范式指南

> **版本**：v1.0 — 2026-03-15
> **前置阅读**：[DEVELOPER_GUIDE.md](../../themes/panda/xingxy/patches/antigravity/DEVELOPER_GUIDE.md)（生态全景 + 身份接入）
> **定位**：本文档面向所有在 Center 前端新增管理页面的开发者。无论你是新增一个业务模块、优化现有 UI，还是接入新的后端服务，本文都将指导你**遵循已验证的编码范式，避免已知的坑，写出风格统一的高质量页面**。

---

## 〇、技术栈速览

| 层 | 技术 | 说明 |
|----|------|------|
| 框架 | Vue 3 + TypeScript | Composition API, `<script setup>` |
| 构建 | Vite + pnpm monorepo | Turbo 缓存，增量构建 |
| UI 库 | **Element Plus** (`web-ele`) | 当前生产版本，非 Ant Design |
| 图标 | Lucide（通过 `@vben/icons` 桥接） | 不直接 import `lucide-vue-next` |
| 状态 | 组件内 `ref`/`computed` | 暂无 Pinia 全局 store 需求 |
| 请求 | `requestClient`（封装 fetch） | 自动带 JWT，自动刷新 token |
| 路由 | Vue Router，按模块文件自动注册 | `src/router/routes/modules/*.ts` |
| 样式 | Scoped CSS + CSS 变量 | 兼容深浅模式，不硬编码颜色 |
| 部署 | `bash deploy.sh` | 一键构建 + 同步到 center.manyuzo.com |

---

## 一、项目结构（你需要关注的部分）

```
vue-vben-admin/
├── apps/web-ele/src/           # ← 你的主战场
│   ├── api/                    # API 封装层
│   │   ├── request.ts          # requestClient 配置（勿改）
│   │   └── airdrop.ts          # ← 示范：空投模块 API
│   ├── router/routes/modules/  # 路由注册
│   │   └── airdrop.ts          # ← 示范：空投模块路由
│   └── views/                  # 页面视图
│       ├── dashboard/analytics/ # ← 示范：拆分良好的页面
│       │   ├── index.vue        #    编排器（~90行）
│       │   ├── analytics-visits.vue
│       │   ├── analytics-visits-data.vue
│       │   └── ...
│       └── airdrop/            # ← 示范：业务模块目录
│           └── index.vue        #    (待拆分为子组件)
├── packages/@core/base/
│   ├── icons/src/lucide.ts     # ← 注册新 Lucide 图标
│   └── design/src/design-tokens/
│       ├── default.css          # 浅色主题 CSS 变量
│       └── dark.css             # 深色主题 CSS 变量
├── deploy.sh                   # 一键构建部署脚本
└── CENTER_FRONTEND_GUIDE.md    # ← 你正在读的文档
```

---

## 二、新增模块：5 步范式

### 步骤 1：定义 API 层 (`src/api/yourmodule.ts`)

```typescript
/**
 * 你的模块 API
 */
import { requestClient } from '#/api/request';

// 1. 用 namespace 组织类型（避免全局命名冲突）
export namespace YourModuleApi {
  export interface Item {
    id: string;
    name: string;
    // ...
  }

  export interface ListResult {
    items: Item[];
    total: number;
    page: number;
    page_size: number;
  }
}

// 2. 导出具名函数，命名规则：动词 + 实体 + Api
export async function listItemsApi(params: {
  search?: string;
  page?: number;
  page_size?: number;
}) {
  return requestClient.get<YourModuleApi.ListResult>('/yourmodule/items', {
    params,
  });
}

export async function updateItemApi(
  itemId: string,
  data: { name?: string },
) {
  return requestClient.put(`/yourmodule/items/${itemId}`, data);
}

export async function deleteItemApi(itemId: string) {
  return requestClient.delete(`/yourmodule/items/${itemId}`);
}
```

**要点**：
- `requestClient` 已配置 base URL、JWT 注入、token 刷新、错误弹窗，**直接用，不要自己封装 fetch/axios**
- `requestClient` 只有 `get`/`post`/`put`/`delete`，**没有 `patch`**，用 `put` 代替
- 返回类型用泛型 `requestClient.get<T>()` 指定

### 步骤 2：注册路由 (`src/router/routes/modules/yourmodule.ts`)

```typescript
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:box',        // 侧边栏图标（Iconify 格式）
      order: 20,                  // 菜单排序
      title: '你的模块',
    },
    name: 'YourModule',
    path: '/yourmodule',
    children: [
      {
        name: 'YourModuleList',
        path: '/yourmodule/list',
        component: () => import('#/views/yourmodule/index.vue'),
        meta: {
          icon: 'lucide:list',
          title: '列表管理',
        },
      },
    ],
  },
];

export default routes;
```

**要点**：
- 文件放在 `modules/` 下即可，框架会**自动扫描注册**
- `icon` 使用 Iconify 格式字符串 `lucide:icon-name`，无需手动 import
- `order` 控制在侧边栏菜单的排序位置

### 步骤 3：编写页面视图

#### 3a. 组件拆分原则（重要！）

**一个 `.vue` 文件不应超过 300 行。** 超过时按以下模式拆分：

```
views/yourmodule/
├── index.vue                   # 编排器：状态管理 + 数据加载 + 子组件组合
├── yourmodule-sidebar.vue      # 侧边栏/筛选器
├── yourmodule-card.vue         # 列表中的单个卡片/行
├── yourmodule-drawer.vue       # 抽屉/弹窗类交互
└── yourmodule-mobile-bar.vue   # 移动端适配组件（如需）
```

**`index.vue` 作为编排器**：
- 持有所有响应式状态（`ref`/`computed`）
- 负责 API 调用和数据加载
- 通过 `props` 向下传数据，通过 `emits` 向上传事件
- 模板只做组件组合，不写复杂逻辑

参考 `dashboard/analytics/index.vue`（91 行编排器 + 5 个子组件）。

#### 3b. `<script setup>` 结构约定

```vue
<script setup lang="ts">
// ① Vue 核心
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

// ② 图标（从 @vben/icons，不是 lucide-vue-next）
import { Search, Plus, Trash2 } from '@vben/icons';

// ③ Element Plus 组件（按需 import，不要全局引入）
import {
  ElButton,
  ElCard,
  ElIcon,
  ElInput,
  ElMessage,
  ElPagination,
  ElTag,
} from 'element-plus';

// ④ 项目 API
import { listItemsApi, deleteItemApi } from '#/api/yourmodule';
import type { YourModuleApi } from '#/api/yourmodule';

// ⑤ defineOptions
defineOptions({ name: 'YourModuleList' });

// ⑥ 状态声明（按功能分组，用注释分隔）
// ─── 列表状态 ───
const loading = ref(false);
const items = ref<YourModuleApi.Item[]>([]);
const total = ref(0);

// ─── 搜索 ───
const searchText = ref('');

// ─── 响应式 ───
const isMobile = ref(false);
function checkMobile() {
  isMobile.value = window.innerWidth < 768;
}

// ⑦ 业务方法
async function loadData() { /* ... */ }

// ⑧ 生命周期
onMounted(() => {
  checkMobile();
  window.addEventListener('resize', checkMobile);
  loadData();
});
onUnmounted(() => {
  window.removeEventListener('resize', checkMobile);
});
</script>
```

### 步骤 4：编写样式（详见第三节）

### 步骤 5：构建部署

```bash
cd /www/wwwroot/xingxy.manyuzo.com/wp-content/plugins/services/vue-vben-admin
bash deploy.sh
```

一键完成：`pnpm build:ele --concurrency=1` → 清空 → 复制到 `center.manyuzo.com`。

---

## 三、样式编码规范

### 3.1 黄金规则：永远用 CSS 变量，永远不硬编码颜色

```css
/* ✅ 正确 — 自动适配深浅模式 */
.my-card {
  background-color: var(--el-bg-color);
  color: var(--el-text-color-primary);
  border: 1px solid var(--el-border-color-lighter);
}

/* ❌ 错误 — 深色模式下白底黑字 */
.my-card {
  background-color: #ffffff;
  color: #333333;
  border: 1px solid #eee;
}
```

### 3.2 可用的 Element Plus CSS 变量速查

| 类别 | 常用变量 | 用途 |
|------|----------|------|
| **背景** | `--el-bg-color` | 组件背景 |
| | `--el-bg-color-page` | 页面底色 |
| | `--el-fill-color` | 填充/badge 背景 |
| | `--el-fill-color-light` | 浅填充 |
| **文字** | `--el-text-color-primary` | 主文本 |
| | `--el-text-color-regular` | 正文 |
| | `--el-text-color-secondary` | 辅助文本 |
| | `--el-text-color-placeholder` | 占位符 |
| **边框** | `--el-border-color` | 标准边框 |
| | `--el-border-color-lighter` | 较浅边框 |
| | `--el-border-color-extra-light` | 极浅边框 |
| **主题** | `--el-color-primary` | 主色 |
| | `--el-color-primary-light-9` | 主色极浅（激活背景） |
| | `--el-color-success` | 成功绿 |
| | `--el-color-warning` | 警告黄 |
| | `--el-color-danger` | 危险红 |
| **圆角** | `--el-border-radius-base` | 标准圆角 |

### 3.3 Vben 框架设计变量（Shadcn 层）

框架还有一套 Shadcn-style 变量（`default.css` / `dark.css`），在 Element Plus 变量不够用时可用：

- `--background` / `--foreground` — 全局背景/前景
- `--card` / `--card-foreground` — 卡片
- `--muted` / `--muted-foreground` — 低调元素
- `--primary` / `--primary-foreground` — 主色
- `--destructive` — 危险色
- `--border` — 边框
- `--radius` — 圆角

**注意**：这些变量的值是 HSL 分量（如 `212 100% 45%`），使用时需要 `hsl()` 包裹：
```css
background-color: hsl(var(--primary));
```

### 3.4 自定义颜色的正确方式

需要框架没有的颜色（如紫色标签）时，用 **CSS 变量覆盖 + `rgba()`**：

```css
/* 通过覆盖 ElTag 的 CSS 变量实现紫色标签 */
.purple-tag {
  --el-tag-bg-color: rgba(147, 51, 234, 0.1) !important;
  --el-tag-border-color: rgba(147, 51, 234, 0.2) !important;
  --el-tag-text-color: #9333ea !important;
}
```

**用 `rgba()` 而非固定 hex，确保在深浅模式下透明度表现一致。**

### 3.5 响应式设计

```css
/* 断点约定 */
@media (max-width: 1199px) { /* 中屏：收起双列为单列 */ }
@media (max-width: 767px)  { /* 移动端：侧边栏隐藏，改为标签栏 */ }
```

移动端检测（JS 侧）：
```typescript
const isMobile = ref(false);
function checkMobile() {
  isMobile.value = window.innerWidth < 768;
}
onMounted(() => {
  checkMobile();
  window.addEventListener('resize', checkMobile);
});
onUnmounted(() => {
  window.removeEventListener('resize', checkMobile);
});
```

用 `v-if="!isMobile"` / `v-if="isMobile"` 切换桌面端侧边栏和移动端标签栏。

---

## 四、图标系统（重要！）

### 4.1 架构

```
lucide-vue-next          (底层包，node_modules 中)
    ↑ re-export
@vben-core/icons         (packages/@core/base/icons/src/lucide.ts)
    ↑ re-export
@vben/icons              (packages/icons/src/index.ts)
    ↑ import
你的 .vue 文件
```

### 4.2 在组件中使用图标

```vue
<script setup>
// ✅ 正确 — 从 @vben/icons 导入
import { Search, Plus, Trash2 } from '@vben/icons';

// ❌ 错误 — 构建会报 "failed to resolve"
import { Search } from 'lucide-vue-next';
</script>

<template>
  <!-- 用 ElIcon 包裹 Lucide 组件 -->
  <ElIcon :size="16"><Search /></ElIcon>

  <!-- 或作为 ElButton 的 icon prop -->
  <ElButton :icon="Trash2" type="danger" />
</template>
```

### 4.3 添加新图标

如果 `@vben/icons` 没有导出你需要的图标：

1. 去 [lucide.dev/icons](https://lucide.dev/icons) 查找图标名
2. 编辑 `packages/@core/base/icons/src/lucide.ts`
3. **按字母顺序**插入新的导出名

```typescript
// packages/@core/base/icons/src/lucide.ts
export {
  // ... existing icons ...
  FileText,        // ← 新增
  // ... existing icons ...
  Globe,           // ← 新增
  // ...
} from 'lucide-vue-next';
```

4. 保存后重新构建即可生效

**⚠️ 已踩的坑**：直接 `import from 'lucide-vue-next'` 在 `web-ele` 的 `.vue` 文件中会导致 Rollup 在构建时报 `failed to resolve import` 错误。**必须**经过 `@vben/icons` 桥接层。

---

## 五、Element Plus 组件使用指南与踩坑记录

### 5.1 ElTag 内嵌多元素（⚠️ 已知坑）

**问题**：在 `ElTag` 内放多个 `ElIcon` + `span` 时，内容会换行错乱。

**根因**：ElTag 内部有一个 `.el-tag__content` 包裹层，默认不是 flex 布局。

**解法**：用 `:deep()` 穿透样式：

```css
.my-tag :deep(.el-tag__content) {
  display: inline-flex !important;
  align-items: center !important;
  white-space: nowrap !important;
}
```

**或者**：对于复杂的内嵌内容（如图标 + 文本 + 图标），考虑不用 ElTag，改用自定义 `<span>` + 手写样式。ElTag 更适合纯文本或简单内容。

### 5.2 ElCard 的 body-style

```vue
<!-- 用 :body-style 控制卡片内边距 -->
<ElCard shadow="hover" :body-style="{ padding: '16px 20px' }">
  <!-- content -->
</ElCard>
```

### 5.3 ElSelect 多选 + 可创建

```vue
<ElSelect
  v-model="selectedTags"
  multiple
  filterable
  allow-create
  default-first-option
  placeholder="选择或创建标签..."
  @change="onTagsChange"
>
  <ElOption
    v-for="tag in allTags"
    :key="tag"
    :label="tag"
    :value="tag"
  />
</ElSelect>
```

### 5.4 ElMessage / ElMessageBox

```typescript
// 成功提示
ElMessage.success('操作成功');

// 确认弹窗
try {
  await ElMessageBox.confirm('确认删除？', '提示', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  });
  // 用户点击了确认
  await deleteItemApi(id);
} catch (e) {
  if (e !== 'cancel') {
    ElMessage.error(e?.message || '操作失败');
  }
  // e === 'cancel' 表示用户取消，静默处理
}
```

### 5.5 按需导入原则

```typescript
// ✅ 按需导入（Tree-shaking 友好）
import { ElButton, ElCard, ElMessage } from 'element-plus';

// ❌ 不要全局引入
import ElementPlus from 'element-plus';
```

---

## 六、CSS `<style scoped>` 编写范式

### 6.1 结构约定

```vue
<style scoped>
/* ═══ 整体布局 ═══ */
.page { }
.layout { }

/* ═══ 侧边栏 ═══ */
.sidebar { }

/* ═══ 主内容区 ═══ */
.main { }

/* ═══ 卡片/列表 ═══ */
.card { }

/* ═══ Drawer / Modal ═══ */
.drawer { }

/* ═══ 响应式 ═══ */
@media (max-width: 1199px) { }
@media (max-width: 767px) { }
</style>
```

### 6.2 `:deep()` 的使用时机

Scoped 样式无法穿透子组件。当你需要覆盖 Element Plus 组件的内部样式时：

```css
/* 穿透 ElTag 内部 */
.my-wrapper :deep(.el-tag__content) {
  display: flex;
}

/* 穿透 ElCollapse 内部 */
.my-collapse :deep(.el-collapse-item__header) {
  background: transparent;
}

/* 高亮标记（v-html 插入的内容不受 scoped 限制，但 :deep(mark) 更安全） */
:deep(mark) {
  background-color: rgba(234, 179, 8, 0.35);
  color: inherit;
}
```

### 6.3 过渡动画

```vue
<template>
  <transition name="slide-fade">
    <div v-if="expanded">...</div>
  </transition>
</template>

<style scoped>
.slide-fade-enter-active { transition: all 0.25s ease; }
.slide-fade-leave-active { transition: all 0.2s ease; }
.slide-fade-enter-from,
.slide-fade-leave-to { opacity: 0; max-height: 0; }
.slide-fade-enter-to,
.slide-fade-leave-from { opacity: 1; max-height: 500px; }
</style>
```

---

## 七、布局模式速查

### 7.1 侧边栏 + 内容区

```
┌──────────────────────────────────────┐
│ .page                                │
│  ┌──────────┬───────────────────────┐│
│  │ .sidebar │ .main                 ││
│  │ 240px    │ flex: 1               ││
│  │ 固定     │ overflow-y: auto      ││
│  └──────────┴───────────────────────┘│
└──────────────────────────────────────┘
```

```css
.layout {
  display: flex;
  height: calc(100vh - 90px); /* 减去顶栏高度 */
}
.sidebar {
  width: 240px;
  min-width: 240px;
  border-right: 1px solid var(--el-border-color-lighter);
  overflow-y: auto;
}
.main {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background-color: var(--el-bg-color-page);
}
```

### 7.2 双列卡片网格

```css
.grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
/* 中屏回退单列 */
@media (max-width: 1199px) {
  .grid { grid-template-columns: 1fr; }
}
```

**注意**：网格内的特殊元素（空状态、分页）需要跨列：
```html
<div style="grid-column: 1 / -1">
  <ElEmpty description="暂无数据" />
</div>
```

### 7.3 激活态侧边栏项

```css
.nav-item {
  border-left: 3px solid transparent;
  transition: all 0.2s ease;
}
.nav-item.active {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  border-left-color: var(--el-color-primary);
  font-weight: 500;
}
```

---

## 八、部署与调试

### 8.1 构建命令

```bash
# 进入项目根目录
cd /www/wwwroot/xingxy.manyuzo.com/wp-content/plugins/services/vue-vben-admin

# 一键构建并部署
bash deploy.sh
```

**deploy.sh 做了什么**：
1. `pnpm run build:ele --concurrency=1`（限制并发防爆内存）
2. 清空 `/www/wwwroot/center.manyuzo.com/`
3. 拷贝 `apps/web-ele/dist/*` 到目标目录

### 8.2 Turbo 缓存

构建系统使用 Turbo 缓存。如果你只改了 `views/` 下的文件，大部分包会命中缓存，构建只需 30 秒左右。如果改了 `packages/@core/` 下的文件（如 `lucide.ts`），关联包会重新构建。

### 8.3 常见构建错误

| 错误 | 原因 | 解法 |
|------|------|------|
| `Rollup failed to resolve import "lucide-vue-next"` | 直接从 lucide-vue-next 导入 | 改为 `from '@vben/icons'`，不够的图标去 lucide.ts 加 |
| `Rollup failed to resolve import "@vben-core/icons"` | 用了内部包路径 | 改为 `from '@vben/icons'`（注意没有 `-core`） |
| `TS4058: Return type of exported function...` | @core 包的类型问题 | 通常不影响构建产物，关注实际 build error |
| `ELIFECYCLE Command failed with exit code 1` | 代码有编译错误 | 看 `@vben/web-ele:build:` 开头的行找真正错误 |

### 8.4 线上地址

- **Center 前端**：https://center.manyuzo.com
- **API 网关**：https://center.manyuzo.com/api/*（Nginx 反代到 FastAPI:8555）

---

## 九、完整示例回顾：空投包管理模块

这是我们第一个完整的业务模块，从零实现了：

### 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `src/api/airdrop.ts` | 154 | API 封装 + TypeScript 类型 |
| `src/router/routes/modules/airdrop.ts` | 27 | 路由注册 |
| `src/views/airdrop/index.vue` | ~1350 | 页面视图（**待拆分**） |

### 功能清单

- ✅ 两级标签分组侧边栏（桌面端）
- ✅ 水平滚动标签栏（移动端）
- ✅ 搜索框 + 防抖 + 高亮
- ✅ 双列卡片网格布局
- ✅ 行内编辑备注/标签
- ✅ 点击复制口令/链接
- ✅ 标签分组管理 Drawer
- ✅ 深浅模式全兼容
- ✅ 响应式（桌面/平板/手机）

### 待改进

- 🔲 将 `index.vue`（1350 行）拆分为 5 个子组件
- 🔲 ElTag 内嵌多图标的换行问题需要改用自定义 span

---

## 十、检查清单（提交前自查）

- [ ] **颜色**：所有颜色使用 CSS 变量或 `rgba()`，不硬编码 hex
- [ ] **深色模式**：切换到深色模式检查一遍（设置 → 外观）
- [ ] **图标**：从 `@vben/icons` 导入，新图标已加到 `lucide.ts`
- [ ] **组件**：Element Plus 组件按需导入
- [ ] **响应式**：缩小浏览器到手机宽度检查布局
- [ ] **文件长度**：单文件不超过 300 行，超过则拆分
- [ ] **`requestClient`**：使用项目封装的请求客户端，不自建 fetch/axios
- [ ] **构建**：`bash deploy.sh` 零错误通过
