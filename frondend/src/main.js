/**
 * @file main entry
 */

// import './public-path';
import Vue from 'vue';
import App from './App';
import router from './router/index.js';
import store from './store/index.js';
import axios from 'axios';

import bkMagic from 'bk-magic-vue';
import 'bk-magic-vue/dist/bk-magic-vue.min.css';
import './css/reset.css';

import $ from 'jquery';
import * as monaco from 'monaco-editor';

$.atoms = {};
$.context = {
  bk_plugin_api_host: {}
};
window.$ = $;
window.monaco = monaco;

Vue.use(bkMagic);

const app = new Vue({
  el: '#app',
  router,
  store,
  components: {
    App
  },
  template: '<App/>'
});
app.$constInfo = {};
window.app = app;
