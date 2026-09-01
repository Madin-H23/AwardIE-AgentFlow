<script setup lang="ts">
import zhCn from 'element-plus/es/locale/lang/zh-cn'
// #39 修复:Element Plus 内置文案(MessageBox 按钮/分页/空态等)默认英文,
// 按需引入模式下用 ElConfigProvider 全局配置中文。
</script>

<template>
  <el-config-provider :locale="zhCn">
    <router-view />
  </el-config-provider>
</template>

<style>
html, body, #app { height: 100%; margin: 0; }
body { background: var(--bg); color: var(--ink); }
</style>
