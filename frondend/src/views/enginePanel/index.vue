<template>
  <div class="engine-panel">
    <div class="request-panel">
      <p class="panel-title">请求</p>
      <bk-form ref="engineForm" :label-width="120" :model="formData" :rules="rules">
        <bk-form-item label="引擎版本">
          <bk-select v-model="formData.version" :clearable="false" @selected="handleReset">
            <bk-option id="bamboo_engine" name="bamboo_engine" />
            <bk-option id="pipeline_engine" name="pipeline_engine" />
          </bk-select>
        </bk-form-item>
        <bk-form-item label="请求资源" :required="true" :property="'action'">
          <bk-select v-model="formData.action" :clearable="false" searchable @selected="handleActionSelected">
            <bk-option
              v-for="option in actionList"
              :id="option.id"
              :key="option.id"
              :name="option.url"
            />
          </bk-select>
        </bk-form-item>
        <bk-form-item label="请求方法" :required="true">
          <bk-select v-model="formData.method" :clearable="false">
            <bk-option id="post" name="Post" />
          </bk-select>
        </bk-form-item>
        <bk-form-item v-if="formData.path.length" label="路径参数" :required="true">
          <ul class="path-list">
            <keyValueFormItem
              v-for="(pathInfo, index) in formData.path"
              :key="index"
              :data="pathInfo"
              :rules="rules"
              type="path"
              :operator="false"
              :readonly="true"
              @updateList="updtaeFormList"
            />
          </ul>
        </bk-form-item>
        <!-- <bk-form-item label="Headers" ext-cls="header-form-item">
                    <ul class="header-list" v-if="formData.headers.length">
                        <keyValueFormItem
                            v-for="(headerInfo, index) in formData.headers"
                            :key="index"
                            :data="headerInfo"
                            :rules="rules"
                            :index="index"
                            type="headers"
                            @updateList="updtaeFormList">
                        </keyValueFormItem>
                    </ul>
                    <bk-button v-else icon="icon-plus-line" @click="updtaeFormList('headers')"></bk-button>
                </bk-form-item> -->
        <bk-form-item label="Query" ext-cls="query-form-item">
          <ul v-if="formData.query.length" class="query-list">
            <keyValueFormItem
              v-for="(queryInfo, index) in formData.query"
              :key="index"
              :data="queryInfo"
              :rules="rules"
              :index="index"
              type="query"
              @updateList="updtaeFormList"
            />
          </ul>
          <bk-button v-else icon="icon-plus-line" @click="updtaeFormList('query')" />
        </bk-form-item>
        <bk-form-item label="Body">
          <p class="tip-docs">
            对应接口参数及参数类型请参考【
            <a
              target="target"
              href="https://github.com/TencentBlueKing/bamboo-engine/blob/master/docs/user_guide/engine_admin_config.md#%E6%93%8D%E4%BD%9C%E5%88%97%E8%A1%A8"
            >文档</a>
            】
          </p>
          <bk-input
            v-model="formData.body"
            placeholder="请输入"
            :type="'textarea'"
          />
        </bk-form-item>
        <bk-form-item>
          <bk-popover content="请完善请求信息" :disabled="isAllowRequest" :arrow="false">
            <bk-button
              theme="primary"
              :disabled="!isAllowRequest"
              @click="handleRequest"
            >
              发送请求
            </bk-button>
          </bk-popover>
          <bk-button class="ml5" @click="handleReset()">重置</bk-button>
        </bk-form-item>
      </bk-form>
    </div>
    <div class="divider" />
    <div class="response-panel">
      <p class="panel-title">响应</p>
      <bk-form v-if="responseInfo.data" :label-width="90">
        <bk-form-item label="Status:">
          {{ responseInfo.status || '--' }}
        </bk-form-item>
        <bk-form-item class="mt10">
          <CodeEditor
            :value="responseInfo.data"
            :options="{ readOnly: true, language: 'json' }"
          />
        </bk-form-item>
      </bk-form>
      <p v-else class="unsent">
        <i class="bk-icon icon-info" />
        请先发送请求
      </p>
    </div>
  </div>
</template>

