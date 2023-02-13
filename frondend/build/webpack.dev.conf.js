const path = require('path');
const webpack = require('webpack');
const merge = require('webpack-merge');
const webpackBase = require('./webpack.base.conf');
const HtmlWebpackPlugin = require('html-webpack-plugin');
// 本地代理地址
const ORIGIN = 'http://{BK_PAAS_HOST}';
const SITE_URL = '/o/bk_sops/';
// 代理接口列表
const proxyPath = [
  'api/',
  'api/v1/'
];
// 代理接口
const proxyRule = {};
proxyPath.forEach((item) => {
  proxyRule[SITE_URL + item] = {
    target: ORIGIN,
    secure: false,
    changeOrigin: true,
    headers: {
      referer: ORIGIN
    }
  };
});

module.exports = merge(webpackBase, {
  // 模式
  mode: 'development',
  // 模块
  module: {
    rules: [
      {
        test: /\.(css|scss|sass)$/,
        use: ['style-loader', 'css-loader', 'sass-loader']
      }
    ]
  },
  // 插件
  plugins: [
    new webpack.NamedModulesPlugin(),
    new webpack.HotModuleReplacementPlugin(),
    new HtmlWebpackPlugin({
      filename: 'index.html',
      template: 'index-dev.html',
      inject: true
    })
  ],
  // 开发工具
  devtool: 'inline-source-map',
  // 代理服务配置
  devServer: {
    contentBase: path.posix.join(__dirname, '../../../static'),
    host: 'dev.{BK_PAAS_HOST}',
    port: 9007,
    https: ORIGIN.indexOf('https') > -1,
    hot: true,
    open: false, // webpack 升级之前设置为打开状态
    overlay: true,
    proxy: proxyRule,
    stats: {
      children: false,
      entrypoints: false,
      modules: false
    }
  }
});
