<template>
  <div class="home">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>欢迎使用 AI 驱动的端到端测试平台</h2>
        </div>
      </template>

      <div class="welcome-content">
        <p>这是一个基于人工智能的自动化测试平台，可以帮您：</p>

        <el-row :gutter="20" style="margin-top: 30px">
          <el-col :span="8">
            <el-card shadow="hover">
              <div class="feature-card">
                <el-icon :size="40" color="#409eff"><FolderOpened /></el-icon>
                <h3>场景化测试管理</h3>
                <p>一个场景对应多个测试用例，支持专业测试策略</p>
              </div>
            </el-card>
          </el-col>

          <el-col :span="8">
            <el-card shadow="hover">
              <div class="feature-card">
                <el-icon :size="40" color="#67c23a"><View /></el-icon>
                <h3>智能验证码识别</h3>
                <p>基于百练平台视觉大模型，自动识别和处理验证码</p>
              </div>
            </el-card>
          </el-col>

          <el-col :span="8">
            <el-card shadow="hover">
              <div class="feature-card">
                <el-icon :size="40" color="#e6a23c"><Document /></el-icon>
                <h3>自动生成报告</h3>
                <p>执行测试后自动生成详细的测试报告</p>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <div class="quick-actions" style="margin-top: 40px">
          <h3>快速开始</h3>
          <el-button type="primary" size="large" @click="$router.push('/quick-generate')">
            <el-icon><MagicStick /></el-icon>
            快速生成场景
          </el-button>
          <el-button type="success" size="large" @click="$router.push('/scenarios')">
            <el-icon><FolderOpened /></el-icon>
            管理测试场景
          </el-button>
          <el-button type="info" size="large" @click="$router.push('/test-cases')">
            <el-icon><Document /></el-icon>
            管理测试用例
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { FolderOpened, MagicStick, View, Document } from '@element-plus/icons-vue'
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header h2 {
  margin: 0;
  color: #303133;
}

.welcome-content p {
  font-size: 16px;
  color: #606266;
  line-height: 1.8;
}

.feature-card {
  text-align: center;
  padding: 20px;
}

.feature-card h3 {
  margin: 15px 0 10px;
  color: #303133;
}

.feature-card p {
  color: #909399;
  font-size: 14px;
}

.quick-actions {
  text-align: center;
}

.quick-actions h3 {
  margin-bottom: 20px;
  color: #303133;
}

.quick-actions .el-button {
  margin: 0 10px;
}
</style>