const webpack = require('webpack');
const merge = require('webpack-merge');
const webpackBase = require('./webpack.base.conf');
const TerserJSPlugin = require("terser-webpack-plugin");
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const OptimizeCSSAssetsPlugin = require("optimize-css-assets-webpack-plugin");
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
// const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin

module.exports = merge(webpackBase, {
  // 模式
  mode: 'production',
  // 开发工具
  devtool: process.env.SOURCE_MAP === 'true' ? 'source-map' : false,
  // 输出
  output: {
    filename: 'js/[name].[contenthash:7].js'
  },
  // 模块
  module: {
    rules: [
      {
        test: /\.(css|scss|sass)$/,
        use: [
          MiniCssExtractPlugin.loader,
          'css-loader',
          'sass-loader'
        ]
      }
    ]
  },
  // 插件
  plugins: [
    new MiniCssExtractPlugin({
      filename: 'css/[name].[contenthash:7].css'
    }),
    new webpack.HashedModuleIdsPlugin(),
    new HtmlWebpackPlugin({
      filename: 'index-prod.html',
      template: 'index.html',
      inject: true
    }),
    new CleanWebpackPlugin({
      cleanOnceBeforeBuildPatterns: ['./assets/**'],
      verbose: true
    })
  ],
  // 优化
  optimization: {
    minimizer: [
      new TerserJSPlugin({
        extractComments: false,
        cache: true,
        parallel: true
      }),
      new OptimizeCSSAssetsPlugin({
        cssProcessorOptions: {
          // map: {  // css 文件 sourcemap
          //     inline: false,
          //     annotation: true
          // },
          safe: true
        }
      })
    ],
    runtimeChunk: 'single',
    splitChunks: {
      cacheGroups: {
        vueLib: {
          test: /[\\/]node_modules[\\/](vue|vue-router|vuex)[\\/]/,
          name: 'vue-lib',
          chunks: 'initial'
        },
        plotly: {
          test: /[\\/]node_modules[\\/]plotly.js[\\/]/,
          name: 'plotly',
          chunks: 'initial'
        },
        highlight: {
          test: /[\\/]node_modules[\\/]highlight.js[\\/]/,
          name: 'highlight',
          chunks: 'all'
        },
        brace: {
          test: /[\\/]node_modules[\\/]brace[\\/]/,
          name: 'brace',
          chunks: 'initial'
        }
      }
    }
  },
  stats: {
    children: false,
    entrypoints: false
  }
});
