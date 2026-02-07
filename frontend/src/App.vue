<template>
  <el-container style="height: 100vh">
    <el-header>
      <div class="header-content">
        <h1>AI驱动的端到端测试平台</h1>
        <div class="header-actions">
          <el-tag type="success">v1.0.0</el-tag>
        </div>
      </div>
    </el-header>

    <el-container>
      <el-aside width="200px">
        <el-menu
          :default-active="$route.path"
          router
          background-color="#545c64"
          text-color="#fff"
          active-text-color="#ffd04b"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/scenarios">
            <el-icon><FolderOpened /></el-icon>
            <span>测试场景</span>
          </el-menu-item>
          <el-menu-item index="/test-cases">
            <el-icon><Document /></el-icon>
            <span>测试用例</span>
          </el-menu-item>
          <el-menu-item index="/quick-generate">
            <el-icon><MagicStick /></el-icon>
            <span>快速生成</span>
          </el-menu-item>
          <el-menu-item index="/configs">
            <el-icon><Setting /></el-icon>
            <span>全局配置</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { HomeFilled, FolderOpened, Document, MagicStick, Setting } from '@element-plus/icons-vue'
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.el-header {
  background-color: #409eff;
  color: white;
  display: flex;
  align-items: center;
  padding: 0 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.header-content h1 {
  font-size: 20px;
  font-weight: 500;
}

.el-aside {
  background-color: #545c64;
}

.el-main {
  background-color: #f5f5f5;
  padding: 20px;
}
</style>