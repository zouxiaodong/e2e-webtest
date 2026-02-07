<template>
  <div class="scenarios">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>测试场景管理</h2>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建场景
          </el-button>
        </div>
      </template>

      <el-table :data="scenarios" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="场景名称" width="200" />
        <el-table-column prop="target_url" label="目标URL" width="300" show-overflow-tooltip />
        <el-table-column prop="generation_strategy" label="生成策略" width="150">
          <template #default="{ row }">
            <el-tag :type="getStrategyType(row.generation_strategy)">
              {{ getStrategyText(row.generation_strategy) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_cases" label="用例数" width="100" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="350" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="generateScenario(row)" :disabled="row.status === 'generating'">
              生成用例
            </el-button>
            <el-button size="small" type="success" @click="executeScenario(row)" :disabled="row.total_cases === 0">
              执行
            </el-button>
            <el-button size="small" @click="viewScenario(row)">
              查看
            </el-button>
            <el-button size="small" type="danger" @click="deleteScenario(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建场景对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建测试场景" width="600px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="场景名称">
          <el-input v-model="createForm.name" placeholder="请输入场景名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="目标URL">
          <el-input v-model="createForm.target_url" placeholder="请输入目标URL" />
        </el-form-item>
        <el-form-item label="场景描述">
          <el-input v-model="createForm.user_query" type="textarea" :rows="5" placeholder="请用自然语言描述测试场景" />
        </el-form-item>
        <el-form-item label="生成策略">
          <el-select v-model="createForm.generation_strategy" placeholder="请选择生成策略">
            <el-option label="仅正向测试" value="happy_path" />
            <el-option label="基础覆盖" value="basic" />
            <el-option label="全面测试" value="comprehensive" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 查看场景对话框 -->
    <el-dialog v-model="viewDialogVisible" title="场景详情" width="1200px">
      <div v-if="currentScenario">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ currentScenario.id }}</el-descriptions-item>
          <el-descriptions-item label="场景名称">{{ currentScenario.name }}</el-descriptions-item>
          <el-descriptions-item label="生成策略">
            <el-tag :type="getStrategyType(currentScenario.generation_strategy)">
              {{ getStrategyText(currentScenario.generation_strategy) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentScenario.status)">
              {{ getStatusText(currentScenario.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="用例数量">{{ currentScenario.total_cases }}</el-descriptions-item>
          <el-descriptions-item label="目标URL">{{ currentScenario.target_url }}</el-descriptions-item>
          <el-descriptions-item label="场景描述" :span="2">{{ currentScenario.user_query }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="currentScenario.test_cases && currentScenario.test_cases.length > 0" style="margin-top: 20px">
          <h3>测试用例列表</h3>
          <el-table :data="currentScenario.test_cases" stripe>
            <el-table-column prop="name" label="用例名称" width="200" />
            <el-table-column prop="description" label="描述" show-overflow-tooltip />
            <el-table-column prop="priority" label="优先级" width="100">
              <template #default="{ row }">
                <el-tag :type="getPriorityType(row.priority)">
                  {{ row.priority }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="case_type" label="类型" width="120">
              <template #default="{ row }">
                <el-tag>{{ getCaseTypeText(row.case_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="execution_count" label="执行次数" width="100" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" @click="viewTestCaseScript(row)">
                  查看脚本
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>

    <!-- 查看脚本对话框 -->
    <el-dialog v-model="scriptDialogVisible" :title="`测试脚本 - ${currentTestCaseName}`" width="900px">
      <el-input v-model="currentTestCaseScript" type="textarea" :rows="20" readonly />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { scenariosApi } from '@/api/scenarios'

const scenarios = ref([])
const loading = ref(false)
const createDialogVisible = ref(false)
const viewDialogVisible = ref(false)
const currentScenario = ref(null)
const scriptDialogVisible = ref(false)
const currentTestCaseScript = ref('')
const currentTestCaseName = ref('')

const createForm = ref({
  name: '',
  description: '',
  target_url: '',
  user_query: '',
  generation_strategy: 'basic'
})

// 加载场景列表
const loadScenarios = async () => {
  loading.value = true
  try {
    scenarios.value = await scenariosApi.getList()
  } catch (error) {
    ElMessage.error('加载场景失败')
  } finally {
    loading.value = false
  }
}

// 显示创建对话框
const showCreateDialog = () => {
  createForm.value = {
    name: '',
    description: '',
    target_url: '',
    user_query: '',
    generation_strategy: 'basic'
  }
  createDialogVisible.value = true
}

// 创建场景
const handleCreate = async () => {
  try {
    await scenariosApi.create(createForm.value)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    loadScenarios()
  } catch (error) {
    ElMessage.error('创建失败')
  }
}

// 生成场景测试用例
const generateScenario = async (scenario) => {
  try {
    ElMessage.info('正在生成测试用例...')
    await scenariosApi.generate(scenario.id)
    ElMessage.success('生成成功')
    loadScenarios()
  } catch (error) {
    ElMessage.error('生成失败')
  }
}

// 执行场景所有用例
const executeScenario = async (scenario) => {
  try {
    ElMessage.info('正在执行测试用例...')
    const result = await scenariosApi.execute(scenario.id)
    ElMessage.success(result.message)
    loadScenarios()
  } catch (error) {
    ElMessage.error('执行失败')
  }
}

// 查看场景详情
const viewScenario = async (scenario) => {
  try {
    currentScenario.value = await scenariosApi.getDetail(scenario.id)
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

// 删除场景
const deleteScenario = async (scenario) => {
  try {
    await ElMessageBox.confirm('确定要删除这个场景吗？删除后将同时删除所有关联的测试用例。', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await scenariosApi.delete(scenario.id)
    ElMessage.success('删除成功')
    loadScenarios()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 获取策略类型
const getStrategyType = (strategy) => {
  const types = {
    happy_path: 'success',
    basic: 'primary',
    comprehensive: 'warning'
  }
  return types[strategy] || 'info'
}

// 获取策略文本
const getStrategyText = (strategy) => {
  const texts = {
    happy_path: '仅正向',
    basic: '基础覆盖',
    comprehensive: '全面测试'
  }
  return texts[strategy] || strategy
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
    draft: 'info',
    generating: 'primary',
    generated: 'warning',
    executing: 'primary',
    completed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

// 获取状态文本
const getStatusText = (status) => {
  const texts = {
    draft: '草稿',
    generating: '生成中',
    generated: '已生成',
    executing: '执行中',
    completed: '已完成',
    failed: '失败'
  }
  return texts[status] || status
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

// 查看测试用例脚本
const viewTestCaseScript = (testCase) => {
  currentTestCaseName.value = testCase.name
  currentTestCaseScript.value = testCase.script || '暂无脚本'
  scriptDialogVisible.value = true
}

onMounted(() => {
  loadScenarios()
})
</script>

<style scoped>
.scenarios {
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
</style>