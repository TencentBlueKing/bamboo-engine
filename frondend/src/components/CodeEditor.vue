<template>
  <section class="code-editor" />
</template>
<script>
  import * as monaco from 'monaco-editor';

  const DEFAULT_OPTIONS = {
    language: 'javascript',
    theme: 'vs-dark',
    automaticLayout: true,
    minimap: {
      enabled: false,
    },
    wordWrap: 'on',
    wrappingIndent: 'same',
  };
  export default {
    name: 'CodeEditor',
    props: {
      value: {
        type: String,
        default: '',
      },
      options: {
        type: Object,
        default () {
          return {};
        },
      },
    },
    data () {
      const editorOptions = Object.assign({}, DEFAULT_OPTIONS, this.options, { value: this.value });
      return {
        editorOptions,
        monacoInstance: null,
      };
    },
    watch: {
      value (val) {
        const valInEditor = this.monacoInstance.getValue();
        if (val !== valInEditor) {
          this.monacoInstance.setValue(val);
        }
      },
      options: {
        deep: true,
        handler (val) {
          this.editorOptions = Object.assign({}, DEFAULT_OPTIONS, val, { value: this.value });
          this.updateOptions();
        },
      },
    },
    mounted () {
      this.initIntance();
    },
    beforeDestroy () {
      if (this.monacoInstance) {
        this.monacoInstance.dispose();
      }
    },
    methods: {
      initIntance () {
        this.monacoInstance = monaco.editor.create(this.$el, this.editorOptions);
        const model = this.monacoInstance.getModel();
        model.setEOL(0); // 设置编辑器在各系统平台下 EOL 统一为 \n
        if (this.value.indexOf('\r\n') > -1) { // 转换已保存的旧数据
          const textareaEl = document.createElement('textarea');
          textareaEl.value = this.value;
          this.$emit('input', textareaEl.value);
        }
        model.onDidChangeContent(() => {
          const value = this.monacoInstance.getValue();
          this.$emit('input', value);
        });
        this.monacoInstance.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KEY_S, () => {
          const value = this.monacoInstance.getValue();
          this.$emit('saveContent', value);
        });
      },
      updateOptions () {
        this.monacoInstance.updateOptions(this.editorOptions);
      },
    },
  };
</script>
<style lang="scss" scoped>
  .code-editor {
    height: 100%;
  }
</style>
