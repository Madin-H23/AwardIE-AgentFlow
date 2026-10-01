<template>
  <div
    :class="prefixCls"
    class="relative h-[100%] lt-md:px-10px lt-sm:px-10px lt-xl:px-10px lt-xl:px-10px"
  >
    <div class="relative mx-auto h-full flex">
      <div
        :class="`${prefixCls}__left flex-1 bg-gray-500 bg-opacity-20 relative p-30px lt-xl:hidden overflow-x-hidden overflow-y-auto`"
      >
        <!-- 左上角的 logo + 系统标题 -->
        <div class="relative flex items-center text-white">
          <img alt="" class="mr-10px h-48px w-48px" src="@/assets/imgs/logo.png" />
          <span class="text-20px font-bold">{{ underlineToHump(appStore.getTitle) }}</span>
        </div>
        <!-- 左边的背景图 + 欢迎语(UX-2 批29:芋道通用插画换成奖章徽记+真实审核流程) -->
        <div class="h-[calc(100%-60px)] flex items-center justify-center">
          <TransitionGroup
            appear
            enter-active-class="animate__animated animate__bounceInLeft"
            tag="div"
            class="login-hero"
          >
            <div key="1" class="medal-emblem" aria-hidden="true">
              <div class="ribbon ribbon-left"></div>
              <div class="ribbon ribbon-right"></div>
              <div class="medal-disc"><span>✦</span></div>
            </div>
            <div key="2" class="hero-welcome">{{ t('login.welcome') }}</div>
            <div key="3" class="hero-message">
              {{ t('login.message') }}
            </div>
            <ol key="4" class="hero-steps">
              <li><span>01</span>提交申报</li>
              <li><span>02</span>教师初审</li>
              <li><span>03</span>归档入库</li>
            </ol>
          </TransitionGroup>
        </div>
      </div>
      <div
        class="relative flex-1 p-30px dark:bg-[var(--login-bg-color)] lt-sm:p-10px overflow-x-hidden overflow-y-auto"
      >
        <!-- 右上角的主题、语言选择 -->
        <div
          class="flex items-center justify-between at-2xl:justify-end at-xl:justify-end"
          style="color: var(--el-text-color-primary)"
        >
          <div class="flex items-center at-2xl:hidden at-xl:hidden">
            <img alt="" class="mr-10px h-48px w-48px" src="@/assets/imgs/logo.png" />
            <span class="text-20px font-bold">{{ underlineToHump(appStore.getTitle) }}</span>
          </div>
          <div class="flex items-center justify-end space-x-10px h-48px">
            <ThemeSwitch />
            <LocaleDropdown />
          </div>
        </div>
        <!-- 右边的登录界面 -->
        <Transition appear enter-active-class="animate__animated animate__bounceInRight">
          <div
            class="m-auto h-[calc(100%-60px)] w-[100%] flex items-center at-2xl:max-w-500px at-lg:max-w-500px at-md:max-w-500px at-xl:max-w-500px"
          >
            <!-- 账号登录 -->
            <LoginForm class="m-auto h-auto p-20px lt-xl:(rounded-3xl light:bg-white)" />
            <!-- 手机登录 -->
            <MobileForm class="m-auto h-auto p-20px lt-xl:(rounded-3xl light:bg-white)" />
            <!-- 二维码登录 -->
            <QrCodeForm class="m-auto h-auto p-20px lt-xl:(rounded-3xl light:bg-white)" />
            <!-- 注册 -->
            <RegisterForm class="m-auto h-auto p-20px lt-xl:(rounded-3xl light:bg-white)" />
            <!-- 三方登录 -->
            <SSOLoginVue class="m-auto h-auto p-20px lt-xl:(rounded-3xl light:bg-white)" />
            <!-- 忘记密码 -->
            <ForgetPasswordForm class="m-auto h-auto p-20px lt-xl:(rounded-3xl light:bg-white)" />
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>
<script lang="ts" setup>
import { underlineToHump } from '@/utils'

import { useDesign } from '@/hooks/web/useDesign'
import { useAppStore } from '@/store/modules/app'
import { ThemeSwitch } from '@/layout/components/ThemeSwitch'
import { LocaleDropdown } from '@/layout/components/LocaleDropdown'

import {
  LoginForm,
  MobileForm,
  QrCodeForm,
  RegisterForm,
  SSOLoginVue,
  ForgetPasswordForm
} from './components'

defineOptions({ name: 'Login' })

const { t } = useI18n()
const appStore = useAppStore()
const { getPrefixCls } = useDesign()
const prefixCls = getPrefixCls('login')
</script>

<style lang="scss" scoped>
$prefix-cls: #{$namespace}-login;

.#{$prefix-cls} {
  overflow: auto;

  &__left {
    &::before {
      position: absolute;
      top: 0;
      left: 0;
      z-index: -1;
      width: 100%;
      height: 100%;
      background-image: url('@/assets/svgs/login-bg.svg');
      background-position: center;
      background-repeat: no-repeat;
      content: '';
    }
  }
}

/* UX-2(批29):奖章徽记——产品的荣誉语义符号,替代上游通用插画 */
.login-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.medal-emblem {
  position: relative;
  width: 150px;
  height: 170px;
  margin-bottom: 28px;
}
.medal-disc {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 112px;
  height: 112px;
  border-radius: 50%;
  box-shadow:
    0 0 0 6px rgba(212, 160, 23, 0.35),
    0 0 0 14px rgba(212, 160, 23, 0.12);
  background: radial-gradient(circle at 32% 28%, #e8c96a, #c99b2d 58%, #a87b18);
  span {
    color: #fff8e6;
    font-size: 40px;
    line-height: 1;
    text-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
  }
}
.ribbon {
  position: absolute;
  top: 96px;
  width: 30px;
  height: 62px;
  border-radius: 0 0 6px 6px;
}
.ribbon-left {
  left: 44px;
  transform: rotate(-24deg);
  background: var(--ribbon-national, #d4a017);
}
.ribbon-right {
  right: 44px;
  transform: rotate(24deg);
  background: #23405e;
}
.hero-welcome {
  color: #fff;
  font-size: 30px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.hero-message {
  margin-top: 12px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 14px;
}
.hero-steps {
  display: flex;
  gap: 34px;
  margin: 34px 0 0;
  padding: 0;
  list-style: none;
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  li {
    display: flex;
    align-items: center;
    gap: 8px;
    span {
      color: #e8c96a;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 15px;
    }
  }
}
@media (prefers-reduced-motion: reduce) {
  .login-hero {
    animation: none;
  }
}
</style>

<style lang="scss">
.dark .login-form {
  .el-divider__text {
    background-color: var(--login-bg-color);
  }

  .el-card {
    background-color: var(--login-bg-color);
  }
}
</style>
