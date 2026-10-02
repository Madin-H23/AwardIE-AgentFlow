<template>
  <el-alert v-if="getEnable()" type="success" show-icon>
    <template #title>
      <div @click="goToUrl">{{ '【' + title + '】文档地址：' + url }}</div>
    </template>
  </el-alert>
</template>
<script setup lang="tsx">
import { propTypes } from '@/utils/propTypes'

defineOptions({ name: 'DocAlert' })

const props = defineProps({
  title: propTypes.string,
  url: propTypes.string
})

/** 跳转 URL 链接 */
const goToUrl = () => {
  window.open(props.url)
}

/** 是否开启。批32:默认**关**——这些横幅指向框架上游文档(doc.iocoder.cn),
 * 对本产品的用户是广告位;确需展示时在 env 显式设 VITE_APP_DOCALERT_ENABLE=true */
const getEnable = () => {
  return import.meta.env.VITE_APP_DOCALERT_ENABLE === 'true'
}
</script>
<style scoped>
.el-alert--success.is-light {
  margin-bottom: 10px;
  cursor: pointer;
  border: 1px solid green;
}
</style>
