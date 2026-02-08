<template>
  <div class="config-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span><el-icon><Setting /></el-icon> 全局配置</span>
        </div>
      </template>

      <el-form :model="form" label-width="120px" v-loading="loading">
        <el-form-item label="目标URL">
          <el-input 
            v-model="form.target_url" 
            placeholder="例如：https://example.com"
            clearable
          />
          <div class="form-tip">所有测试场景的默认目标URL</div>
        </el-form-item>

        <el-form-item label="默认用户名">
          <el-input 
            v-model="form.default_username" 
            placeholder="默认登录用户名"
            clearable
          />
          <div class="form-tip">测试用例中使用的默认用户名</div>
        </el-form-item>

        <el-form-item label="默认密码">
          <el-input 
            v-model="form.default_password" 
            type="password"
            placeholder="默认登录密码"
            show-password
            clearable
          />
          <div class="form-tip">测试用例中使用的默认密码</div>
        </el-form-item>

        <el-divider />

        <el-form-item label="验证码选择器">
          <el-input 
            v-model="form.captcha_selector" 
            placeholder="例如：#captcha img"
            clearable
          />
          <div class="form-tip">验证码图片的CSS选择器</div>
        </el-form-item>

        <el-form-item label="输入框选择器">
          <el-input 
            v-model="form.captcha_input_selector" 
            placeholder="例如：#captcha-input"
            clearable
          />
          <div class="form-tip">验证码输入框的CSS选择器</div>
        </el-form-item>

        <el-form-item label="自动检测验证码">
          <el-switch v-model="form.auto_detect_captcha" />
          <div class="form-tip">开启后自动检测并识别验证码</div>
        </el-form-item>

        <el-divider />

        <el-form-item label="浏览器无头模式">
          <el-switch v-model="form.browser_headless" />
          <div class="form-tip">关闭后可以看到浏览器运行过程</div>
        </el-form-item>

        <el-form-item label="使用 Computer-Use">
          <el-switch v-model="form.use_computer_use" />
          <div class="form-tip">使用截图+坐标定位方案（更稳定但成本更高，需要VL模型支持）</div>
        </el-form-item>

        <el-form-item label="浏览器超时">
          <el-input-number 
            v-model="form.browser_timeout" 
            :min="5000"
            :max="120000"
            :step="5000"
          />
          <span style="margin-left: 10px">毫秒</span>
          <div class="form-tip">浏览器操作的超时时间</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="saving">
            <el-icon><Check /></el-icon>
            保存配置
          </el-button>
          <el-button @click="handleReset">
            <el-icon><RefreshLeft /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configsApi } from '@/api/configs'

const form = ref({
  target_url: '',
  default_username: '',
  default_password: '',
  captcha_selector: '',
  captcha_input_selector: '',
  auto_detect_captcha: false,
  browser_headless: true,
  use_computer_use: false,
  browser_timeout: 30000
})

const loading = ref(false)
const saving = ref(false)

// 加载配置
const loadConfig = async () => {
  loading.value = true
  try {
    const response = await configsApi.getSettings()
    console.log('加载配置响应:', response)
    Object.assign(form.value, response)
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

// 保存配置
const handleSave = async () => {
  saving.value = true
  try {
    console.log('保存配置数据:', form.value)
    await configsApi.updateSettings(form.value)
    ElMessage.success('配置保存成功')
  } catch (error) {
    console.error('保存配置失败:', error)
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

// 重置配置
const handleReset = () => {
  loadConfig()
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.config-container {
  padding: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
}

.card-header .el-icon {
  margin-right: 8px;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.el-divider {
  margin: 24px 0;
}
</style>
