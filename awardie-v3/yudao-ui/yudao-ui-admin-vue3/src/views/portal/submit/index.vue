<template>
  <div class="portal-page">
    <PendingSubmitForm @submitted="router.push('/portal/submissions')" />
  </div>
</template>

<script setup lang="ts">
// 批15:表单抽到 business/components/PendingSubmitForm(教师工作台共用),
// 本页只剩壳——提交成功后跳学生门户的「我的提交」。
import PendingSubmitForm from '@/views/business/components/PendingSubmitForm.vue'

defineOptions({ name: 'PortalSubmit' })

const router = useRouter()
</script>

<style scoped>
.portal-page {
  max-width: 720px;
  margin: 0 auto;
}
</style>
