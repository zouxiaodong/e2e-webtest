import api from './index'

export const testCasesApi = {
  // 获取测试用例列表
  getList(params) {
    return api.get('/test-cases', { params })
  },

  // 获取测试用例详情
  getDetail(id) {
    return api.get(`/test-cases/${id}`)
  },

  // 创建测试用例
  create(data) {
    return api.post('/test-cases', data)
  },

  // 更新测试用例
  update(id, data) {
    return api.put(`/test-cases/${id}`, data)
  },

  // 删除测试用例
  delete(id) {
    return api.delete(`/test-cases/${id}`)
  },

  // 生成测试用例
  generate(id) {
    return api.post(`/test-cases/${id}/generate`)
  },

  // 执行测试用例
  execute(id) {
    return api.post(`/test-cases/${id}/execute`)
  },

  // 获取测试报告
  getReports(id) {
    return api.get(`/test-cases/${id}/reports`)
  },

  // 快速生成测试用例
  quickGenerate(params) {
    return api.post('/test-cases/quick-generate', null, { params })
  },

  // 快速生成带验证码的测试用例
  quickGenerateWithCaptcha(params) {
    return api.post('/test-cases/quick-generate-with-captcha', null, { params })
  }
}