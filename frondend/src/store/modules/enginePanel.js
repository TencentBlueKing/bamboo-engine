/**
 * @file enginePanel store
 */
import ajax from '../../common/ajax.js';

export default {
  namespaced: true,
  state: {},
  mutations: {},
  actions: {
    saveActionData (state, data) {
      const { version, actionName, method, pathId, query } = data;
      return ajax[method](`api/v1/${version}/${actionName}/${pathId}/`, query).then(response => response);
    }
  }
};