<script>
  import keyValueFormItem from './keyValueFormItem';
  import CodeEditor from '@/components/CodeEditor';
  import { mapActions } from 'vuex';

  export default {
    components: {
      keyValueFormItem,
      CodeEditor,
    },
    data () {
      return {
        formData: {
          version: 'bamboo_engine',
          action: '',
          method: 'post',
          path: [],
          headers: [],
          query: [],
          body: '',
        },
        actionList: [
          {
            url: '/task_pause/{task_id}',
            id: 'task_pause',
            keys: ['task_id'],
          },
          {
            url: '/task_resume/{task_id}',
            id: 'task_resume',
            keys: ['task_id'],
          },
          {
            url: '/task_revoke/{task_id}',
            id: 'task_revoke',
            keys: ['task_id'],
          },
          {
            url: '/node_retry/{node_id}/',
            id: 'node_retry',
            keys: ['node_id', 'inputs'],
          },
          {
            url: '/node_skip/{node_id}/',
            id: 'node_skip',
            keys: ['node_id'],
          },
          {
            url: '/node_callback/{node_id}/',
            id: 'node_callback',
            keys: ['node_id', 'data', 'version'],
          },
          {
            url: '/node_skip_exg/{node_id}/',
            id: 'node_skip_exg',
            keys: ['node_id', 'flow_id'],
          },
          {
            url: '/node_skip_cpg/{node_id}/',
            id: 'node_skip_cpg',
            keys: ['node_id', 'flow_ids', 'converge_gateway_id'],
          },
          {
            url: '/node_forced_fail/{node_id}/',
            id: 'node_forced_fail',
            keys: ['node_id'],
          },
        ],
        rules: {
          action: [
            {
              required: true,
              message: '必填项',
              trigger: 'blur',
            },
          ],
          key: [
            {
              required: true,
              message: '必填项',
              trigger: 'blur',
            },
          ],
          value: [
            {
              required: true,
              message: '必填项',
              trigger: 'blur',
            },
          ],
        },
        responseInfo: {
          status: null,
          data: null,
        },
      };
    },
    computed: {
      isAllowRequest () {
        const { action, method } = this.formData;
        if (action && method) {
          return true;
        }
        return false;
      },
    },
    methods: {
      ...mapActions('enginePanel', [
        'saveActionData',
      ]),
      handleActionSelected (val) {
        this.formData.query = [];
        this.responseInfo = {
          status: null,
          data: null,
        };
        const actionInfo = this.actionList.find(item => item.id === val);
        const body = {};
        const path = [];
        actionInfo.keys.forEach((key, index) => {
          if (index === 0) {
            path.push({
              key,
              value: '',
            });
          } else {
            body[key] = '';
          }
        });
        this.formData.path = path;
        this.formData.body = Object.keys(body).length ? JSON.stringify(body, null, 4) : '';
      },
      updtaeFormList (type, index) {
        if (!type) return;
        if (index !== undefined) {
          this.formData[type].splice(index, 1);
        } else {
          this.formData[type].push({
            key: '',
            value: '',
          });
        }
      },
      handleRequest () {
        try {
          if (!this.isAllowRequest) return;
          this.responseInfo = {
            status: null,
            data: null,
          };
          const { path, body } = this.formData;
          const valueValid = path.length ? path.every(item => item.key && item.value) : true;
          if (!valueValid) {
            this.$bkMessage({
              message: '请输入完整的路径参数',
              theme: 'error',
            });
            return;
          }
          let bodyJson = {};
          if (body) {
            if (this.checkIsJSON(body)) {
              bodyJson = JSON.parse(body);
            } else {
              this.$bkMessage({
                message: 'Body格式不正确，应为JSON格式',
                theme: 'error',
              });
              return;
            }
          }
          this.$refs.engineForm.validate().then(async (result) => {
            if (!result) return;
            const { version, action, method, path, query } = this.formData;
            const queryInfo = [...path, ...query].reduce((acc, cur) => {
              acc[cur.key] = cur.value;
              return acc;
            }, {});
            Object.assign(queryInfo, bodyJson);
            const pathId = queryInfo.task_id || queryInfo.node_id;
            this.$delete(queryInfo, 'task_id');
            this.$delete(queryInfo, 'node_id');
            const actionInfo = this.actionList.find(item => item.id === action);
            const params = {
              version,
              actionName: actionInfo.id,
              method,
              pathId,
              query: queryInfo,
            };
            const response = await this.saveActionData(params);
            if (response.status === 200) {
              this.responseInfo = { status: response.status, data: JSON.stringify(response.data, null, 4) };
            } else {
              this.responseInfo = { status: null, data: null };
            }
          });
        } catch (error) {
          console.warn(error);
        }
      },
      checkIsJSON (str) {
        if (typeof str === 'string') {
          try {
            const obj = JSON.parse(str);
            if (obj && Object.prototype.toString.call(obj) === '[object Object]') {
              return true;
            }
            return false;
          } catch (e) {
            return false;
          }
        }
        return false;
      },
      handleReset (version = this.formData.version) {
        this.formData = {
          version,
          action: '',
          method: 'post',
          path: [],
          headers: [],
          query: [],
          body: '',
        };
        this.responseInfo = {
          status: null,
          data: null,
        };
      },
    },
  };
</script>

<style lang="scss" scoped>
  .engine-panel {
    display: flex;
    height: 100%;
    padding: 24px;
    background: #f6f7fb;
    .request-panel {
      width: 50%;
      .bk-select {
        background: #fff;
      }
      /deep/.bk-textarea-wrapper {
        border: none;
        textarea {
          min-height: 450px;
          background: #313238;
          padding: 10px;
          border: none;
          color: #fff;
          &:focus {
            background-color: #313238 !important;
            border: none;
            color: #fff;
          }
        }
      }
      /deep/.header-form-item,
      /deep/.query-form-item {
        .bk-button {
          padding: 0;
          min-width: 32px;
          i {
            top: -1px;
            font-size: 12px;
          }
        }
      }
    }
    .divider {
      flex: none;
      margin: 0 40px;
      width: 1px;
      background: #dcdee5;
    }
    .response-panel {
      width: 50%;
      .unsent {
        color: #7b7d8a;
        font-size: 14px;
        margin-left: 12px;
      }
      /deep/.bk-form-item {
        font-size: 12px;
        margin-top: 0;
        .bk-form-content {
          display: flex;
          align-items: center;
        }
        .unit {
          color: #63656e;
          margin-left: 4px;
        }
      }
      .code-editor {
        height: 460px;
        width: 100%;
      }
    }
    .panel-title {
      font-size: 14px;
      font-weight: 700;
      color: #313238;
      margin-bottom: 16px;
    }
    .tip-docs {
      font-size: 14px;
      color: #7b7d8a;
      a {
        color: #3a84ff;
      }
    }
  }
</style>
