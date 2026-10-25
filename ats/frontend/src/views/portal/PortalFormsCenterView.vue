<!--
  【我的表单】页：表单列表抽成了 PortalFormsList 组件，与「文件」页共用；
  这里只是给它一个带标题的独立页面（底部导航入口仍可达）。
-->
<script setup>
import PortalFormsList from '../../components/PortalFormsList.vue'
</script>

<template>
  <div class="portal-page">
    <div class="portal-page-head">
      <h1>我的表单</h1>
      <p class="portal-page-sub">点表单直接进填写页</p>
    </div>

    <PortalFormsList />
  </div>
</template>
