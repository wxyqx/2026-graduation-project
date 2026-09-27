"""
【这个文件夹（routers）是干什么的？】
这里是「接口」——浏览器能访问的每一个网址，都在这里定义。

打个比方：routers 是公司前台。浏览器（前端）说「我要看岗位列表」，
前台看一眼是不是登录了、参数对不对，然后去 services / models 里把东西拿出来交给它。

每个文件管一类事：
  auth.py         登录注册
  positions.py    岗位
  candidates.py   候选人
  applications.py 投递 + 推进 / 撤回
  ai_configs.py   AI 接口配置
  ai_screen.py    AI 智能录入
  stats.py        统计数字
  export.py       导出 Excel

读懂一个接口的窍门：看 @router.get / .post / .put / .delete 后面的网址，再看函数的参数（浏览器要传什么），
最后看 return（回给浏览器什么）。函数第一行的中文字符串会出现在 /docs 文档页里。
"""
