<!--
  【这个文件是干什么的？】
  根组件。只做一件事：用 el-config-provider 把 Element Plus 的语言设成中文（分页、日期选择器等内置文字），
  然后把当前路由对应的页面（router-view）显示出来。
-->
<script setup>
import zhCn from 'element-plus/es/locale/lang/zh-cn'
</script>

<template>
  <el-config-provider :locale="zhCn">
    <router-view />
  </el-config-provider>
</template>
