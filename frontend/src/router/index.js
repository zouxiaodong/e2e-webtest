import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue')
  },
  {
    path: '/scenarios',
    name: 'Scenarios',
    component: () => import('../views/Scenarios.vue')
  },
  {
    path: '/test-cases',
    name: 'TestCases',
    component: () => import('../views/TestCases.vue')
  },
  {
    path: '/quick-generate',
    name: 'QuickGenerate',
    component: () => import('../views/QuickGenerate.vue')
  },
  {
    path: '/configs',
    name: 'Configs',
    component: () => import('../views/Configs.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router