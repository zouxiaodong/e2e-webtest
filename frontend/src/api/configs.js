import api from './index'

export const configsApi = {
  // 获取所有配置
  getList(params) {
    return api.get('/configs/', { params })
  },

  // 获取全局配置设置
  getSettings() {
    return api.get('/configs/settings')
  },

  // 更新全局配置设置
  updateSettings(data) {
    return api.put('/configs/settings', data)
  },

  // 获取指定配置
  getConfig(key) {
    return api.get(`/configs/${key}`)
  },

  // 更新指定配置
  updateConfig(key, data) {
    return api.put(`/configs/${key}`, data)
  }
}
