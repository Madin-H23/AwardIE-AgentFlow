<script lang="ts" setup>
import { useTagsViewStore } from '@/store/modules/tagsView'
import { useAppStore } from '@/store/modules/app'
import { Footer } from '@/layout/components/Footer'

defineOptions({ name: 'AppView' })

const appStore = useAppStore()

const footer = computed(() => appStore.getFooter)

const tagsViewStore = useTagsViewStore()

const getCaches = computed((): string[] => {
  return tagsViewStore.getCachedViews
})

//region 无感刷新
const routerAlive = ref(true)
// 无感刷新，防止出现页面闪烁白屏
const reload = () => {
  routerAlive.value = false
  nextTick(() => (routerAlive.value = true))
}
// 为组件后代提供刷新方法
provide('reload', reload)
//endregion
</script>

<template>
  <section
    :class="[
      'p-[var(--app-content-padding)] w-full bg-[var(--app-content-bg-color)] dark:bg-[var(--el-bg-color)]',
      {
        '!min-h-[calc(100vh-var(--top-tool-height)-var(--tags-view-height)-var(--app-footer-height))] pb-0':
          footer
      }
    ]"
  >
    <router-view v-if="routerAlive">
      <template #default="{ Component, route }">
        <!-- UX-1 移植(批28):150ms 路由过渡;transition 必须在 keep-alive 外层,
             key 沿用 v3 的 viewKey 语义(菜单 component_name 是缓存键,见批14 教训) -->
        <transition
          name="page-fade"
          mode="out-in"
        >
          <keep-alive :include="getCaches">
            <component
              :is="Component"
              :key="route.meta.viewKey || route.fullPath"
            />
          </keep-alive>
        </transition>
      </template>
    </router-view>
  </section>
  <Footer v-if="footer" />
</template>
