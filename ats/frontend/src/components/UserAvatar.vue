<!--
  【用户头像】三个端共用：显示头像图片，没设置时显示名字首字占位；
  点击头像直接选图上传（image/*，≤5MB，后端校验），传完自动刷新。
  用法：<UserAvatar :fetch-blob="api.avatarBlob" :upload="api.updateAvatar" name="张三" />
-->
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  fetchBlob: { type: Function, required: true },
  // 只传 fetchBlob = 仅展示（换头像入口在「个人信息」处）；upload + editable 才可点击更换
  upload: { type: Function, default: null },
  editable: { type: Boolean, default: false },
  name: { type: String, default: '?' },
  size: { type: Number, default: 28 },
})
const emit = defineEmits(['updated'])

const url = ref(null)
const busy = ref(false)
const fileInput = ref(null)
let objectUrl = null

function release() {
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  objectUrl = null
}

async function load() {
  try {
    const resp = await props.fetchBlob()
    release()
    objectUrl = URL.createObjectURL(resp.data)
    url.value = objectUrl
  } catch (e) {
    // 404 = 还没设置头像，用首字占位
    url.value = null
  }
}

function pick() {
  if (!props.editable || !props.upload) return
  fileInput.value?.click()
}

async function onPicked(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('头像必须是图片')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('头像不能超过 5MB')
    return
  }
  busy.value = true
  try {
    await props.upload(file)
    await load()
    ElMessage.success('头像已更新')
    emit('updated')
  } finally {
    busy.value = false
  }
}

// 别处（个人信息弹窗 / 我的资料页）换了头像，这里跟着刷新
function onAvatarUpdated() {
  load()
}

onMounted(() => {
  load()
  window.addEventListener('avatar-updated', onAvatarUpdated)
})
onBeforeUnmount(() => {
  release()
  window.removeEventListener('avatar-updated', onAvatarUpdated)
})
</script>

<template>
  <span
    class="u-avatar"
    :class="{ editable: editable && upload }"
    :style="{ width: `${size}px`, height: `${size}px` }"
    :title="editable && upload ? '点击更换头像' : name"
    @click="pick"
  >
    <img v-if="url" :src="url" :alt="name" />
    <span v-else class="u-avatar-fallback">{{ (name || '?').trim().charAt(0).toUpperCase() || '?' }}</span>
    <span v-if="busy" class="u-avatar-mask">…</span>
    <input ref="fileInput" type="file" accept="image/*" hidden @change="onPicked" />
  </span>
</template>

<style scoped>
.u-avatar {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  overflow: hidden;
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
  font-weight: var(--ats-fw-medium);
  flex: none;
  user-select: none;
}
.u-avatar.editable {
  cursor: pointer;
}
.u-avatar:hover {
  box-shadow: 0 0 0 2px var(--el-color-primary-light-5);
}
.u-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.u-avatar-fallback {
  font-size: 0.55em;
}
.u-avatar-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(0 0 0 / 35%);
  color: #fff;
  font-size: 12px;
}
</style>
