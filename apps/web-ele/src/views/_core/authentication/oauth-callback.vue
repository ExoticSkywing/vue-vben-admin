<script setup lang="ts">
/**
 * OAuth 回调中转页面
 * 功能：从 URL query 中提取后端签发的 accessToken,
 *       存入 Vben 的 accessStore，加载用户信息，然后跳转到首页。
 */
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { preferences } from '@vben/preferences';
import { useAccessStore, useUserStore } from '@vben/stores';

import { ElNotification } from 'element-plus';

import { getAccessCodesApi, getUserInfoApi } from '#/api';

defineOptions({ name: 'OAuthCallback' });

const route = useRoute();
const router = useRouter();
const accessStore = useAccessStore();
const userStore = useUserStore();

const statusText = ref('正在处理授权登录...');
const hasError = ref(false);

onMounted(async () => {
  try {
    // 从 URL query 中提取 accessToken
    const accessToken = route.query.accessToken as string;

    if (!accessToken) {
      statusText.value = '授权失败：未收到有效的登录凭证';
      hasError.value = true;
      return;
    }

    statusText.value = '正在验证身份信息...';

    // 存储 Token 到全局状态
    accessStore.setAccessToken(accessToken);

    // 获取用户信息和权限码
    const [userInfo, accessCodes] = await Promise.all([
      getUserInfoApi(),
      getAccessCodesApi(),
    ]);

    userStore.setUserInfo(userInfo);
    accessStore.setAccessCodes(accessCodes);

    statusText.value = `欢迎回来，${userInfo?.realName || '管理员'}！正在跳转...`;

    // 显示登录成功通知
    ElNotification({
      message: `星小芽授权登录成功：${userInfo?.realName || ''}`,
      title: '登录成功',
      type: 'success',
    });

    // 跳转到目标页：优先使用 redirect 参数，否则跳首页
    const redirectPath = (route.query.redirect as string)
      || userInfo?.homePath
      || preferences.app.defaultHomePath;

    await router.replace(decodeURIComponent(redirectPath));
  } catch (error: any) {
    statusText.value = `授权处理异常：${error?.message || '未知错误'}`;
    hasError.value = true;
    console.error('OAuth callback error:', error);
  }
});
</script>

<template>
  <div class="flex min-h-screen items-center justify-center">
    <div class="text-center">
      <div v-if="!hasError" class="mb-4">
        <div
          class="border-primary mx-auto h-8 w-8 animate-spin rounded-full border-4 border-t-transparent"
        />
      </div>
      <p :class="hasError ? 'text-red-500' : 'text-muted-foreground'" class="text-lg">
        {{ statusText }}
      </p>
    </div>
  </div>
</template>
