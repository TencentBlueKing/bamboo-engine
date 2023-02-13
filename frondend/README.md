bamboo_engine_admin_frontend
===

## 本地开发

# 安装依赖包
npm install

# host配置
打开build/webpack.dev.config.js
host: dev + 代理地址的域名
例如：
    host: dev.xxxx-xxxx.com

# webpack 代理配置
打开build/webpack.dev.config.js
设置代理地址ORIGIN
例如：
    const ORIGIN = 'http://xxxx-xxxx.com'
在proxyPath里面添加需要代理的接口
例如：
    const proxyPath = [ 'api/', 'api/*' ]

# 本地项目运行
npm run dev

# 打包构建
npm run build
使用时后端需要：
    在html中配置接口请求路径SITE_URL和静态资源文件路径BK_STATIC_URL
    在后台框架的静态资源目录/static/images里添加网页icon

# 打包生成目录
项目子目录static文件
static
    - assets
        - css
        - fonts
        - img
        - js
        index.html
    json.works.js



