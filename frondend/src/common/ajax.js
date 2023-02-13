/**
 * @file ajax 封装
 */

import Vue from 'vue';
import axios from 'axios';

const instance = axios.create({
  validateStatus: status => status >= 200 && status <= 505,
  baseURL: window.SITE_URL,
  // `headers` are custom headers to be sent
  headers: { 'X-Requested-With': 'XMLHttpRequest' },
  // csrftoken变量名
  xsrfCookieName: 'bk_sops_csrftoken',
  // cookie中的csrftoken信息名称
  xsrfHeaderName: 'X-CSRFToken',
  withCredentials: true,
});

// 拦截器：在这里对ajax请求做一些统一公用处理
instance.interceptors.response.use(
  (response) => {
    if (response.status) {
      switch (response.status) {
        case 401:
          break;
      }
    }
    return response;
  },
  error => Promise.reject(error) // 返回接口返回的错误信息

);

Vue.prototype.$http = instance;

export default instance;
