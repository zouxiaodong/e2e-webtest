import api from './index'

export const scenariosApi = {
  // 获取场景列表
  getList(params) {
    return api.get('/scenarios/', { params })
  },

  // 获取场景详情
  getDetail(id) {
    return api.get(`/scenarios/${id}`)
  },

  // 创建场景
  create(data) {
    return api.post('/scenarios/', data)
  },

  // 更新场景
  update(id, data) {
    return api.put(`/scenarios/${id}`, data)
  },

  // 删除场景
  delete(id) {
    return api.delete(`/scenarios/${id}`)
  },

  // 生成场景测试用例
  generate(id, strategy) {
    return api.post(`/scenarios/${id}/generate`, { generation_strategy: strategy })
  },

  // 执行场景所有用例
  execute(id) {
    return api.post(`/scenarios/${id}/execute`)
  },

  // 获取场景下的用例列表
  getCases(id) {
    return api.get(`/scenarios/${id}/cases`)
  },

  // 获取场景的报告列表
  getReports(id) {
    return api.get(`/scenarios/${id}/reports`)
  },

  // 快速生成场景
  quickGenerate(data) {
    return api.post('/scenarios/quick-generate', data)
  }
}