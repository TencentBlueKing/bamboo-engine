/**
 * @file main store
 */

import Vue from 'vue';
import Vuex from 'vuex';
import enginePanel from './modules/enginePanel';

Vue.use(Vuex);

const store = new Vuex.Store({
  // 模块
  modules: {
    enginePanel
  },
  // 公共 store
  state: {
  },
  // 公共 getters
  getters: {
  },
  // 公共 mutations
  mutations: {
  },
  actions: {
  }
});

export default store;
