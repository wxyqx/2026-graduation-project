<!-- 【系统设置页】占位。AI 接口配置管理属于 M4。主题切换在顶栏，这里放一句说明。 -->
<script setup>
import { THEMES, applyTheme, theme } from '../theme'
</script>

<template>
  <div>
    <div class="page-header"><h2>系统设置</h2></div>
    <el-card shadow="never" style="margin-bottom: 14px">
      <template #header>主题偏好</template>
      <el-radio-group :model-value="theme" @change="applyTheme">
        <el-radio v-for="t in THEMES" :key="t.value" :value="t.value">{{ t.label }}</el-radio>
      </el-radio-group>
      <p class="muted">选择保存在本浏览器，刷新后保持。顶部状态栏右侧也可以随时切换。</p>
    </el-card>
    <el-card shadow="never">
      <template #header>AI 筛选 API 管理</template>
      <el-empty description="M4 阶段实现：添加 / 编辑 / 删除大模型接口配置，可同时启用多个" />
    </el-card>
  </div>
</template>

<style scoped>
.muted {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
