<template>
  <div class="quick-generate">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <h2>快速生成测试用例</h2>
            </div>
          </template>

          <el-form :model="form" label-width="100px">
            <el-form-item label="使用全局配置">
              <el-switch v-model="form.useGlobalConfig" />
              <span style="margin-left: 10px; color: #909399; font-size: 12px">
                使用全局配置中的URL、用户名、密码等
              </span>
            </el-form-item>

            <el-form-item label="目标URL" v-if="!form.useGlobalConfig">
              <el-input v-model="form.target_url" placeholder="https://example.com" />
              <div style="color: #909399; font-size: 12px; margin-top: 4px">
                也可以在"全局配置"中设置默认URL
              </div>
            </el-form-item>

            <el-form-item label="目标URL" v-else>
              <el-input v-model="globalConfig.target_url" placeholder="使用全局配置" disabled />
              <div style="color: #909399; font-size: 12px; margin-top: 4px">
                将使用全局配置中的URL
              </div>
            </el-form-item>

            <el-form-item label="测试需求">
              <el-input
                v-model="form.user_query"
                type="textarea"
                :rows="5"
                placeholder="请用自然语言描述您的测试需求，例如：测试登录功能，输入用户名和密码后点击登录按钮，验证是否成功登录"
              />
            </el-form-item>

            <el-form-item label="生成策略">
              <el-select v-model="form.generationStrategy" placeholder="请选择生成策略">
                <el-option label="仅正向测试" value="happy_path">
                  <div>
                    <span>仅正向测试</span>
                    <span style="color: #999; font-size: 12px; margin-left: 10px">生成1个正向测试用例</span>
                  </div>
                </el-option>
                <el-option label="基础覆盖" value="basic">
                  <div>
                    <span>基础覆盖</span>
                    <span style="color: #999; font-size: 12px; margin-left: 10px">生成正向+异常+边界测试</span>
                  </div>
                </el-option>
                <el-option label="全面测试" value="comprehensive">
                  <div>
                    <span>全面测试</span>
                    <span style="color: #999; font-size: 12px; margin-left: 10px">生成所有维度的完整测试</span>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>

            <el-form-item label="自动识别验证码">
              <el-switch v-model="form.autoDetectCaptcha" />
              <span style="margin-left: 10px; color: #909399; font-size: 12px">
                AI 会自动分析页面，识别验证码位置并填入
              </span>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="handleGenerate" :loading="generating" size="large">
                <el-icon><MagicStick /></el-icon>
                生成测试用例
              </el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card v-if="result">
          <template #header>
            <div class="card-header">
              <h2>生成结果</h2>
              <div>
                <el-tag type="primary" style="margin-right: 10px">
                  共 {{ result.test_cases?.length || 0 }} 个用例
                </el-tag>
                <el-tag type="success" v-if="result.summary">
                  通过: {{ result.summary.passed }}
                </el-tag>
                <el-tag type="danger" v-if="result.summary">
                  失败: {{ result.summary.failed }}
                </el-tag>
              </div>
            </div>
          </template>

          <el-tabs v-if="result.test_cases && result.test_cases.length > 0">
            <el-tab-pane
              v-for="(testCase, index) in result.test_cases"
              :key="index"
              :label="testCase.name"
            >
              <el-descriptions :column="2" border>
                <el-descriptions-item label="用例名称">{{ testCase.name }}</el-descriptions-item>
                <el-descriptions-item label="优先级">
                  <el-tag :type="getPriorityType(testCase.priority)">
                    {{ testCase.priority }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="类型">
                  <el-tag>{{ getCaseTypeText(testCase.case_type) }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="getStatusType(testCase.status)">
                    {{ getStatusText(testCase.status) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="描述" :span="2">{{ testCase.description }}</el-descriptions-item>
              </el-descriptions>

              <div style="margin-top: 20px">
                <h4>操作步骤</h4>
                <el-steps direction="vertical" :active="testCase.actions?.length || 0" finish-status="success">
                  <el-step v-for="(action, idx) in testCase.actions" :key="idx" :title="action" />
                </el-steps>
              </div>

              <div style="margin-top: 20px">
                <h4>生成的脚本</h4>
                <el-input v-model="testCase.script" type="textarea" :rows="15" readonly />
                <el-button type="primary" @click="copyScript(index)" style="margin-top: 10px">
                  复制脚本
                </el-button>
              </div>

              <div v-if="testCase.report" style="margin-top: 20px">
                <h4>测试报告</h4>
                <div v-html="renderedReports[index]" class="report-content"></div>
              </div>
            </el-tab-pane>
          </el-tabs>

          <el-empty v-else description="未生成测试用例" />
        </el-card>

        <el-empty v-else description="请填写表单并生成测试用例" />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { scenariosApi } from '@/api/scenarios'
import { configsApi } from '@/api/configs'

const form = ref({
  target_url: '',
  user_query: '',
  generationStrategy: 'basic',
  autoDetectCaptcha: false,
  useGlobalConfig: false
})

const globalConfig = ref({
  target_url: ''
})

const generating = ref(false)
const result = ref(null)
const renderedReports = ref({})

// 加载全局配置
const loadGlobalConfig = async () => {
  try {
    const response = await configsApi.getSettings()
    globalConfig.value = response.data
  } catch (error) {
    console.error('加载全局配置失败', error)
  }
}

// 生成测试用例
const handleGenerate = async () => {
  const targetUrl = form.value.useGlobalConfig ? globalConfig.value.target_url : form.value.target_url
  
  if (!targetUrl || !form.value.user_query) {
    ElMessage.warning('请填写完整信息')
    return
  }

  generating.value = true
  result.value = null
  renderedReports.value = {}

  try {
    result.value = await scenariosApi.quickGenerate({
      user_query: form.value.user_query,
      target_url: targetUrl,
      generation_strategy: form.value.generationStrategy,
      auto_detect_captcha: form.value.autoDetectCaptcha
    })

    // 渲染所有报告
    if (result.value.test_cases) {
      result.value.test_cases.forEach((testCase, index) => {
        if (testCase.report) {
          renderedReports.value[index] = marked(testCase.report)
        }
      })
    }

    ElMessage.success(`生成成功，共 ${result.value.test_cases?.length || 0} 个测试用例`)
  } catch (error) {
    ElMessage.error('生成失败：' + (error.response?.data?.detail || error.message))
  } finally {
    generating.value = false
  }
}

// 重置表单
const handleReset = () => {
  form.value = {
    target_url: '',
    user_query: '',
    generationStrategy: 'basic',
    autoDetectCaptcha: false
  }
  result.value = null
  renderedReports.value = {}
}

// 复制脚本
const copyScript = (index) => {
  if (result.value && result.value.test_cases && result.value.test_cases[index]) {
    const script = result.value.test_cases[index].script
    if (script) {
      navigator.clipboard.writeText(script).then(() => {
        ElMessage.success('复制成功')
      }).catch(() => {
        ElMessage.error('复制失败')
      })
    }
  }
}

// 获取优先级类型
const getPriorityType = (priority) => {
  const types = {
    P0: 'danger',
    P1: 'warning',
    P2: 'primary',
    P3: 'info'
  }
  return types[priority] || 'info'
}

// 获取用例类型文本
const getCaseTypeText = (type) => {
  const texts = {
    positive: '正向',
    negative: '负向',
    boundary: '边界',
    exception: '异常',
    security: '安全',
    performance: '性能',
    compatibility: '兼容'
  }
  return texts[type] || type
}

// 获取状态类型
const getStatusType = (status) => {
  const types = {
    success: 'success',
    failed: 'danger',
    error: 'danger'
  }
  return types[status] || 'info'
}

// 获取状态文本
const getStatusText = (status) => {
  const texts = {
    success: '成功',
    failed: '失败',
    error: '错误'
  }
  return texts[status] || status
}

// 加载全局配置
loadGlobalConfig()
</script>

<style scoped>
.quick-generate {
  max-width: 1400px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  color: #303133;
}

.report-content {
  background-color: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
  max-height: 500px;
  overflow-y: auto;
}

.report-content :deep(pre) {
  background-color: #fff;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

.report-content :deep(code) {
  font-family: 'Courier New', monospace;
}
</style>