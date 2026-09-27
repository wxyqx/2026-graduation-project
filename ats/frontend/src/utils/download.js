/**
 * 【这个文件是干什么的？】
 * 浏览器下载小工具：把一个文件的内容（blob）存成真正的文件。
 * 做法：临时造一个 <a> 标签指向这段内容，点它一下，浏览器就弹下载。
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  // 释放临时内存
  URL.revokeObjectURL(url)
}
