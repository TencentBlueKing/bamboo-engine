/**
 * @file router 配置
 */

import Vue from 'vue';
import VueRouter from 'vue-router';

import NotFound from '../views/404.vue';
import EnginePanel from '../views/enginePanel/index.vue';

Vue.use(VueRouter);

const routes = [
  {
    path: '/',
    name: 'EnginePanel',
    component: EnginePanel,
  },
  // 404
  {
    path: '*',
    name: '404',
    component: NotFound,
  },
];

const router = new VueRouter({
  base: window.SITE_URL,
  mode: 'history',
  routes,
});

export default router;
