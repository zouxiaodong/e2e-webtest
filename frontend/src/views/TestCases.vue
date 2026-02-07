<template>
  <div class="test-cases">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>测试用例管理</h2>
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建测试用例
          </el-button>
        </div>
      </template>

      <el-table :data="testCases" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="target_url" label="目标URL" width="300" show-overflow-tooltip />
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
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="generateTestCase(row)" :disabled="row.status === 'generated' || row.status === 'completed'">
              生成
            </el-button>
            <el-button size="small" type="success" @click="executeTestCase(row)" :disabled="row.status !== 'generated' && row.status !== 'completed'">
              执行
            </el-button>
            <el-button size="small" @click="viewTestCase(row)">
              查看
            </el-button>
            <el-button size="small" type="danger" @click="deleteTestCase(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建测试用例对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建测试用例" width="600px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="测试用例名称">
          <el-input v-model="createForm.name" placeholder="请输入测试用例名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="目标URL">
          <el-input v-model="createForm.target_url" placeholder="请输入目标URL" />
        </el-form-item>
        <el-form-item label="测试需求">
          <el-input v-model="createForm.user_query" type="textarea" :rows="5" placeholder="请用自然语言描述测试需求" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 查看测试用例对话框 -->
    <el-dialog v-model="viewDialogVisible" title="测试用例详情" width="800px">
      <div v-if="currentTestCase">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ currentTestCase.id }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ currentTestCase.name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentTestCase.status)">
              {{ getStatusText(currentTestCase.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="目标URL">{{ currentTestCase.target_url }}</el-descriptions-item>
          <el-descriptions-item label="测试需求" :span="2">{{ currentTestCase.user_query }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="currentTestCase.actions && currentTestCase.actions.length > 0" style="margin-top: 20px">
          <h4>操作步骤</h4>
          <el-steps :active="currentTestCase.actions.length" finish-status="success">
            <el-step v-for="(action, index) in currentTestCase.actions" :key="index" :title="action" />
          </el-steps>
        </div>

        <div v-if="currentTestCase.script" style="margin-top: 20px">
          <h4>生成的脚本</h4>
          <el-input v-model="currentTestCase.script" type="textarea" :rows="15" readonly />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { testCasesApi } from '@/api/testCases'

const testCases = ref([])
const loading = ref(false)
const createDialogVisible = ref(false)
const viewDialogVisible = ref(false)
const currentTestCase = ref(null)

const createForm = ref({
  name: '',
  description: '',
  target_url: '',
  user_query: ''
})

// 加载测试用例列表
const loadTestCases = async () => {
  loading.value = true
  try {
    testCases.value = await testCasesApi.getList()
  } catch (error) {
    ElMessage.error('加载测试用例失败')
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
    user_query: ''
  }
  createDialogVisible.value = true
}

// 创建测试用例
const handleCreate = async () => {
  try {
    await testCasesApi.create(createForm.value)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    loadTestCases()
  } catch (error) {
    ElMessage.error('创建失败')
  }
}

// 生成测试用例
const generateTestCase = async (testCase) => {
  try {
    ElMessage.info('正在生成测试用例...')
    await testCasesApi.generate(testCase.id)
    ElMessage.success('生成成功')
    loadTestCases()
  } catch (error) {
    ElMessage.error('生成失败')
  }
}

// 执行测试用例
const executeTestCase = async (testCase) => {
  try {
    ElMessage.info('正在执行测试用例...')
    await testCasesApi.execute(testCase.id)
    ElMessage.success('执行成功')
    loadTestCases()
  } catch (error) {
    ElMessage.error('执行失败')
  }
}

// 查看测试用例
const viewTestCase = async (testCase) => {
  try {
    currentTestCase.value = await testCasesApi.getDetail(testCase.id)
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

// 删除测试用例
const deleteTestCase = async (testCase) => {
  try {
    await ElMessageBox.confirm('确定要删除这个测试用例吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await testCasesApi.delete(testCase.id)
    ElMessage.success('删除成功')
    loadTestCases()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 获取状态类型
const getStatusType = (status) => {
  const types = {
    draft: 'info',
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

onMounted(() => {
  loadTestCases()
})
</script>

<style scoped>
.test-cases {
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