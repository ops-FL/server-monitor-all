// pages/login/login.js
const app = getApp()

Page({
  data: {
    username: '',
    password: '',
    error: '',
    loading: false,
  },

  onInputUser(e) {
    this.setData({ username: e.detail.value, error: '' })
  },

  onInputPwd(e) {
    this.setData({ password: e.detail.value, error: '' })
  },

  async doLogin() {
    const { username, password } = this.data

    if (!username || !password) {
      this.setData({ error: '请输入账号和密码' })
      return
    }

    this.setData({ loading: true, error: '' })

    const res = await app.request('/api/login', {
      username,
      password,
    }, 'POST')

    this.setData({ loading: false })

    if (res && res.code === 200 && res.token) {
      wx.setStorageSync('token', res.token)
      wx.redirectTo({ url: '/pages/index/index' })
    } else {
      this.setData({ error: (res && res.msg) || '登录失败，请检查账号密码' })
    }
  },
})
